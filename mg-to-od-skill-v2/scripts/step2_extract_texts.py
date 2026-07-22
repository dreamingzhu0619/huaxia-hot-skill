"""
Step 2 - Phase 0 脚本：统一检测重复实例 + 提取模板型 TEXT。

对所有 frame（template + content），先检测重复子模块（结构指纹），将
repeatable / repeatCount 写回 step2-01_frame-types.json。然后对 template 帧，
从去重后的模板子树提取 TEXT，输出 step2-02_text-judgments.json 供 AI 判断。

这样重复检测在分叉之前一次性完成，后续步骤在去重后的单个模板实例上操作。

Usage:
  python scripts/step2_extract_texts.py --project huaxia-hot-citc
"""

import json
import argparse
from pathlib import Path

CONTAINER_TYPES = {"GROUP", "FRAME", "COMPONENT", "INSTANCE"}


def resolve_path(project: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / project


# ---------------------------------------------------------------------------
# 结构指纹 & 重复检测（与 build_slots.py 逻辑一致）
# ---------------------------------------------------------------------------

def make_fingerprint(node):
    """为节点子树生成结构指纹，忽略 text 值和 name。"""
    if node is None:
        return None
    sig = {"type": node.get("type")}
    children = node.get("children", [])
    if children:
        sig["children"] = [make_fingerprint(c) for c in children]
        sig["childCount"] = len(children)
    if node.get("type") == "TEXT":
        sig["isText"] = True
    return sig


def fingerprint_key(sig):
    return json.dumps(sig, sort_keys=True, ensure_ascii=False)


def detect_repeats(children):
    """检测连续结构指纹相同的子模块，返回 (去重列表, repeatable, repeatCount)。

    只有 CONTAINER_TYPES 能作为重复模板。
    """
    if len(children) <= 1:
        return children, False, 1

    fingerprints = []
    for c in children:
        if c["type"] in CONTAINER_TYPES:
            fingerprints.append(make_fingerprint(c))
        else:
            fingerprints.append(None)

    deduped = []
    repeat_count = 0
    i = 0
    while i < len(children):
        deduped.append(children[i])
        fp = fingerprints[i]
        if fp is not None:
            j = i + 1
            while j < len(children) and fingerprints[j] is not None and fingerprint_key(fingerprints[j]) == fingerprint_key(fp):
                j += 1
            if j > i + 1:
                repeat_count = j - i
            i = j
        else:
            i += 1

    return deduped, repeat_count > 1, repeat_count if repeat_count > 1 else 1


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Step 2: 统一重复检测 + 提取模板型 TEXT")
    parser.add_argument("--project", required=True, help="项目名，如 huaxia-hot-citc")
    args = parser.parse_args()

    base = resolve_path(args.project)
    frame_types_path = base / "output" / "step2-01_frame-types.json"
    index_path = base / "modules" / "_index.json"
    modules_dir = base / "modules"
    output_path = base / "output" / "step2-02_text-judgments.json"

    frame_types_data = json.loads(frame_types_path.read_text(encoding="utf-8"))
    index_data = json.loads(index_path.read_text(encoding="utf-8"))

    # Build file name → module info lookup
    file_lookup = {}
    for m in index_data["modules"]:
        file_lookup[m["fileName"]] = m

    templates_for_judgment = {}
    repeat_summary = []

    for entry in frame_types_data.get("frames", []):
        frame_type = entry.get("frameType", "")
        if not frame_type:
            continue

        # 找 module JSON
        file_name = Path(entry["moduleJson"]).name
        module_json_path = modules_dir / file_name
        if not module_json_path.exists():
            print(f"[WARN] 找不到 {file_name}，跳过 {entry['groupName']}")
            continue

        module = json.loads(module_json_path.read_text(encoding="utf-8"))
        root = module["node"]

        # ---- 统一重复检测（template + content 都做） ----
        children = root.get("children", [])
        deduped_children, repeatable, repeat_count = detect_repeats(children)

        entry["repeatable"] = repeatable
        entry["repeatCount"] = repeat_count
        if repeatable:
            repeat_summary.append(f"  {entry['groupName']}[{frame_type}]: {repeat_count} 个重复 → 取第一个为模板")

        # ---- 模板型：从去重模板提取 TEXT → step2-02_text-judgments.json ----
        if frame_type == "template":
            # 直接使用 step2-01 已提取的 texts（含 name-based 隐式 TEXT）
            texts = []
            for t in entry.get("texts", []):
                texts.append({
                    "text": t["text"],
                    "judgment": "",
                    "nodeId": t["nodeId"],
                    "fromName": t.get("fromName", False),
                })
            templates_for_judgment[entry["groupName"]] = {"texts": texts}

    # 写回 step2-01_frame-types.json（添加了 repeatable / repeatCount）
    frame_types_path.write_text(
        json.dumps(frame_types_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 输出 step2-02_text-judgments.json（仅模板型）
    output = {"frames": templates_for_judgment}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    total_texts = sum(len(f["texts"]) for f in templates_for_judgment.values())
    repeat_count = len(repeat_summary)
    print(f"[OK] 重复检测完成 → {frame_types_path}")
    if repeat_summary:
        print(f"[INFO] {repeat_count} 个 frame 含重复子模块：")
        for line in repeat_summary:
            print(line)
    print(f"[OK] {len(templates_for_judgment)} 个模板型 frame，共 {total_texts} 条 TEXT → {output_path}")
    print("[INFO] 请 AI 将 judgment 字段填写为 \"fixed\" 或 \"variable\"，然后运行 step2_build_slots.py")


if __name__ == "__main__":
    main()

"""
Step 2 - Phase 0 脚本：选取代表 frame + 提取 TEXT 预览，输出待标注的 frame-types.json。

从 Step 1 的 modules-classification.json 中，对每个 group 取 moduleIndexes[0]
作为代表，提取所有 TEXT 节点内容，输出 step2-01_frame-types.json（frameType 留空，待 AI 填写）。

AI 只需看这个文件里的 texts 列表即可判断 frameType，无需打开 module JSON。

Usage:
  python scripts/step2_select_representatives.py --project huaxia-hot-citc
"""

import json
import re
import argparse
from pathlib import Path


def resolve_path(project: str) -> Path:
    return Path(__file__).resolve().parent.parent / "data" / project


def _is_meaningful_name(name: str) -> bool:
    """判断 GROUP/FRAME 名称是否为有意义的文字内容（非通用容器名）。

    当文字被 MasterGo 转为矢量 PATH 时，容器名会保留原始文字，
    如 GROUP "红利低波反脆弱价值图" 内含 PATH。此时名称即是文字。
    """
    if not name or len(name) < 2:
        return False
    # 必须包含中文
    has_cjk = any('\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf' for c in name)
    if not has_cjk:
        return False
    # 排除通用容器名（设计稿里的结构名称，不是文字内容）
    generic_patterns = [
        '编组', '矩形', '路径', '椭圆', '备份', '拷贝',
        '蒙版', '遮罩', '按钮', '输入文本', '形状结合',
        '图片', '图层', '形状', '线条', '矢量',
        'Clip', 'Mask', 'Gradient',
    ]
    # 纯数字/编号类名称也不取（如 "编 23"）
    if re.match(r'^[\s\d编组号\.\-#]+$', name):
        return False
    for p in generic_patterns:
        if p in name:
            return False
    return True


def extract_texts(node):
    """递归提取 TEXT 节点；对仅含 PATH 的 GROUP/FRAME，用其名称作为隐式 TEXT。"""
    results = []

    if node.get("type") == "TEXT":
        text = (node.get("text") or "").strip()
        if text:
            results.append({"text": text, "nodeId": node["id"], "fromName": False})
        return results

    # 递归子节点
    for child in node.get("children", []):
        results.extend(extract_texts(child))

    # 子树没有 TEXT，但容器名保留着原始文字（文字被 MasterGo 转成了 PATH）
    if results:
        return results

    if node.get("type") in ("GROUP", "FRAME", "COMPONENT", "INSTANCE"):
        children = node.get("children", [])
        if not children:
            return results
        has_visual = any(
            c.get("type") in ("PATH", "LAYER", "VECTOR", "RECTANGLE", "ELLIPSE", "SVG_ELLIPSE")
            for c in children
        )
        if has_visual:
            name = (node.get("name") or "").strip()
            if _is_meaningful_name(name):
                results.append({"text": name, "nodeId": node["id"], "fromName": True})

    return results


def main():
    parser = argparse.ArgumentParser(description="Step 2 Phase 0: 选取代表 frame")
    parser.add_argument("--project", required=True, help="项目名，如 huaxia-hot-citc")
    args = parser.parse_args()

    base = resolve_path(args.project)
    classification_path = base / "output" / "modules-classification.json"
    index_path = base / "modules" / "_index.json"
    modules_dir = base / "modules"
    output_path = base / "output" / "step2-01_frame-types.json"

    classification = json.loads(classification_path.read_text(encoding="utf-8"))
    index_data = json.loads(index_path.read_text(encoding="utf-8"))

    # Build module lookup: moduleIndex -> module info
    module_lookup = {}
    for m in index_data["modules"]:
        module_lookup[m["moduleIndex"]] = m

    frames = []
    for g in classification["groups"]:
        rep_idx = g["moduleIndexes"][0]
        mod = module_lookup[rep_idx]

        # 读取代表 frame，提取所有 TEXT
        module_json_path = modules_dir / mod["fileName"]
        module = json.loads(module_json_path.read_text(encoding="utf-8"))
        texts = extract_texts(module["node"])

        frames.append({
            "groupId": g["groupId"],
            "groupName": g["groupName"],
            "moduleJson": f"data/{args.project}/modules/{mod['fileName']}",
            "frameType": "",
            "textCount": len(texts),
            "texts": texts,
        })

    output = {"frames": frames}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    total_texts = sum(f["textCount"] for f in frames)
    print(f"[OK] {len(frames)} 个 frame（共 {total_texts} 条 TEXT）→ {output_path}")
    print("[INFO] 请 AI 打开此文件，根据 texts 列表判断 frameType 并填写")


if __name__ == "__main__":
    main()

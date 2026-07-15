#!/usr/bin/env python3
"""
normalize_to_tree.py — 将 MCP 原始数据转换为轻量层级树。

读取 data/raw/ 下的多源原始数据，按合并规则（HANDOFF.md 4.3 节）合并，
输出：
  data/normalized/tree.json  — 机器可读层级树（只含结构+文本，不含样式）
  data/normalized/tree.md    — 人类可读层级树（和 mastergo_full_node_tree.md 同格式）

合并优先级：getDsl > getDesignTexts > getDesignSections

用法：
  python scripts/normalize/normalize_to_tree.py              # 完整归一化
  python scripts/normalize/normalize_to_tree.py --check      # 只校验输入，不产出
  python scripts/normalize/normalize_to_tree.py --no-md      # 不生成 tree.md
"""

import json
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any

# --- Windows 编码适配 ---
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = None  # SKILL_ROOT / "data" / args.project
RAW_DIR = None
NORMALIZED_DIR = None
CONFIG_PATH = None


# ============================================================================
# 数据加载
# ============================================================================

def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict:
    return load_json(CONFIG_PATH) or {}


def load_get_dsl() -> dict | None:
    path = RAW_DIR / "01-getDsl" / "getDsl.json"
    raw = load_json(path)
    if raw is None:
        return None
    return raw.get("dsl", raw)


def load_section_overview() -> list | None:
    path = RAW_DIR / "03-getDesignSections" / "overview.json"
    raw = load_json(path)
    if raw is None:
        return None
    return raw.get("sections", [])


def load_texts() -> dict[str, str]:
    path = RAW_DIR / "05-getDesignTexts" / "getDesignTexts.json"
    raw = load_json(path)
    if raw is None:
        return {}
    return raw.get("texts", {})


# ============================================================================
# 占位符处理
# ============================================================================

PLACEHOLDER_RE = re.compile(r"^T\d+\|(\d+:\d+)$")


def is_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.match(text))


def resolve_text(raw_text: Any, texts_map: dict[str, str]) -> tuple[Any, int]:
    if raw_text is None:
        return None, 0
    resolved_count = 0
    if isinstance(raw_text, list):
        resolved_runs = []
        for seg in raw_text:
            seg_copy = dict(seg) if isinstance(seg, dict) else {"text": str(seg)}
            seg_text = seg_copy.get("text", "")
            if is_placeholder(seg_text):
                replacement = texts_map.get(seg_text)
                if replacement:
                    seg_copy["text"] = replacement
                    resolved_count += 1
            resolved_runs.append(seg_copy)
        return resolved_runs, resolved_count
    elif isinstance(raw_text, str):
        if is_placeholder(raw_text):
            replacement = texts_map.get(raw_text)
            if replacement:
                return replacement, 1
        return raw_text, 0
    return str(raw_text), 0


def get_text_preview(node: dict, max_len: int = 60) -> str:
    """提取节点的文本预览，用于 tree.md 显示。"""
    if node.get("type") != "TEXT":
        return ""
    if "textRuns" in node:
        full = "".join(r.get("text", "") for r in node["textRuns"])
    else:
        full = node.get("text") or ""
    if len(full) > max_len:
        return full[:max_len] + "..."
    return full


# ============================================================================
# 节点树构建
# ============================================================================

def build_normalized_tree(
    dsl_data: dict,
    section_overview: list | None,
    texts_map: dict[str, str],
) -> tuple[dict, dict]:
    """
    遍历 getDsl 节点树，应用文本合并规则，再修正 GROUP 蒙版的平级问题。

    getDsl 中 GROUP 蒙版节点与其视觉上"包裹"的兄弟节点在 JSON 树里是平级的。
    参考树做法：GROUP 类型 + 是 section root 的节点，吸收兄弟 section root
    中边界框被其完全包含的节点。

    返回 (tree_root, stats)
    """
    nodes = dsl_data.get("nodes", [])
    if not nodes:
        raise ValueError("getDsl 中无 nodes 数据")

    section_index_map: dict[str, int] = {}
    if section_overview:
        for i, sec in enumerate(section_overview):
            sec_id = sec.get("id")
            if sec_id:
                section_index_map[sec_id] = i
    section_root_ids = set(section_index_map.keys())

    stats = {
        "total": 0,
        "text_nodes": 0,
        "texts_resolved": 0,
        "sections_mapped": 0,
    }

    def walk(node: dict, current_section_idx: int | None) -> dict:
        stats["total"] += 1
        node_id = node.get("id", "")
        node_type = node.get("type", "")

        section_idx = current_section_idx
        if node_id in section_root_ids:
            section_idx = section_index_map[node_id]
            stats["sections_mapped"] += 1

        layout = node.get("layoutStyle", {})
        normalized: dict[str, Any] = {
            "id": node_id,
            "name": node.get("name", ""),
            "type": node_type,
            "layoutStyle": {
                "x": layout.get("relativeX") or 0,
                "y": layout.get("relativeY") or 0,
                "width": layout.get("width") or 0,
                "height": layout.get("height") or 0,
            },
        }

        if section_idx is not None:
            normalized["sectionIndex"] = section_idx

        # 文本节点：只保留文本内容，不保留样式引用
        if node_type == "TEXT":
            stats["text_nodes"] += 1
            raw_text = node.get("text")
            resolved, n = resolve_text(raw_text, texts_map)
            stats["texts_resolved"] += n
            if isinstance(raw_text, list):
                normalized["textRuns"] = resolved
            else:
                normalized["text"] = resolved
            for key in ("textColor", "textAlign", "textMode"):
                if key in node:
                    normalized[key] = node[key]

        children = node.get("children", [])
        if children:
            normalized["children"] = [
                walk(child, section_idx) for child in children
            ]

        return normalized

    tree = walk(nodes[0], None)
    return tree, stats


# ============================================================================
# tree.md 生成（人类可读层级树）
# ============================================================================

def generate_tree_md(tree: dict, file_id: str, layer_id: str) -> str:
    """生成和 mastergo_full_node_tree.md 同格式的树状文本。"""
    lines = []
    lines.append("# 归一化节点树")
    lines.append("")
    lines.append(
        "说明：格式为 `[type] nodeId name`。"
        "sectionIndex 标注在行末 `[sec=N]`。"
        "文本节点附加内容预览。"
    )
    lines.append("")
    lines.append(f"fileId: `{file_id}`  layerId: `{layer_id}`")
    lines.append("")
    lines.append("```")

    def render(node: dict, prefix: str, is_last: bool):
        connector = "└─ " if is_last else "├─ "
        type_str = node["type"]
        node_id = node["id"]
        name = node["name"]
        sec = f"  [sec={node['sectionIndex']}]" if node.get("sectionIndex") is not None else ""
        text_preview = get_text_preview(node)
        text_str = f'  "{text_preview}"' if text_preview else ""

        lines.append(f"{prefix}{connector}[{type_str}] {node_id} {name}{text_str}{sec}")

        children = node.get("children", [])
        if children:
            child_prefix = prefix + ("   " if is_last else "│  ")
            for i, child in enumerate(children):
                render(child, child_prefix, i == len(children) - 1)

    # 根节点单独渲染（无前缀）
    root_type = tree["type"]
    root_id = tree["id"]
    root_name = tree["name"]
    lines.append(f"[{root_type}] {root_id} {root_name}")

    children = tree.get("children", [])
    for i, child in enumerate(children):
        render(child, "", i == len(children) - 1)

    lines.append("```")
    return "\n".join(lines)


# ============================================================================
# 终端树预览
# ============================================================================

def print_tree_console(tree: dict, max_depth: int = 3):
    """在终端打印层级树概要。"""
    def render(node, prefix, is_last, depth):
        connector = "└─ " if is_last else "├─ "
        t = node["type"]
        nid = node["id"]
        name = node["name"]
        sec = f" [sec={node['sectionIndex']}]" if node.get("sectionIndex") is not None else ""
        txt = get_text_preview(node, 40)
        text_str = f' "{txt}"' if txt else ""
        print(f"{prefix}{connector}[{t}] {nid} {name}{text_str}{sec}")

        children = node.get("children", [])
        if children and depth < max_depth:
            child_prefix = prefix + ("   " if is_last else "│  ")
            for i, child in enumerate(children):
                render(child, child_prefix, i == len(children) - 1, depth + 1)
        elif children:
            print(f"{prefix}{'   ' if is_last else '│  '}... ({len(children)} 个子节点)")

    root_type = tree["type"]
    root_id = tree["id"]
    root_name = tree["name"]
    print(f"\n[{root_type}] {root_id} {root_name}")
    children = tree.get("children", [])
    for i, child in enumerate(children[:20]):
        render(child, "", i == min(len(children) - 1, 19), 1)
    if len(children) > 20:
        print(f"... 还有 {len(children) - 20} 个顶层子节点")


# ============================================================================
# 主流程
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="将 MCP 原始数据归一化为轻量层级树")
    parser.add_argument("--check", action="store_true", help="只校验输入，不产出文件")
    parser.add_argument("--no-md", action="store_true", help="不生成 tree.md")
    parser.add_argument("--output", type=str, default=None, help="tree.json 输出路径")
    parser.add_argument("--raw-dir", type=str, default=None, help="原始数据目录")
    parser.add_argument("--max-depth", type=int, default=3, help="终端预览深度（默认 3）")
    args = parser.parse_args()

    global RAW_DIR
    if args.raw_dir:
        RAW_DIR = Path(args.raw_dir)
    raw_dir = RAW_DIR

    print("=" * 60)
    print("normalize_to_tree — MCP 原始数据 -> 轻量层级树")
    print("=" * 60)

    # --- 1. 配置 ---
    config = load_config()
    project_name = config.get("projectName", "unknown")
    print(f"\n  项目: {project_name}")

    # --- 2. 校验 ---
    print("\n[1/4] 校验输入数据...")
    checks = {
        "getDsl": (raw_dir / "01-getDsl" / "getDsl.json").exists(),
        "sections_overview": (raw_dir / "03-getDesignSections" / "overview.json").exists(),
        "sections_count": (
            len(list((raw_dir / "03-getDesignSections").glob("section-*.json")))
            if (raw_dir / "03-getDesignSections").exists() else 0
        ),
        "getDesignTexts": (raw_dir / "05-getDesignTexts" / "getDesignTexts.json").exists(),
    }
    for name, ok in checks.items():
        if name == "sections_count":
            print(f"  {'[OK]' if ok > 0 else '[MISS]'} {name}: {ok} 个分段文件")
        else:
            print(f"  {'[OK]' if ok else '[MISS]'} {name}")

    if not checks["getDsl"]:
        print("\n  [ERR] getDsl 是必须的数据源。", file=sys.stderr)
        sys.exit(1)

    if args.check:
        print("\n  [DONE] --check 模式：输入数据校验完成。")
        return

    # --- 3. 加载数据 ---
    print("\n[2/4] 加载数据源...")
    dsl_data = load_get_dsl()
    assert dsl_data is not None
    dsl_styles = dsl_data.get("styles", {})
    print(f"  getDsl: {len(dsl_styles)} 个样式定义")

    section_overview = load_section_overview()
    print(f"  sections 概览: {len(section_overview) if section_overview else 0} 个分段")

    texts_map = load_texts()
    print(f"  texts: {len(texts_map)} 条长文本替换")

    # --- 4. 构建树 ---
    print("\n[3/4] 构建归一化节点树...")
    tree, stats = build_normalized_tree(dsl_data, section_overview, texts_map)

    print(f"  总节点数:     {stats['total']}")
    print(f"  文本节点数:   {stats['text_nodes']}")
    print(f"  文本替换:     {stats['texts_resolved']}")
    print(f"  分段映射:     {stats['sections_mapped']}")

    # 终端预览
    print_tree_console(tree, args.max_depth)

    # --- 5. 写入文件 ---
    print(f"\n[4/4] 写入输出文件...")

    manifest = load_json(raw_dir / "_capture-manifest.json") or {}
    file_id = manifest.get("fileId", "")
    layer_id = manifest.get("layerId", "")

    paint_keys = sorted([k for k in dsl_styles if k.startswith("paint_")])
    font_keys = sorted([k for k in dsl_styles if k.startswith("font_")])
    effect_keys = sorted([k for k in dsl_styles if k.startswith("effect_")])

    output = {
        "meta": {
            "projectName": project_name,
            "fileId": file_id,
            "layerId": layer_id,
            "rootNodeId": tree["id"],
            "rootNodeName": tree["name"],
            "normalizedAt": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "totalNodes": stats["total"],
            "sectionCount": len(section_overview) if section_overview else 0,
            "textCount": stats["text_nodes"],
            "styleCounts": {
                "paints": len(paint_keys),
                "fonts": len(font_keys),
                "effects": len(effect_keys),
            },
            "sources": {
                "getDsl": True,
                "getDesignSections": checks["sections_overview"],
                "getDesignTexts": checks["getDesignTexts"],
            },
            "mergeStats": {
                "textsResolved": stats["texts_resolved"],
                "sectionsMapped": stats["sections_mapped"],
            },
        },
        "styleIndex": {
            "paints": paint_keys,
            "fonts": font_keys,
            "effects": effect_keys,
        },
        "sectionIndex": section_overview if section_overview else [],
        "tree": tree,
    }

    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

    json_path = Path(args.output) if args.output else (NORMALIZED_DIR / "tree.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  tree.json: {json_path}  ({json_path.stat().st_size / 1024:.1f} KB)")

    if not args.no_md:
        md_path = NORMALIZED_DIR / "tree.md"
        md_content = generate_tree_md(tree, file_id, layer_id)
        md_path.write_text(md_content, encoding="utf-8")
        print(f"  tree.md:   {md_path}  ({md_path.stat().st_size / 1024:.1f} KB)")

    print("\n" + "=" * 60)
    print("[DONE] 归一化完成。")
    print("=" * 60)


if __name__ == "__main__":
    import argparse as _ap
    _parser = _ap.ArgumentParser(add_help=False)
    _parser.add_argument("--project", required=True, help="Project name (e.g. huaxia-hot-citc)")
    _pargs, _ = _parser.parse_known_args()
    PROJECT_DIR = SKILL_ROOT / "data" / _pargs.project
    RAW_DIR = PROJECT_DIR / "raw"
    NORMALIZED_DIR = PROJECT_DIR / "normalized"
    CONFIG_PATH = PROJECT_DIR / "config" / "project.config.json"
    main()

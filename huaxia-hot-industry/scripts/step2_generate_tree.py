#!/usr/bin/env python3
"""
step2_generate_tree.py — 读取合并后的 Frame JSON，生成业务 Frame 节点树。

用法：python scripts/step2_generate_tree.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "input"
MERGED_DIR = PROJECT_ROOT / "data-output" / "frames-merged"
TREE_DIR = PROJECT_ROOT / "data-output" / "normalized"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_tree(node, prefix="", is_last=True):
    """递归输出紧凑树状图。"""
    connector = "└─ " if is_last else "├─ "
    node_type = node.get("type", "?")
    node_id = node.get("id", "")
    node_name = node.get("name", "")
    text = node.get("text", "")
    line = f"{prefix}{connector}[{node_type}] {node_id} {node_name}"
    if text:
        text_short = text[:60].replace("\n", "\\n")
        line += f'  "{text_short}"'

    lines = [line]

    children = node.get("children", [])
    for i, child in enumerate(children):
        child_prefix = prefix + ("   " if is_last else "│  ")
        child_lines = format_tree(child, child_prefix, i == len(children) - 1)
        lines.extend(child_lines)

    return lines


def main():
    definitions_path = INPUT_DIR / "1-frame-definitions.json"
    if not definitions_path.exists():
        print(f"[ERR] 找不到 {definitions_path}")
        sys.exit(1)

    definitions = load_json(definitions_path)

    TREE_DIR.mkdir(parents=True, exist_ok=True)

    tree_lines = [
        "# 业务 Frame 节点树",
        "",
        "说明：按业务 Frame 重组。格式为 `[type] nodeId name`。文本节点附加内容预览。",
        f"共 {len(definitions)} 个业务 Frame，按页面从上到下排列。",
        "",
        "```",
    ]

    for frame_id in definitions:
        merged_path = MERGED_DIR / f"{frame_id}.json"
        if not merged_path.exists():
            print(f"  [WARN] 找不到合并文件: {merged_path.name}")
            continue

        merged = load_json(merged_path)
        meta = merged["meta"]

        tree_lines.append(f"[FRAME] {frame_id}  [{meta['type']}]  "
                         f"({meta['bounds']['x']:.0f},{meta['bounds']['y']:.0f})  "
                         f"{meta['bounds']['width']:.0f}×{meta['bounds']['height']:.0f}")

        modules_in_order = merged["modules"]
        for mi, mod in enumerate(modules_in_order):
            is_last_mod = (mi == len(modules_in_order) - 1)
            mod_prefix = "└─ " if is_last_mod else "├─ "

            pos = mod["position"]
            tree_lines.append(
                f"{mod_prefix}[MODULE] {mod['fileName']}  zIndex={mod['zIndex']}  "
                f"({pos['x']:.0f},{pos['y']:.0f}) {pos['width']:.0f}×{pos['height']:.0f}"
            )

            node = mod.get("node")
            if node:
                children = node.get("children", [])
                child_prefix = "   " if is_last_mod else "│  "
                for ci, child in enumerate(children):
                    is_last_child = (ci == len(children) - 1)
                    child_lines = format_tree(child, child_prefix, is_last_child)
                    tree_lines.extend(child_lines)

        tree_lines.append("")

    tree_lines.append("```")

    tree_path = TREE_DIR / "tree.md"
    with open(tree_path, "w", encoding="utf-8") as f:
        f.write("\n".join(tree_lines))

    print(f"[DONE] tree.md → {tree_path}")


if __name__ == "__main__":
    main()

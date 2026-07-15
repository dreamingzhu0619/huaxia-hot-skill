#!/usr/bin/env python3
"""计算模块 contentArea padding。

遍历模块 node 树，排除指定的固定节点后，计算剩余内容节点的包围盒，
输出 paddingTop / paddingBottom / paddingLeft / paddingRight。

用法：
  python scripts/calc_content_area.py data/<project>/modules/01-产品卡.json \
      --exclude-ids "0:51,0:52,0:53,0:62,0:65"

  python scripts/calc_content_area.py data/<project>/modules/01-产品卡.json \
      --exclude exclude_ids.json
"""

import json
import sys
import argparse
from pathlib import Path


def collect_bounds(node, exclude_ids):
    """递归收集非排除节点的 bounds。

    遇到被排除的节点时，跳过该节点及其所有子节点。
    只收集叶子节点的 bounds（TEXT / LAYER / PATH / ELLIPSE / SVG_ELLIPSE）。
    """
    node_id = node.get("id", "")
    if node_id in exclude_ids:
        return []

    bounds_list = []
    node_type = node.get("type", "")

    leaf_types = {"TEXT", "LAYER", "PATH", "ELLIPSE", "SVG_ELLIPSE"}
    if node.get("bounds") and node_type in leaf_types:
        b = node["bounds"]
        bounds_list.append({
            "x": b["x"],
            "y": b["y"],
            "width": b["width"],
            "height": b["height"],
        })

    for child in node.get("children", []):
        bounds_list.extend(collect_bounds(child, exclude_ids))

    return bounds_list


def calc_content_area(module_path, exclude_ids):
    """计算单个模块的 contentArea。"""
    with open(module_path, "r", encoding="utf-8") as f:
        module = json.load(f)

    root = module["node"]
    frame = root["bounds"]
    frame_left = frame["x"]
    frame_top = frame["y"]
    frame_right = frame_left + frame["width"]
    frame_bottom = frame_top + frame["height"]

    all_bounds = []
    for child in root.get("children", []):
        all_bounds.extend(collect_bounds(child, exclude_ids))

    if not all_bounds:
        return {
            "paddingTop": 0,
            "paddingBottom": 0,
            "paddingLeft": 0,
            "paddingRight": 0,
            "note": "无内容节点，所有边距为 0（可能所有节点都被排除了）",
        }

    min_left = min(b["x"] for b in all_bounds)
    min_top = min(b["y"] for b in all_bounds)
    max_right = max(b["x"] + b["width"] for b in all_bounds)
    max_bottom = max(b["y"] + b["height"] for b in all_bounds)

    return {
        "paddingTop": round(min_top - frame_top, 2),
        "paddingBottom": round(frame_bottom - max_bottom, 2),
        "paddingLeft": round(min_left - frame_left, 2),
        "paddingRight": round(frame_right - max_right, 2),
        "note": "所有值为设计稿原始 px，Step 3 统一 ÷3 换算",
    }


def main():
    parser = argparse.ArgumentParser(description="计算模块 contentArea padding")
    parser.add_argument("module_json", help="模块 JSON 文件路径")
    parser.add_argument(
        "--exclude", "-e",
        help="排除的 node ID 列表（JSON 文件，内容为字符串数组）",
    )
    parser.add_argument(
        "--exclude-ids", "-x",
        help="排除的 node ID（逗号分隔）",
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        default=True,
        help="格式化输出 JSON",
    )
    args = parser.parse_args()

    exclude_ids = set()
    if args.exclude:
        with open(args.exclude, "r", encoding="utf-8") as f:
            exclude_ids.update(json.load(f))
    if args.exclude_ids:
        exclude_ids.update(s.strip() for s in args.exclude_ids.split(",") if s.strip())

    result = calc_content_area(args.module_json, exclude_ids)
    indent = 2 if args.pretty else None
    print(json.dumps(result, ensure_ascii=False, indent=indent))


if __name__ == "__main__":
    main()

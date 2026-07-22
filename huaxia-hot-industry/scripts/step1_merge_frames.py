#!/usr/bin/env python3
"""
step1_merge_frames.py — 按 1-frame-merge-map.json 合并模块为业务 Frame。

读取 data/input/1-frame-merge-map.json，将对应模块 JSON 合并，
模块按 y 坐标排序（从上到下），输出到 data-output/frames-merged/。

用法：python scripts/step1_merge_frames.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = PROJECT_ROOT / "data" / "modules"
INPUT_DIR = PROJECT_ROOT / "data" / "input"
OUTPUT_DIR = PROJECT_ROOT / "data-output" / "frames-merged"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    definitions_path = INPUT_DIR / "1-frame-definitions.json"
    if not definitions_path.exists():
        print(f"[ERR] 找不到 {definitions_path}")
        sys.exit(1)

    definitions = load_json(definitions_path)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for frame_id, frame_def in definitions.items():
        module_names = frame_def["modules"]
        frame_type = frame_def["type"]
        print(f"\n[{frame_id}] type={frame_type}  合并 {len(module_names)} 个模块...")

        # 加载模块数据
        modules = []
        for name in module_names:
            mod_path = MODULES_DIR / f"{name}.json"
            if not mod_path.exists():
                print(f"  [WARN] 模块文件不存在: {mod_path.name}")
                continue
            mod = load_json(mod_path)
            modules.append(mod)
            print(f"  ✓ {name}  (y={mod['meta']['position']['y']})")

        if not modules:
            print(f"  [ERR] 没有成功加载任何模块，跳过 {frame_id}")
            continue

        # 按 y 坐标排序（从上到下）
        modules.sort(key=lambda m: m["meta"]["position"]["y"])

        # 计算合并后的总边界
        min_x = min(m["meta"]["position"]["x"] for m in modules)
        min_y = min(m["meta"]["position"]["y"] for m in modules)
        max_x = max(m["meta"]["position"]["x"] + m["meta"]["position"]["width"] for m in modules)
        max_y = max(m["meta"]["position"]["y"] + m["meta"]["position"]["height"] for m in modules)

        # 收集所有 section indexes
        all_sections = []
        for m in modules:
            all_sections.extend(m["meta"].get("sectionIndexes", []))

        # 合并 assets（nodeId 全局唯一，直接合并不会冲突）
        merged_svgs = {}
        merged_bitmaps = []
        for m in modules:
            merged_svgs.update(m.get("assets", {}).get("svgs", {}))
            merged_bitmaps.extend(m.get("assets", {}).get("bitmaps", []))

        # 合并 D2C html 片段（按 y 排序后拼接）
        d2c_html_parts = []
        d2c_svg_icons = {}
        d2c_export_images = {}
        for m in modules:
            d2c = m.get("d2c")
            if d2c:
                html = d2c.get("html", "")
                if html:
                    d2c_html_parts.append(html)
                d2c_svg_icons.update(d2c.get("svgIcons", {}))
                d2c_export_images.update(d2c.get("exportImages", {}))

        merged = {
            "meta": {
                "frameId": frame_id,
                "type": frame_type,
                "moduleNames": [m["meta"]["fileName"] for m in modules],
                "moduleCount": len(modules),
                "bounds": {
                    "x": min_x,
                    "y": min_y,
                    "width": max_x - min_x,
                    "height": max_y - min_y,
                },
                "sectionIndexes": sorted(set(all_sections)),
                "totalNodes": sum(m["meta"]["nodeCount"] for m in modules),
                "totalTexts": sum(m["meta"]["textCount"] for m in modules),
                "moduleOrder": [m["meta"]["fileName"] for m in modules],
            },
            "modules": [
                {
                    "fileName": m["meta"]["fileName"],
                    "moduleIndex": m["meta"]["moduleIndex"],
                    "zIndex": m["meta"]["moduleIndex"],
                    "moduleId": m["meta"]["moduleId"],
                    "moduleName": m["meta"]["moduleName"],
                    "position": m["meta"]["position"],
                    "nodeCount": m["meta"]["nodeCount"],
                    "textCount": m["meta"]["textCount"],
                    "sectionIndexes": m["meta"]["sectionIndexes"],
                    "node": m.get("node"),
                    "sections": m.get("sections", []),
                    "d2c": m.get("d2c"),
                }
                for m in modules
            ],
            "assets": {
                "bitmaps": merged_bitmaps,
                "svgs": merged_svgs,
            },
            "d2c": {
                "html": "\n".join(d2c_html_parts),
                "svgIcons": d2c_svg_icons,
                "exportImages": d2c_export_images,
            } if d2c_html_parts else None,
        }

        out_path = OUTPUT_DIR / f"{frame_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        print(f"  → {out_path.name}  ({out_path.stat().st_size / 1024:.1f} KB)")
        print(f"    边界: ({min_x}, {min_y}) {max_x - min_x:.0f} × {max_y - min_y:.0f}")

    print(f"\n[DONE] 输出: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
extract_union_schema.py — 按数据源分组，输出极简的「来源 → 字段列表」。
每个字段只有路径，没有示例、没有分析。

输出: data/audit/union-schema.json
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
AUDIT_DIR = PROJECT_ROOT / "data" / "audit"


# ============================================================================
# 1. getDsl — 节点字段（所有 type 并集）
# ============================================================================

def getdsl_node_fields(raw_dir: Path) -> list:
    dsl_raw = json.load(open(raw_dir / "01-getDsl/getDsl.json", encoding="utf-8"))
    dsl = dsl_raw.get("dsl", dsl_raw)
    nodes_root = dsl.get("nodes", [])

    all_fields = set()

    def walk(node, depth=0):
        if depth > 8:
            return

        def _collect(obj, prefix=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "children":
                        continue
                    full = f"{prefix}.{k}" if prefix else k
                    all_fields.add(full)
                    if isinstance(v, (dict, list)):
                        _collect(v, full)
            elif isinstance(obj, list) and len(obj) > 0:
                full = f"{prefix}[]" if prefix else "[]"
                all_fields.add(full)
                for item in obj[:2]:
                    _collect(item, full)

        _collect(node)
        for child in node.get("children", []):
            walk(child, depth + 1)

    for root in nodes_root:
        walk(root)

    return sorted(all_fields)


# ============================================================================
# 2. getDsl — styles 子字段（按 paint_ / font_ / effect_ 分组）
# ============================================================================

def getdsl_style_fields(raw_dir: Path) -> dict:
    dsl_raw = json.load(open(raw_dir / "01-getDsl/getDsl.json", encoding="utf-8"))
    dsl = dsl_raw.get("dsl", dsl_raw)
    styles = dsl.get("styles", {})

    paint = set()
    font = set()
    effect = set()

    for key, style_obj in styles.items():
        value = style_obj.get("value")
        prefix = key.split("_")[0]

        if prefix == "paint" and isinstance(value, list):
            paint.add("value[]")
            for item in value[:3]:
                if isinstance(item, dict):
                    for k in item:
                        paint.add(f"value[].{k}")
                else:
                    paint.add(f"value[].<color-string>")

        elif prefix == "font" and isinstance(value, dict):
            for k in value:
                font.add(f"value.{k}")

        elif prefix == "effect" and isinstance(value, list):
            effect.add("value[]")

    return {
        "paint_": sorted(paint),
        "font_": sorted(font),
        "effect_": sorted(effect),
    }


# ============================================================================
# 3. D2C — CSS 属性
# ============================================================================

def d2c_css_fields(raw_dir: Path) -> list:
    path = raw_dir / "07-getD2c" / "getD2c.json"
    if not path.exists():
        return []

    data = json.load(open(path, encoding="utf-8"))
    d2c_data = data.get("data", [])
    if not d2c_data:
        return []
    payload = d2c_data[0].get("payload", {})
    html = payload.get("code", "")

    props = set()
    for m in re.finditer(r'style="([^"]*)"', html):
        for d in m.group(1).split(";"):
            d = d.strip()
            if ":" in d:
                props.add(d.split(":", 1)[0].strip())

    return sorted(props)


# ============================================================================
# 4. D2C payload 结构（svg / image 字典）
# ============================================================================

def d2c_payload_keys(raw_dir: Path) -> list:
    path = raw_dir / "07-getD2c" / "getD2c.json"
    if not path.exists():
        return []
    data = json.load(open(path, encoding="utf-8"))
    d2c_data = data.get("data", [])
    if not d2c_data:
        return []
    payload = d2c_data[0].get("payload", {})
    return sorted(k for k in payload if k != "code")


# ============================================================================
# 5. 其他工具
# ============================================================================

def other_fields(raw_dir: Path) -> dict:
    result = {}

    # extractSvg
    es_path = raw_dir / "05-extractSvg" / "extractSvg.json"
    if es_path.exists():
        es = json.load(open(es_path, encoding="utf-8"))
        if es.get("svgs"):
            result["extractSvg"] = sorted(es["svgs"][0].keys())

    # getDesignSvgs
    ds_path = raw_dir / "05-getDesignSvgs" / "getDesignSvgs.json"
    if ds_path.exists():
        result["getDesignSvgs"] = ["svgs"]  # {key: svgString}

    # getDesignTexts
    txt_path = raw_dir / "05-getDesignTexts" / "getDesignTexts.json"
    if txt_path.exists():
        result["getDesignTexts"] = ["texts"]  # {placeholder: fullText}

    # getDesignSections overview
    ov_path = raw_dir / "03-getDesignSections" / "overview.json"
    if ov_path.exists():
        ov = json.load(open(ov_path, encoding="utf-8"))
        if ov.get("sections"):
            result["getDesignSections.overview"] = sorted(ov["sections"][0].keys())

    # getDesignSections 分段详情
    detail_paths = sorted((raw_dir / "03-getDesignSections").glob("section-*.json"))
    if detail_paths:
        detail = json.load(open(detail_paths[0], encoding="utf-8"))
        result["getDesignSections.detail"] = sorted(detail.keys())

    return result


# ============================================================================
# 主流程
# ============================================================================

def main():
    print("提取极简字段清单...")

    union = {
        "getDsl": {
            "node": getdsl_node_fields(RAW_DIR),
            "styles": getdsl_style_fields(RAW_DIR),
        },
        "getD2c": {
            "css": d2c_css_fields(RAW_DIR),
            "payload": d2c_payload_keys(RAW_DIR),
        },
    }

    others = other_fields(RAW_DIR)
    union.update(others)

    print(f"  getDsl.node: {len(union['getDsl']['node'])} 字段")
    print(f"  getDsl.styles: paint_={len(union['getDsl']['styles']['paint_'])}, "
          f"font_={len(union['getDsl']['styles']['font_'])}, "
          f"effect_={len(union['getDsl']['styles']['effect_'])}")
    print(f"  getD2c.css: {len(union['getD2c']['css'])} 属性")
    print(f"  getD2c.payload: {union['getD2c']['payload']}")
    for k, v in others.items():
        print(f"  {k}: {v}")

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / "union-schema.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(union, f, ensure_ascii=False, indent=2)

    print(f"\n输出: {out_path}  ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()

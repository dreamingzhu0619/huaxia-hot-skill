#!/usr/bin/env python3
"""
scan_all_fields.py — 扫描所有 MCP 工具原始数据，提取完整字段清单。

遍历 data/raw/ 下所有工具的原始输出，提取：
  1. getDsl 节点树中每个节点出现的所有字段（按 type 分组）
  2. getDsl styles 字典中每种样式类型的所有字段
  3. getDesignSections overview + 分段详情中的所有字段
  4. getDesignSvgs / extractSvg 的数据结构
  5. getDesignTexts 的数据结构
  6. D2C HTML 中所有 CSS 属性名
  7. getMeta 的结构

最后合并输出为 data/audit/all-fields.json。

用法：
  python scripts/audit/scan_all_fields.py
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
# 工具函数：递归收集 dict 内所有字段路径
# ============================================================================

def collect_field_paths(obj, prefix="", max_depth=5):
    """
    递归收集 obj 中所有字段路径，返回 set of "a.b.c"。
    只深入到 max_depth，避免过度展开。
    数组元素只取第一个做样本。
    """
    paths = set()
    if max_depth <= 0:
        return paths

    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            paths.add(full)
            child_paths = collect_field_paths(v, full, max_depth - 1)
            paths.update(child_paths)
    elif isinstance(obj, list) and len(obj) > 0:
        paths.add(f"{prefix}[]")
        child_paths = collect_field_paths(obj[0], f"{prefix}[]", max_depth - 1)
        paths.update(child_paths)

    return paths


def collect_leaf_paths(obj, prefix="", max_depth=6):
    """
    收集到叶子值（非 dict 非 list），返回 set of "a.b.c"。
    """
    paths = set()
    if max_depth <= 0:
        return paths

    if isinstance(obj, dict):
        if not obj:
            paths.add(f"{prefix}={{}}")
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            leaf = collect_leaf_paths(v, full, max_depth - 1)
            paths.update(leaf)
    elif isinstance(obj, list):
        paths.add(f"{prefix}[]")
        for i, item in enumerate(obj):
            if i >= 3:  # 最多取前 3 个样本
                break
            leaf = collect_leaf_paths(item, f"{prefix}[]", max_depth - 1)
            paths.update(leaf)
    else:
        # 叶子值：记录路径 + 值的示例
        val_repr = repr(obj)
        if len(val_repr) > 80:
            val_repr = val_repr[:77] + "..."
        paths.add(f"{prefix} = {val_repr}")

    return paths


# ============================================================================
# 解析器
# ============================================================================

def scan_getdsl_nodes(raw_dir: Path) -> dict:
    """扫描 getDsl 节点树，收集所有节点字段 + 按 type 分组。"""
    dsl_raw = json.load(open(raw_dir / "01-getDsl/getDsl.json", encoding="utf-8"))
    dsl = dsl_raw.get("dsl", dsl_raw)
    nodes_root = dsl.get("nodes", [])
    styles = dsl.get("styles", {})

    all_field_paths = set()
    fields_by_type = defaultdict(set)

    def walk(node):
        node_type = node.get("type", "UNKNOWN")
        fields = set()
        for k in node.keys():
            if k == "children":
                continue
            fields.add(k)
        all_field_paths.update(fields)
        fields_by_type[node_type].update(fields)

        # 递归展开子字段（dict 值）
        for k, v in node.items():
            if k == "children" or k == "type":
                continue
            sub = collect_field_paths(v, k, max_depth=4)
            all_field_paths.update(sub)
            fields_by_type[node_type].update(sub)

        for child in node.get("children", []):
            walk(child)

    for root in nodes_root:
        walk(root)

    # 将 set 转 sorted list
    return {
        "allPaths": sorted(all_field_paths),
        "byType": {t: sorted(fs) for t, fs in sorted(fields_by_type.items())},
        "typeCount": {t: len(fs) for t, fs in fields_by_type.items()},
    }


def scan_getdsl_styles(raw_dir: Path) -> dict:
    """扫描 getDsl styles 字典，按 paint_/font_/effect_ 分组收集字段。"""
    dsl_raw = json.load(open(raw_dir / "01-getDsl/getDsl.json", encoding="utf-8"))
    dsl = dsl_raw.get("dsl", dsl_raw)
    styles = dsl.get("styles", {})

    fields_by_prefix = defaultdict(set)
    prefix_counts = defaultdict(int)

    for key, style_obj in styles.items():
        prefix = key.split("_")[0] + "_"  # "paint_", "font_", "effect_"
        prefix_counts[prefix] += 1
        # 收集 value 里的叶子字段
        value = style_obj.get("value")
        if value is not None:
            leaf_paths = collect_leaf_paths(value, f"{prefix}value", max_depth=5)
            fields_by_prefix[prefix].update(leaf_paths)
        else:
            # style 自身可能还有其他字段
            for k, v in style_obj.items():
                if k == "value":
                    continue
                fields_by_prefix[prefix].add(f"{prefix}{k} = {repr(v)[:60]}")

    result = {}
    for prefix in sorted(prefix_counts):
        result[prefix] = {
            "count": prefix_counts[prefix],
            "fields": sorted(fields_by_prefix[prefix]),
        }
    return result


def scan_design_sections(raw_dir: Path) -> dict:
    """扫描 getDesignSections overview + 分段详情。"""
    overview_path = raw_dir / "03-getDesignSections" / "overview.json"
    if not overview_path.exists():
        return {"error": "overview.json not found"}

    overview = json.load(open(overview_path, encoding="utf-8"))

    # overview 自身的字段
    overview_fields = sorted(overview.keys())

    # sections[] 里每个 section 的字段
    sections = overview.get("sections", [])
    section_fields = set()
    for s in sections[:10]:  # 取前 10 个样本
        section_fields.update(s.keys())
        for k, v in s.items():
            if isinstance(v, dict):
                section_fields.update(collect_field_paths(v, k, max_depth=3))
    section_fields.discard("id")
    section_fields.discard("name")
    section_fields.discard("type")

    # 分段详情 (section-00.json 等)
    detail_paths = sorted((raw_dir / "03-getDesignSections").glob("section-*.json"))
    detail_fields = set()
    detail_dsl_fields = set()
    if detail_paths:
        detail = json.load(open(detail_paths[0], encoding="utf-8"))
        detail_fields.update(detail.keys())
        # section.dsl 里的节点字段
        section_dsl = detail.get("dsl", {})
        if isinstance(section_dsl, dict):
            detail_dsl_fields.update(collect_field_paths(section_dsl, "dsl", max_depth=4))
        # section.section 里的字段
        section_meta = detail.get("section", {})
        if isinstance(section_meta, dict):
            detail_fields.update(f"section.{k}" for k in section_meta.keys())

    return {
        "overviewTopKeys": overview_fields,
        "rootMetadata": sorted(overview.get("rootMetadata", {}).keys()) if overview.get("rootMetadata") else [],
        "rootContainer": sorted(overview.get("rootContainer", {}).keys()) if overview.get("rootContainer") else [],
        "splitContainers": type(overview.get("splitContainers")).__name__,
        "sectionKeys": sorted(section_fields),
        "detailTopKeys": sorted(detail_fields),
        "detailDslFields": sorted(detail_dsl_fields),
        "totalSections": overview.get("totalSections", 0),
    }


def scan_svgs(raw_dir: Path) -> dict:
    """扫描 getDesignSvgs + extractSvg。"""
    result = {}

    # getDesignSvgs
    design_svgs_path = raw_dir / "05-getDesignSvgs" / "getDesignSvgs.json"
    if design_svgs_path.exists():
        ds = json.load(open(design_svgs_path, encoding="utf-8"))
        result["getDesignSvgs"] = {
            "topKeys": sorted(ds.keys()),
            "svgsCount": len(ds.get("svgs", {})),
            "keySample": list(ds.get("svgs", {}).keys())[:3],
        }

    # extractSvg
    extract_svgs_path = raw_dir / "05-extractSvg" / "extractSvg.json"
    if extract_svgs_path.exists():
        es = json.load(open(extract_svgs_path, encoding="utf-8"))
        svgs_list = es.get("svgs", [])
        item_fields = set()
        if svgs_list:
            for item in svgs_list[:5]:
                item_fields.update(item.keys())
        result["extractSvg"] = {
            "topKeys": sorted(es.keys()),
            "svgsCount": len(svgs_list),
            "itemFields": sorted(item_fields),
        }

    return result


def scan_design_texts(raw_dir: Path) -> dict:
    """扫描 getDesignTexts。"""
    path = raw_dir / "05-getDesignTexts" / "getDesignTexts.json"
    if not path.exists():
        return {"error": "not found"}

    data = json.load(open(path, encoding="utf-8"))
    texts = data.get("texts", {})
    return {
        "topKeys": sorted(data.keys()),
        "textsCount": len(texts),
        "keySample": list(texts.keys())[:5],
    }


def scan_d2c_css(raw_dir: Path) -> dict:
    """解析 D2C HTML，提取所有 CSS 属性名。"""
    path = raw_dir / "07-getD2c" / "getD2c.json"
    if not path.exists():
        return {"error": "getD2c.json not found"}

    data = json.load(open(path, encoding="utf-8"))
    d2c_data = data.get("data", [])
    if not d2c_data:
        return {"error": "empty data array"}

    payload = d2c_data[0].get("payload", {})
    html = payload.get("code", "")
    if not html:
        return {"error": "no code in payload"}

    # 提取所有 CSS 属性名
    css_props = set()
    # 匹配 style="prop: value; prop2: value2"
    for m in re.finditer(r'style="([^"]*)"', html):
        decls = m.group(1).split(";")
        for d in decls:
            d = d.strip()
            if ":" in d:
                prop = d.split(":", 1)[0].strip()
                if prop:
                    css_props.add(prop)

    # 也检查 <style> 块
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", html, re.S):
        for pm in re.finditer(r"([-\w]+)\s*:", m.group(1)):
            css_props.add(pm.group(1))

    # 按类别分组
    categories = {
        "positioning": [],
        "dimensions": [],
        "visual": [],
        "typography": [],
        "transform": [],
        "effects": [],
        "other": [],
    }

    for prop in sorted(css_props):
        if prop in ("position", "left", "top", "right", "bottom", "z-index", "inset"):
            categories["positioning"].append(prop)
        elif prop in ("width", "height", "max-width", "max-height", "min-width", "min-height", "display", "overflow", "overflow-x", "overflow-y"):
            categories["dimensions"].append(prop)
        elif prop in ("background", "background-color", "background-image", "background-size", "background-position", "background-repeat", "background-clip", "background-origin", "border", "border-radius", "border-width", "border-style", "border-color", "opacity", "visibility", "box-shadow", "mix-blend-mode", "background-blend-mode", "isolation", "filter", "backdrop-filter"):
            categories["visual"].append(prop)
        elif prop in ("font-family", "font-size", "font-weight", "font-style", "line-height", "letter-spacing", "color", "text-align", "text-decoration", "text-transform", "text-indent", "white-space", "word-break", "word-wrap", "-webkit-text-fill-color", "-webkit-text-stroke", "-webkit-text-stroke-width", "-webkit-text-stroke-color"):
            categories["typography"].append(prop)
        elif prop in ("transform", "transform-origin", "transform-style", "perspective", "rotate", "scale", "translate"):
            categories["transform"].append(prop)
        elif prop.startswith("mask") or prop.startswith("clip") or prop.startswith("-webkit-mask"):
            categories["effects"].append(prop)
        else:
            categories["other"].append(prop)

    # 同时提取 payload 其他字段
    payload_keys = {
        "code": f"str len={len(html)}",
        "svg": f"dict count={len(payload.get('svg', {}))}",
        "image": f"dict count={len(payload.get('image', {}))}",
    }

    return {
        "payloadKeys": payload_keys,
        "cssPropertyCount": len(css_props),
        "cssPropertiesByCategory": {k: v for k, v in categories.items() if v},
        "allCssProperties": sorted(css_props),
    }


def scan_get_meta(raw_dir: Path) -> dict:
    """扫描 getMeta。"""
    path = raw_dir / "02-getMeta" / "getMeta.txt"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        return {"format": "txt", "length": len(text), "preview": text[:200]}
    path = raw_dir / "02-getMeta" / "getMeta.md"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        return {"format": "md", "length": len(text), "preview": text[:200]}
    path = raw_dir / "02-getMeta" / "getMeta.json"
    if path.exists():
        data = json.load(open(path, encoding="utf-8"))
        return {"format": "json", "topKeys": sorted(data.keys())}
    return {"error": "no getMeta file found"}


# ============================================================================
# 合并：生成完整字段清单
# ============================================================================

def merge_all(results: dict) -> dict:
    """
    将各工具的字段合并成一份「全集字段清单」。
    按 CSS 属性维度组织，标注每个字段从哪些数据源可获得。
    """

    dsl_nodes = results.get("getDslNodes", {})
    dsl_styles = results.get("getDslStyles", {})
    d2c = results.get("d2c", {})

    # 从 getDsl 节点字段 -> CSS 属性的映射
    dsl_to_css_map = {
        # layoutStyle
        "layoutStyle.width": "width",
        "layoutStyle.height": "height",
        "layoutStyle.relativeX": "left",
        "layoutStyle.relativeY": "top",
        "layoutStyle.rotate": "transform: rotate()",
        "layoutStyle.rotateX": "transform: rotateX()",
        "layoutStyle.rotateY": "transform: rotateY()",
        # 节点直接字段
        "opacity": "opacity",
        "borderRadius": "border-radius",
        "borderRadius.topLeft": "border-top-left-radius",
        "borderRadius.topRight": "border-top-right-radius",
        "borderRadius.bottomRight": "border-bottom-right-radius",
        "borderRadius.bottomLeft": "border-bottom-left-radius",
        "visible": "visibility",
        "name": "(layer name)",
        "id": "(node id)",
        "type": "(node type)",
        # fill (解引用 paint_)
        "fill": "background / color",
        # stroke
        "strokeWeight": "stroke-width / border-width",
        "strokeAlign": "(stroke alignment)",
        "strokeColor": "border-color / -webkit-text-stroke-color",
        "strokeType": "border-style",
        # effect (解引用 effect_)
        "effect": "box-shadow / filter / backdrop-filter",
        # text
        "text": "(text content)",
        "textColor": "(text color per run)",
        "textAlign": "text-align",
        "textMode": "(text mode)",
        # path
        "path.data": "(SVG path data)",
        "path.winding": "(fill rule)",
        # mask
        "mask": "mask / -webkit-mask",
        # clip
        "clip": "overflow: hidden",
        # component
        "componentId": "(component source)",
        "componentName": "(component name)",
    }

    # styles 能提供的 CSS 属性
    style_to_css_map = {
        "paint_": "background / background-image / color / linear-gradient()",
        "font_": "font-family / font-size / font-weight / font-style / line-height / letter-spacing",
        "effect_": "box-shadow / filter: blur() / backdrop-filter",
    }

    # D2C 独有的
    d2c_only = [
        "mix-blend-mode",
        "background-blend-mode",
        "overflow",
        "isolation",
    ]

    css_fields = []
    all_css_props = d2c.get("allCssProperties", [])

    for prop in all_css_props:
        sources = ["getD2c"]  # D2C 总是有这个属性
        getdsl_source = None
        styles_source = None
        d2c_is_only_source = True

        # 反向查：这个 CSS 属性能从 getDsl 的哪个字段推导
        for dsl_path, css_name in dsl_to_css_map.items():
            if prop == css_name or (css_name.startswith(prop) and ":" in css_name):
                getdsl_source = dsl_path
                d2c_is_only_source = False
                break
            if prop in css_name or css_name in prop:
                getdsl_source = dsl_path
                d2c_is_only_source = False
                break

        # 查 styles
        for style_prefix, css_desc in style_to_css_map.items():
            if any(keyword in prop for keyword in ["font", "background", "color", "box-shadow", "filter", "backdrop", "gradient", "image"]):
                if any(kw in css_desc for kw in [prop, prop.replace("-", "")]):
                    styles_source = f"styles[{style_prefix}*]"
                    d2c_is_only_source = False
                    break

        if getdsl_source:
            sources.append(f"getDsl → {getdsl_source}")
        if styles_source:
            sources.append(styles_source)

        entry = {
            "cssProperty": prop,
            "sources": sources,
            "getdslOnly": d2c_is_only_source and not getdsl_source,
        }
        css_fields.append(entry)

    return {
        "summary": {
            "totalCssPropertiesFromD2C": len(all_css_props),
            "getdslNodeFieldCount": len(dsl_nodes.get("allPaths", [])),
            "getdslStyleTypeCount": len(dsl_styles),
            "nodeTypes": list(dsl_nodes.get("byType", {}).keys()),
        },
        "byDataSource": {
            "getDslNodes": {
                "nodeTypeFieldCounts": dsl_nodes.get("typeCount", {}),
                "allUniqueFields": dsl_nodes.get("allPaths", []),
                "fieldsByType_sample": {
                    t: fs[:30] for t, fs in dsl_nodes.get("byType", {}).items()
                },
            },
            "getDslStyles": dsl_styles,
            "getDesignSections": results.get("designSections", {}),
            "getDesignSvgs_extractSvg": results.get("svgs", {}),
            "getDesignTexts": results.get("designTexts", {}),
            "getD2c": {
                "payloadKeys": d2c.get("payloadKeys", {}),
                "cssPropertyCount": d2c.get("cssPropertyCount", 0),
                "cssPropertiesByCategory": d2c.get("cssPropertiesByCategory", {}),
            },
            "getMeta": results.get("getMeta", {}),
        },
        "cssCoverage": css_fields,
    }


# ============================================================================
# 主流程
# ============================================================================

def main():
    print("=" * 60)
    print("scan_all_fields — 全工具字段扫描")
    print("=" * 60)

    results = {}

    # 1. getDsl 节点
    print("\n[1/7] 扫描 getDsl 节点树...")
    results["getDslNodes"] = scan_getdsl_nodes(RAW_DIR)
    n = results["getDslNodes"]
    print(f"  节点类型: {list(n['byType'].keys())}")
    for t, fs in n["typeCount"].items():
        print(f"    {t}: {fs} 个唯一字段路径")

    # 2. getDsl styles
    print("\n[2/7] 扫描 getDsl styles...")
    results["getDslStyles"] = scan_getdsl_styles(RAW_DIR)
    for prefix, info in results["getDslStyles"].items():
        print(f"  {prefix}: {info['count']} 条, {len(info['fields'])} 个字段")

    # 3. getDesignSections
    print("\n[3/7] 扫描 getDesignSections...")
    results["designSections"] = scan_design_sections(RAW_DIR)
    ds = results["designSections"]
    print(f"  totalSections: {ds.get('totalSections')}")
    print(f"  overview keys: {ds.get('overviewTopKeys')}")
    print(f"  section keys: {ds.get('sectionKeys')}")

    # 4. getDesignSvgs + extractSvg
    print("\n[4/7] 扫描 getDesignSvgs + extractSvg...")
    results["svgs"] = scan_svgs(RAW_DIR)
    for k, v in results["svgs"].items():
        print(f"  {k}: {v}")

    # 5. getDesignTexts
    print("\n[5/7] 扫描 getDesignTexts...")
    results["designTexts"] = scan_design_texts(RAW_DIR)
    print(f"  texts: {results['designTexts'].get('textsCount')} 条")

    # 6. D2C
    print("\n[6/7] 扫描 D2C HTML/CSS...")
    results["d2c"] = scan_d2c_css(RAW_DIR)
    d2c = results["d2c"]
    print(f"  CSS 属性总数: {d2c.get('cssPropertyCount')}")
    for cat, props in d2c.get("cssPropertiesByCategory", {}).items():
        print(f"    {cat}: {props}")

    # 7. getMeta
    print("\n[7/7] 扫描 getMeta...")
    results["getMeta"] = scan_get_meta(RAW_DIR)
    print(f"  getMeta: {results['getMeta']}")

    # 合并输出
    print("\n" + "=" * 60)
    print("合并生成完整字段清单...")
    merged = merge_all(results)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = AUDIT_DIR / "all-fields.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"输出: {out_path}  ({out_path.stat().st_size / 1024:.1f} KB)")

    # 同时生成一份人类可读的 markdown
    md_path = AUDIT_DIR / "all-fields.md"
    md = generate_markdown(merged)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"输出: {md_path}  ({md_path.stat().st_size / 1024:.1f} KB)")

    print("\n[DONE] 字段扫描完成。")
    print(f"  JSON: {out_path}")
    print(f"  MD:   {md_path}")


def generate_markdown(merged: dict) -> str:
    """生成人类可读的字段清单 markdown。"""
    lines = []
    lines.append("# 完整字段清单 — 全 MCP 工具合并")
    lines.append("")
    lines.append(f"> 自动生成，扫描自 `data/raw/` 下所有工具的原始输出。")
    lines.append("")

    # 概要
    s = merged["summary"]
    lines.append("## 概要")
    lines.append("")
    lines.append(f"- D2C CSS 属性总数: **{s['totalCssPropertiesFromD2C']}**")
    lines.append(f"- getDsl 节点唯一字段路径: **{s['getdslNodeFieldCount']}**")
    lines.append(f"- getDsl 样式类型: **{s['getdslStyleTypeCount']}**")
    lines.append(f"- 节点类型: {s['nodeTypes']}")
    lines.append("")

    # 各数据源详细字段
    ds = merged["byDataSource"]
    lines.append("## 1. getDsl — 节点字段（按 type 分组）")
    lines.append("")
    for t, fs in ds["getDslNodes"]["nodeTypeFieldCounts"].items():
        lines.append(f"### {t} ({fs} 个唯一字段路径)")
        lines.append("")
        sample = ds["getDslNodes"]["fieldsByType_sample"].get(t, [])
        for f in sample:
            lines.append(f"- `{f}`")
        if fs > len(sample):
            lines.append(f"- ... 还有 {fs - len(sample)} 个字段（见 JSON）")
        lines.append("")

    lines.append("## 2. getDsl — Styles 字典")
    lines.append("")
    styles = ds["getDslStyles"]
    for prefix, info in styles.items():
        lines.append(f"### {prefix} ({info['count']} 条)")
        lines.append("")
        for f in info["fields"]:
            lines.append(f"- `{f}`")
        lines.append("")

    lines.append("## 3. getDesignSections")
    lines.append("")
    sec = ds["getDesignSections"]
    lines.append(f"- overview 顶层键: `{sec.get('overviewTopKeys')}`")
    lines.append(f"- section 条目键: `{sec.get('sectionKeys')}`")
    lines.append(f"- 详情顶层键: `{sec.get('detailTopKeys')}`")
    lines.append(f"- totalSections: {sec.get('totalSections')}")
    lines.append("")

    lines.append("## 4. getDesignSvgs + extractSvg")
    lines.append("")
    svgs = ds["getDesignSvgs_extractSvg"]
    for k, v in svgs.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## 5. getDesignTexts")
    lines.append("")
    txts = ds["getDesignTexts"]
    lines.append(f"- 顶层键: `{txts.get('topKeys')}`")
    lines.append(f"- texts 数量: {txts.get('textsCount')}")
    lines.append(f"- key 样本: `{txts.get('keySample')}`")
    lines.append("")

    lines.append("## 6. D2C — CSS 属性（按类别）")
    lines.append("")
    d2c = ds["getD2c"]
    for cat, props in d2c.get("cssPropertiesByCategory", {}).items():
        lines.append(f"### {cat}")
        lines.append("")
        for p in props:
            lines.append(f"- `{p}`")
        lines.append("")
    lines.append(f"### 全部 CSS 属性 ({d2c.get('cssPropertyCount')} 个)")
    lines.append("")

    lines.append("## 7. getMeta")
    lines.append("")
    meta = ds["getMeta"]
    lines.append(f"```\n{json.dumps(meta, ensure_ascii=False, indent=2)}\n```")
    lines.append("")

    # CSS 覆盖分析
    lines.append("## 8. CSS 属性 → 数据源对照")
    lines.append("")
    lines.append("| CSS 属性 | 数据源 | 仅 D2C? |")
    lines.append("|---|---|---|")
    d2c_only_props = []
    for entry in merged.get("cssCoverage", []):
        sources_str = " + ".join(entry["sources"])
        only = "⚠️ 仅 D2C" if entry["getdslOnly"] else ""
        if entry["getdslOnly"]:
            d2c_only_props.append(entry["cssProperty"])
        lines.append(f"| `{entry['cssProperty']}` | {sources_str} | {only} |")

    if d2c_only_props:
        lines.append("")
        lines.append("### ⚠️ 仅 D2C 能提供的属性")
        lines.append("")
        lines.append("这些属性 getDsl 无法提供，必须从 D2C 提取：")
        lines.append("")
        for p in d2c_only_props:
            lines.append(f"- `{p}`")

    return "\n".join(lines)


if __name__ == "__main__":
    main()

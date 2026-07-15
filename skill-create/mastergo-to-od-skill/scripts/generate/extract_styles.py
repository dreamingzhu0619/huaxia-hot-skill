#!/usr/bin/env python3
"""
extract_styles.py -- 从 modules JSON 机械提取视觉属性 -> styles.css。

Step 5a: 读取 component-config.json 确定合并后的组件列表，从代表模块的节点数据中
机械提取视觉属性。优先使用 d2cCss 值，getDsl 原始值作为补充。

Output: output/<project>-od/assets/<component>/styles.css

Usage:
  python scripts/generate/extract_styles.py --project <name>
  python scripts/generate/extract_styles.py --project <name> --component <name>
"""

import json
import sys
import argparse
import re
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = None
MODULES_DIR = None
ANALYSIS_DIR = None
OD_OUTPUT_DIR = None

LIB_DIR = SKILL_ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))
import css_core  # noqa: E402


def _num(v, ndigits=2):
    if v is None: return "0"
    f = round(float(v), ndigits)
    if f == int(f): return str(int(f))
    return f"{f:.{ndigits}f}".rstrip("0").rstrip(".")


def scale_px_value(val, scale):
    """Scale a px value: '55.85px' / 3 = '18.62px'"""
    if val is None: return None
    try:
        s = str(val).replace("px", "").strip()
        if not s: return None
        f = float(s)
        return f"{_num(f / scale)}px"
    except (ValueError, TypeError):
        return None


def scale_px_tokens(val, scale):
    if val is None:
        return None
    def repl(m):
        return scale_px_value(m.group(0), scale) or m.group(0)
    return re.sub(r"-?\d+(?:\.\d+)?px", repl, str(val))


def merge_visual_props(node):
    """从 node 的 d2cCss + getDsl 原始字段中融合视觉属性。
    d2cCss 优先级最高，getDsl 字段作为补充。
    """
    props = {}
    d2c = node.get("d2cCss") or {}
    ntype = node.get("type", "")
    is_text = ntype == "TEXT"
    is_path = ntype == "PATH"

    # --- 从 d2cCss 取值（优先） ---
    if not is_path:
        d2c_background = d2c.get("background") or d2c.get("background-image")
        if d2c_background and d2c_background != "null":
            props["background"] = d2c_background

        d2c_border = d2c.get("border")
        if d2c_border and d2c_border != "null":
            props["border"] = d2c_border

        d2c_radius = d2c.get("border-radius")
        if d2c_radius and d2c_radius != "null":
            props["border-radius"] = d2c_radius

    d2c_shadow = d2c.get("box-shadow")
    if d2c_shadow and d2c_shadow != "null":
        props["box-shadow"] = d2c_shadow

    d2c_opacity = d2c.get("opacity")
    if d2c_opacity and d2c_opacity != "null" and d2c_opacity != "1":
        props["opacity"] = d2c_opacity

    if is_text:
        props.update(css_core.font_to_css(node))
        props.update(css_core.effect_to_css(node.get("effect"), is_text=True))
        runs = node.get("textRuns") or []
        font = (runs[0].get("font") or {}) if runs else {}
        letter_spacing = font.get("letterSpacing")
        font_size = font.get("size")
        if isinstance(letter_spacing, str) and letter_spacing.endswith("%") and font_size is not None:
            try:
                props["letter-spacing"] = f"{_num(float(font_size) * float(letter_spacing.rstrip('%')) / 100.0)}px"
            except ValueError:
                pass
        family = str(font.get("family") or "")
        if not props.get("font-weight"):
            if "ExtraBold" in family or "Heavy" in family or "Black" in family:
                props["font-weight"] = "800"
            elif "Semibold" in family or "SemiBold" in family or "DemiBold" in family:
                props["font-weight"] = "600"
            elif "Bold" in family:
                props["font-weight"] = "700"
        for d2c_prop in ["font-family", "font-size", "color", "line-height",
                          "letter-spacing", "font-weight", "text-align"]:
            val = d2c.get(d2c_prop)
            if val and val != "null" and val != "none":
                props[d2c_prop] = val
        # text-shadow
        ts = d2c.get("text-shadow")
        if ts and ts != "null":
            props["text-shadow"] = ts

    # --- 从 getDsl 字段补充（d2cCss 缺失时） ---
    if not is_path and not props.get("background"):
        fill = node.get("fill")
        if fill:
            fill_css = css_core.fill_to_css(fill)
            props.update(fill_css)

    if not is_path and not props.get("border"):
        stroke = css_core.stroke_to_css(node, is_text=False)
        if stroke:
            props.update(stroke)

    if not is_path and not props.get("border-radius"):
        radius = node.get("borderRadius")
        if radius:
            props["border-radius"] = radius

    if is_path:
        props.update(css_core.effect_to_css(node.get("effect"), is_text=False))

    # --- 缩放 px 值 ---
    # Will be done by caller with designScale

    return props


def extract_for_component(comp, scale):
    """Extract styles for a single merged component."""
    module_file = comp.get("representativeModule") or comp["modules"][0]
    mod_path = MODULES_DIR / module_file
    if not mod_path.exists():
        print(f"  WARNING: {module_file} not found, skipping {comp['name']}")
        return None

    with open(mod_path, "r", encoding="utf-8") as f:
        mod_data = json.load(f)

    node = mod_data.get("node")
    if not node:
        return None

    rules = []
    node_count = 0

    def walk(n, depth=0):
        nonlocal node_count
        nid = n.get("id", "")
        ntype = n.get("type", "")

        if nid:
            node_count += 1
            props = merge_visual_props(n)

            # Scale px values
            scaled = {}
            for k, v in props.items():
                if v is None: continue
                if k in ("font-size", "line-height", "letter-spacing", "width", "height") or "radius" in k:
                    sv = scale_px_value(v, scale)
                    scaled[k] = sv if sv else str(v)
                elif k == "border":
                    # Scale border px values: "1px solid #xxx" -> "0.33px solid #xxx"
                    parts = str(v).split()
                    new_parts = []
                    for p in parts:
                        sp = scale_px_value(p, scale)
                        new_parts.append(sp if sp else p)
                    scaled[k] = " ".join(new_parts)
                elif k in ("box-shadow", "text-shadow", "filter"):
                    scaled[k] = scale_px_tokens(v, scale)
                else:
                    scaled[k] = str(v)

            if scaled:
                class_name = f".n-{nid.replace(':', '-')}"
                rules.append(_format_rule(class_name, scaled, nid, ntype, n.get("name", "")))

        for child in n.get("children") or []:
            walk(child, depth + 1)

    walk(node)

    return {"rules": rules, "nodeCount": node_count}


def _format_rule(class_name, props, nid, ntype, name):
    lines = [f"  /* {nid} {ntype} -- {name} */", f"  {class_name} {{"]
    for k, v in props.items():
        lines.append(f"    {k}: {v};")
    lines.append("  }")
    return "\n".join(lines)


def run(component_name=None):
    config_path = ANALYSIS_DIR / "component-config.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found. Run Step 4 first.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    scale = config["designScale"]["scale"]
    logical_w = config["designScale"]["logicalWidth"]

    out_base = OD_OUTPUT_DIR / "assets"
    out_base.mkdir(parents=True, exist_ok=True)

    processed = 0
    for comp in config["components"]:
        cname = comp["name"]
        if component_name and cname != component_name:
            continue

        module_files = comp.get("modules") or [comp.get("representativeModule")]
        if comp.get("instanceMode") != "array":
            module_files = [comp.get("representativeModule") or module_files[0]]

        rules = []
        node_count = 0
        for module_file in module_files:
            comp_for_module = dict(comp)
            comp_for_module["representativeModule"] = module_file
            result = extract_for_component(comp_for_module, scale)
            if result is None:
                continue
            rules.extend(result["rules"])
            node_count += result["nodeCount"]

        if not rules:
            continue

        comp_dir = out_base / cname
        comp_dir.mkdir(parents=True, exist_ok=True)

        header = f"/* {'='*60} */\n"
        header += f"/* {cname} -- styles.css\n"
        header += f"/* From: {', '.join(module_files)}\n"
        header += f"/* Scale: @{scale}x, logical width: {logical_w}px\n"
        header += f"/* Nodes extracted: {node_count}\n"
        header += f"/* {'='*60} */\n\n"

        with open(comp_dir / "styles.css", "w", encoding="utf-8") as f:
            f.write(header + "\n".join(rules) + "\n")

        processed += 1
        print(f"  {cname}: {len(rules)} rules, {node_count} nodes -> {comp_dir / 'styles.css'}")

    print(f"\nGenerated styles.css for {processed} components in {out_base}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract visual props -> styles.css")
    parser.add_argument("--project", required=True)
    parser.add_argument("--component", help="Process only this component")
    args = parser.parse_args()

    PROJECT_DIR = SKILL_ROOT / "data" / args.project
    MODULES_DIR = PROJECT_DIR / "modules"
    ANALYSIS_DIR = PROJECT_DIR / "analysis"
    OD_OUTPUT_DIR = SKILL_ROOT / "output" / f"{args.project}-od"
    run(args.component)

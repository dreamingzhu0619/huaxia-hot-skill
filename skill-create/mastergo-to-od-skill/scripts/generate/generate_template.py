#!/usr/bin/env python3
"""
generate_template.py -- 遍历节点树 + fixed/variable 标记 -> template.html。

Step 5c: 规则翻译每个节点为 DOM + {{slots}}。不手写 DOM，纯机械翻译。
  FRAME        -> <section> / <div>
  TEXT(variable) -> <span> {{slot}} (用节点 ID 作为临时 slot 名)
  TEXT(fixed)    -> <span> 固定文字
  GROUP(含variable) -> <div> 递归包裹
  GROUP(全fixed)   -> 跳过（已在 decorations.html）
  图表(variable-all) -> <div> {{chart}}

Output: output/<project>-od/assets/<component>/template.html

Usage:
  python scripts/generate/generate_template.py --project <name>
"""

import json
import sys
import argparse
import html
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = None
MODULES_DIR = None
ANALYSIS_DIR = None
OD_OUTPUT_DIR = None


def _safe_name(text):
    """Generate a readable slot name from node name or text content."""
    if not text:
        return "slot"
    # Take first 20 chars, replace whitespace
    clean = text.strip().replace("\n", " ").replace("  ", " ")[:30]
    return clean


def _num(v, ndigits=2):
    if v is None:
        return "0"
    f = round(float(v), ndigits)
    if f == int(f):
        return str(int(f))
    return f"{f:.{ndigits}f}".rstrip("0").rstrip(".")


def _layout_style(node, scale, include_size=True):
    layout = node.get("layoutStyle") or {}
    decls = [
        "position:absolute",
        f"left:{_num(float(layout.get('relativeX') or 0) / scale)}px",
        f"top:{_num(float(layout.get('relativeY') or 0) / scale)}px",
    ]
    if include_size:
        decls.extend([
            f"width:{_num(float(layout.get('width') or 0) / scale)}px",
            f"height:{_num(float(layout.get('height') or 0) / scale)}px",
        ])
    rotate = layout.get("rotate") or 0
    if rotate:
        decls.append(f"transform:rotate({_num(float(rotate))}deg)")
        decls.append("transform-origin:0 0")
    return "; ".join(decls)


def _text_value(node):
    text = node.get("text", "")
    if isinstance(text, list):
        return "".join(str(seg.get("text", "")) for seg in text if isinstance(seg, dict))
    return str(text or "")


def _collect_text_ids(node):
    ids = []
    if node.get("type") == "TEXT" and node.get("id"):
        ids.append(node["id"])
    for child in node.get("children") or []:
        ids.extend(_collect_text_ids(child))
    return ids


def generate_template(comp, classification, root_node, scale, indent=0):
    """Generate template.html DOM for a component."""
    prefix = "  " * indent
    nid = root_node.get("id", "")
    ntype = root_node.get("type", "")
    name = root_node.get("name", "")
    layout = root_node.get("layoutStyle") or {}

    all_fixed = classification.get("allFixed", False)
    variable_texts = set(classification.get("variableTexts") or [])
    fixed_texts = set(classification.get("fixedTexts") or [])
    fixed_groups = set(classification.get("fixedGroups") or [])
    charts = set(classification.get("charts") or [])

    def _is_fixed(nid):
        return nid in fixed_groups or nid in fixed_texts or (all_fixed and nid not in variable_texts)

    def _is_variable(nid):
        return nid in variable_texts or nid in charts

    # --- FRAME (root) ---
    if ntype == "FRAME":
        comp_name = comp["name"]
        children_html = ""
        for child in root_node.get("children") or []:
            children_html += generate_template(comp, classification, child, scale, indent)

        tag = "section" if indent == 0 else "div"
        if indent == 0:
            return f'<{tag} data-od-id="{comp_name}">\n{children_html}</{tag}>\n'
        else:
            class_name = f"n-{nid.replace(':', '-')}"
            return f'{prefix}<{tag} class="{class_name}" style="{_layout_style(root_node, scale)}">\n{children_html}{prefix}</{tag}>\n'

    # --- GROUP ---
    if ntype == "GROUP":
        if nid in fixed_groups or all_fixed:
            # Entirely fixed, skip (handled by decorations.html)
            # Unless it contains variable children (edge case)
            has_variable = False
            def _has_var(node):
                if node.get("id") in variable_texts:
                    return True
                for c in node.get("children") or []:
                    if _has_var(c): return True
                return False

            if not _has_var(root_node):
                return f'{prefix}<!-- {nid} GROUP (fixed) -- in decorations.html -->\n'
            # fall through: has variable children, render container

        children_html = ""
        for child in root_node.get("children") or []:
            children_html += generate_template(comp, classification, child, scale, indent + 1)

        if children_html.strip():
            class_name = f"n-{nid.replace(':', '-')}"
            return f'{prefix}<div class="{class_name}" style="{_layout_style(root_node, scale)}">\n{children_html}{prefix}</div>\n'
        return ""

    # --- TEXT (variable) ---
    if ntype == "TEXT" and nid in variable_texts:
        slot_id = nid.replace(":", "_")
        slot_name = f"text_{slot_id}"
        # Use node name or text content as hint
        hint = html.escape(_safe_name(_text_value(root_node) or name))
        class_name = f"n-{nid.replace(':', '-')}"
        return f'{prefix}<span class="{class_name}" style="{_layout_style(root_node, scale)}">{{{{{slot_name}}}}}<!-- {hint} --></span>\n'

    # --- TEXT (fixed) ---
    if ntype == "TEXT" and (nid in fixed_texts or _is_fixed(nid)):
        return f'{prefix}<!-- {nid} TEXT (fixed) -- in decorations.html -->\n'

    # --- TEXT (unmarked, default fixed) ---
    if ntype == "TEXT":
        text = html.escape(_text_value(root_node)).replace("\n", "<br>")
        class_name = f"n-{nid.replace(':', '-')}"
        return f'{prefix}<span class="{class_name}" style="{_layout_style(root_node, scale)}">{text}</span>\n'

    # --- LAYER fixed ---
    if ntype == "LAYER":
        if _is_fixed(nid):
            return f'{prefix}<!-- {nid} LAYER (fixed) -- in decorations.html -->\n'
        return ""

    # --- PATH/BITMAP fixed, skip (in decorations.html) ---
    if ntype in ("PATH", "BITMAP"):
        return ""

    # --- SVG_ELLIPSE ---
    if ntype == "SVG_ELLIPSE":
        return ""

    # --- unknown ---
    children_html = ""
    for child in root_node.get("children") or []:
        children_html += generate_template(comp, classification, child, scale, indent)
    if children_html.strip():
        class_name = f"n-{nid.replace(':', '-')}"
        return f'{prefix}<div class="{class_name}" style="{_layout_style(root_node, scale)}">\n{children_html}{prefix}</div>\n'

    return ""


def run():
    config_path = ANALYSIS_DIR / "component-config.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    out_base = OD_OUTPUT_DIR / "assets"
    out_base.mkdir(parents=True, exist_ok=True)

    processed = 0
    for comp in config["components"]:
        cname = comp["name"]
        comp_dir = out_base / cname
        comp_dir.mkdir(parents=True, exist_ok=True)

        module_files = comp.get("modules") or [comp.get("representativeModule")]
        if comp.get("instanceMode") != "array":
            module_files = [comp.get("representativeModule") or module_files[0]]

        wrote_default = False
        slot_total = 0
        for idx, module_file in enumerate(module_files):
            mod_path = MODULES_DIR / module_file
            if not mod_path.exists():
                print(f"  WARNING: {module_file} not found, skipping {cname}")
                continue

            with open(mod_path, "r", encoding="utf-8") as f:
                mod_data = json.load(f)

            root_node = mod_data.get("node")
            if not root_node:
                continue

            classification = comp.get("classification", {})
            if comp.get("instanceMode") == "array" and module_file != (comp.get("representativeModule") or module_files[0]):
                classification = {
                    "variableTexts": _collect_text_ids(root_node),
                    "fixedTexts": [],
                    "fixedGroups": [],
                    "charts": [],
                }
            scale = config["designScale"]["scale"]
            template_html = generate_template(comp, classification, root_node, scale)

            content = f"<!-- {cname} -- template.html -->\n"
            content += f"<!-- From: {module_file} -->\n\n"
            content += template_html

            variant_path = comp_dir / f"template.{idx}.html"
            with open(variant_path, "w", encoding="utf-8") as f:
                f.write(content)
            if not wrote_default:
                with open(comp_dir / "template.html", "w", encoding="utf-8") as f:
                    f.write(content)
                wrote_default = True

            import re
            slots = re.findall(r'\{\{(\w+)\}\}', template_html)
            slot_total += len(slots)
            print(f"  {cname}[{idx}]: {len(slots)} slots -> {variant_path}")
        processed += 1
        print(f"  {cname}: {slot_total} slots total")

    print(f"\nGenerated template.html for {processed} components in {out_base}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate template.html from node tree")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()

    PROJECT_DIR = SKILL_ROOT / "data" / args.project
    MODULES_DIR = PROJECT_DIR / "modules"
    ANALYSIS_DIR = PROJECT_DIR / "analysis"
    OD_OUTPUT_DIR = SKILL_ROOT / "output" / f"{args.project}-od"
    run()

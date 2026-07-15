#!/usr/bin/env python3
"""
extract_decorations.py -- 提取装饰元素 -> decorations.html。

Step 5b: 两层提取逻辑：
  第一层（机械）：PATH->SVG, BITMAP->img, 装饰LAYER->div, outlinedText->span, Gradient Overlay
  第二层（AI判定后纳入）：读 component-config.json 中 fixedGroups，递归渲染完整子树

Output: output/<project>-od/assets/<component>/decorations.html

Usage:
  python scripts/generate/extract_decorations.py --project <name>
  python scripts/generate/extract_decorations.py --project <name> --component <name>
"""

import json
import sys
import argparse
from pathlib import Path
import html

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


def scale_px(val, scale):
    if val is None: return "0px"
    try: return f"{round(float(val) / scale, 2)}px"
    except (ValueError, TypeError): return str(val)


def _text_value(node):
    text = node.get("text", "")
    if isinstance(text, list):
        return "".join(str(seg.get("text", "")) for seg in text if isinstance(seg, dict))
    return str(text or "")


def render_node_as_html(node, scale, indent=0):
    """Render a single decoration node to HTML string."""
    nid = node.get("id", "")
    ntype = node.get("type", "")
    name = node.get("name", "")
    layout = node.get("layoutStyle") or {}
    prefix = "  " * indent
    html = ""

    x = scale_px(layout.get("relativeX", 0), scale)
    y = scale_px(layout.get("relativeY", 0), scale)
    w = scale_px(layout.get("width", 0), scale)
    h = scale_px(layout.get("height", 0), scale)
    rotate = layout.get("rotate") or 0
    transform = ""
    if rotate:
        transform = f"; transform:rotate({round(float(rotate), 2)}deg); transform-origin:0 0"

    if ntype == "PATH":
        path_data = node.get("path") or []
        if path_data:
            class_name = f"n-{nid.replace(':', '-')}"
            html += f'{prefix}<!-- {nid} PATH | {name} -->\n'
            html += f'{prefix}<div class="{class_name}" style="position:absolute; left:{x}; top:{y}; width:{w}; height:{h}{transform}">\n'
            html += f'{prefix}  {_path_to_svg(node, path_data)}\n'
            html += f'{prefix}</div>\n'

    elif ntype == "BITMAP":
        export_img = node.get("exportImage") or {}
        url = export_img.get("url", "")
        if url:
            class_name = f"n-{nid.replace(':', '-')}"
            html += f'{prefix}<!-- {nid} BITMAP | {name} -->\n'
            html += f'{prefix}<img class="{class_name}" src="{url}" style="position:absolute; left:{x}; top:{y}; width:{w}; height:{h}{transform}">\n'

    elif ntype == "LAYER":
        fill = node.get("fill")
        if fill:
            class_name = f"n-{nid.replace(':', '-')}"
            html += f'{prefix}<!-- {nid} LAYER decoration | {name} -->\n'
            html += f'{prefix}<div class="{class_name}" style="position:absolute; left:{x}; top:{y}; width:{w}; height:{h}{transform}"></div>\n'

    elif ntype == "GROUP":
        children_html = ""
        for child in node.get("children") or []:
            children_html += render_node_as_html(child, scale, indent + 1)
        if children_html:
            class_name = f"n-{nid.replace(':', '-')}"
            html += f'{prefix}<!-- {nid} GROUP decoration | {name} -->\n'
            html += f'{prefix}<div class="{class_name}" style="position:absolute; left:{x}; top:{y}; width:{w}; height:{h}{transform}">\n'
            html += children_html
            html += f'{prefix}</div>\n'

    return html


def _path_to_svg(node, path_data):
    """Convert PATH node data to inline SVG."""
    fill = node.get("fill") or "none"
    if isinstance(fill, list):
        fill = "none"
    layout = node.get("layoutStyle") or {}
    w = layout.get("width", 100)
    h = layout.get("height", 100)

    paths = []
    for p in path_data:
        if isinstance(p, dict):
            d = p.get("data") or p.get("path") or ""
            pf = p.get("fill") or fill
        elif isinstance(p, str):
            d = p
            pf = fill
        else:
            continue
        if d:
            paths.append(f'<path d="{d}" fill="{pf}"/>')

    if not paths:
        return ""

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="100%" height="100%" shape-rendering="crispEdges">\n'
        f'  {"  ".join(paths)}\n'
        f'</svg>'
    )
    uid = (node.get("id") or "path").replace(":", "_")
    svg = css_core.inline_svg_fix_gradients(svg, uid_prefix=uid)
    svg = css_core.fix_svg_frame_fill(svg)
    svg = css_core.fix_svg_thin_lines(svg)
    return svg


def _is_clip_placeholder(node, parent_stack):
    """MasterGo often exports gray fallback layers inside Clip groups.

    Those layers are masks/fallbacks for a clipped image or SVG, not visible design
    content. Rendering them creates gray/black rectangles over the real artwork.
    """
    fill = node.get("fill")
    if fill != "#D8D8D8":
        return False
    return any((p.get("name") or "").lower() == "clip" for p in parent_stack)


def _collect_text_ids(node):
    ids = []
    if node.get("type") == "TEXT" and node.get("id"):
        ids.append(node["id"])
    for child in node.get("children") or []:
        ids.extend(_collect_text_ids(child))
    return ids


def extract_for_module(comp, module_file, scale):
    """Extract decorations for a single merged component."""
    mod_path = MODULES_DIR / module_file
    if not mod_path.exists():
        print(f"  WARNING: {module_file} not found")
        return None

    with open(mod_path, "r", encoding="utf-8") as f:
        mod_data = json.load(f)

    root_node = mod_data.get("node")
    if not root_node:
        return None

    classification = comp.get("classification", {})
    representative = comp.get("representativeModule") or (comp.get("modules") or [module_file])[0]
    if comp.get("instanceMode") == "array" and module_file != representative:
        classification = {
            "variableTexts": _collect_text_ids(root_node),
            "fixedTexts": [],
            "fixedGroups": [],
            "charts": [],
        }
    all_fixed = classification.get("allFixed", False)
    fixed_groups = set(classification.get("fixedGroups") or [])
    variable_texts = set(classification.get("variableTexts") or [])
    fixed_texts = set(classification.get("fixedTexts") or [])

    svg_count = [0]
    img_count = [0]

    def walk(node, in_fixed_group=False, parent_stack=None):
        parent_stack = parent_stack or []
        nid = node.get("id", "")
        ntype = node.get("type", "")

        is_fixed = in_fixed_group or all_fixed or nid in fixed_groups
        is_variable = nid in variable_texts

        # Skip variable TEXTs (go to template.html)
        if is_variable:
            return ""

        # Decoration types: PATH, BITMAP
        if ntype in ("PATH", "BITMAP"):
            if ntype == "PATH" and _is_clip_placeholder(node, parent_stack):
                return ""
            h = render_node_as_html(node, scale, 1)
            if ntype == "PATH": svg_count[0] += 1
            elif ntype == "BITMAP": img_count[0] += 1
            return h

        # LAYER decoration (non-TEXT, always fixed)
        if ntype == "LAYER":
            if _is_clip_placeholder(node, parent_stack):
                return ""
            return render_node_as_html(node, scale, 1)

        # Fixed TEXT: render it within the decoration
        if ntype == "TEXT" and (is_fixed or nid in fixed_texts):
            text = _text_value(node)
            layout = node.get("layoutStyle") or {}
            x = scale_px(layout.get("relativeX", 0), scale)
            y = scale_px(layout.get("relativeY", 0), scale)
            w = scale_px(layout.get("width", 0), scale)
            h = scale_px(layout.get("height", 0), scale)
            rotate = layout.get("rotate") or 0
            transform = ""
            if rotate:
                transform = f"; transform:rotate({round(float(rotate), 2)}deg); transform-origin:0 0"
            class_name = f"n-{nid.replace(':', '-')}"
            text = html.escape(str(text)).replace("\n", "<br>")
            return (
                f'  <!-- {nid} TEXT (fixed) | {node.get("name", "")} -->\n'
                f'  <span class="{class_name}" style="position:absolute; left:{x}; top:{y}; width:{w}; height:{h}{transform}">{text}</span>\n'
            )

        # GROUP: if it's a fixed group, render whole subtree
        if ntype == "GROUP":
            if is_fixed:
                children_html = ""
                for child in node.get("children") or []:
                    children_html += walk(child, True, parent_stack + [node])
                if children_html:
                    layout = node.get("layoutStyle") or {}
                    x = scale_px(layout.get("relativeX", 0), scale)
                    y = scale_px(layout.get("relativeY", 0), scale)
                    w = scale_px(layout.get("width", 0), scale)
                    h = scale_px(layout.get("height", 0), scale)
                    class_name = f"n-{nid.replace(':', '-')}"
                    return (
                        f'  <!-- {nid} GROUP (fixed) | {node.get("name", "")} -->\n'
                        f'  <div class="{class_name}" style="position:absolute; left:{x}; top:{y}; width:{w}; height:{h}">\n'
                        f'{children_html}'
                        f'  </div>\n'
                    )
                return ""
            else:
                # Not a fixed group: recurse for decoration children
                children_html = ""
                for child in node.get("children") or []:
                    children_html += walk(child, False, parent_stack + [node])
                if children_html:
                    layout = node.get("layoutStyle") or {}
                    x = scale_px(layout.get("relativeX", 0), scale)
                    y = scale_px(layout.get("relativeY", 0), scale)
                    w = scale_px(layout.get("width", 0), scale)
                    h = scale_px(layout.get("height", 0), scale)
                    class_name = f"n-{nid.replace(':', '-')}"
                    return (
                        f'  <!-- {nid} GROUP | {node.get("name", "")} -->\n'
                        f'  <div class="{class_name}" style="position:absolute; left:{x}; top:{y}; width:{w}; height:{h}">\n'
                        f'{children_html}'
                        f'  </div>\n'
                    )
                return ""

        # FRAME: descend into children
        if ntype == "FRAME":
            children_html = ""
            for child in node.get("children") or []:
                children_html += walk(child, all_fixed and nid not in fixed_groups, parent_stack + [node])
            return children_html

        return ""

    body_html = walk(root_node)

    return {
        "html": body_html,
        "svgCount": svg_count[0],
        "imgCount": img_count[0],
        "moduleFile": module_file,
    }


def extract_for_component(comp, scale):
    module_file = comp.get("representativeModule") or comp["modules"][0]
    return extract_for_module(comp, module_file, scale)


def run(component_name=None):
    config_path = ANALYSIS_DIR / "component-config.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found. Run Step 4 first.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    scale = config["designScale"]["scale"]
    out_base = OD_OUTPUT_DIR / "assets"
    out_base.mkdir(parents=True, exist_ok=True)

    processed = 0
    for comp in config["components"]:
        cname = comp["name"]
        if component_name and cname != component_name:
            continue

        comp_dir = out_base / cname
        comp_dir.mkdir(parents=True, exist_ok=True)

        module_files = comp.get("modules") or [comp.get("representativeModule")]
        if comp.get("instanceMode") != "array":
            module_files = [comp.get("representativeModule") or module_files[0]]

        wrote_default = False
        for idx, module_file in enumerate(module_files):
            result = extract_for_module(comp, module_file, scale)
            if result is None:
                continue

            header = f"<!-- {'='*60} -->\n"
            header += f"<!-- {cname} -- decorations.html -->\n"
            header += f"<!-- From: {result['moduleFile']} -->\n"
            header += f"<!-- Scale: @{scale}x -->\n"
            header += f"<!-- SVGs: {result['svgCount']}, images: {result['imgCount']} -->\n"
            header += f"<!-- {'='*60} -->\n\n"
            content = header + (result["html"] or "<!-- No decorations -->\n")

            variant_path = comp_dir / f"decorations.{idx}.html"
            with open(variant_path, "w", encoding="utf-8") as f:
                f.write(content)
            if not wrote_default:
                with open(comp_dir / "decorations.html", "w", encoding="utf-8") as f:
                    f.write(content)
                wrote_default = True
            print(f"  {cname}[{idx}]: {result['svgCount']} SVGs, {result['imgCount']} images -> {variant_path}")
        processed += 1

    print(f"\nGenerated decorations.html for {processed} components in {out_base}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract decorations -> decorations.html")
    parser.add_argument("--project", required=True)
    parser.add_argument("--component", help="Process only this component")
    args = parser.parse_args()

    PROJECT_DIR = SKILL_ROOT / "data" / args.project
    MODULES_DIR = PROJECT_DIR / "modules"
    ANALYSIS_DIR = PROJECT_DIR / "analysis"
    OD_OUTPUT_DIR = SKILL_ROOT / "output" / f"{args.project}-od"
    run(args.component)

#!/usr/bin/env python3
"""
build_html.py -- 组装引擎：page.html 骨架 + 各组件 template × N + decorations 嵌入。

Step 6 of the pipeline:
  1. Read component-config.json for component list and order.
  2. Read page.html as the outer skeleton.
  3. For each component: read template.html, decorations.html.
  4. Replicate multi-instance components by array length from content.template.json.
  5. Fill {{slots}} with data, embed decorations.
  6. Insert all component HTML into page.html container.
  7. Output example.html (filled) + template.html (seed, unfilled).

Output:
  output/<project>-od/example.html
  output/<project>-od/template.html

Usage:
  python scripts/assemble/build_html.py --project <name>
  python scripts/assemble/build_html.py --project <name> --template-only
"""

import json
import re
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

SLOT_RE = re.compile(r"\{\{(\w+)\}\}")


def _num(v, ndigits=2):
    if v is None: return "0"
    f = round(float(v), ndigits)
    if f == int(f): return str(int(f))
    return f"{f:.{ndigits}f}".rstrip("0").rstrip(".")


def load_file(path):
    if path and Path(path).exists():
        return Path(path).read_text(encoding="utf-8")
    return ""


def load_module_layouts(scale):
    index_path = MODULES_DIR / "_index.json"
    if not index_path.exists():
        return {}, 0

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    layouts = {}
    for mod in index.get("modules", []):
        file_name = mod.get("fileName")
        pos = mod.get("position") or {}
        if not file_name:
            continue
        layouts[file_name] = {
            "left": float(pos.get("x") or 0) / scale,
            "top": float(pos.get("y") or 0) / scale,
            "width": float(pos.get("width") or 0) / scale,
            "height": float(pos.get("height") or 0) / scale,
        }

    page = (index.get("meta") or {}).get("page") or {}
    page_height = float(page.get("height") or 0) / scale if page.get("height") else 0
    return layouts, page_height


def _node_text(node):
    text = node.get("text", "")
    if isinstance(text, list):
        return "".join(str(seg.get("text", "")) for seg in text if isinstance(seg, dict))
    return str(text or "")


def module_text_slots(module_file):
    if not module_file:
        return {}
    mod_path = MODULES_DIR / module_file
    if not mod_path.exists():
        return {}
    with open(mod_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    slots = {}
    def walk(node):
        if node.get("type") == "TEXT" and node.get("id"):
            slot = "text_" + node["id"].replace(":", "_")
            slots[slot] = _node_text(node)
        for child in node.get("children") or []:
            walk(child)
    root = data.get("node")
    if root:
        walk(root)
    return slots


def section_style(layout, z_index):
    if not layout:
        return ""
    return (
        "position:absolute; "
        f"left:{_num(layout['left'])}px; "
        f"top:{_num(layout['top'])}px; "
        f"width:{_num(layout['width'])}px; "
        f"height:{_num(layout['height'])}px; "
        f"z-index:{z_index}; "
        "overflow:visible;"
    )


def apply_section_style(instance_html, layout, z_index):
    style = section_style(layout, z_index)
    if not style:
        return instance_html

    def repl(match):
        tag = match.group(0)
        if "style=" in tag:
            return re.sub(r'style="([^"]*)"', lambda m: f'style="{m.group(1).rstrip(";")}; {style}"', tag, count=1)
        return tag[:-1] + f' style="{style}">'

    return re.sub(r'<section\s+data-od-id="[^"]*"[^>]*>', repl, instance_html, count=1)


def fill_slots(template_html, instance_data):
    """Fill {{slotName}} with data values."""
    def replacer(m):
        slot = m.group(1)
        val = instance_data.get(slot)
        if val is not None:
            return html.escape(str(val)).replace("\n", "<br>")
        return m.group(0)
    return SLOT_RE.sub(replacer, template_html)


def build_page_html(components, config, assets_dir, fill_data=False):
    """Build complete HTML page.

    If fill_data=True, fill slots with content.template.json data.
    Otherwise keep {{slots}} as-is (seed template).
    """
    page_cfg = config.get("pageConfig", {})
    logical_w = config["designScale"]["logicalWidth"]
    page_title = page_cfg.get("title", "Design Example")
    component_order = page_cfg.get("componentOrder", [])
    module_layouts, indexed_page_height = load_module_layouts(config["designScale"]["scale"])

    # Read page.html skeleton
    page_file = assets_dir / "shared" / "page.html"
    page_skeleton = load_file(page_file)

    # Build component HTML blocks
    comp_html_blocks = []

    for comp_name in component_order:
        comp = next((c for c in components if c["name"] == comp_name), None)
        if comp is None:
            comp_html_blocks.append(f"    <!-- {comp_name}: UNKNOWN COMPONENT -->")
            continue

        instance_mode = comp.get("instanceMode", "fixed")
        module_files = comp.get("modules") or []
        comp_layouts = [module_layouts[m] for m in module_files if m in module_layouts]

        # Determine instances from content.template.json
        instances_data = [{}]
        if fill_data:
            content_file = OD_OUTPUT_DIR / "content.template.json"
            if content_file.exists():
                with open(content_file, "r", encoding="utf-8") as f:
                    content_data = json.load(f)
                # Try to find data for this component
                comp_data = content_data.get(comp_name)
                if comp_data is None:
                    # Try display name
                    comp_data = content_data.get(comp.get("displayName", ""))
                if isinstance(comp_data, list):
                    instances_data = comp_data
                elif isinstance(comp_data, dict) and not comp_data.get("_"):
                    instances_data = [comp_data]
                else:
                    instances_data = [{}]
            if not instances_data:
                instances_data = [{}]

        if instance_mode == "array":
            if comp_layouts and (not fill_data or instances_data == [{}]):
                instances_data = [{} for _ in comp_layouts]
            elif comp_layouts and len(instances_data) < len(comp_layouts):
                instances_data = instances_data + [{} for _ in range(len(comp_layouts) - len(instances_data))]
        else:
            instances_data = instances_data[:1]  # fixed = single instance

        for i, inst_data in enumerate(instances_data):
            template_file = assets_dir / comp_name / f"template.{i}.html"
            decorations_file = assets_dir / comp_name / f"decorations.{i}.html"
            if not template_file.exists():
                template_file = assets_dir / comp_name / "template.html"
            if not decorations_file.exists():
                decorations_file = assets_dir / comp_name / "decorations.html"

            template_content = load_file(template_file)
            decorations_content = load_file(decorations_file)

            if not template_content:
                comp_html_blocks.append(f"    <!-- {comp_name}: MISSING template.html -->")
                continue

            instance_html = template_content
            layout = comp_layouts[min(i, len(comp_layouts) - 1)] if comp_layouts else None
            z_index = 0 if comp_name == "background" else 10 + len(comp_html_blocks)

            if fill_data:
                module_file = module_files[min(i, len(module_files) - 1)] if module_files else None
                merged_data = module_text_slots(module_file)
                merged_data.update(inst_data)
                instance_html = fill_slots(instance_html, inst_data)
                instance_html = fill_slots(instance_html, merged_data)

            # Embed decorations into the data-od-id section
            if decorations_content.strip():
                # Insert decorations right after the opening <section> tag
                section_pattern = re.compile(r'(<section\s+data-od-id="[^"]*">)')
                if section_pattern.search(instance_html):
                    instance_html = section_pattern.sub(
                        r'\1\n' + decorations_content, instance_html, count=1
                    )
                else:
                    # No section tag, append decorations at the top
                    instance_html = decorations_content + "\n" + instance_html

            instance_html = apply_section_style(instance_html, layout, z_index)
            comp_html_blocks.append(f"    {instance_html}")

    # Generate the final HTML
    # Build <link> list
    links = []
    links.append('  <link rel="stylesheet" href="assets/shared/page.css">')
    for comp_name in component_order:
        css_file = assets_dir / comp_name / "styles.css"
        if css_file.exists():
            links.append(f'  <link rel="stylesheet" href="assets/{comp_name}/styles.css">')

    # Build the full HTML
    page_height = indexed_page_height or page_cfg.get("containerHeight") or "100vh"
    page_height_css = f"{_num(page_height)}px" if isinstance(page_height, (int, float)) and page_height else "100vh"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
{chr(10).join(links)}
  <style>
    .page-container {{
      width: {logical_w}px;
      margin: 0 auto;
      position: relative;
      height: {page_height_css};
      min-height: {page_height_css};
      overflow: hidden;
    }}
  </style>
</head>
<body>
  <div class="page-container">
{chr(10).join(comp_html_blocks)}
  </div>
</body>
</html>
"""
    return html


def run(template_only=False):
    config_path = ANALYSIS_DIR / "component-config.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found. Run Step 4 first.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    components = config["components"]
    component_order = config.get("pageConfig", {}).get("componentOrder", [])

    print(f"Component order ({len(component_order)} components):")
    for cname in component_order:
        comp = next((c for c in components if c["name"] == cname), None)
        mode = comp.get("instanceMode", "fixed") if comp else "unknown"
        print(f"  {cname} (mode={mode})")

    out_dir = OD_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = out_dir / "assets"

    # Generate seed template.html (slots unfilled)
    seed_html = build_page_html(components, config, assets_dir, fill_data=False)
    seed_path = out_dir / "template.html"
    seed_path.write_text(seed_html, encoding="utf-8")
    print(f"  template.html -> {seed_path}")

    if not template_only:
        # Generate example.html (slots filled)
        example_html = build_page_html(components, config, assets_dir, fill_data=True)
        example_path = out_dir / "example.html"
        example_path.write_text(example_html, encoding="utf-8")
        print(f"  example.html -> {example_path}")

    print(f"\nAssembly complete in {out_dir}/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble complete HTML from component templates")
    parser.add_argument("--project", required=True)
    parser.add_argument("--template-only", action="store_true")
    args = parser.parse_args()

    PROJECT_DIR = SKILL_ROOT / "data" / args.project
    MODULES_DIR = PROJECT_DIR / "modules"
    ANALYSIS_DIR = PROJECT_DIR / "analysis"
    OD_OUTPUT_DIR = SKILL_ROOT / "output" / f"{args.project}-od"
    run(args.template_only)

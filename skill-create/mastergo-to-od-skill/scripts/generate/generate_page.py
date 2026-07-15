#!/usr/bin/env python3
"""
generate_page.py -- 生成全局页面骨架 page.html + page.css。

Step 5d: 读 component-config.json 获取组件列表和页面配置，
  生成 page.html（<html> + <head> + <link> + <body> + 容器）和 page.css。

Output: output/<project>-od/assets/shared/page.html + page.css

Usage:
  python scripts/generate/generate_page.py --project <name>
"""

import json
import sys
import argparse
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = None
ANALYSIS_DIR = None
OD_OUTPUT_DIR = None


def run():
    config_path = ANALYSIS_DIR / "component-config.json"
    if not config_path.exists():
        print(f"ERROR: {config_path} not found. Run Step 4 first.")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    page_cfg = config.get("pageConfig", {})
    components = config["components"]
    logical_w = config["designScale"]["logicalWidth"]

    out_dir = OD_OUTPUT_DIR / "assets" / "shared"
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- page.css ---
    page_css = f"""/* page.css -- 页面容器 + 全局样式 */
/* Generated from component-config.json */

* {{
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}}

body {{
  font-family: 'MiSans', 'PingFang SC', 'SourceHanSansCN', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}

.page-container {{
  width: {logical_w}px;
  margin: 0 auto;
  position: relative;
  min-height: 100vh;
}}
"""

    with open(out_dir / "page.css", "w", encoding="utf-8") as f:
        f.write(page_css)

    # --- page.html ---
    title = page_cfg.get("title", "Design Example")
    component_order = page_cfg.get("componentOrder", [])

    links = []
    links.append('  <link rel="stylesheet" href="assets/shared/page.css">')
    for comp_name in component_order:
        links.append(f'  <link rel="stylesheet" href="assets/{comp_name}/styles.css">')

    # Component include placeholders
    component_includes = []
    for comp_name in component_order:
        comp = next((c for c in components if c["name"] == comp_name), None)
        if comp and comp.get("instanceMode") == "array":
            component_includes.append(f'  <!-- {comp_name} -- array-driven, insert N instances here -->')
        else:
            component_includes.append(f'  <!-- {comp_name} -- single instance -->')

    page_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="{page_cfg.get('viewport', 'width=device-width, initial-scale=1.0')}">
  <title>{title}</title>
{chr(10).join(links)}
</head>
<body>
  <div class="page-container">
{chr(10).join(component_includes)}
  </div>
</body>
</html>
"""

    with open(out_dir / "page.html", "w", encoding="utf-8") as f:
        f.write(page_html)

    print(f"  page.css -> {out_dir / 'page.css'}")
    print(f"  page.html -> {out_dir / 'page.html'}")
    print(f"  Components in order: {component_order}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate page.html skeleton")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()

    PROJECT_DIR = SKILL_ROOT / "data" / args.project
    ANALYSIS_DIR = PROJECT_DIR / "analysis"
    OD_OUTPUT_DIR = SKILL_ROOT / "output" / f"{args.project}-od"
    run()

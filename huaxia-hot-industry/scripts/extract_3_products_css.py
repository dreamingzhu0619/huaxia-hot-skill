#!/usr/bin/env python3
"""Extract CSS assets for the 3-products frame from merged MasterGo JSON."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = PROJECT_ROOT / "data-output" / "frames-merged" / "3-products.json"
CSS_PATH = PROJECT_ROOT / "data-output" / "frames" / "3-products" / "assets" / "product-section.css"


def load_source() -> dict:
    with SOURCE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def walk(node: dict):
    yield node
    for child in node.get("children") or []:
        yield from walk(child)


def collect_nodes(data: dict) -> list[dict]:
    nodes: list[dict] = []
    for module in data.get("modules", []):
        node = module.get("node")
        if node:
            nodes.extend(walk(node))
    return nodes


def text_style(nodes: list[dict], text: str, fallback: dict) -> dict:
    for node in nodes:
        if node.get("type") == "TEXT" and node.get("text") == text:
            run = (node.get("textRuns") or [{}])[0]
            font = run.get("font") or {}
            return {
                "family": font.get("family") or fallback["family"],
                "size": font.get("size") or fallback["size"],
                "line_height": font.get("lineHeight") if font.get("lineHeight") != "-1" else fallback["line_height"],
                "color": run.get("color") or fallback["color"],
                "align": node.get("textAlign") or fallback.get("align", "left"),
            }
    return fallback


def first_fill(nodes: list[dict], width: int | float, height: int | float, fallback: str) -> str:
    for node in nodes:
        bounds = node.get("bounds") or {}
        if bounds.get("width") == width and bounds.get("height") == height and node.get("fill"):
            fill = node["fill"]
            if isinstance(fill, list):
                return fill[0]
            return fill
    return fallback


def px(value: object) -> str:
    if value is None:
        return "normal"
    if isinstance(value, (int, float)):
        return f"{value}px"
    if isinstance(value, str) and value.replace(".", "", 1).isdigit():
        return f"{value}px"
    return str(value)


def build_css(data: dict) -> str:
    nodes = collect_nodes(data)
    title = text_style(nodes, "关联产品", {"family": "FZZDHJW--GB1", "size": 17, "line_height": 24, "color": "#FFFFFF"})
    intro = text_style(nodes, "半导体行业波动显著，机遇与风险并存。对于波动承受有限的投资者，不妨以小仓位先行参与，或通过定投分批买入。", {"family": "MiSans", "size": 11, "line_height": 13, "color": "#485F94"})
    active_title = text_style(nodes, "追求超额", {"family": "MiSans", "size": 13, "line_height": 17, "color": "#FFFFFF"})
    active_desc = text_style(nodes, "主动研判 调仓灵活", {"family": "MiSans", "size": 11, "line_height": 15, "color": "#FFFFFF"})
    passive_title = text_style(nodes, "紧密跟踪", {"family": "MiSans", "size": 13, "line_height": 17, "color": "#4670C8"})
    passive_desc = text_style(nodes, "被动复制 持仓透明", {"family": "MiSans", "size": 11, "line_height": 15, "color": "#859ED7"})
    product_name = text_style(nodes, "永赢先锋半导体智选C", {"family": "MiSans", "size": 15, "line_height": 20, "color": "#3A3E45"})
    code = text_style(nodes, "025209", {"family": "FZLTHJW--GB1", "size": 10, "line_height": 14, "color": "#91431C"})
    metric = text_style(nodes, "近1年涨跌幅", {"family": "FZLTHJW--GB1", "size": 11, "line_height": 15, "color": "#A1A9B3"})
    detail = text_style(nodes, "详情 >", {"family": "FZLTHJW--GB1", "size": 10, "line_height": 14, "color": "#8CABDA"})
    buy = text_style(nodes, "买入", {"family": "FZLTDHJW--GB1", "size": 14, "line_height": 20, "color": "linear-gradient(180deg, #FFFFFF 26%, #FFECD6 80%)"})

    section_bg = first_fill(nodes, 351, 440, "linear-gradient(180deg, #DCEBFF -3%, #FFFFFF 13%, rgba(255, 255, 255, 0.8) 100%)")
    title_bg = first_fill(nodes, 190, 34, "linear-gradient(104deg, #EAF3FF -1%, #A3C9FF 12%, #6EA0EE 30%, #327CF2 47%, #6A9AED 73%, rgba(193, 198, 255, 0) 111%)")

    return f'''*, *::before, *::after {{
  box-sizing: border-box;
}}

:root {{
  --ff-title: {title["family"]}, "FZZDHJW", "Microsoft YaHei", sans-serif;
  --ff-body: {intro["family"]}, "Microsoft YaHei", sans-serif;
  --ff-tag: {code["family"]}, "Microsoft YaHei", sans-serif;
  --ff-cta: {buy["family"]}, "Microsoft YaHei", sans-serif;
  --c-card-text: {product_name["color"]};
  --c-body-blue: {intro["color"]};
  --c-muted: {metric["color"]};
  --c-link: {detail["color"]};
  --c-tag-text: {code["color"]};
  --c-track-blue: {passive_title["color"]};
  --c-track-sub: {passive_desc["color"]};
  --g-section-card: {section_bg};
  --g-title-pill: {title_bg};
  --g-note: linear-gradient(180deg, #FFFFFF 0%, #FBFDFF 46%, #F3F8FF 100%);
  --g-code-tag: linear-gradient(180deg, #FFEABE 0%, #FFF9ED 100%);
  --g-buy: linear-gradient(180deg, #FCE4C1 0%, #E6AB63 22%, #D89A4B 41%, #E2AF68 76%, #FFEDCB 100%);
  --g-buy-text: linear-gradient(180deg, #FFFFFF 0%, #FFECD6 100%);
}}

body {{
  margin: 0;
  background: #FFFFFF;
}}

.products-page {{
  width: 375px;
  min-height: 440px;
  margin: 0 auto;
  padding: 0 0 16px;
  background: #DFEBFE;
  overflow: hidden;
  position: relative;
  font-family: var(--ff-body);
}}

.products-section {{
  width: 351px;
  min-height: 440px;
  margin: 0 auto;
  padding: 0 10px 12px;
  position: relative;
  border-radius: 16px;
  background: var(--g-section-card);
  border: 1.5px solid rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(8px);
}}

.product-stack::before {{
  content: "";
  position: absolute;
  left: -12px;
  right: -12px;
  top: 73px;
  height: 250px;
  z-index: -1;
  background: #DFEFFC;
  pointer-events: none;
}}

.frame-title {{
  width: 190px;
  height: 34px;
  margin: 0 auto 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 2;
  color: {title["color"]};
  font-family: var(--ff-title);
  font-size: {px(title["size"])};
  line-height: {px(title["line_height"])};
  text-align: center;
  text-shadow: 0 1px 4px rgba(51, 71, 156, 0.5);
  background: var(--g-title-pill);
  clip-path: polygon(0 0, 100% 0, 84% 100%, 16% 100%);
  filter: drop-shadow(-2px 2px 4px rgba(255, 255, 255, 0.65));
}}

.intro-block {{
  width: 331px;
  min-height: 38px;
  margin: 0 auto 10px;
  padding: 6px 8px 6px 39px;
  position: relative;
  z-index: 2;
  border-radius: 8px;
  background: var(--g-note);
  border: 1px solid rgba(217, 233, 255, 0.72);
  color: var(--c-body-blue);
  font-family: var(--ff-body);
  font-size: {px(intro["size"])};
  font-weight: 500;
  line-height: {px(intro["line_height"])};
}}

.intro-block::before {{
  content: "";
  position: absolute;
  left: 8px;
  top: 8px;
  width: 22px;
  height: 23px;
  border-radius: 50% 45% 50% 45%;
  background: linear-gradient(145deg, #FFFFFF 0%, #FFD45E 45%, #F18720 100%);
  box-shadow: 0 7px 0 -6px #86B1E9;
  transform: rotate(-4deg);
}}

.product-stack {{
  width: 323px;
  margin: 0 auto;
  position: relative;
  z-index: 2;
}}

.strategy-tabs {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  width: 323px;
  margin: 0 auto 16px;
  position: relative;
  z-index: 2;
}}

.strategy-tab {{
  height: 44px;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #D1DFFC;
  background: linear-gradient(180deg, rgba(60, 131, 242, 0.2) 0%, rgba(245, 251, 255, 0.2) 100%);
}}

.strategy-tab.is-active {{
  border-color: #F4B053;
  background: var(--g-buy);
}}

.strategy-tab__title {{
  display: block;
  color: var(--c-track-blue);
  font-size: {px(passive_title["size"])};
  font-weight: 700;
  line-height: {px(passive_title["line_height"])};
  text-align: right;
}}

.strategy-tab__desc {{
  display: block;
  margin-top: 1px;
  color: var(--c-track-sub);
  font-size: {px(passive_desc["size"])};
  font-weight: 500;
  line-height: {px(passive_desc["line_height"])};
}}

.strategy-tab.is-active .strategy-tab__title,
.strategy-tab.is-active .strategy-tab__desc {{
  color: {active_title["color"]};
  text-shadow: 0 1px 4px rgba(177, 79, 19, 0.81);
}}

.product-list {{
  width: 319px;
  margin: 0 auto;
  position: relative;
  z-index: 2;
}}

.product-card {{
  min-height: 76px;
  padding: 0 4px 12px 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 88px;
  column-gap: 36px;
  border-bottom: 1px dashed #B9C9E0;
}}

.product-card + .product-card {{
  margin-top: 10px;
}}

.product-main {{
  min-width: 0;
  padding-top: 1px;
}}

.product-row {{
  display: flex;
  align-items: flex-start;
  min-width: 0;
  gap: 8px;
}}

.product-name {{
  min-height: 20px;
  color: var(--c-card-text);
  font-family: var(--ff-body);
  font-size: {px(product_name["size"])};
  font-weight: 600;
  line-height: {px(product_name["line_height"])};
  overflow-wrap: anywhere;
}}

.product-detail {{
  flex: none;
  margin-top: 6px;
  color: var(--c-link);
  font-family: var(--ff-tag);
  font-size: {px(detail["size"])};
  line-height: {px(detail["line_height"])};
  letter-spacing: -0.32px;
  text-decoration: none;
}}

.product-tags {{
  display: flex;
  gap: 5px;
  margin-top: 3px;
  flex-wrap: wrap;
}}

.product-tag {{
  min-width: 46px;
  height: 15px;
  padding: 1px 4px 0;
  border-radius: 2px;
  background: var(--g-code-tag);
  color: var(--c-tag-text);
  font-family: var(--ff-tag);
  font-size: {px(code["size"])};
  line-height: {px(code["line_height"])};
  letter-spacing: 0.13px;
  white-space: nowrap;
}}

.metric-label {{
  display: block;
  margin-top: 18px;
  color: var(--c-muted);
  font-family: var(--ff-tag);
  font-size: {px(metric["size"])};
  line-height: {px(metric["line_height"])};
  letter-spacing: 0.15px;
}}

.buy-button {{
  align-self: center;
  width: 88px;
  height: 37px;
  border: 0;
  border-radius: 8px;
  position: relative;
  overflow: hidden;
  cursor: pointer;
  background: var(--g-buy);
  box-shadow:
    0 8px 12px rgba(255, 77, 95, 0.22),
    inset 0 0 0 1px rgba(255, 255, 255, 0.78);
  color: #FFFFFF;
  font-family: var(--ff-cta);
  font-size: {px(buy["size"])};
  line-height: {px(buy["line_height"])};
  letter-spacing: 0.5px;
  text-shadow: 0 2px 4px rgba(219, 0, 16, 0.6);
}}

.buy-button::before {{
  content: "";
  position: absolute;
  left: 4px;
  right: 4px;
  top: 3px;
  height: 31px;
  border-radius: 7px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.75) 0%, rgba(255, 255, 255, 0) 70%);
  pointer-events: none;
}}

.buy-button__text {{
  position: relative;
  z-index: 1;
  background: var(--g-buy-text);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}}

.more-button {{
  width: 92px;
  height: 24px;
  margin: 12px auto 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  position: relative;
  z-index: 2;
  color: #5075B7;
  font-family: var(--ff-body);
  font-size: 13px;
  line-height: 17px;
  text-decoration: none;
}}
'''


def main() -> None:
    data = load_source()
    CSS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CSS_PATH.write_text(build_css(data), encoding="utf-8")
    print(f"Extracted CSS -> {CSS_PATH}")


if __name__ == "__main__":
    main()

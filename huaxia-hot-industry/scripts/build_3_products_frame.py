#!/usr/bin/env python3
"""Build the 3-products frame as static HTML from schema data.

This is an upstream build helper. The final frame output remains plain static
HTML + CSS under data-output/frames/3-products.
"""

from __future__ import annotations

import html
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRAME_DIR = PROJECT_ROOT / "data-output" / "frames" / "3-products"
SCHEMA_PATH = FRAME_DIR / "schema.json"
CSS_PATH = FRAME_DIR / "assets" / "product-section.css"
HTML_PATH = FRAME_DIR / "template.html"


def escape(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data.get("products"), list):
        raise ValueError("schema.json must contain a products array")
    return data


def render_strategy_tabs(tabs: list[dict]) -> str:
    parts = []
    for tab in tabs:
        active = " is-active" if tab.get("active") else ""
        parts.append(
            f'''            <div class="strategy-tab{active}">
              <span class="strategy-tab__title">{escape(tab.get("title"))}</span>
              <span class="strategy-tab__desc">{escape(tab.get("description"))}</span>
            </div>'''
        )
    return "\n".join(parts)


def render_product_card(product: dict) -> str:
    """Render one 编组43 product-card skeleton with variable text only."""
    return f'''            <article class="product-card">
              <div class="product-main">
                <div class="product-row">
                  <div class="product-name">{escape(product.get("name"))}</div>
                  <a class="product-detail" href="{escape(product.get("detailUrl", "#"))}">{escape(product.get("detailText", "详情 >"))}</a>
                </div>
                <div class="product-tags">
                  <span class="product-tag">{escape(product.get("code"))}</span>
                  <span class="product-tag">{escape(product.get("riskLevel"))}</span>
                </div>
                <span class="metric-label">{escape(product.get("metricLabel", "近1年涨跌幅"))}</span>
              </div>
              <button class="buy-button" type="button">
                <span class="buy-button__text">{escape(product.get("buyText", "买入"))}</span>
              </button>
            </article>'''


def render_static_html(data: dict) -> str:
    section_title = data.get("sectionTitle", "关联产品")
    tabs_html = render_strategy_tabs(data.get("strategyTabs", []))
    products_html = "\n".join(render_product_card(item) for item in data["products"])
    return f'''<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=375, initial-scale=1">
    <title>{escape(section_title)}</title>
    <link rel="stylesheet" href="./assets/product-section.css">
  </head>
  <body>
    <main class="products-page">
      <section class="products-section" aria-labelledby="products-title">
        <h2 id="products-title" class="frame-title">{escape(section_title)}</h2>
        <p class="intro-block">{escape(data.get("introText"))}</p>
        <div class="product-stack">
          <div class="strategy-tabs">
{tabs_html}
          </div>
          <div class="product-list">
{products_html}
          </div>
          <a class="more-button" href="{escape(data.get("moreUrl", "#"))}">{escape(data.get("moreText", "查看更多"))}</a>
        </div>
      </section>
    </main>
  </body>
</html>
'''


def main() -> None:
    data = load_schema()
    if not CSS_PATH.exists():
        raise FileNotFoundError(f"Missing extracted CSS asset: {CSS_PATH}")
    HTML_PATH.write_text(render_static_html(data), encoding="utf-8")
    print(f"Rendered {len(data['products'])} products -> {HTML_PATH}")
    print(f"Using CSS asset -> {CSS_PATH}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
generate_template_from_modules.py — 从 modules JSON 直接生成模板 HTML。

不依赖 d2c.html，而是递归遍历节点树，根据节点类型和属性渲染 HTML：
  - TEXT 节点 → 可变内容替换为 {{slot}}，固定内容保留原文
  - IMAGE fill 节点 → <img> 使用 MasterGo CDN URL
  - SVG 节点 → 内联 SVG
  - 容器节点 → 定位 div，递归 children
  - 重复产品卡片 → 只渲染第一个实例，包裹 {% for item in items %}

用法：python scripts/generate_template_from_modules.py [frame_id]
默认：3-products
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MERGED_DIR = PROJECT_ROOT / "data-output" / "frames-merged"
TEMPLATES_PATH = PROJECT_ROOT / "data-output" / "repeats" / "templates.json"
OUTPUT_DIR = PROJECT_ROOT / "data-output" / "frames"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 固定文案白名单（不替换为 slot）
FIXED_WHITELIST = {
    "关联产品", "查看更多", "近期热点", "行业直击",
    "捕捉热点事件", "拆解产业逻辑", "精选关联产品",
    "产业基石", "价值核心", "需求源泉", "风险提示",
    "追求超额", "紧密跟踪", "主动研判 调仓灵活",
    "被动复制 持仓透明", "详情", ">",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_slot_map(frame_templates):
    """构建 text → slot_name 映射（来自 repeat slots 的 exampleValues）。"""
    slot_map = {}
    for tmpl in frame_templates:
        for slot in tmpl.get("slots", []):
            for val in slot["exampleValues"]:
                if val not in slot_map:
                    slot_map[val] = slot["name"]
    return slot_map


def collect_all_texts(modules):
    """收集所有模块中的所有文本。"""
    texts = set()

    def walk(node):
        t = node.get("text")
        if t:
            texts.add(t)
        for c in node.get("children", []):
            walk(c)

    for mod in modules:
        if mod.get("node"):
            walk(mod["node"])
    return texts


def add_single_slots(slot_map, modules, frame_templates):
    """将不在白名单且不在 repeat slot 中的文本标记为 single slot。"""
    # 收集已存在的 slot 文本
    existing_texts = set(slot_map.keys())

    # 收集 repeat 中已经覆盖的文本
    repeat_texts = set()
    for tmpl in frame_templates:
        for slot in tmpl.get("slots", []):
            for val in slot["exampleValues"]:
                repeat_texts.add(val)

    # 找出新的可变文本
    all_texts = collect_all_texts(modules)
    new_texts = []
    for t in all_texts:
        if t in FIXED_WHITELIST:
            continue
        if t in existing_texts:
            continue
        new_texts.append(t)

    # 按长度降序（避免短文本误匹配）
    new_texts.sort(key=lambda x: -len(x))

    # 分配 slot 名：从 0 开始（与 repeat slots 用同名，Jinja2 作用域隔离）
    for i, t in enumerate(new_texts):
        slot_map[t] = f"slot_{i}"

    return new_texts


def extract_font_style(node):
    """从 textRuns 提取字体 CSS。"""
    runs = node.get("textRuns", [])
    if not runs:
        return ""
    run = runs[0]
    font = run.get("font", {})
    color = run.get("color", "")

    styles = []
    if font.get("family"):
        styles.append(f"font-family: {font['family']}")
    if font.get("size"):
        styles.append(f"font-size: {font['size']}px")
    lh = font.get("lineHeight")
    if lh and lh != "-1":
        styles.append(f"line-height: {lh}")
    if font.get("letterSpacing"):
        styles.append(f"letter-spacing: {font['letterSpacing']}")

    style_val = font.get("style", "0")
    weight_map = {"0": "400", "Bold": "700", "Medium": "500", "Demibold": "600",
                  "Light": "300", "Regular": "400", "Semibold": "600"}
    weight = weight_map.get(style_val, style_val)
    if style_val and style_val != "0":
        styles.append(f"font-weight: {weight}")

    # 文字颜色（可能是渐变色）
    if color:
        if "gradient" in color.lower():
            styles.append(f"background: {color}")
            styles.append("background-clip: text")
            styles.append("-webkit-background-clip: text")
            styles.append("text-fill-color: transparent")
            styles.append("-webkit-text-fill-color: transparent")
        else:
            styles.append(f"color: {color}")

    align = node.get("textAlign")
    if align:
        styles.append(f"text-align: {align}")

    text_shadow = _extract_text_shadow(node)
    if text_shadow:
        styles.append(text_shadow)

    return "; ".join(styles)


def _extract_text_shadow(node):
    """提取文字阴影。"""
    effect = node.get("effect")
    if not effect:
        return None
    for shadow in effect.get("boxShadow", []):
        if "box-shadow" in shadow:
            return shadow.replace("box-shadow: ", "text-shadow: ").rstrip(";")
    return None


def build_inline_style(node, assets, skip_text_fx=False):
    """从节点属性构建 inline style 字符串（CSS 属性去重）。

    skip_text_fx: 为 True 时跳过 fill/effect（TEXT 节点由 extract_font_style 处理文字样式）
    """
    css = node.get("d2cCss", {})
    style = {}  # property → value，避免重复

    # 文本相关属性跳过（在 extract_font_style 中处理）
    TEXT_KEYS = {
        "color", "font-family", "font-size", "line-height",
        "letter-spacing", "text-align", "text-fill-color",
        "text-shadow", "-webkit-text-fill-color", "-webkit-background-clip",
    }

    for k, v in css.items():
        if v is not None and k not in TEXT_KEYS:
            style[k] = v

    # 填充：只在 d2cCss 没有 background 时添加（TEXT 节点跳过，文字颜色由 textRuns 处理）
    if not skip_text_fx and "background" not in style and "background-image" not in style:
        fill = node.get("fill")
        if isinstance(fill, str) and fill:
            style["background"] = fill

    # 圆角
    br = node.get("borderRadius")
    if br and "border-radius" not in style:
        style["border-radius"] = br

    # 边框（渐变色用 border-image，纯色用 border）
    if "border" not in style:
        sc = node.get("strokeColor")
        sw = node.get("strokeWidth")
        if sc and sw:
            if isinstance(sc, str) and "gradient" in sc.lower():
                style["border-image"] = f"{sc} 1 1 1 1"
                style["border"] = f"{sw} solid"
            elif isinstance(sc, str):
                style["border"] = f"{sw} solid {sc}"

    # 透明度
    opacity = node.get("opacity")
    if opacity is not None and opacity != 1 and "opacity" not in style:
        style["opacity"] = str(opacity)

    # 效果：使用 effect.raw（已是完整的 CSS 声明），去重
    # TEXT 节点跳过（文字阴影由 extract_font_style 通过 text-shadow 处理）
    if not skip_text_fx:
        effect = node.get("effect")
        if effect:
            for raw in effect.get("raw", []):
                raw = raw.rstrip(";").strip()
                if ":" in raw:
                    prop, val = raw.split(":", 1)
                    prop = prop.strip()
                    if prop not in style:
                        style[prop] = val.strip()

    return "; ".join(f"{k}: {v}" for k, v in style.items())


def render_node(node, assets, slot_map, repeat_info):
    """递归渲染单个节点为 HTML 字符串。

    Args:
        node: 节点 dict
        assets: {"svgs": {...}, "bitmaps": [...]}
        slot_map: text → slot_name 映射
        repeat_info: 来自 templates.json 的重复组定义，或 None

    Returns:
        HTML 字符串
    """
    node_type = node.get("type")
    fill = node.get("fill")
    node_id = node.get("id", "")
    children = node.get("children", [])
    d2c_css = node.get("d2cCss", {})

    # 判断此节点是否有独立的定位样式
    has_positioning = any(
        d2c_css.get(k) is not None
        for k in ("position", "left", "right", "top", "bottom", "width", "height")
    )

    # 构建 inline style（TEXT 节点跳过 fill/effect，由 extract_font_style 处理文字样式）
    is_text = (node_type == "TEXT")
    inline_style = build_inline_style(node, assets, skip_text_fx=is_text)
    style_attr = f' style="{inline_style}"' if inline_style else ""

    # --- TEXT 节点 ---
    if node_type == "TEXT":
        text = node.get("text", "")
        font_style = extract_font_style(node)

        # 检查是否匹配 slot
        slot_name = slot_map.get(text)
        if slot_name and text not in FIXED_WHITELIST:
            display = "{{ " + slot_name + " }}"
        else:
            display = text

        all_styles = inline_style
        if font_style:
            all_styles += ("; " + font_style) if all_styles else font_style
        style_attr2 = f' style="{all_styles}"' if all_styles else ""
        return f"<span{style_attr2}>{display}</span>"

    # --- IMAGE 填充节点 ---
    if isinstance(fill, dict) and fill.get("type") == "IMAGE":
        url = fill.get("url", "")
        return f'<img src="{url}"{style_attr} />'

    # --- SVG 节点（仅叶子节点使用 assets svg，有 children 的不短路） ---
    if node.get("hasSvg") and node_id in assets.get("svgs", {}) and not children:
        svg = assets["svgs"][node_id]
        if has_positioning or inline_style:
            return f"<div{style_attr}>{svg}</div>"
        return svg

    # --- PATH / LAYER 叶子节点 ---
    if node_type in ("PATH", "LAYER") and not children:
        if has_positioning or inline_style:
            return f"<div{style_attr}></div>"
        return ""

    # --- 容器节点 (FRAME, GROUP, 或有 children) ---
    children_html_parts = []

    # 检查是否有重复子节点
    repeat_children_indices = set()
    if repeat_info:
        repeat_key = repeat_info.get("repeatKey", "")
        repeat_parent_id = repeat_info.get("parentId", "")

        if node_id == repeat_parent_id:
            # 在当前节点的 children 中找到重复项
            repeat_indices = []
            for i, c in enumerate(children):
                if c["name"].startswith(repeat_key):
                    repeat_indices.append(i)

            if len(repeat_indices) >= 2:
                # 只渲染第一个重复项作为模板
                first_idx = repeat_indices[0]
                first_html = render_node(
                    children[first_idx], assets, slot_map, None
                )
                indent = " " * 6
                children_html_parts.append(
                    f"{{% for item in items %}}\n{indent}{first_html}\n{{% endfor %}}"
                )
                # 标记其余重复项为已处理
                for idx in repeat_indices:
                    repeat_children_indices.add(idx)

    # 渲染子节点
    for i, c in enumerate(children):
        if i in repeat_children_indices:
            continue
        child_html = render_node(c, assets, slot_map, repeat_info)
        if child_html:
            children_html_parts.append(child_html)

    children_html = "\n".join(children_html_parts)

    if has_positioning or inline_style:
        if children_html:
            return f"<div{style_attr}>\n{children_html}\n</div>"
        else:
            return f"<div{style_attr}></div>"
    else:
        return children_html


def generate_template(frame_id="3-products"):
    """主入口：为指定 frame 生成模板 HTML。"""
    print(f"[{frame_id}] 从 modules 生成模板 HTML...")

    # 加载数据
    merged_path = MERGED_DIR / f"{frame_id}.json"
    if not merged_path.exists():
        print(f"  [ERROR] 找不到 {merged_path}")
        return

    merged = load_json(merged_path)
    modules = merged["modules"]
    assets = merged.get("assets", {})

    # 加载重复/槽位定义
    templates = {}
    if TEMPLATES_PATH.exists():
        templates = load_json(TEMPLATES_PATH)
    frame_templates = templates.get(frame_id, [])

    # 构建 slot 映射
    slot_map = build_slot_map(frame_templates)

    # 添加 single slots（不在白名单、不在 repeat slot 中的文本）
    single_texts = add_single_slots(slot_map, modules, frame_templates)
    if single_texts:
        print(f"  发现 {len(single_texts)} 个 single slot")

    # 取第一个 repeat_info（3-products 只有一个 repeat group）
    repeat_info = frame_templates[0] if frame_templates else None

    # 渲染所有模块
    html_parts = []
    for mod in modules:
        node = mod.get("node")
        if not node:
            continue
        mod_html = render_node(node, assets, slot_map, repeat_info)
        if mod_html:
            html_parts.append(mod_html)

    body_html = "\n".join(html_parts)

    # 包装完整 HTML 文档
    full_html = (
        '<!DOCTYPE html>\n'
        '<html lang="zh-CN">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=375, initial-scale=1.0">\n'
        '<style>\n'
        '  *,*::before,*::after { box-sizing: border-box }\n'
        '  body { padding: 0; margin: 0 }\n'
        '  p { margin: 0 }\n'
        '</style>\n'
        '</head>\n'
        '<body>\n'
        + body_html +
        '\n</body>\n</html>'
    )

    # 输出
    frame_out = OUTPUT_DIR / frame_id
    frame_out.mkdir(parents=True, exist_ok=True)
    html_path = frame_out / "template.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    # 输出 schema
    schema = {
        "frameId": frame_id,
        "type": "template",
        "singleSlots": [
            {"name": slot_map[t], "example": t}
            for t in single_texts
        ],
        "repeatGroups": [
            {
                "repeatKey": tmpl.get("repeatKey", "items"),
                "count": tmpl.get("count", 1),
                "slots": tmpl.get("slots", []),
            }
            for tmpl in frame_templates
        ],
    }
    schema_path = frame_out / "schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    print(f"  template.html ({len(full_html)} bytes)")
    print(f"  schema.json")
    print(f"  单槽位: {len(single_texts)} 个")
    if repeat_info:
        print(f"  重复组: {repeat_info.get('repeatKey')} × {repeat_info.get('count')}")


if __name__ == "__main__":
    frame_id = sys.argv[1] if len(sys.argv) > 1 else "3-products"
    generate_template(frame_id)

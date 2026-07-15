#!/usr/bin/env python3
"""
split_modules.py — 按页面层级树识别业务模块，提取每个模块的完整设计数据。

模块 = 页面根节点（getDsl 根 FRAME）的直接子节点。每个直接子节点就是一个
可独立生成 CSS/HTML 的 H5 业务模块（如 头图banner、热点前线、相关产品 ...）。

与 normalize_to_tree.py 的区别：
  normalize 只保留结构+文本（轻量层级树，不含样式）。
  split_modules 保留每个模块的**完整设计数据**，供后续直接转 CSS：
    - node        节点全部字段（layoutStyle / fill / effect / text / textColor ...）
    - styles      该模块引用到的样式子集（paint/font/effect，paint 内含图片 url）
    - assets      节点级图片/矢量资源（getDsl 位图 url + extractSvg + getDesignSvgs）
    - d2c         MasterGo 已算好的渲染级 HTML/CSS 片段 + 内联 svg 图标 + 导出清单
                  （整页 D2C 无 node-id 锚点，按顶层 div 的 left/top 位置对齐到模块）

输出：
  data/modules/{序号}-{语义名}.json   每个模块一份完整设计数据
  data/modules/_index.json            模块清单（供 audit / 下游脚本索引）

用法：
  python scripts/prepare/split_modules.py            # 完整拆分
  python scripts/prepare/split_modules.py --check    # 只校验输入
  python scripts/prepare/split_modules.py --dry-run  # 打印模块概要，不写文件
"""

import json
import re
import sys
import copy
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

# --- Windows 编码适配 ---
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = None  # SKILL_ROOT / "data" / args.project
RAW_DIR = None
MODULES_DIR = None
CONFIG_PATH = None

# 复用渲染层的 SVG 合法化工具
LIB_DIR = SKILL_ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB_DIR))
import css_core  # noqa: E402

# 已知模块中文名 -> 英文语义 slug。命中则用英文，未命中回退到 sanitize（保留原名）。
# 可选填：每张新设计稿的模块名不同，在此填入中文名→英文 slug 的映射。
SLUG_MAP = {}

# 匹配样式引用键：paint_0:74 / font_0:80 / effect_0:78
STYLE_REF_RE = re.compile(r"([a-z]+_\d+:\d+)")
PLACEHOLDER_RE = re.compile(r"^T\d+\|(\d+:\d+)$")

# 检测节点名是否含可读文本（中文/日文/韩文等 CJK 字符）
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uff00-\uffef]")
# 明确不是文本的节点名黑名单（部分匹配即排除）
_OUTLINED_NAME_BLACKLIST = [
    "Gradient Overlay", "Color Overlay", "图层", "矩形", "路径",
    "椭圆", "形状", "Clip", "组 ", "拷贝", "Copy", "直线",
    "圆角矩形", "按钮", "标签", "底框", "图标", "背景",
]


# ============================================================================
# 数据加载
# ============================================================================

def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict:
    return load_json(CONFIG_PATH) or {}


def load_get_dsl() -> dict | None:
    raw = load_json(RAW_DIR / "01-getDsl" / "getDsl.json")
    if raw is None:
        return None
    return raw.get("dsl", raw)


def load_section_overview() -> list:
    raw = load_json(RAW_DIR / "03-getDesignSections" / "overview.json")
    if raw is None:
        return []
    return raw.get("sections", [])


def load_texts() -> dict[str, str]:
    raw = load_json(RAW_DIR / "05-getDesignTexts" / "getDesignTexts.json")
    if raw is None:
        return {}
    return raw.get("texts", {})


def load_extract_svgs() -> dict[str, dict]:
    """05-extractSvg：节点级内联 svg，返回 {nodeId: {name, svg}}。"""
    raw = load_json(RAW_DIR / "05-extractSvg" / "extractSvg.json")
    if raw is None:
        return {}
    out = {}
    for item in raw.get("svgs", []):
        nid = item.get("id")
        if nid:
            out[nid] = {"name": item.get("name", ""), "svg": item.get("svg", "")}
    return out


def load_design_svgs() -> dict[str, dict]:
    """05-getDesignSvgs：section 级 svg，键形如 S{sec}:{name}|{nodeId}。
    返回 {nodeId: {key, svg}}。"""
    raw = load_json(RAW_DIR / "05-getDesignSvgs" / "getDesignSvgs.json")
    if raw is None:
        return {}
    out = {}
    for key, svg in raw.get("svgs", {}).items():
        m = re.search(r"\|(\d+:\d+)$", key)
        if m:
            out[m.group(1)] = {"key": key, "svg": svg}
    return out


def _sanitize_inline_svg(svg: str, node_id: str) -> str:
    """让烘焙内联 SVG 自洽合法后再存入 modules.assets.svgs。

    坑（根治点）：extractSvg 透传的 SVG，其 path 的 fill 常是 CSS 渐变串
    fill="linear-gradient(...)"（radial 还可能带 NaN）——这是**非法 SVG**，浏览器
    不渲染。此前只有 generate_html 渲染阶段才修，导致 data/modules 里存的是坏 SVG，
    任何直接读 modules 的下游（如 Open Design skill）都会拿到非法图形。
    修复：在生成 modules 时就应用与渲染同源的合法化（渐变→<defs>+url(#id)、
    边框实心 fill-rule、细线 crispEdges）。这些变换幂等，渲染阶段再调也是 no-op。
    注：inject_svg_filters（子节点 blur）与 position_inline_svg（定位/z-index）依赖
    节点树/布局，属渲染层，不在此前移。"""
    if not svg:
        return svg
    uid = node_id.replace(":", "_")
    svg = css_core.inline_svg_fix_gradients(svg, uid_prefix=uid)
    svg = css_core.fix_svg_frame_fill(svg)
    svg = css_core.fix_svg_thin_lines(svg)
    return svg


def load_d2c_payload() -> dict | None:
    """07-getD2c：返回 payload（含 code / svg / image ...）。"""
    raw = load_json(RAW_DIR / "07-getD2c" / "getD2c.json")
    if raw is None:
        return None
    data = raw.get("data")
    if not data:
        return None
    return data[0].get("payload")



# ============================================================================
# 工具函数
# ============================================================================

def slugify(name: str, index: int) -> str:
    """模块中文名 -> 文件名 slug。命中映射用英文，否则清洗原名。"""
    if name in SLUG_MAP:
        return SLUG_MAP[name]
    cleaned = re.sub(r"[\s/\\:*?\"<>|]+", "-", name.strip()).strip("-")
    return cleaned or f"module-{index}"


def detect_design_scale(page_width: float, page_height: float) -> dict:
    """根据页面宽度推断设计稿缩放比。

    MasterGo 移动端设计稿常见分辨率：
      - @1x: 320-430（原生移动端逻辑像素）
      - @2x: 640-860
      - @3x: 960-1290

    与常见移动端逻辑宽度（375/390/414/360/320）逐一比对，
    容忍 ±5px 偏差。匹配到则返回 scale 与逻辑宽高，否则按 @1x 处理。
    """
    CANDIDATES = [375, 390, 414, 360, 320]
    page_w = round(page_width)

    # 先查 @3x / @2x
    for scale in [3, 2]:
        for cw in CANDIDATES:
            expected = cw * scale
            if abs(page_w - expected) <= 5:
                return {
                    "scale": scale,
                    "logicalWidth": cw,
                    "logicalHeight": round(page_height / scale),
                    "nativeWidth": page_width,
                    "nativeHeight": page_height,
                    "label": f"@{scale}x ({cw}×{scale}={expected})",
                }

    # @1x
    for cw in CANDIDATES:
        if abs(page_w - cw) <= 5:
            return {
                "scale": 1,
                "logicalWidth": cw,
                "logicalHeight": round(page_height),
                "nativeWidth": page_width,
                "nativeHeight": page_height,
                "label": "@1x",
            }

    # 未命中任何常见宽度 → @1x，保留原宽
    return {
        "scale": 1,
        "logicalWidth": page_w,
        "logicalHeight": round(page_height),
        "nativeWidth": page_width,
        "nativeHeight": page_height,
        "label": "@1x (non-standard width)",
    }


def is_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_RE.match(text))


def resolve_texts_inplace(node: dict, texts_map: dict[str, str]) -> int:
    """就地把 TEXT 节点里的占位符 T{n}|{id} 替换成真实文本，返回替换数。"""
    count = 0
    if node.get("type") == "TEXT":
        raw = node.get("text")
        if isinstance(raw, list):
            for seg in raw:
                if isinstance(seg, dict) and is_placeholder(seg.get("text", "")):
                    repl = texts_map.get(seg["text"])
                    if repl:
                        seg["text"] = repl
                        count += 1
        elif isinstance(raw, str) and is_placeholder(raw):
            repl = texts_map.get(raw)
            if repl:
                node["text"] = repl
                count += 1
    for child in node.get("children", []):
        count += resolve_texts_inplace(child, texts_map)
    return count


def collect_node_ids(node: dict, out: set):
    out.add(node.get("id", ""))
    for child in node.get("children", []):
        collect_node_ids(child, out)


def collect_style_refs(node: dict) -> set:
    """遍历子树，收集所有被引用的样式键（paint/font/effect）。"""
    refs = set()

    def walk(n):
        for key, value in n.items():
            if key == "children":
                continue
            blob = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            refs.update(STYLE_REF_RE.findall(blob))
        for child in n.get("children", []):
            walk(child)

    walk(node)
    return refs


def count_text_nodes(node: dict) -> int:
    n = 1 if node.get("type") == "TEXT" else 0
    for child in node.get("children", []):
        n += count_text_nodes(child)
    return n


def collect_image_urls(styles_subset: dict) -> list[dict]:
    """从 paint 样式子集里提取图片 url（位图节点靠 paint.value[].url 引用图片）。"""
    images = []
    for style_key, style_val in styles_subset.items():
        if not style_key.startswith("paint_"):
            continue
        for paint in (style_val.get("value") or []):
            url = paint.get("url") if isinstance(paint, dict) else None
            if url:
                images.append({"styleKey": style_key, "url": url})
    return images


# ============================================================================
# 样式引用解析（paint_ / font_ / effect_ → 实际值）
# ============================================================================

def resolve_paint(paint_key: str | None, styles: dict):
    """解引用 paint_ 键，返回颜色字符串、IMAGE 对象、或 null。"""
    if not paint_key or paint_key not in styles:
        return None
    value = styles[paint_key].get("value")
    if not value or not isinstance(value, list) or len(value) == 0:
        return None
    results = []
    for v in value:
        if isinstance(v, str):
            results.append(v)
        elif isinstance(v, dict):
            if "url" in v:
                results.append({"type": "IMAGE", "url": v["url"]})
            else:
                results.append(v)
    return results[0] if len(results) == 1 else (results if results else None)


def resolve_effect(effect_key: str | None, styles: dict):
    """解引用 effect_ 键，返回结构化效果对象。"""
    if not effect_key or effect_key not in styles:
        return None
    value = styles[effect_key].get("value")
    if not value or not isinstance(value, list) or len(value) == 0:
        return {"boxShadow": [], "filter": [], "backdropFilter": [], "raw": []}
    result = {"boxShadow": [], "filter": [], "backdropFilter": [], "raw": list(value)}
    for v in value:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if s.startswith("box-shadow"):
            result["boxShadow"].append(s)
        elif s.startswith("filter"):
            result["filter"].append(s)
        elif s.startswith("backdrop-filter"):
            result["backdropFilter"].append(s)
    return result


def resolve_font(font_key: str | None, styles: dict):
    """解引用 font_ 键，返回字体属性对象。"""
    if not font_key or font_key not in styles:
        return None
    val = styles[font_key].get("value")
    if not isinstance(val, dict):
        return None
    return {
        "family": val.get("family"),
        "size": val.get("size"),
        "style": val.get("style"),
        "lineHeight": val.get("lineHeight"),
        "letterSpacing": val.get("letterSpacing"),
        "case": val.get("case"),
        "decoration": val.get("decoration"),
    }


def resolve_text_runs(node: dict, styles: dict):
    """解析 TEXT 节点的 text[] + textColor[] 为自包含 textRuns。"""
    raw = node.get("text")
    if not raw or not isinstance(raw, list):
        return None
    text_colors = node.get("textColor") or []

    runs = []
    for seg in raw:
        if not isinstance(seg, dict):
            continue
        run = {"text": seg.get("text", "")}
        font_key = seg.get("font")
        run["font"] = resolve_font(font_key, styles) if font_key else None
        runs.append(run)

    # 把 textColor 分段颜色合并到对应 run
    for tc in text_colors:
        if not isinstance(tc, dict):
            continue
        start, end = tc.get("start", 0), tc.get("end", 0)
        color_key = tc.get("color")
        color_val = resolve_paint(color_key, styles) if color_key else None
        pos = 0
        for run in runs:
            run_end = pos + len(run["text"])
            if start < run_end and end > pos:
                run["color"] = color_val
            pos = run_end

    return runs


def resolve_text_color(node: dict, styles: dict):
    """把 TEXT 节点 textColor[] 的 paint 引用解析成 hex，供逐字上色。
    返回 [{start,end,color(hex/渐变/None)}]；无 textColor 返回 None。
    （单 textRun 场景下逐字颜色无法塞进 textRuns——resolve_text_runs 会被末段覆盖——
    故单独保留解析后的分段颜色，让渲染层按字符区间上色。）"""
    text_colors = node.get("textColor") or []
    if not text_colors:
        return None
    out = []
    for tc in text_colors:
        if not isinstance(tc, dict):
            continue
        ck = tc.get("color")
        cv = resolve_paint(ck, styles) if ck else None
        out.append({"start": tc.get("start"), "end": tc.get("end"), "color": cv})
    return out or None


def _make_null_css() -> dict:
    """构造一个全部属性为 null 的 D2C CSS 对象。"""
    return {p: None for p in ALL_CSS_PROPS}


def _style_to_css(style_str: str) -> dict:
    """将 inline style 字符串解析为 CSS 属性字典。"""
    css = {}
    for decl in style_str.split(";"):
        decl = decl.strip()
        if ":" in decl:
            prop, val = decl.split(":", 1)
            prop, val = prop.strip(), val.strip()
            if prop in ALL_CSS_PROPS:
                css[prop] = val
    return css


def _parse_d2c_elements(html: str) -> list[dict]:
    """将 D2C HTML 解析为元素列表，追踪嵌套层级。

    返回 [{tag, style, src, css, depth, absBounds}]
    absBounds 是 page-absolute 的 px 坐标。
    """
    # Tokenize
    tokens = []
    for m in re.finditer(r"<(div|img|span)\b([^>]*?)(/?)>|</(div)>", html, re.S):
        raw = m.group(0)
        if raw.startswith("</"):
            tokens.append({"type": "close", "tag": m.group(4)})
            continue

        tag = m.group(1)
        attrs = m.group(2)
        self_close = m.group(3) == "/"

        style_str = ""
        sm = re.search(r'style="([^"]*)"', attrs)
        if sm:
            style_str = sm.group(1)

        src = ""
        srcm = re.search(r'src="([^"]*)"', attrs)
        if srcm:
            src = srcm.group(1)

        tokens.append({
            "type": "open" if (tag == "div" and not self_close) else "self_close",
            "tag": tag,
            "style": style_str,
            "css": _style_to_css(style_str) if style_str else {},
            "src": src,
        })

    # Build tree with absolute bounds
    # Stack: [(element_dict, {x,y,w,h})]
    # Default page size
    stack = [({"tag": "page"}, {"x": 0.0, "y": 0.0, "w": 375.0, "h": 3000.0})]
    results = []

    def _resolve_val(val, unit, parent_size):
        if unit == "%":
            return val / 100.0 * parent_size
        return val

    for tok in tokens:
        if tok["type"] == "close":
            if len(stack) > 1:
                stack.pop()
            continue

        parent_bounds = stack[-1][1]

        # Parse left/top/width/height from style
        pos = {}
        for prop in ["left", "top", "width", "height"]:
            m2 = re.search(rf"{prop}:\s*([\d.-]+)(px|%)?", tok["style"])
            if m2:
                pos[prop] = (float(m2.group(1)), m2.group(2) or "px")

        # Compute absolute bounds
        left = _resolve_val(*pos["left"], parent_bounds["w"]) if "left" in pos else 0
        top = _resolve_val(*pos["top"], parent_bounds["h"]) if "top" in pos else 0
        w = _resolve_val(*pos["width"], parent_bounds["w"]) if "width" in pos else 0
        h = _resolve_val(*pos["height"], parent_bounds["h"]) if "height" in pos else 0

        abs_bounds = {
            "x": parent_bounds["x"] + left,
            "y": parent_bounds["y"] + top,
            "w": w,
            "h": h,
        }

        el = {
            "tag": tok["tag"],
            "style": tok["style"],
            "css": tok["css"],
            "src": tok["src"],
            "depth": len(stack) - 1,
            "absBounds": abs_bounds,
        }
        results.append(el)

        if tok["type"] == "open":
            stack.append((el, abs_bounds))

    return results


def _collect_node_bounds(node: dict, parent_x: float = 0, parent_y: float = 0) -> dict[str, dict]:
    """收集 getDsl 子树中所有节点的 page-absolute bounds。返回 {nodeId: {x,y,w,h}}。"""
    bounds = {}
    layout = node.get("layoutStyle") or {}
    w = layout.get("width") or 0
    h = layout.get("height") or 0
    rx = layout.get("relativeX") or 0
    ry = layout.get("relativeY") or 0
    abs_x = parent_x + rx
    abs_y = parent_y + ry
    bounds[node["id"]] = {"x": abs_x, "y": abs_y, "w": w, "h": h}
    for child in node.get("children", []):
        bounds.update(_collect_node_bounds(child, abs_x, abs_y))
    return bounds


def _bounds_match_score(a: dict, b: dict) -> float:
    """计算两个 bounds 的匹配分数（越小越匹配）。使用中心点距离 + 尺寸差异。"""
    ax = a["x"] + a["w"] / 2 if a["w"] else a["x"]
    ay = a["y"] + a["h"] / 2 if a["h"] else a["y"]
    bx = b["x"] + b["w"] / 2 if b["w"] else b["x"]
    by = b["y"] + b["h"] / 2 if b["h"] else b["y"]
    center_dist = abs(ax - bx) + abs(ay - by)
    size_diff = abs(a["w"] - b["w"]) + abs(a["h"] - b["h"])
    return center_dist + size_diff * 0.5


def parse_d2c_node_css(d2c_html: str, node_bounds: dict[str, dict]) -> dict[str, dict]:
    """解析模块 D2C HTML，提取每个元素的 CSS，按 nodeId 匹配返回。

    匹配策略（按优先级）：
      1. img-src 精确：<img src="...名字-0-921.svg"> 文件名含 nodeId → 该元素 CSS 归入此 nodeId
      2. img-src 父级：img 的父级 div 的 CSS 也归入同一个 nodeId
      3. 几何匹配：剩余元素按其 absolute bounds 找最接近的 nodeId

    返回 {nodeId: {css_prop: value, ...}}
    """
    if not d2c_html:
        return {}

    elements = _parse_d2c_elements(d2c_html)
    if not elements:
        return {}

    node_css: dict[str, dict] = {}
    matched_element_indices: set = set()

    # --- 第一遍：img-src 精确匹配 ---
    # 找到每个 img 的 nodeId，同时标记其父 div
    img_node_map = {}  # element_index → nodeId
    for i, el in enumerate(elements):
        if el["tag"] == "img" and el["src"]:
            m = D2C_IMG_NODEID_RE.search(el["src"])
            if m:
                # D2C 用短横线分隔 nodeId (0-921)，统一转为 getDsl 格式 (0:921)
                img_node_map[i] = m.group(1).replace("-", ":", 1)

    # 把 img 及其各层父级 div 的 CSS 都归入对应 nodeId
    for i, node_id in img_node_map.items():
        css = node_css.setdefault(node_id, _make_null_css())
        # 合并 img 自身的 CSS
        for prop, val in elements[i]["css"].items():
            css[prop] = val
        matched_element_indices.add(i)

        # 向上找父级 div（depth 更小的），并入同一 nodeId
        el_depth = elements[i]["depth"]
        for j in range(i - 1, -1, -1):
            parent = elements[j]
            if parent["depth"] < el_depth and parent["tag"] == "div":
                for prop, val in parent["css"].items():
                    if css[prop] is None:
                        css[prop] = val
                matched_element_indices.add(j)
                el_depth = parent["depth"]
                if parent["depth"] == 0:
                    break

    # --- 第二遍：几何匹配剩余元素 ---
    # 只对带特殊 CSS 属性（mix-blend-mode / overflow 等）或带非空 CSS 的 div 做匹配
    unmatched = [
        (i, el) for i, el in enumerate(elements)
        if i not in matched_element_indices and el["css"] and el["tag"] == "div"
    ]
    if unmatched:
        # 对每个未匹配元素，找 bounds 最近的 node
        for i, el in unmatched:
            el_bounds = el["absBounds"]
            best_node, best_score = None, 1e9
            for nid, nb in node_bounds.items():
                # 跳过 bounds 为空或尺寸悬殊过大的
                if nb["w"] <= 0 or nb["h"] <= 0:
                    continue
                score = _bounds_match_score(el_bounds, nb)
                if score < best_score:
                    best_score, best_node = score, nid

            # 阈值：中心距离 + 尺寸差异 < 阈值才接受
            if best_node is not None and best_score < 200:
                css = node_css.setdefault(best_node, _make_null_css())
                for prop, val in el["css"].items():
                    if css[prop] is None:
                        css[prop] = val
                matched_element_indices.add(i)

    return node_css


def match_export_image(node_id: str, node_name: str, export_images: dict) -> dict | None:
    """匹配 D2C exportImages 中对应这个 node 的条目。"""
    # D2C 文件名用短横线分隔 nodeId：位图一-0-1317.svg
    d2c_id = node_id.replace(":", "-")
    for fname, meta in (export_images or {}).items():
        if f"-{d2c_id}." in fname or fname.endswith(f"-{d2c_id}.svg"):
            return {"fileName": fname, **meta}
    # 备选：按节点名匹配
    if node_name:
        for fname, meta in (export_images or {}).items():
            if fname.startswith(f"{node_name}-"):
                return {"fileName": fname, **meta}
    return None


# ============================================================================
# 核心：递归解析节点树 → 固定 Schema
# ============================================================================

def _is_outlined_text_name(name: str) -> bool:
    """检查节点名是否像被转成路径的文字（含 CJK 且不在黑名单中）。"""
    if not name or not isinstance(name, str):
        return False
    for pat in _OUTLINED_NAME_BLACKLIST:
        if pat in name:
            return False
    return bool(_CJK_RE.search(name))


def _subtree_has_text(children: list) -> bool:
    """递归检查子树中是否有 TEXT 节点。"""
    for child in children:
        if child.get("type") == "TEXT":
            return True
        if _subtree_has_text(child.get("children", [])):
            return True
    return False


def _collect_sibling_text_fonts(resolved_children: list, styles: dict) -> dict | None:
    """从已解析的兄弟节点中收集第一个 TEXT 节点的字体信息。
    用于 outlined text 节点推断字体属性。返回 {family, size, lineHeight, letterSpacing} 或 None。"""
    for child in resolved_children:
        if child["type"] == "TEXT" and child.get("textRuns"):
            runs = child["textRuns"]
            if runs:
                font = runs[0].get("font") or {}
                return {
                    "family": font.get("family"),
                    "size": font.get("size"),
                    "lineHeight": font.get("lineHeight"),
                    "letterSpacing": font.get("letterSpacing"),
                    "weight": font.get("weight"),
                }
        # 也检查兄弟 GROUP 的子节点
        if child["type"] == "GROUP":
            result = _collect_sibling_text_fonts(child.get("children", []), styles)
            if result:
                return result
    return None


def resolve_node(
    node: dict,
    styles: dict,
    d2c_css_map: dict[str, dict],
    svg_ids: set,
    design_svg_ids: set,
    export_images: dict,
    parent_x: float = 0,
    parent_y: float = 0,
) -> dict:
    """递归解析单个节点，返回固定 Schema 的自包含节点对象。"""
    node_id = node.get("id", "")
    node_name = node.get("name", "")
    node_type = node.get("type", "")
    layout = node.get("layoutStyle") or {}

    # --- 几何 ---
    w = layout.get("width") or 0
    h = layout.get("height") or 0
    rx = layout.get("relativeX") or 0
    ry = layout.get("relativeY") or 0
    rotate = layout.get("rotate") or 0
    rotate_x = layout.get("rotateX")
    abs_x = parent_x + rx
    abs_y = parent_y + ry

    # --- 视觉（解引用） ---
    fill_val = resolve_paint(node.get("fill"), styles)
    effect_val = resolve_effect(node.get("effect"), styles)
    stroke_color_val = resolve_paint(node.get("strokeColor"), styles)

    # --- 文本 ---
    text_runs = resolve_text_runs(node, styles)
    full_text = None
    if text_runs:
        full_text = "".join(r["text"] for r in text_runs)

    # --- 路径 ---
    path_raw = node.get("path")
    path_resolved = None
    if path_raw and isinstance(path_raw, list):
        path_resolved = []
        for p in path_raw:
            if isinstance(p, dict):
                pf = resolve_paint(p.get("fill"), styles)
                path_resolved.append({
                    "data": p.get("data"),
                    "fill": pf,
                    "transform": p.get("transform"),
                })

    # PATH 节点的 fill 常写在 path[0].fill 而非 node.fill；
    # 提升到节点级供 CSS 生成使用（css_core.fill_to_css 只读 node.fill）。
    # 只提升 path[0]（外层/主体形状的 fill），后续 path[1+] 的 fill（内层轮廓、
    # 描边等）由 baked SVG 表达，CSS 无法用单一矩形还原多路径的不同几何形状。
    if fill_val is None and path_resolved and isinstance(path_resolved, list) and len(path_resolved) > 0:
        first_fill = path_resolved[0].get("fill")
        if first_fill is not None:
            fill_val = first_fill

    # --- SVG ---
    has_svg = node_id in svg_ids or node_id in design_svg_ids

    # --- D2C CSS ---
    d2c_css = d2c_css_map.get(node_id, _make_null_css())
    d2c_match = "img-src" if node_id in d2c_css_map else None

    # --- Export image ---
    export_img = match_export_image(node_id, node_name, export_images)

    # --- Style refs（原始引用键保留） ---
    style_refs = {}
    if node.get("fill") and isinstance(node.get("fill"), str) and node["fill"].startswith("paint_"):
        style_refs["fill"] = node["fill"]
    if node.get("effect") and isinstance(node["effect"], str) and node["effect"].startswith("effect_"):
        style_refs["effect"] = node["effect"]
    if node.get("strokeColor") and isinstance(node["strokeColor"], str) and node["strokeColor"].startswith("paint_"):
        style_refs["strokeColor"] = node["strokeColor"]
    if text_runs:
        font_refs = []
        tc_refs = []
        raw_text = node.get("text") or []
        for seg in raw_text:
            if isinstance(seg, dict) and seg.get("font"):
                font_refs.append(seg["font"])
        for tc in (node.get("textColor") or []):
            if isinstance(tc, dict) and tc.get("color"):
                tc_refs.append(tc["color"])
        if font_refs:
            style_refs["font"] = font_refs
        if tc_refs:
            style_refs["textColors"] = tc_refs
    if not style_refs:
        style_refs = None

    # --- Sources ---
    sources = ["getDsl"]
    if node_id in d2c_css_map:
        sources.append("getD2c")
    if has_svg:
        if node_id in svg_ids:
            sources.append("extractSvg")
        if node_id in design_svg_ids:
            sources.append("getDesignSvgs")
    if export_img:
        sources.append("getD2c-image")

    # --- Capture status ---
    capture_status = "complete"
    # 如果 d2c 没匹配到但该类型通常有 d2c 数据，标 partial
    # 简单策略：LAYER 和 FRAME 类型如果有 blendMode 需从 D2C 来
    # 当前不标记，因为 blendMode 在 d2cMatch=null 时自然为 null

    # --- 递归 children ---
    resolved_children = []
    for child in node.get("children", []):
        resolved_children.append(
            resolve_node(child, styles, d2c_css_map, svg_ids, design_svg_ids,
                        export_images, abs_x, abs_y)
        )

    # --- 检测文字转路径（outlined text）---
    # MasterGo 中文字被转成轮廓后，MCP 只返回 PATH/Gradient Overlay 节点，
    # 原始文字内容仅保存在节点名称中。此处检测这类情况并标注。
    outlined_text = False
    outlined_text_font = None
    if (node_type in ("GROUP",) and not full_text
            and not _subtree_has_text(resolved_children)
            and _is_outlined_text_name(node_name)):
        outlined_text = True
        # 兄弟 TEXT 节点推断字体
        outlined_text_font = _collect_sibling_text_fonts(resolved_children, styles)

    # --- 组件定义（本设计稿无，留位） ---
    component_definition = None

    return {
        "id": node_id,
        "name": node_name,
        "type": node_type,

        "layoutStyle": {
            "width": w,
            "height": h,
            "relativeX": rx,
            "relativeY": ry,
            "rotate": rotate,
            "rotateX": rotate_x,
        },

        "bounds": {"x": abs_x, "y": abs_y, "width": w, "height": h},

        "opacity": node.get("opacity"),
        "fill": fill_val,
        "effect": effect_val,
        "borderRadius": node.get("borderRadius"),
        "strokeAlign": node.get("strokeAlign"),
        "strokeColor": stroke_color_val,
        "strokeType": node.get("strokeType"),
        "strokeWidth": node.get("strokeWidth"),
        "mask": node.get("mask"),

        "path": path_resolved,
        "text": full_text,
        "textRuns": text_runs,
        "textAlign": node.get("textAlign"),
        "textMode": node.get("textMode"),
        "textColor": resolve_text_color(node, styles),

        # 文字转路径标注：当目标是文本但被设计工具转成轮廓时启用
        "outlinedText": outlined_text,
        "outlinedTextFont": outlined_text_font,

        "hasSvg": has_svg,
        "exportImage": export_img,
        "styleRefs": style_refs,
        "componentDefinition": component_definition,

        "d2cCss": d2c_css,
        "d2cMatch": d2c_match,

        "sources": sources,
        "captureStatus": capture_status,

        "children": resolved_children,
    }


# ============================================================================
# D2C 整页 HTML 按顶层 div 位置切成模块片段
# ============================================================================

SVG_ICON_RE = re.compile(r"svg_[0-9a-f]{8}\.svg")
ASSET_IMG_RE = re.compile(r"asset/images/([^\"']+\.(?:svg|png|jpg|jpeg))")

# D2C HTML 中 img 文件名含 nodeId：如 "名字-0-921.svg"（D2C 用短横线分隔 nodeId）
D2C_IMG_NODEID_RE = re.compile(r"[\u4e00-\u9fff\w]+-(\d+-\d+)\.(?:svg|png|jpg|jpeg)")
# exportImages 的 key 中也含 nodeId
EXPORT_IMG_KEY_RE = re.compile(r"-(\d+-\d+)\.\w+$")

# D2C CSS 属性全集（所有可能出现的 CSS 属性，没匹配到的填 null）
ALL_CSS_PROPS = [
    "-webkit-background-clip", "-webkit-text-fill-color",
    "background", "background-clip", "background-image",
    "border", "border-bottom-left-radius", "border-radius", "border-top-left-radius",
    "bottom", "box-shadow", "color", "filter", "flex",
    "font-family", "font-size", "height", "left", "letter-spacing",
    "line-height", "mix-blend-mode", "object-fit", "opacity", "overflow",
    "position", "right", "text-align", "text-fill-color", "text-shadow",
    "top", "transform", "transform-origin", "width", "z-index",
]


def _pos_from_style(style: str, page_w: float, page_h: float):
    """从 div 的 style 里解析 (x, y)，支持 px 与 %。"""
    l = re.search(r"left:\s*(-?[\d.]+)(px|%)", style)
    t = re.search(r"top:\s*(-?[\d.]+)(px|%)", style)
    if not l or not t:
        return None
    x = float(l.group(1))
    x = x if l.group(2) == "px" else x / 100 * page_w
    y = float(t.group(1))
    y = y if t.group(2) == "px" else y / 100 * page_h
    return (x, y)


def parse_d2c_fragments(payload: dict) -> tuple[list[dict], dict]:
    """把 D2C 整页 HTML 切成顶层片段。

    整页 HTML 是 root 页面 div 包着若干顶层子 div，每个顶层子 div 对应一个模块
    （无 node-id，只能靠 left/top 位置对齐）。返回：
      fragments: [{pos:(x,y), html:...}]  顶层片段列表
      page:      {width, height, background}  页面级信息
    """
    html = payload.get("code", "")
    m_body = re.search(r"<body>\s*(.*)\s*</body>", html, re.S)
    body = m_body.group(1) if m_body else html

    m_dim = re.search(r"width:\s*([\d.]+)px;\s*height:\s*([\d.]+)px", body)
    page_w = float(m_dim.group(1)) if m_dim else 375.0
    page_h = float(m_dim.group(2)) if m_dim else 0.0
    m_bg = re.search(r"background:\s*([^;\"]+)", body)
    page = {
        "width": page_w,
        "height": page_h,
        "background": m_bg.group(1).strip() if m_bg else "",
    }

    fragments = []
    depth = 0
    start = None
    start_pos = None
    for m in re.finditer(r"<div\b([^>]*)>|</div>", body):
        if m.group(0).startswith("</"):
            depth -= 1
            if depth == 1 and start is not None:
                fragments.append({"pos": start_pos, "html": body[start:m.end()]})
                start = None
        else:
            if depth == 1:  # root 页面 div 的直接子 div = 模块
                start_pos = _pos_from_style(m.group(1), page_w, page_h)
                start = m.start()
            depth += 1
    return fragments, page


def match_d2c_fragment(module_pos, fragments, used: set):
    """按 (x,y) 曼哈顿距离把模块匹配到最近的未占用 D2C 片段。"""
    best_i, best_d = None, 1e9
    for i, frag in enumerate(fragments):
        if i in used or frag["pos"] is None:
            continue
        fx, fy = frag["pos"]
        d = abs(fx - module_pos[0]) + abs(fy - module_pos[1])
        if d < best_d:
            best_d, best_i = d, i
    return best_i, best_d


def slice_d2c_for_module(fragment_html: str, payload: dict) -> dict:
    """从模块的 D2C 片段里，切出它引用到的内联 svg 图标和导出图片清单。"""
    svg_map = payload.get("svg", {}) or {}
    image_map = payload.get("image", {}) or {}

    icon_names = set(SVG_ICON_RE.findall(fragment_html))
    svg_icons = {name: svg_map[name] for name in sorted(icon_names) if name in svg_map}

    export_images = {
        fname: meta for fname, meta in image_map.items()
        if fname in fragment_html
    }
    return {
        "html": fragment_html,
        "svgIcons": svg_icons,
        "exportImages": export_images,
    }



# ============================================================================
# 模块提取
# ============================================================================

def _has_mask_child(node: dict) -> bool:
    """检查直接子节点中是否有蒙版（mask=outline/alpha）。"""
    return any(c.get("mask") for c in node.get("children", []))


def _extract_corner_radius_from_mask_path(node: dict) -> str | None:
    """从蒙版 PATH 节点的 path[0].data 提取左上角圆角半径。

    圆角矩形蒙版的 data 通常以 M{R},0 L{W-R},0 开头，R 即圆角半径。
    只处理 Y≈0 且 X>0 的简单情况。失败返回 None。"""
    path_list = node.get("path")
    if not path_list or not isinstance(path_list, list):
        return None
    first = path_list[0]
    if not isinstance(first, dict):
        return None
    data = first.get("data", "")
    if not data:
        return None
    m = re.match(r"^M\s*([\d.]+)\s*[,\s]\s*([\d.eE+-]+)", data)
    if not m:
        return None
    rx, ry = float(m.group(1)), float(m.group(2))
    if abs(ry) < 0.01 and rx > 0:
        rounded = round(rx, 1)
        return f"{rounded}px" if rounded == int(rounded) else f"{rounded:.1f}px"
    return None


def _enrich_mask_overflow(node: dict):
    """递归遍历已解析的节点树，为含蒙版子节点的 FRAME 补 overflow:hidden + borderRadius。

    当 FRAME 节点的直接子节点中有 mask=outline/alpha 的蒙版时：
      - 设置 d2cCss['overflow'] = 'hidden'（近似蒙版裁剪效果）
      - 尝试从蒙版 path 提取圆角，写入节点的 borderRadius 字段（CSS gen 从这读取）
    """
    if node.get("type") == "FRAME" and _has_mask_child(node):
        d2c = node.setdefault("d2cCss", {})
        if d2c.get("overflow") is None:
            d2c["overflow"] = "hidden"
        if node.get("borderRadius") is None:
            for c in node.get("children", []):
                if c.get("mask"):
                    br = _extract_corner_radius_from_mask_path(c)
                    if br:
                        node["borderRadius"] = br
                    break
    for child in node.get("children", []):
        _enrich_mask_overflow(child)


def extract_module(child_node: dict, index: int, all_styles: dict,
                   section_overview: list, texts_map: dict,
                   extract_svgs: dict, design_svgs: dict,
                   d2c_fragments: list, d2c_used: set, d2c_payload: dict | None) -> dict:
    """从 getDsl 根节点的一个直接子节点提取完整模块设计数据。"""
    # 深拷贝，避免就地替换文本时污染共享数据
    node = copy.deepcopy(child_node)

    texts_resolved = resolve_texts_inplace(node, texts_map)

    node_ids = set()
    collect_node_ids(node, node_ids)

    style_refs = collect_style_refs(node)
    missing = sorted(style_refs - all_styles.keys())
    styles_subset = {k: all_styles[k] for k in sorted(style_refs) if k in all_styles}

    # 分段(section)在 overview 里没有显式下标，下标即数组位置。
    # 归属本模块的分段 = section root 落在本模块子树节点集合内的分段。
    module_sections = [
        {"sectionIndex": i, **s}
        for i, s in enumerate(section_overview)
        if s.get("id") in node_ids
    ]

    name = node.get("name", "")
    slug = slugify(name, index)

    # --- 资源（按 nodeId 归属本模块）---
    bitmaps = collect_image_urls(styles_subset)  # getDsl 位图照片 url
    node_svgs = [
        {"id": nid, "name": extract_svgs[nid]["name"], "svg": extract_svgs[nid]["svg"]}
        for nid in node_ids if nid in extract_svgs
    ]
    section_svgs = [
        {"id": nid, "key": design_svgs[nid]["key"], "svg": design_svgs[nid]["svg"]}
        for nid in node_ids if nid in design_svgs
    ]

    # --- D2C 渲染级片段（按顶层 div 位置对齐）---
    layout = node.get("layoutStyle", {})
    module_pos = (layout.get("relativeX") or 0, layout.get("relativeY") or 0)
    d2c_block = None
    d2c_match_dist = None
    if d2c_fragments and d2c_payload is not None:
        fi, dist = match_d2c_fragment(module_pos, d2c_fragments, d2c_used)
        if fi is not None:
            d2c_used.add(fi)
            d2c_match_dist = round(dist, 3)
            d2c_block = slice_d2c_for_module(d2c_fragments[fi]["html"], d2c_payload)

    # --- 收集 getDsl 节点 bounds（供 D2C 几何匹配）---
    node_bounds = _collect_node_bounds(node) if d2c_block else {}

    # --- 解析 D2C 节点级 CSS ---
    d2c_html = d2c_block["html"] if d2c_block else ""
    d2c_node_css_map = parse_d2c_node_css(d2c_html, node_bounds)

    # --- 收集 SVG nodeId 集合 ---
    svg_ids = set()
    for nid in node_ids:
        if nid in extract_svgs:
            svg_ids.add(nid)
    design_svg_ids = set()
    for nid in node_ids:
        if nid in design_svgs:
            design_svg_ids.add(nid)

    # --- D2C export images ---
    export_images = d2c_block["exportImages"] if d2c_block else {}

    # --- 解析节点树为固定 Schema ---
    resolved_tree = resolve_node(
        node, all_styles, d2c_node_css_map,
        svg_ids, design_svg_ids, export_images,
    )

    # --- 后处理：蒙版裁剪 → overflow:hidden + border-radius ---
    # getDsl 的 mask=outline/alpha 表示该帧的子元素应被裁剪到蒙版形状。
    # D2C 对 hasSvg 帧映射为 img-src，不会产出 overflow:hidden；
    # 但 mask 数据已在 getDsl 中，此处将其转化为父帧的 CSS overflow。
    _enrich_mask_overflow(resolved_tree)

    # --- 集中化 SVG 字符串到 assets.svgs（存入前先合法化，见 _sanitize_inline_svg）---
    all_svgs = {}
    for sv in node_svgs:
        all_svgs[sv["id"]] = _sanitize_inline_svg(sv["svg"], sv["id"])
    for sv in section_svgs:
        all_svgs[sv["id"]] = _sanitize_inline_svg(sv["svg"], sv["id"])

    paint_keys = sorted(k for k in styles_subset if k.startswith("paint_"))
    font_keys = sorted(k for k in styles_subset if k.startswith("font_"))
    effect_keys = sorted(k for k in styles_subset if k.startswith("effect_"))

    image_total = len(bitmaps) + len(node_svgs) + len(section_svgs)

    # --- 统计 resolved 节点数 ---
    def count_resolved(n):
        c = 1
        for child in n.get("children", []):
            c += count_resolved(child)
        return c

    result = {
        "meta": {
            "moduleIndex": index,
            "moduleId": node.get("id", ""),
            "moduleName": name,
            "slug": slug,
            "fileName": f"{index:02d}-{slug}.json",
            "position": {"x": module_pos[0], "y": module_pos[1],
                         "width": layout.get("width") or 0, "height": layout.get("height") or 0},
            "nodeCount": len(node_ids),
            "resolvedNodeCount": count_resolved(resolved_tree),
            "textCount": count_text_nodes(node),
            "textsResolved": texts_resolved,
            "sectionIndexes": [s["sectionIndex"] for s in module_sections],
            "styleCounts": {
                "paints": len(paint_keys),
                "fonts": len(font_keys),
                "effects": len(effect_keys),
            },
            "assetCounts": {
                "bitmaps": len(bitmaps),
                "svgs": len(all_svgs),
                "d2cSvgIcons": len(d2c_block["svgIcons"]) if d2c_block else 0,
                "d2cExportImages": len(d2c_block["exportImages"]) if d2c_block else 0,
            },
            "imageCount": image_total,
            "d2cMatched": d2c_block is not None,
            "d2cMatchDistance": d2c_match_dist,
            "d2cNodeCssCount": len(d2c_node_css_map),
            "missingStyleRefs": missing,
        },
        "sections": module_sections,
        "assets": {
            "bitmaps": bitmaps,
            "svgs": all_svgs,
        },
        "node": resolved_tree,
    }
    if d2c_block is not None:
        result["d2c"] = d2c_block
    return result


# ============================================================================
# 主流程
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="按层级树拆分业务模块并提取完整设计数据")
    parser.add_argument("--check", action="store_true", help="只校验输入，不产出")
    parser.add_argument("--dry-run", action="store_true", help="打印模块概要，不写文件")
    parser.add_argument("--raw-dir", type=str, default=None, help="原始数据目录")
    args = parser.parse_args()

    global RAW_DIR
    if args.raw_dir:
        RAW_DIR = Path(args.raw_dir)

    print("=" * 60)
    print("split_modules — 层级树 -> 业务模块完整设计数据")
    print("=" * 60)

    config = load_config()
    print(f"\n  项目: {config.get('projectName', 'unknown')}")

    # --- 1. 校验 ---
    print("\n[1/4] 校验输入数据...")
    dsl_ok = (RAW_DIR / "01-getDsl" / "getDsl.json").exists()
    print(f"  {'[OK]' if dsl_ok else '[MISS]'} getDsl")
    if not dsl_ok:
        print("\n  [ERR] getDsl 是必须的数据源。", file=sys.stderr)
        sys.exit(1)

    if args.check:
        print("\n  [DONE] --check 模式：输入校验完成。")
        return

    # --- 2. 加载 ---
    print("\n[2/4] 加载数据源...")
    dsl = load_get_dsl()
    assert dsl is not None
    all_styles = dsl.get("styles", {})
    root_nodes = dsl.get("nodes", [])
    if not root_nodes:
        print("\n  [ERR] getDsl 中无 nodes。", file=sys.stderr)
        sys.exit(1)
    root = root_nodes[0]
    module_children = root.get("children", [])
    section_overview = load_section_overview()
    texts_map = load_texts()
    extract_svgs = load_extract_svgs()
    design_svgs = load_design_svgs()
    d2c_payload = load_d2c_payload()
    d2c_fragments, d2c_page = ([], {})
    if d2c_payload is not None:
        d2c_fragments, d2c_page = parse_d2c_fragments(d2c_payload)
    d2c_used: set = set()

    print(f"  样式定义: {len(all_styles)}")
    print(f"  根节点:   {root.get('id')} {root.get('name')}")
    print(f"  直接子节点(模块数): {len(module_children)}")
    print(f"  分段概览: {len(section_overview)}  文本替换表: {len(texts_map)}")
    print(f"  extractSvg: {len(extract_svgs)} 节点  getDesignSvgs: {len(design_svgs)} 节点")
    page_w = d2c_page.get("width") or 0
    page_h = d2c_page.get("height") or 0
    design_scale = detect_design_scale(page_w, page_h) if page_w > 0 else {"scale": 1, "logicalWidth": page_w, "logicalHeight": page_h, "nativeWidth": page_w, "nativeHeight": page_h, "label": "unknown"}
    print(f"  D2C: {'有' if d2c_payload else '无'}  顶层片段: {len(d2c_fragments)}"
          f"  页面: {page_w}x{page_h}")
    if design_scale["scale"] > 1:
        print(f"  设计缩放: {design_scale['label']}  →  逻辑尺寸: {design_scale['logicalWidth']}x{design_scale['logicalHeight']}")

    # --- 3. 提取模块 ---
    print("\n[3/4] 提取模块...")
    modules = []
    for i, child in enumerate(module_children):
        mod = extract_module(child, i, all_styles, section_overview, texts_map,
                             extract_svgs, design_svgs, d2c_fragments, d2c_used, d2c_payload)
        modules.append(mod)
        m = mod["meta"]
        secs = m["sectionIndexes"]
        sec_str = f"sec {min(secs)}-{max(secs)}" if secs else "无分段"
        a = m["assetCounts"]
        d2c_str = f"D2C✓(d={m['d2cMatchDistance']})" if m["d2cMatched"] else "D2C✗"
        print(
            f"  [{i:02d}] {m['fileName']:<28} "
            f"节点{m['nodeCount']:>3} 文本{m['textCount']:>2} "
            f"位图{a['bitmaps']:>2} svg{a['svgs']:>2} "
            f"图标{a['d2cSvgIcons']:>2}  {d2c_str}  {sec_str}"
        )
        if m["missingStyleRefs"]:
            print(f"       [WARN] 缺失样式引用 {len(m['missingStyleRefs'])} 个: {m['missingStyleRefs'][:5]}")

    unmatched = [f for i, f in enumerate(d2c_fragments) if i not in d2c_used]
    if unmatched:
        print(f"  [WARN] 有 {len(unmatched)} 个 D2C 顶层片段未匹配到模块")

    total_nodes = sum(m["meta"]["nodeCount"] for m in modules)
    total_texts = sum(m["meta"]["textCount"] for m in modules)
    total_images = sum(m["meta"]["imageCount"] for m in modules)
    print(f"\n  合计: {len(modules)} 模块 / {total_nodes} 节点 / {total_texts} 文本 / {total_images} 图片资源")

    if args.dry_run:
        print("\n  [DONE] --dry-run 模式：未写入文件。")
        return

    # --- 4. 写入 ---
    print("\n[4/4] 写入输出文件...")
    MODULES_DIR.mkdir(parents=True, exist_ok=True)

    for mod in modules:
        out_path = MODULES_DIR / mod["meta"]["fileName"]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(mod, f, ensure_ascii=False, indent=2)
        size_kb = out_path.stat().st_size / 1024
        print(f"  {out_path.name:<28} {size_kb:>7.1f} KB")

    manifest = load_json(RAW_DIR / "_capture-manifest.json") or {}
    index_doc = {
        "meta": {
            "projectName": config.get("projectName", "unknown"),
            "fileId": manifest.get("fileId", ""),
            "layerId": manifest.get("layerId", ""),
            "rootNodeId": root.get("id", ""),
            "rootNodeName": root.get("name", ""),
            "splitAt": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "moduleCount": len(modules),
            "totalNodes": total_nodes,
            "totalTexts": total_texts,
            "totalImages": total_images,
            "page": d2c_page,
            "designScale": design_scale,
            "d2cUnmatchedFragments": len(unmatched),
        },
        "modules": [
            {
                "fileName": m["meta"]["fileName"],
                "moduleIndex": m["meta"]["moduleIndex"],
                "moduleId": m["meta"]["moduleId"],
                "moduleName": m["meta"]["moduleName"],
                "slug": m["meta"]["slug"],
                "position": m["meta"]["position"],
                "nodeCount": m["meta"]["nodeCount"],
                "textCount": m["meta"]["textCount"],
                "imageCount": m["meta"]["imageCount"],
                "assetCounts": m["meta"]["assetCounts"],
                "d2cMatched": m["meta"]["d2cMatched"],
                "sectionIndexes": m["meta"]["sectionIndexes"],
            }
            for m in modules
        ],
    }
    index_path = MODULES_DIR / "_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index_doc, f, ensure_ascii=False, indent=2)
    print(f"  {index_path.name:<28} {index_path.stat().st_size / 1024:>7.1f} KB")

    print("\n" + "=" * 60)
    print(f"[DONE] 拆分完成，共 {len(modules)} 个模块 -> {MODULES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    import argparse as _ap
    _parser = _ap.ArgumentParser(add_help=False)
    _parser.add_argument("--project", required=True, help="Project name (e.g. huaxia-hot-citc)")
    _pargs, _ = _parser.parse_known_args()
    PROJECT_DIR = SKILL_ROOT / "data" / _pargs.project
    RAW_DIR = PROJECT_DIR / "raw"
    MODULES_DIR = PROJECT_DIR / "modules"
    CONFIG_PATH = PROJECT_DIR / "config" / "project.config.json"
    main()

#!/usr/bin/env python3
"""
css_core.py —— 把模块 JSON 里的单个节点转成 CSS（唯一核心，import-only）。

取值原则（已与用户确认）：
  - getDsl 解析出的字段为唯一基底，绝大多数 CSS 属性都从这里算。
  - 只有 getDsl 结构上根本给不出的 3 个属性（mix-blend-mode / overflow / object-fit）
    才从同一个节点的 d2cCss 里补（数据本就在模块 JSON 中，非外部对账）。
  - 定位用 getDsl 原生绝对 px：根节点 position:relative 作定位上下文，
    后代 position:absolute + left/top = relativeX/relativeY。

不产 CSS（只出定位盒子）的东西：
  - PATH 的 path[].data / 渐变（走内联 SVG，不是 CSS）
  - mask=alpha/outline（由导出资源实现，CSS 表达不了）
这些节点仍会得到 position/size 规则，视觉部分留给资源。

对外接口：
  node_to_css(node, *, is_root=False, z_index=None) -> dict[str,str]   # getDsl 基底
  d2c_supplement(node) -> dict[str,str]                                # 只补那 3 个
  node_css_full(node, **kw) -> dict[str,str]                           # 基底 + 补充
  css_class(node_id) -> str                                           # 0:921 -> n-0-921
  PROP_ORDER                                                          # 属性输出顺序
"""

import re
import math

# getDsl 结构上给不出、只能从 d2cCss 借的 3 个属性
D2C_SUPPLEMENT_PROPS = ("mix-blend-mode", "overflow", "object-fit")

# CSS 属性输出顺序（可读性：定位 -> 盒子 -> 视觉 -> 文本）
PROP_ORDER = [
    "position", "left", "top", "right", "bottom", "z-index",
    "width", "height", "box-sizing",
    "transform", "transform-origin",
    "opacity", "mix-blend-mode", "overflow",
    "background-color", "background-image", "background-size", "background-repeat",
    "object-fit",
    "border", "border-radius",
    "box-shadow", "filter", "backdrop-filter",
    "font-family", "font-size", "font-weight", "font-style",
    "line-height", "letter-spacing", "text-align", "white-space",
    "text-decoration", "text-transform", "text-shadow",
    "-webkit-text-stroke",
    "color",
    "-webkit-background-clip", "background-clip",
    "-webkit-text-fill-color", "text-fill-color",
]


# ============================================================================
# 数值/颜色格式化
# ============================================================================

def _num(v, ndigits=2) -> str:
    """浮点转紧凑字符串：整数去小数点，否则去尾零。"""
    f = round(float(v), ndigits)
    if f == int(f):
        return str(int(f))
    return f"{f:.{ndigits}f}".rstrip("0").rstrip(".")


def fmt_px(v, ndigits=2) -> str | None:
    """数字 -> '123px' / '12.5px'。"""
    if v is None:
        return None
    return _num(v, ndigits) + "px"


def _is_number(s) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def _round_px_token(s: str, ndigits=2) -> str:
    """'0.699999px' -> '0.7px'；非 px 原样返回。"""
    if not isinstance(s, str):
        return s
    m = re.match(r"^(-?[\d.]+)px$", s.strip())
    return _num(m.group(1), ndigits) + "px" if m else s.strip()


def _round_px_in_str(s: str, ndigits=2) -> str:
    """把字符串里所有小数四舍五入（用于 border-radius 多值）。"""
    return re.sub(r"-?\d+\.\d+", lambda m: _num(m.group(0), ndigits), s)


def sanitize_gradient(s: str) -> str:
    """修 MasterGo 导出的损坏渐变：rgba(...,NaN) / 'NaN%' 里的 NaN。
    （node 级 fill 目前无 NaN，NaN 只出现在 PATH 的 path[].fill；此处仍防御性处理。）"""
    if "NaN" not in s:
        return s
    s = re.sub(r",\s*NaN\s*\)", ", 1)", s)   # 透明度 NaN -> 1（可见）
    s = s.replace("NaN%", "0%")               # 色标位置 NaN% -> 0%
    s = s.replace("NaN", "0")                 # 兜底
    return s


def fmt_color(c: str) -> str:
    """颜色值直取（已是 #hex 或 rgba()）。"""
    return c.strip()


def _is_gradient(s: str) -> bool:
    return isinstance(s, str) and s.lstrip().startswith(
        ("linear-gradient", "radial-gradient", "conic-gradient")
    )


# ============================================================================
# 分块：fill / effect / stroke / font
# ============================================================================

def _single_fill_to_css(fill) -> dict:
    """单层 fill -> CSS background 属性（不含多值列表逻辑）。"""
    if isinstance(fill, dict) and fill.get("type") == "IMAGE" and fill.get("url"):
        return {
            "background-image": f"url({fill['url']})",
            "background-size": "cover",
            "background-repeat": "no-repeat",
        }
    if isinstance(fill, str):
        if _is_gradient(fill):
            return {"background-image": sanitize_gradient(fill)}
        return {"background-color": fmt_color(fill)}
    return {}


def fill_to_css(fill) -> dict:
    """非 TEXT 节点的 fill -> background*。TEXT 的颜色走 font_color_css。

    MasterGo 的 fill 可有多层叠加。经 raw getDsl 核对：fill 数组为 [顶,…,底]
    （index 0 = 最上层，末尾 = 最底层），与 CSS background 的层序一致
    （第一个逗号分隔值 = 顶层）。故按数组原序拼接，不倒序。
    （典型案例：产品卡 0:1369 fill=[蓝白渐变, 暖白渐变]，蓝白在上；若倒序则
    不透明暖白盖住蓝白，卡片错误地显偏黄。）
    """
    if fill is None:
        return {}
    # 单值：直接处理（最常见路径）
    if not isinstance(fill, list):
        return _single_fill_to_css(fill)
    if not fill:
        return {}
    # 多值：fill [顶,…,底] 与 CSS background [顶,…,底] 同序，直接顺序拼接
    images = []
    sizes = []
    repeats = []
    bg_color = None
    for layer in fill:  # 顶 -> 底
        css = _single_fill_to_css(layer)
        if "background-color" in css:
            bg_color = css["background-color"]  # 迭代到底，最后一个纯色 = 最底层，作 background-color
        if "background-image" in css:
            images.append(css["background-image"])
            sizes.append(css.get("background-size", "auto"))
            repeats.append(css.get("background-repeat", "repeat"))
    result = {}
    if bg_color:
        result["background-color"] = bg_color
    if images:
        result["background-image"] = ", ".join(images)
        # 只有至少一层需要特定尺寸/重复方式时才输出（避免无意义的 auto, auto / repeat, repeat）
        if any(s != "auto" for s in sizes):
            result["background-size"] = ", ".join(sizes)
        if any(r != "repeat" for r in repeats):
            result["background-repeat"] = ", ".join(repeats)
    return result


def _decl_value(s: str) -> str:
    """'box-shadow: 0px 1px 0px #FFF;' -> '0px 1px 0px #FFF'。"""
    v = s.split(":", 1)[1] if ":" in s else s
    return v.strip().rstrip(";").strip()


def _boxshadow_to_textshadow(value: str) -> str:
    """box-shadow 值 -> text-shadow 值：去掉 inset 与第 4 个 spread。
    '0px 1px 0px 0px #FFFFFF' -> '0px 1px 0px #FFFFFF'。"""
    value = re.sub(r"^\s*inset\s+", "", value)
    m = re.match(r"^\s*((?:-?[\d.]+px?\s*){2,4})(.*)$", value)
    if not m:
        return value.strip()
    lengths = m.group(1).split()
    color = m.group(2).strip()
    if len(lengths) == 4:          # 有 spread，text-shadow 不支持 -> 丢弃
        lengths = lengths[:3]
    return (" ".join(lengths) + (" " + color if color else "")).strip()


def effect_to_css(effect, is_text: bool) -> dict:
    """effect{boxShadow[],filter[],backdropFilter[]} -> CSS。
    TEXT 节点的 boxShadow 实为 text-shadow（D2C 印证）。"""
    if not isinstance(effect, dict):
        return {}
    out = {}
    box = [_decl_value(x) for x in (effect.get("boxShadow") or [])]
    if box:
        if is_text:
            out["text-shadow"] = ", ".join(_boxshadow_to_textshadow(v) for v in box)
        else:
            out["box-shadow"] = ", ".join(box)
    filt = [_decl_value(x) for x in (effect.get("filter") or [])]
    if filt:
        out["filter"] = ", ".join(filt)
    back = [_decl_value(x) for x in (effect.get("backdropFilter") or [])]
    if back:
        out["backdrop-filter"] = ", ".join(back)
    return out


def stroke_to_css(node, is_text: bool) -> dict:
    """有 strokeColor + strokeWidth 才成边框。TEXT -> text-stroke，其余 -> border。"""
    sc = node.get("strokeColor")
    sw = node.get("strokeWidth")
    if not sc or not sw:
        return {}
    w = _round_px_token(sw)
    if is_text:
        return {"-webkit-text-stroke": f"{w} {fmt_color(sc)}"}
    out = {"border": f"{w} {node.get('strokeType') or 'solid'} {fmt_color(sc)}"}
    if node.get("strokeAlign") == "inside":
        out["box-sizing"] = "border-box"
    return out


def _font_color_css(color) -> dict:
    """TEXT run 颜色 -> CSS。渐变文字用 background-clip:text 三件套。"""
    if not color:
        return {}
    if _is_gradient(color):
        return {
            "background-image": sanitize_gradient(color),
            "-webkit-background-clip": "text",
            "background-clip": "text",
            "-webkit-text-fill-color": "transparent",
            "text-fill-color": "transparent",
        }
    return {"color": fmt_color(color)}


# MasterGo font.case -> text-transform
_CASE_MAP = {"upper": "uppercase", "lower": "lowercase", "title": "capitalize"}


def font_to_css(node) -> dict:
    """TEXT 节点 textRuns[0].font + 颜色 + 对齐 -> CSS。"""
    runs = node.get("textRuns") or []
    if not runs:
        out = {}
    else:
        font = runs[0].get("font") or {}
        out = {}
        if font.get("family"):
            out["font-family"] = font["family"]
        if font.get("size") is not None:
            out["font-size"] = fmt_px(font["size"])
        # line-height："-1" = auto -> normal；数字 -> px
        lh = font.get("lineHeight")
        if lh in (None, "-1", -1):
            out["line-height"] = "normal"
        elif _is_number(lh):
            out["line-height"] = fmt_px(lh)
        else:
            out["line-height"] = str(lh)
        # letter-spacing："auto" -> normal
        ls = font.get("letterSpacing")
        if ls in (None, "auto"):
            out["letter-spacing"] = "normal"
        else:
            out["letter-spacing"] = _round_px_token(ls)
        # 装饰 / 大小写
        dec = font.get("decoration")
        if dec and dec != "none":
            out["text-decoration"] = dec
        case = font.get("case")
        if case and case != "none":
            out["text-transform"] = _CASE_MAP.get(case, case)
        # 字重：font.style 观测值恒为 "0"（regular），仅当是合法字重数字才输出
        st = font.get("style")
        if st is not None and str(st).isdigit() and 100 <= int(st) <= 900:
            out["font-weight"] = str(int(st))
        # 颜色
        out.update(_font_color_css(runs[0].get("color")))
        # 单行判定 -> nowrap：设计框高 <= 行高单位×1.6 视为单行文本，
        # 防止浏览器缺字体回退到更宽字体后把末尾字符挤到下一行（如产品全称的 "C"）。
        h = (node.get("layoutStyle") or {}).get("height")
        fs = font.get("size")
        if h is not None and fs:
            lh_css = out.get("line-height")
            if isinstance(lh_css, str) and lh_css.endswith("px"):
                line_unit = float(lh_css[:-2])
            else:  # normal/auto：CJK 自动行高约 1.4×字号
                line_unit = float(fs) * 1.4
            if float(h) <= line_unit * 1.6:
                out["white-space"] = "nowrap"
    if node.get("textAlign"):
        out["text-align"] = node["textAlign"]
    return out


# ============================================================================
# 主接口
# ============================================================================

def node_to_css(node, *, is_root=False, z_index=None) -> dict:
    """把单个节点转成 CSS 属性字典（getDsl 基底）。"""
    css: dict[str, str] = {}
    is_text = node.get("type") == "TEXT"
    layout = node.get("layoutStyle") or {}

    # --- 定位 ---
    css["position"] = "relative" if is_root else "absolute"
    if not is_root:
        css["left"] = fmt_px(layout.get("relativeX") or 0)
        css["top"] = fmt_px(layout.get("relativeY") or 0)
    css["width"] = fmt_px(layout.get("width") or 0)
    css["height"] = fmt_px(layout.get("height") or 0)
    # 坑B：纯结构容器若子树含 mix-blend-mode 节点，则不发 z-index。
    # 定位元素带 z-index 会形成独立层叠上下文，把内部 blend 图层隔离在组内，
    # 使其无法与容器外的图层混合（头图"光"层 screen 混不到页面蓝 → 发黑）。
    # 只有"结构组 + 子树含 blend"才抑制，避免打乱其它组的层序（如 0:947 分享保留）。
    if z_index is not None and not (
        _is_structural_container(node) and _subtree_has_blend(node)
    ):
        css["z-index"] = str(z_index)

    # --- 旋转 ---
    rot = layout.get("rotate") or 0
    rot_x = layout.get("rotateX") or 0
    if rot or rot_x:
        parts = []
        if rot:
            parts.append(f"rotate({_num(rot)}deg)")
        if rot_x:
            parts.append(f"rotateX({_num(rot_x)}deg)")
        css["transform"] = " ".join(parts)
        # 180° 倍数的旋转（如编组8的对称装饰）：用 center 作 transform-origin，
        # 使元素在原位翻转，视觉位置不变。非 180° 倍数的旋转（如矩形旋转 45°
        # 做菱形）保持 0 0，让元素绕自身左上角旋转。
        if abs(rot) % 180 == 0 and abs(rot) % 360 != 0:
            css["transform-origin"] = "center"
        else:
            css["transform-origin"] = "0 0"

    # --- 透明度 ---
    if node.get("opacity") is not None:
        css["opacity"] = _num(node["opacity"], 3)

    # --- 填充（非 TEXT）---
    if not is_text:
        css.update(fill_to_css(node.get("fill")))

    # --- 效果（阴影/模糊）---
    css.update(effect_to_css(node.get("effect"), is_text))

    # --- 圆角 ---
    if node.get("borderRadius"):
        css["border-radius"] = _round_px_in_str(node["borderRadius"])
    elif node.get("type") == "SVG_ELLIPSE":
        # SVG_ELLIPSE 是椭圆/圆形元素，必须 border-radius:50% 才能正确渲染；
        # 否则仅凭 background-color 只会显示为正方形/长方形。
        css["border-radius"] = "50%"

    # --- 描边 ---
    css.update(stroke_to_css(node, is_text))

    # --- 文本 ---
    if is_text:
        css.update(font_to_css(node))

    return css


def d2c_supplement(node) -> dict:
    """只从 d2cCss 取 getDsl 给不出的 3 个属性（非空时）。"""
    d2c = node.get("d2cCss") or {}
    out = {}
    for prop in D2C_SUPPLEMENT_PROPS:
        v = d2c.get(prop)
        if v is not None:
            out[prop] = v
    return out


def _apply_d2c_rotate_position(node, css) -> dict:
    """坑C：带真旋转的节点用 d2c 权威定位/变换覆盖 raw 计算值。

    css_core 裸用 relativeX/Y 当 left/top，对旋转节点**没补偿旋转位移**，且会把
    layoutStyle.rotateX 盲加成 rotateX(180deg)。d2c（MasterGo 自己的 design-to-code）
    的 transform/left/top 已经补偿了旋转、也不含多余的 rotateX，是正确渲染的标准答案。

    触发判据：d2cCss.transform 非空——只有"真旋转位图/手"(0:935/0:1317/0:1380)符合。
    45°菱形、180°编组8、-46°年份文字的 d2c.transform 为 None → 不触发，保留 css_core
    的 raw-px + transform-origin 逻辑（已由 rules #3 验证正确，不可动）。
    """
    d2c = node.get("d2cCss") or {}
    if not d2c.get("transform"):
        return css
    for k in ("left", "top", "transform", "transform-origin"):
        if d2c.get(k) is not None:
            css[k] = d2c[k]
    return css


def node_css_full(node, **kw) -> dict:
    """getDsl 基底 + d2c 补充（补充只加键，不覆盖基底）。"""
    css = node_to_css(node, **kw)
    for k, v in d2c_supplement(node).items():
        css.setdefault(k, v)
    css = _apply_d2c_rotate_position(node, css)
    return css


def css_class(node_id: str) -> str:
    """0:921 -> n-0-921。"""
    return "n-" + node_id.replace(":", "-")


def has_mask_child(node: dict) -> bool:
    """检查节点的直接子节点中是否存在蒙版（mask=outline/alpha）。"""
    return any(c.get("mask") for c in node.get("children", []))


def _is_structural_container(node: dict) -> bool:
    """纯结构容器：FRAME/GROUP 且自身无任何视觉（fill/effect/opacity/mask/hasSvg）。
    这类节点只是用来分组子节点，本身不该产生独立的层叠上下文。"""
    return (
        node.get("type") in ("FRAME", "GROUP")
        and not node.get("fill")
        and not node.get("effect")
        and node.get("opacity") is None
        and not node.get("mask")
        and not node.get("hasSvg")
    )


def _subtree_has_blend(node: dict) -> bool:
    """子树内是否存在带 mix-blend-mode 的节点（blend 来源为 d2cCss）。
    带 mix-blend-mode 的图层需要与容器**外部**的图层混合（如头图"光"层与页面蓝底
    做 screen），若被祖先容器的 z-index 层叠上下文隔离，混合就失效（发黑）。"""
    d2c = node.get("d2cCss") or {}
    if d2c.get("mix-blend-mode"):
        return True
    return any(_subtree_has_blend(c) for c in node.get("children", []))


def subtree_has_layer(node: dict) -> bool:
    """子树里是否含 LAYER 节点。
    LAYER 节点的视觉（边框、背景色、阴影）完全通过 CSS 渲染，不会被烘焙进父级 SVG。
    若父帧是 hasSvg，其 SVG 中不包含 LAYER 子节点的视觉内容，
    因此不能作为 full-bake leaf 跳过 LAYER 子孙。"""
    if node.get("type") == "LAYER":
        return True
    return any(subtree_has_layer(c) for c in node.get("children", []))


def _extract_corner_radius_from_mask_path(node: dict) -> str | None:
    """从蒙版 PATH 节点的第一个子路径中提取圆角半径。

    蒙版 path 如果是圆角矩形，其 data 通常形如：
      M{R},0 L{W-R},0 C{...} ... Z
    其中 R ≈ 圆角半径。提取 M 命令后的 X 坐标作为 border-radius 近似值。
    只处理简单情况：path[0].data 以 'M{num},' 或 'M{num} ' 开头。
    失败或非矩形蒙版返回 None。"""
    path_list = node.get("path")
    if not path_list or not isinstance(path_list, list):
        return None
    first_path = path_list[0]
    if not isinstance(first_path, dict):
        return None
    data = first_path.get("data", "")
    if not data:
        return None
    # 匹配开头的 M{num},{num} 或 M{num} {num}
    m = re.match(r"^M\s*([\d.]+)\s*[,\s]\s*([\d.eE+-]+)", data)
    if not m:
        return None
    rx = float(m.group(1))
    ry = float(m.group(2))
    # 圆角矩形：左上角 M{R,0} 或 M{R,~0}
    if abs(ry) < 0.01 and rx > 0:
        return f"{_num(rx)}px"
    return None


# ============================================================================
# 内联 SVG 定位：按 viewBox 原点把 SVG 对齐回节点本地坐标
#   坑：MasterGo 导出的每段 SVG，viewBox 起点常常不是 (0,0)——它会把溢出节点框的
#   装饰（左耳朵、发光、超界贴片）也包进 viewBox，使 minX/minY 变成负数或较大正数。
#   若把 SVG 直接塞进节点 div 文档流（相当于摆在 div 的 0,0），viewBox 里的图形会整体
#   平移 (-minX,-minY)：minX≈0 的模块看不出问题，minX 大的（01 白卡 -31、02 药丸 +17/+42、
#   05 金勾 +105/+12）就会明显错位/被裁。
#   解法：给 <svg> 注入 position:absolute; left=minX*scale; top=minY*scale，使 viewBox
#   坐标 (X,Y) 落到节点本地 div 的 (X,Y)——与该节点子节点用的坐标系一致。scale 兜底处理
#   width/height 属性与 viewBox 尺寸不一致（本数据集恒为 1:1）的情形。
# ============================================================================

_SVG_OPEN_RE = re.compile(r"<svg\b[^>]*>", re.I)
_FLOAT = r"[-+]?(?:\d*\.?\d+)(?:[eE][-+]?\d+)?"
_VIEWBOX_RE = re.compile(
    rf'viewBox="\s*({_FLOAT})\s+({_FLOAT})\s+({_FLOAT})\s+({_FLOAT})\s*"'
)


def _svg_attr_num(tag: str, name: str):
    m = re.search(rf'\b{name}="\s*({_FLOAT})', tag)
    return float(m.group(1)) if m else None


def position_inline_svg(svg_text: str, *, z_index=None) -> str:
    """给内联 SVG 的 <svg> 注入定位样式，使其 viewBox 原点对齐节点本地坐标。
    z_index 非空时一并写入（用于被烘焙进父级 SVG 的前景图形的层级还原）。"""
    m = _SVG_OPEN_RE.search(svg_text)
    if not m:
        return svg_text
    tag = m.group(0)
    vb = _VIEWBOX_RE.search(tag)
    if not vb:
        return svg_text
    minx, miny, vbw, vbh = (float(x) for x in vb.groups())
    wpx = _svg_attr_num(tag, "width")
    hpx = _svg_attr_num(tag, "height")
    sx = (wpx / vbw) if (wpx and vbw) else 1.0
    sy = (hpx / vbh) if (hpx and vbh) else 1.0
    decls = [
        "position:absolute",
        f"left:{_num(minx * sx)}px",
        f"top:{_num(miny * sy)}px",
    ]
    if z_index is not None:
        decls.append(f"z-index:{z_index}")
    style = ";".join(decls)
    ms = re.search(r'style="', tag)
    if ms:
        new_tag = tag[: ms.end()] + style + ";" + tag[ms.end():]
    else:
        new_tag = tag[:-1] + f' style="{style}">'
    return svg_text[: m.start()] + new_tag + svg_text[m.end():]



# ============================================================================
# 内联 SVG 渐变修复
#   MasterGo 导出的内联 SVG 用了 SVG 不支持的写法：
#     <path fill="linear-gradient(180deg, #FFDA92 12%, #FFF1D4 99%)"/>
#   SVG 原生 fill 不认 CSS 渐变函数，必须转成 <defs> 里的
#   <linearGradient>/<radialGradient> + fill="url(#id)"。
#   本组函数在渲染层（generate_html.py 内联 SVG 前）调用，不改 data/modules。
# ============================================================================

# 匹配 fill="linear/radial-gradient(...)"，允许一层内嵌括号（吞下 rgba(...) 与 at X% Y%）
_GRAD_FILL_RE = re.compile(
    r'fill="((?:linear|radial)-gradient\((?:[^()]|\([^()]*\))*\))"'
)


def _split_top_level_commas(s: str) -> list:
    """按顶层逗号切分，括号内的逗号不切（rgba(...) 里的逗号要保留）。"""
    parts, depth, buf = [], 0, []
    for ch in s:
        if ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return parts


def _color_to_stop(color: str) -> tuple:
    """CSS 颜色 -> (stop-color, stop-opacity)。支持 #hex 与 rgba()/rgb()。"""
    color = color.strip()
    m = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", color)
    if m:
        r, g, b = m.group(1), m.group(2), m.group(3)
        a = m.group(4)
        rgb = f"rgb({_num(r,0)}, {_num(g,0)}, {_num(b,0)})"
        return rgb, (a if a is not None else "1")
    return color, "1"  # #hex 或具名色


def _parse_stops(stop_strs: list) -> list:
    """['#FFDA92 12%', 'rgba(...,0) 99%'] -> [(offset_str, stop-color, stop-opacity)]。
    位置缺省则按序号均匀补。"""
    parsed = []
    for seg in stop_strs:
        # 位置在末尾（形如 '12%' 或 '-9%'），颜色在前
        mpos = re.search(r"(-?[\d.]+%)\s*$", seg)
        if mpos:
            pos = mpos.group(1)
            color = seg[: mpos.start()].strip()
        else:
            pos = None
            color = seg.strip()
        parsed.append([pos, color])
    n = len(parsed)
    for i, item in enumerate(parsed):
        if item[0] is None:
            item[0] = f"{(100 * i / (n - 1)) if n > 1 else 0:.0f}%"
    out = []
    for pos, color in parsed:
        sc, so = _color_to_stop(color)
        out.append((pos, sc, so))
    return out


def _stops_svg(stops: list) -> str:
    return "".join(
        f'<stop offset="{off}" stop-color="{sc}" stop-opacity="{so}"/>'
        for off, sc, so in stops
    )


def _stop_color_to_rgb(sc: str):
    """SVG stop-color（'rgb(r, g, b)' 或 '#hex' 或具名）-> (r,g,b) float，或 None。"""
    m = re.match(r"rgb\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", sc)
    if m:
        return (float(m.group(1)), float(m.group(2)), float(m.group(3)))
    if sc.startswith("#"):
        h = sc.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) >= 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return None  # 具名色不插值


def _normalize_stops_range(stops: list) -> list:
    """把越界（<0% 或 >100%）的色标按线性插值重算到 [0%,100%]。

    坑：CSS 渐变允许 -10% / 110% 这类越界色标（语义=沿渐变线插值），但 SVG 的
    <stop offset> 只接受 [0,1]，浏览器对越界值直接"夹紧且保留端点颜色/透明度"，
    与 CSS 的插值语义不符。典型：CTA 按钮高光 fill=linear-gradient(180deg,
    #FFFFFF -10%, #ffffff00 56%)，-10% 被夹成 0% 且 opacity 仍=1 → 顶部满白偏硬，
    应为插值后的 ~0.85。此处在生成 SVG 前把越界色标插值回边界，保真还原。
    """
    parsed = []
    for off, sc, so in stops:
        try:
            pct = float(str(off).rstrip("%"))
        except (TypeError, ValueError):
            return stops  # 非百分比 offset，放弃处理
        try:
            op = float(so)
        except (TypeError, ValueError):
            op = 1.0
        parsed.append([pct, sc, op])
    if not parsed:
        return stops
    parsed.sort(key=lambda x: x[0])
    if parsed[0][0] >= 0 and parsed[-1][0] <= 100:
        return stops  # 无越界，原样返回

    def sample(t):
        if t <= parsed[0][0]:
            return parsed[0][1], parsed[0][2]
        if t >= parsed[-1][0]:
            return parsed[-1][1], parsed[-1][2]
        for i in range(len(parsed) - 1):
            a, b = parsed[i], parsed[i + 1]
            if a[0] <= t <= b[0]:
                frac = (t - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0.0
                ra, rb = _stop_color_to_rgb(a[1]), _stop_color_to_rgb(b[1])
                if ra and rb:
                    col = "rgb(%s, %s, %s)" % tuple(
                        _num(ra[k] + (rb[k] - ra[k]) * frac, 0) for k in range(3)
                    )
                else:
                    col = a[1]
                return col, a[2] + (b[2] - a[2]) * frac
        return parsed[-1][1], parsed[-1][2]

    kept = [s for s in parsed if 0 <= s[0] <= 100]
    if parsed[0][0] < 0 and not any(abs(s[0]) < 1e-9 for s in kept):
        c, o = sample(0.0)
        kept.append([0.0, c, o])
    if parsed[-1][0] > 100 and not any(abs(s[0] - 100) < 1e-9 for s in kept):
        c, o = sample(100.0)
        kept.append([100.0, c, o])
    kept.sort(key=lambda x: x[0])
    return [(f"{_num(p, 2)}%", c, _num(o, 4)) for p, c, o in kept]


def _linear_endpoints(angle_deg: float) -> tuple:
    """CSS 角度（0deg 向上、顺时针）-> SVG objectBoundingBox 端点 (x1,y1,x2,y2)。"""
    rad = angle_deg * math.pi / 180.0
    dx = math.sin(rad)
    dy = -math.cos(rad)  # SVG y 向下为正
    x1 = 0.5 - dx * 0.5
    y1 = 0.5 - dy * 0.5
    x2 = 0.5 + dx * 0.5
    y2 = 0.5 + dy * 0.5
    return (round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4))


def _gradient_to_def(grad: str, grad_id: str) -> str | None:
    """把单个 CSS 渐变字符串转成 <linearGradient>/<radialGradient> 定义。失败返回 None。"""
    grad = sanitize_gradient(grad.strip())
    m = re.match(r"(linear|radial)-gradient\((.*)\)\s*$", grad, re.S)
    if not m:
        return None
    kind, inner = m.group(1), m.group(2)
    args = _split_top_level_commas(inner)
    if not args:
        return None

    if kind == "linear":
        angle = 180.0  # CSS 默认 to bottom
        first = args[0].strip()
        ma = re.match(r"(-?[\d.]+)deg\s*$", first)
        if ma:
            angle = float(ma.group(1))
            stop_args = args[1:]
        elif first.startswith("to "):
            stop_args = args[1:]  # 'to ...' 方向暂按默认 180（样本中未出现）
        else:
            stop_args = args
        stops = _parse_stops(stop_args)
        stops = _normalize_stops_range(stops)
        x1, y1, x2, y2 = _linear_endpoints(angle)
        return (
            f'<linearGradient id="{grad_id}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">'
            f"{_stops_svg(stops)}</linearGradient>"
        )

    # radial：首段形如 '54% 20% at 34% 50%' 或 'circle at 50% 50%'
    first = args[0].strip()
    cx, cy, r = 0.5, 0.5, 0.5
    mat = re.search(r"at\s+(-?[\d.]+)%\s+(-?[\d.]+)%", first)
    if mat:
        cx = float(mat.group(1)) / 100.0
        cy = float(mat.group(2)) / 100.0
    msize = re.match(r"([\d.]+)%\s+([\d.]+)%", first)
    if msize:
        r = max(float(msize.group(1)), float(msize.group(2))) / 100.0
        stop_args = args[1:]
    elif mat or first.startswith(("circle", "ellipse")):
        stop_args = args[1:]
    else:
        stop_args = args
    stops = _parse_stops(stop_args)
    stops = _normalize_stops_range(stops)
    return (
        f'<radialGradient id="{grad_id}" cx="{round(cx,4)}" cy="{round(cy,4)}" r="{round(r,4)}">'
        f"{_stops_svg(stops)}</radialGradient>"
    )


def fix_svg_frame_fill(svg_text: str) -> str:
    """修复 SVG 边框路径的实心填充问题。

    坑：MasterGo 导出的表格边框 SVG，path 包含两个子路径（外框 + 内框），
    两者走向相同（同顺时针/逆时针）。SVG 默认 fill-rule="nonzero" 下，
    同向子路径不会形成"洞"，导致整个矩形被实心填充，遮住表格内部的所有内容。

    修复：对包含恰好 2 个子路径且有 solid fill（非渐变/透明/url）的 path，
    添加 fill-rule="evenodd"，使填充仅作用于边框区域。"""
    if not svg_text:
        return svg_text

    def _count_subpaths(d: str) -> int:
        # M/m 命令开新子路径；排除科学计数法里的 e 前面的情况
        m_count = len(re.findall(r'(?<![eE])[Mm][-\d.\s,]', d))
        # 兜底：至少算 1
        if m_count >= 2:
            return m_count
        # 用 Z/z 也能大致判定（一个子路径以 Z 结束，下一个以 M 开始）
        z_parts = re.split(r'[Zz]\s*', d)
        return len([p for p in z_parts if p.strip()])

    def _fix_path(m: re.Match) -> str:
        tag = m.group(0)
        if "fill-rule=" in tag:
            return tag
        d_match = re.search(r'd="([^"]*)"', tag)
        if not d_match:
            return tag
        subpaths = _count_subpaths(d_match.group(1))
        if subpaths != 2:
            return tag
        fill_match = re.search(r'fill="([^"]*)"', tag)
        if not fill_match:
            return tag
        fill_val = fill_match.group(1)
        if not fill_val or fill_val == "none" or "url(#" in fill_val:
            return tag
        if "gradient(" in fill_val:
            return tag
        if re.match(r'rgba?\s*\(\s*255\s*,\s*255\s*,\s*255', fill_val):
            return tag  # 白色/透明矩形不影响
        return tag.replace("<path ", '<path fill-rule="evenodd" ')

    return re.sub(r"<path\b[^>]*>", _fix_path, svg_text)


def fix_svg_thin_lines(svg_text: str) -> str:
    """给 SVG 根元素添加 shape-rendering="crispEdges"，确保细线（如表格
    0.5px 竖线分隔符）不会被浏览器抗锯齿渲染得看不见。

    坑：MasterGo 导出的表格/分隔线 SVG，path 用 fill 画矩形线条，经 matrix
    旋转后线宽常仅 0.5px。浏览器抗锯齿会把 0.5px 填色渲染成半透明，在浅色
    背景上几乎不可见（如合规提示表格二的竖线分隔符 0:1310）。
    crispEdges 会使细线吸附到整像素，保证最小可见线宽。"""
    if not svg_text:
        return svg_text
    if "shape-rendering=" in svg_text:
        return svg_text
    return re.sub(
        r"(<svg\b[^>]*)>",
        r'\1 shape-rendering="crispEdges">',
        svg_text,
        count=1,
    )


def inline_svg_fix_gradients(svg_text: str, *, uid_prefix: str) -> str:
    """把一段内联 SVG 里所有 fill="...gradient(...)" 换成 fill="url(#id)"，
    并把对应 <linearGradient>/<radialGradient> 注入 <defs>。
    uid_prefix 由调用方传节点 id（冒号转下划线），保证全页面 id 唯一。"""
    if not svg_text or "gradient(" not in svg_text:
        return svg_text

    defs_parts: list[str] = []
    seq = 0

    def repl(m):
        nonlocal seq
        grad = m.group(1)
        grad_id = f"grad_{uid_prefix}_{seq}"
        definition = _gradient_to_def(grad, grad_id)
        if definition is None:
            return m.group(0)  # 无法解析则保留原样
        defs_parts.append(definition)
        seq += 1
        return f'fill="url(#{grad_id})"'

    new_svg = _GRAD_FILL_RE.sub(repl, svg_text)
    if not defs_parts:
        return new_svg

    defs_block = "".join(defs_parts)
    # 已有 <defs> 则插到其末尾；否则在 <svg ...> 开标签后插入新 <defs>
    if "</defs>" in new_svg:
        return new_svg.replace("</defs>", defs_block + "</defs>", 1)
    m_svg = re.search(r"<svg\b[^>]*>", new_svg)
    if m_svg:
        insert_at = m_svg.end()
        return new_svg[:insert_at] + f"<defs>{defs_block}</defs>" + new_svg[insert_at:]
    return new_svg


# ============================================================================
# 内联 SVG 效果注入：把 PATH 子节点的 CSS filter(blur) 转成 SVG <filter>
#   坑：PATH 子节点的 effect（如 filter: blur(25.22px)）在 CSS 生成阶段正确输出，
#   但 CSS 只作用于空 div，PATH 的视觉完全由内联 SVG 承担。inline_svg_fix_gradients
#   只处理渐变，不处理 filter → 内联 SVG 的 path 缺少模糊效果，硬边形状破坏设计层次。
#   修复：扫描 hasSvg 帧的子节点，对带 blur 效果的 PATH 子节点，在 SVG 的 <defs> 中
#   生成 <filter>，并在对应 <path> 上引用。
# ============================================================================

_BLUR_RE = re.compile(r"blur\(([\d.]+)px\)")


def _path_count_for_child(child: dict) -> int:
    """子节点在父 SVG 中占据几个 <path>。mask 子节点占 2 个（outline+fill）；
    非 mask PATH 子节点占 1 个；其他（TEXT/LAYER/SVG_ELLIPSE/FRAME）占 0 个。"""
    if child.get("mask"):
        return 2
    if child.get("type") == "PATH":
        return 1
    return 0


def inject_svg_filters(svg_text: str, parent_node: dict) -> str:
    """对 hasSvg 帧的内联 SVG，注入子节点 effect.filter（blur）对应的 SVG <filter>。

    参数：
      svg_text:    已处理过渐变/细线/边框的 SVG 字符串
      parent_node: hasSvg 帧的 modules 节点（含 children 列表）

    返回注入 filter 后的 SVG 字符串；无 blur 子节点时返回原字符串。
    """
    if not svg_text or "<path " not in svg_text:
        return svg_text

    children = parent_node.get("children") or []
    if not children:
        return svg_text

    # 收集需要注入 filter 的子节点：{(svg_path_index, child_id, blur_px)}
    filters_needed: list[tuple[int, str, float]] = []
    path_idx = 0
    for child in children:
        n_paths = _path_count_for_child(child)
        if n_paths == 0:
            continue
        effect = child.get("effect")
        if isinstance(effect, dict):
            filter_list = effect.get("filter") or []
            for f in filter_list:
                m = _BLUR_RE.search(f)
                if m:
                    # 非 mask 子节点占 1 个 path，取其索引
                    if not child.get("mask"):
                        filters_needed.append((path_idx, child["id"], float(m.group(1))))
                    break  # 一个子节点只取第一个 blur
        path_idx += n_paths

    if not filters_needed:
        return svg_text

    # 生成 filter defs + path 序号映射
    filter_defs_parts: list[str] = []
    path_filters: dict[int, str] = {}  # {0-based path index: filter_id}
    for svg_path_idx, child_id, blur_px in filters_needed:
        fid = child_id.replace(":", "_")
        filter_id = f"blur_{fid}"
        # 避免重复 defs
        if not any(f'id="{filter_id}"' in d for d in filter_defs_parts):
            filter_defs_parts.append(
                f'<filter id="{filter_id}">'
                f'<feGaussianBlur stdDeviation="{_num(blur_px)}"/>'
                f"</filter>"
            )
        path_filters[svg_path_idx] = filter_id

    # 注入 filter defs 到 defs 块末尾
    defs_block = "".join(filter_defs_parts)
    if "</defs>" in svg_text:
        svg_text = svg_text.replace("</defs>", defs_block + "</defs>", 1)
    else:
        m_svg = re.search(r"<svg\b[^>]*>", svg_text)
        if m_svg:
            insert_at = m_svg.end()
            svg_text = svg_text[:insert_at] + f"<defs>{defs_block}</defs>" + svg_text[insert_at:]

    # 给第 N 个 <path> 添加 filter 属性
    path_matches = list(re.finditer(r"<path\b[^>]*>", svg_text))
    for svg_path_idx, filter_id in sorted(path_filters.items(), reverse=True):
        if svg_path_idx < len(path_matches):
            m = path_matches[svg_path_idx]
            tag = m.group(0)
            if "filter=" not in tag:
                new_tag = tag[:-1] + f' filter="url(#{filter_id})">'
                svg_text = svg_text[: m.start()] + new_tag + svg_text[m.end():]

    return svg_text

#!/usr/bin/env python3
"""
generate_html.py —— 合并「现成模块 CSS + 模块 JSON 结构 + user-input」生成完整 H5。

分工（关键）：
  - 视觉样式：全部来自 assets/styles/modules/*.css（<link> 引入），本脚本不生成任何视觉 CSS。
  - DOM 结构 / 文本 / 内联 SVG：CSS 表达不了，来自 data/modules/*.json（node 树 + assets.svgs）。
  - 两者靠同名 class 对接：根 .m-{NN}-{slug}，其余 css_core.css_class(id)（0:937 -> n-0-937）。

本脚本只负责编排，产物落到 output/fund-h5/：
  index.html、css/*.css（含流式 page.css）、images/*、input-used.json

流式布局：模块按 _index.json 的 position.y 升序纵向排布，模块间 margin 由相邻 y 差算出，
上一个模块变高，后续模块靠 flow 自动下移。

用法：
  python scripts/render/generate_html.py               # 全量：下载图片 + 改写 URL + 生成
  python scripts/render/generate_html.py --no-download  # 跳过下载，CSS 保留远程 URL（快速预览）
  python scripts/render/generate_html.py --dry-run      # 只打印概要，不写文件、不下载
  python scripts/render/generate_html.py --check        # 只校验输入
"""

import sys
import re
import json
import shutil
import hashlib
import argparse
import html as html_mod
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# --- Windows 编码适配 ---
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_DIR = PROJECT_ROOT / "data" / "modules"
INDEX_PATH = MODULES_DIR / "_index.json"
CSS_SRC_DIR = PROJECT_ROOT / "assets" / "styles" / "modules"
USER_INPUT_PATH = PROJECT_ROOT / "data" / "input" / "user-input.json"
LIB_DIR = PROJECT_ROOT / "scripts" / "lib"
OUT_DIR = PROJECT_ROOT / "output" / "fund-h5"
OUT_CSS_DIR = OUT_DIR / "css"
OUT_IMG_DIR = OUT_DIR / "images"

sys.path.insert(0, str(LIB_DIR))
import css_core  # noqa: E402

URL_RE = re.compile(r"url\(\s*(['\"]?)(https?://[^)'\"]+)\1\s*\)")


# ============================================================================
# 加载
# ============================================================================

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def module_files() -> list[Path]:
    return sorted(p for p in MODULES_DIR.glob("*.json") if not p.name.startswith("_"))


# ============================================================================
# 图片：收集 -> 下载 -> URL 映射
# ============================================================================

def collect_css_urls(css_texts: list[str]) -> set[str]:
    urls: set[str] = set()
    for text in css_texts:
        for _, url in URL_RE.findall(text):
            urls.add(url)
    return urls


def local_name_for(url: str, used: set[str]) -> str:
    """URL 末段做文件名；重名加短 hash 前缀。"""
    base = Path(urlparse(url).path).name or "img"
    name = base
    if name in used:
        h = hashlib.md5(url.encode("utf-8")).hexdigest()[:6]
        stem, dot, ext = base.partition(".")
        name = f"{stem}-{h}{dot}{ext}"
    used.add(name)
    return name


def download_images(urls: set[str]) -> tuple[dict[str, str], list[str]]:
    """下载到 OUT_IMG_DIR，返回 ({url: 'images/name'}, [失败 url])。"""
    mapping: dict[str, str] = {}
    failures: list[str] = []
    used: set[str] = set()
    OUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    for url in sorted(urls):
        name = local_name_for(url, used)
        dest = OUT_IMG_DIR / name
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                dest.write_bytes(resp.read())
            mapping[url] = f"images/{name}"
            print(f"    [OK] {name}  <- {url[:60]}...")
        except Exception as e:  # noqa: BLE001
            failures.append(url)
            print(f"    [FAIL] {url[:70]}...  ({e})")
    return mapping, failures


def rewrite_css_urls(css_text: str, mapping: dict[str, str]) -> str:
    """把 CSS 里的远程 url() 换成本地相对路径（css/ 下引用 ../images/name）。"""
    def repl(m):
        url = m.group(2)
        local = mapping.get(url)
        if not local:
            return m.group(0)  # 未下载成功，保留远程
        return f"url(../{local})"
    return URL_RE.sub(repl, css_text)


# ============================================================================
# 节点树 -> HTML
# ============================================================================

def extract_text_runs(node: dict) -> list[dict]:
    return node.get("textRuns") or []


def _escape_text(txt: str) -> str:
    """HTML 转义文本，并将 \\n 转为 <br> 以保留多行布局（如表格单元格内的多行文本）。"""
    escaped = html_mod.escape(txt)
    return escaped.replace("\n", "<br>")


def render_text_inner(node: dict, override_text: str | None) -> str:
    """TEXT 节点内部 HTML：单 run 直出转义文本；多 run 每段 span（内联 color 承载混色）。"""
    if override_text is not None:
        return _escape_text(override_text)
    runs = extract_text_runs(node)
    if not runs:
        return _escape_text(node.get("text") or "")
    if len(runs) == 1:
        return _escape_text(runs[0].get("text") or "")
    parts = []
    for r in runs:
        txt = _escape_text(r.get("text") or "")
        color = r.get("color")
        if color and not css_core._is_gradient(color):
            parts.append(f'<span style="color:{color}">{txt}</span>')
        else:
            parts.append(f"<span>{txt}</span>")
    return "".join(parts)


def inline_style_from_override(override: dict) -> str:
    """variable-all 覆盖：width/height/fill/stroke -> 内联 style（覆盖外部 CSS）。"""
    if not override:
        return ""
    decls = []
    if override.get("width") is not None:
        decls.append(f"width:{css_core.fmt_px(override['width'])}")
    if override.get("height") is not None:
        decls.append(f"height:{css_core.fmt_px(override['height'])}")
    fill = override.get("fill")
    if fill:
        for k, v in css_core.fill_to_css(fill).items():
            decls.append(f"{k}:{v}")
    stroke = override.get("stroke") or {}
    if stroke.get("strokeColor") and stroke.get("strokeWidth"):
        w = css_core._round_px_token(stroke["strokeWidth"])
        decls.append(f"border:{w} {stroke.get('strokeType') or 'solid'} {stroke['strokeColor']}")
    return ";".join(decls)


def subtree_has_text(node: dict) -> bool:
    """子树里是否含 TEXT 节点。"""
    if node.get("type") == "TEXT":
        return True
    return any(subtree_has_text(c) for c in node.get("children", []))


def has_nested_hassvg(node: dict, svgs: dict) -> bool:
    """子孙里是否含在 svgs 中注册的 hasSvg 节点（即嵌套的独立矢量层）。"""
    for c in node.get("children", []):
        if c.get("hasSvg") and c.get("id") in svgs:
            return True
        if has_nested_hassvg(c, svgs):
            return True
    return False


def _node_path_fragment(node: dict) -> str | None:
    """取 path[0].data 的一小段（[15:50]）做指纹，用于判断是否已被祖先 SVG 烘焙。"""
    p = node.get("path")
    if isinstance(p, list) and p and isinstance(p[0], dict):
        d = p[0].get("data") or ""
        if len(d) >= 50:
            return d[15:50]
    return None


def _is_baked(node: dict, ancestor_svgs: tuple) -> bool:
    """节点的 path 指纹命中任一祖先 hasSvg 的 SVG 字符串 -> 该图形已被烘焙。"""
    frag = _node_path_fragment(node)
    return bool(frag) and any(frag in s for s in ancestor_svgs)


def _subtree_has_layer(node: dict) -> bool:
    """子树里是否含 LAYER 节点。
    LAYER 节点视觉完全通过 CSS 渲染（边框/背景/阴影），不会被烘焙进父级 SVG。
    因此有 LAYER 子孙的 hasSvg 帧不能作为 full-bake leaf 跳过它们。"""
    if node.get("type") == "LAYER":
        return True
    return any(_subtree_has_layer(c) for c in node.get("children", []))


def _has_mask_child(node: dict) -> bool:
    """检查直接子节点中是否存在蒙版（mask=outline/alpha）。
    含蒙版的帧其 baked SVG 可能未正确应用蒙版裁剪效果（MasterGo SVG 导出
    不会把 outline mask 转成 clipPath），因此不能作为 full-bake leaf 跳过子孙。"""
    return any(c.get("mask") for c in node.get("children", []))


def _has_multi_value_fill(node: dict) -> bool:
    """检查节点是否有 MasterGo baked SVG 无法完整表达的多值填充。

    MasterGo 导出的 baked SVG 对每个 path 只保留一个 fill 值（通常是数组的最后
    一个）。当 PATH 节点的任一 path 的 fill 本身是一个包含 2+ 层的数组时，baked SVG
    会丢失除最后一层外的所有渐变/颜色层，导致渲染颜色与设计稿不一致。

    此时不能用 _is_baked 跳过该节点——必须渲染 CSS div（其 fill_to_css 已正确
    处理多值 background-image），CSS div 渲染在 baked SVG 之上，补全丢失的层。

    注意：只检查原始 path[].fill 是否为多值数组，不检查 node.fill。
    node.fill 可能因 split_modules 的多 path 合并变成数组（多个单值 path fill
    合并），这种合并数组不代表 baked SVG 丢失数据，不应触发本检查。
    """
    for p in (node.get("path") or []):
        pf = p.get("fill") if isinstance(p, dict) else None
        if isinstance(pf, list) and len(pf) >= 2:
            return True
    return False


def _merged_text_column_centers(node: dict, siblings: tuple, n_words: int):
    """用兄弟竖线分隔符的**真实 relativeX** 算合并文本每列的中心（相对文本框宽度的 %）。

    多词合并文本（如"费率低 品类全 策略优 服务好"）在设计稿里被竖线分隔成不等宽的列，
    每个词居中于自己那一列。竖线是本文本节点的**兄弟 PATH 节点**（同一父帧坐标系）。
    取落在文本横向范围内的窄高竖线，用它们把 [文本左, 文本右] 切成 n_words 段，各段取中心。

    只有当竖线数量恰为 n_words-1 时才返回列中心列表；否则返回 None（调用方不拆分，
    保持原文本，避免用等分占位近似——宁可不拆也不猜位置）。
    """
    layout = node.get("layoutStyle") or {}
    tx = layout.get("relativeX")
    tw = layout.get("width") or 0
    if tx is None or tw <= 0:
        return None
    seps = []
    for s in siblings:
        if s is node or s.get("type") != "PATH":
            continue
        sl = s.get("layoutStyle") or {}
        sw = sl.get("width") or 0
        sh = sl.get("height") or 0
        sx = sl.get("relativeX")
        if sx is None:
            continue
        # 竖线判据：窄（宽<2px）、高（高 > 宽×3）、且横向落在文本框范围内
        if sw < 2 and sh > sw * 3 and tx <= sx <= tx + tw:
            seps.append(sx + sw / 2.0)  # 用线条中心作列边界
    seps.sort()
    if len(seps) != n_words - 1:
        return None
    bounds = [tx] + seps + [tx + tw]
    return [((bounds[i] + bounds[i + 1]) / 2.0 - tx) / tw * 100.0 for i in range(n_words)]


def _wrap_color_span(color, text: str) -> str:
    esc = html_mod.escape(text)
    return f'<span style="color:{color}">{esc}</span>' if color else esc


def _colorize_by_textcolor(word: str, start_idx: int, text_color) -> str:
    """按 textColor 分段给 word 逐字上色，连续同色合并为一个 <span>。
    text_color: [{start,end,color}]（split_modules 已解析成 hex）；无则返回转义原文。
    start_idx: word 在原始文本中的起始字符索引（textColor 的 start/end 基于原始文本）。"""
    if not text_color:
        return html_mod.escape(word)

    def color_at(idx):
        for seg in text_color:
            s, e, c = seg.get("start"), seg.get("end"), seg.get("color")
            if s is not None and e is not None and s <= idx < e:
                # 只用纯色；渐变不能作 CSS color
                if isinstance(c, str) and not c.lstrip().startswith(
                    ("linear-gradient", "radial-gradient", "conic-gradient")
                ):
                    return c
                return None
        return None

    out, buf, cur = [], [], None
    for j, ch in enumerate(word):
        c = color_at(start_idx + j)
        if not buf:
            buf, cur = [ch], c
        elif c == cur:
            buf.append(ch)
        else:
            out.append(_wrap_color_span(cur, "".join(buf)))
            buf, cur = [ch], c
    if buf:
        out.append(_wrap_color_span(cur, "".join(buf)))
    return "".join(out)


def render_node(node: dict, svgs: dict, mod_input: dict, *, is_root: bool,
                root_class: str, ancestor_svgs: tuple = (),
                under_baked_leaf: bool = False, siblings: tuple = ()) -> str:
    nid = node.get("id", "")

    # 判据①：处于「full-bake leaf 帧」之下的子孙，整树已被那张 SVG 表达，跳过。
    if under_baked_leaf:
        return ""
    # 判据②：容器帧内的纯图形（子树无 TEXT）且 path 已被某祖先 SVG 烘焙 -> 跳过重复渲染。
    # 例外：节点有多值 fill（如 path[0].fill 为 2+ 层数组）-> 不能跳过。
    # MasterGo 的 baked SVG 每个 path 只保留单值 fill，多值中的其他层会丢失。
    # 此时必须渲染 CSS div（其 fill_to_css 已正确输出多层 background-image），
    # CSS div 渲染在 baked SVG 之上，补全丢失的渐变/颜色层。
    if (not is_root and node.get("type") != "TEXT"
            and not subtree_has_text(node)
            and not _has_multi_value_fill(node)
            and _is_baked(node, ancestor_svgs)):
        return ""

    cls = root_class if is_root else css_core.css_class(nid)
    override = mod_input.get(nid, {}) if not is_root else {}

    attrs = [f'class="{cls}"']
    style = inline_style_from_override(override)
    if style:
        attrs.append(f'style="{style}"')
    open_tag = f"<div {' '.join(attrs)}>"

    # TEXT：渲染文本内容（TEXT 不会同时是容器）
    if node.get("type") == "TEXT":
        override_text = override.get("text")
        inner = render_text_inner(node, override_text)  # None 时用节点自身 text
        # 多词合并文本拆分：单行、无换行、含 2+ 个空白分隔段时，拆为独立定位的 span，
        # 用兄弟竖线分隔符的**真实位置**把每段文字居中于对应列（如"费率低 品类全 策略优 服务好"）。
        # override 提供的也是同一合并串，一并处理。仅当竖线数量与词数匹配时才拆，
        # 否则保持原样（不用等分占位近似）。
        src_text = override_text if override_text is not None else (node.get("text") or "")
        is_single_line = node.get("textMode") == "single-line"
        if is_single_line and "\n" not in src_text:
            word_matches = list(re.finditer(r"\S+", src_text))
            words = [m.group() for m in word_matches]
            if 2 <= len(words) <= 6:
                layout = node.get("layoutStyle") or {}
                nw = layout.get("width") or 0
                nh = layout.get("height") or 0
                centers = _merged_text_column_centers(node, siblings, len(words))
                if nw > 0 and nh > 0 and centers is not None:
                    # override 未改文本时按 textColor 逐字上色；改了文本则索引可能错位，不上色
                    text_color = (node.get("textColor")
                                  if override_text in (None, node.get("text")) else None)
                    spans = []
                    for i, m in enumerate(word_matches):
                        word_html = _colorize_by_textcolor(m.group(), m.start(), text_color)
                        spans.append(
                            f'<span style="position:absolute;'
                            f'left:{css_core._num(centers[i])}%;top:0;'
                            f'transform:translateX(-50%);white-space:nowrap;'
                            f'text-align:center">'
                            f'{word_html}</span>'
                        )
                    inner = "".join(spans)
        return f"{open_tag}{inner}</div>"

    parts = []
    child_ancestor_svgs = ancestor_svgs
    child_under_leaf = False
    # hasSvg：内联整段 SVG 作为矢量层（内联前把非法的 fill="...gradient(...)"
    # 转成规范的 <defs>+url(#id)，否则渐变在浏览器里不渲染）。
    if node.get("hasSvg") and nid in svgs:
        this_svg = svgs[nid]
        fixed = css_core.inline_svg_fix_gradients(this_svg, uid_prefix=nid.replace(":", "_"))
        fixed = css_core.fix_svg_frame_fill(fixed)
        fixed = css_core.fix_svg_thin_lines(fixed)
        # 注入子节点 PATH 的 CSS filter(blur) 效果到 SVG（如按钮的椭圆形备份3 的 25px 模糊光晕）
        fixed = css_core.inject_svg_filters(fixed, node)
        # full-bake leaf：不含 TEXT、不含嵌套 hasSvg、不含 LAYER、不含蒙版子节点
        # → 其 SVG 已完整表达整树，子孙全跳过，
        # 该 SVG 就是本节点的整体背景，不需要额外 z-index（由节点 div 自身层级决定）。
        # LAYER 节点（矩形等）通过 CSS 边框/背景渲染，不在 baked SVG 中；
        # 含蒙版子节点时 baked SVG 可能未正确应用蒙版裁剪，都不能作为 leaf。
        is_leaf = (not subtree_has_text(node)
                   and not has_nested_hassvg(node, svgs)
                   and not _subtree_has_layer(node)
                   and not _has_mask_child(node))
        svg_z = None
        if not is_leaf:
            # 容器帧：MasterGo 常把「直接子矢量图形」烘焙进本帧 SVG（这些子节点随后会被
            # _is_baked 跳过）。这段 SVG 作为第一个子节点渲染会被后面带 z-index 的兄弟盖住，
            # 需按被烘焙子节点的最小子序号还原层级（如 02 药丸 z=3、05 金勾+分隔线 z=3）。
            baked_idx = [
                i for i, c in enumerate(node.get("children", []))
                if c.get("type") != "TEXT"
                and not subtree_has_text(c)
                and _is_baked(c, (this_svg,))
            ]
            if baked_idx:
                svg_z = min(baked_idx)
        parts.append(css_core.position_inline_svg(fixed, z_index=svg_z))
        child_ancestor_svgs = tuple(ancestor_svgs) + (this_svg,)
        if is_leaf:
            child_under_leaf = True

    for c in node.get("children", []):
        parts.append(render_node(
            c, svgs, mod_input, is_root=False, root_class="",
            ancestor_svgs=child_ancestor_svgs, under_baked_leaf=child_under_leaf,
            siblings=tuple(node.get("children", [])),
        ))

    return f"{open_tag}{''.join(parts)}</div>"


# ============================================================================
# 流式 page.css
# ============================================================================

def build_page_css(index: dict, ordered_mods: list[dict]) -> str:
    page = index.get("meta", {}).get("page", {})
    bg = page.get("background", "#FFFFFF")
    pw = css_core.fmt_px(page.get("width") or 375)
    ph = css_core.fmt_px(page.get("height") or 0)

    lines = [
        "/* page.css —— 页面骨架 + 模块流式定位（本文件由 generate_html.py 生成） */",
        "* { box-sizing: border-box; }",
        f"body {{ margin: 0; background: {bg}; }}",
        ".page {",
        "  position: relative;",
        f"  width: {pw};",
        f"  min-height: {ph};",
        "  margin: 0 auto;",
        f"  background: {bg};",
        "  display: flex;",
        "  flex-direction: column;",
        "  align-items: flex-start;",
        "  overflow: hidden;",
        "}",
    ]

    prev_bottom = 0.0
    for m in ordered_mods:
        pos = m["position"]
        gap = pos["y"] - prev_bottom
        cls = f"m-{m['moduleIndex']:02d}-{m['slug']}"
        lines.append(
            f".{cls} {{ margin-top: {css_core._num(gap)}px; "
            f"margin-left: {css_core._num(pos['x'])}px; }}"
        )
        prev_bottom = pos["y"] + pos["height"]

    return "\n".join(lines) + "\n"


# ============================================================================
# 组装
# ============================================================================

def build_index_html(ordered_mods: list[dict], bodies: dict[int, str]) -> str:
    links = ['  <link rel="stylesheet" href="css/page.css">']
    for m in ordered_mods:
        links.append(f'  <link rel="stylesheet" href="css/{m["fileName_stem"]}.css">')
    body_parts = [bodies[m["moduleIndex"]] for m in ordered_mods]
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "  <title>华夏热点速递 H5</title>\n"
        + "\n".join(links) + "\n"
        "</head>\n"
        "<body>\n"
        '  <div class="page">\n'
        + "\n".join(body_parts) + "\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ============================================================================
# 主流程
# ============================================================================

def main():
    ap = argparse.ArgumentParser(description="合并模块CSS+JSON+user-input 生成 H5")
    ap.add_argument("--check", action="store_true", help="只校验输入")
    ap.add_argument("--dry-run", action="store_true", help="不写文件、不下载")
    ap.add_argument("--no-download", action="store_true", help="跳过下载，CSS 保留远程 URL")
    args = ap.parse_args()

    print("=" * 60)
    print("generate_html —— 模块CSS + JSON + user-input -> H5")
    print("=" * 60)

    # [1] 校验
    print(f"\n[1/6] 校验输入...")
    files = module_files()
    problems = []
    if not INDEX_PATH.exists():
        problems.append(f"缺 {INDEX_PATH}")
    if not files:
        problems.append("data/modules 下没有模块 JSON")
    if not USER_INPUT_PATH.exists():
        problems.append(f"缺 {USER_INPUT_PATH}")
    for p in files:
        css = CSS_SRC_DIR / (p.stem + ".css")
        if not css.exists():
            problems.append(f"缺 CSS：{css.name}（先跑 generate_module_css.py）")
    if problems:
        for x in problems:
            print(f"  [ERR] {x}", file=sys.stderr)
        sys.exit(1)
    print(f"  [OK] {len(files)} 模块 JSON + CSS，index、user-input 齐全")
    if args.check:
        print("\n  [DONE] --check 完成。")
        return

    index = load_json(INDEX_PATH)
    user_input = load_json(USER_INPUT_PATH)

    # 模块元信息（附 stem/y 排序键）
    mods = []
    for m in index["modules"]:
        m = dict(m)
        m["fileName_stem"] = Path(m["fileName"]).stem
        mods.append(m)
    ordered = sorted(mods, key=lambda m: m["position"]["y"])
    print(f"\n  模块流式顺序（按 y）：")
    for m in ordered:
        print(f"    y={m['position']['y']:>7.1f}  [{m['moduleIndex']}] {m['slug']}")

    # [2] 收集 CSS 里的图片 URL
    print(f"\n[2/6] 收集图片 URL...")
    css_texts = {}
    for m in ordered:
        css_texts[m["moduleIndex"]] = (CSS_SRC_DIR / (m["fileName_stem"] + ".css")).read_text(encoding="utf-8")
    urls = collect_css_urls(list(css_texts.values()))
    print(f"  发现 {len(urls)} 个远程图片 URL")

    # [3] 下载图片
    mapping: dict[str, str] = {}
    failures: list[str] = []
    if args.dry_run:
        print("\n[3/6] 下载图片... (--dry-run 跳过)")
    elif args.no_download:
        print("\n[3/6] 下载图片... (--no-download 跳过，CSS 保留远程 URL)")
    else:
        print(f"\n[3/6] 下载图片 -> {OUT_IMG_DIR.relative_to(PROJECT_ROOT)} ...")
        mapping, failures = download_images(urls)

    # [4] 渲染每个模块的 body HTML
    print(f"\n[4/6] 渲染节点树 -> HTML...")
    bodies: dict[int, str] = {}
    for m in ordered:
        module = load_json(MODULES_DIR / m["fileName"])
        svgs = module.get("assets", {}).get("svgs", {})
        mod_input = user_input.get(m["slug"], {})
        root = module["node"]
        root_class = f"m-{m['moduleIndex']:02d}-{m['slug']}"
        bodies[m["moduleIndex"]] = render_node(
            root, svgs, mod_input, is_root=True, root_class=root_class
        )
        print(f"  [{m['moduleIndex']}] {m['slug']:<20} {len(bodies[m['moduleIndex']]):>6} 字节")

    # [5] 组装 page.css / index.html
    print(f"\n[5/6] 组装 page.css + index.html...")
    page_css = build_page_css(index, ordered)
    index_html = build_index_html(ordered, bodies)

    if args.dry_run:
        print("\n  [DONE] --dry-run：未写文件。")
        return

    # [6] 写出
    print(f"\n[6/6] 写入 -> {OUT_DIR.relative_to(PROJECT_ROOT)} ...")
    OUT_CSS_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_CSS_DIR / "page.css").write_text(page_css, encoding="utf-8")
    print(f"  css/page.css")
    for m in ordered:
        text = css_texts[m["moduleIndex"]]
        if mapping:
            text = rewrite_css_urls(text, mapping)
        (OUT_CSS_DIR / (m["fileName_stem"] + ".css")).write_text(text, encoding="utf-8")
        print(f"  css/{m['fileName_stem']}.css")
    (OUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"  index.html  ({(OUT_DIR / 'index.html').stat().st_size / 1024:.1f} KB)")
    shutil.copyfile(USER_INPUT_PATH, OUT_DIR / "input-used.json")
    print(f"  input-used.json")

    print("\n" + "=" * 60)
    if failures:
        print(f"[DONE] 完成，但 {len(failures)} 张图片下载失败（CSS 保留远程 URL）：")
        for u in failures:
            print(f"  - {u}")
    else:
        print(f"[DONE] 生成完成 -> {OUT_DIR.relative_to(PROJECT_ROOT)}")
    print("=" * 60)


if __name__ == "__main__":
    main()

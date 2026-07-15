#!/usr/bin/env python3
"""Step 3: 从模块 JSON 提取样式，生成 components.css。

基于 Step 2 输出（v3 格式）中标注的 nodeId，
去模块 JSON 里读取真实的视觉属性，按角色归类生成 CSS。

用法：
  python scripts/step3_generate_css.py \
    --step2 data/<project>/output/slots-definition.json \
    --modules data/<project>/modules/ \
    --output data/<project>/output/assets/styles/components.css
"""

import json
import sys
import argparse
import re
import math
from pathlib import Path
from collections import defaultdict

# ============================================================
# 常量
# ============================================================

DESIGN_WIDTH = 1125  # 设计稿逻辑宽度
TARGET_WIDTH = 375   # 目标逻辑宽度
SCALE = TARGET_WIDTH / DESIGN_WIDTH  # ≈ 1/3

FONT_FALLBACK = '"PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif'

# 字体粗细映射（从 Google Fonts 风格名推断）
STYLE_WEIGHT_MAP = {
    "thin": 100,
    "hairline": 100,
    "extralight": 200,
    "ultralight": 200,
    "light": 300,
    "regular": 400,
    "normal": 400,
    "medium": 500,
    "semibold": 600,
    "demibold": 600,
    "bold": 700,
    "extrabold": 800,
    "ultrabold": 800,
    "black": 900,
    "heavy": 900,
}


# ============================================================
# 工具函数
# ============================================================

def to_kebab(name):
    """中文名保持不变，非中文转 kebab-case。"""
    if not name:
        return "unnamed"
    # 如果全是中文，直接用作 class 后缀
    if all("\u4e00" <= c <= "\u9fff" or c in "_ -" for c in name.strip()):
        # 包含中文，直接用 groupId 的 kebab 更可靠
        slug = re.sub(r"[^\w\u4e00-\u9fff-]", "-", name).strip("-").lower()
        return slug if slug else "unnamed"
    # 英文/混合：转 kebab-case
    slug = re.sub(r"([a-z])([A-Z])", r"\1-\2", name)
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff-]", "-", slug.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug if slug else "unnamed"


def scale_px(value):
    """÷3 换算并四舍五入到整数（字号必须整数，其他保留 2 位）。"""
    if isinstance(value, (int, float)):
        return round(value * SCALE, 2)
    return value


def parse_font_style(style_str):
    """解析 font.style 字段，返回 {fontWeight, fontStyle}。"""
    result = {"fontWeight": None, "fontStyle": None}
    if not style_str:
        return result
    try:
        style_obj = json.loads(style_str)
    except (json.JSONDecodeError, TypeError):
        return result
    font_style = style_obj.get("fontStyle", "").lower()
    if font_style in STYLE_WEIGHT_MAP:
        result["fontWeight"] = STYLE_WEIGHT_MAP[font_style]
    if "italic" in font_style:
        result["fontStyle"] = "italic"
    return result


def format_color(color):
    """格式化颜色值（hex / rgba / linear-gradient）。"""
    if not color:
        return None
    if isinstance(color, str):
        return color
    if isinstance(color, dict):
        ctype = color.get("type", "")
        if ctype == "IMAGE":
            return None  # 图片不生成 CSS 颜色
        # 其他复杂类型返回 None
        return None
    return str(color)


def format_background(fill):
    """格式化背景值，处理 IMAGE 类型的 fill。"""
    if not fill:
        return None
    if isinstance(fill, str):
        return fill
    if isinstance(fill, dict) and fill.get("type") == "IMAGE":
        url = fill.get("url", "")
        if url:
            return f'url("{url}")'
        return None
    return str(fill)


# ============================================================
# 节点查找
# ============================================================

class NodeFinder:
    """在模块 node 树中按 ID 查找节点。"""

    def __init__(self, root_node):
        self.lookup = {}
        self._index(root_node)

    def _index(self, node):
        nid = node.get("id")
        if nid:
            self.lookup[nid] = node
        for child in node.get("children", []):
            self._index(child)

    def get(self, node_id):
        return self.lookup.get(node_id)

    def get_text_node(self, node_id):
        """获取 TEXT 节点，如果 node_id 是 GROUP，则取其第一个 TEXT 子节点。"""
        node = self.lookup.get(node_id)
        if not node:
            return None
        if node.get("type") == "TEXT":
            return node
        # 如果是 GROUP，递归查找第一个 TEXT
        return self._find_first_text(node)

    def _find_first_text(self, node):
        if node.get("type") == "TEXT":
            return node
        for child in node.get("children", []):
            result = self._find_first_text(child)
            if result:
                return result
        return None


# ============================================================
# 样式提取
# ============================================================

def extract_layer_styles(node):
    """提取 LAYER 节点的装饰样式。"""
    styles = {}
    bg = format_background(node.get("fill"))
    if bg:
        styles["background"] = bg

    radius = node.get("borderRadius")
    if radius:
        styles["border-radius"] = f"{round(scale_px(parse_px(radius)))}px"

    # 阴影
    effect = node.get("effect")
    if isinstance(effect, dict):
        shadows = effect.get("boxShadow", [])
        if shadows:
            shadow_strs = []
            for s in shadows:
                if isinstance(s, str):
                    css = s.strip().rstrip(";")
                    css = re.sub(r"^\s*box-shadow\s*:\s*", "", css)
                    shadow_strs.append(scale_box_shadow(css))
                elif isinstance(s, dict):
                    parts = []
                    for k in ("offsetX", "offsetY", "blurRadius", "spreadRadius"):
                        v = s.get(k, 0)
                        parts.append(f"{scale_px(v)}px")
                    color = s.get("color", "rgba(0,0,0,0.1)")
                    parts.append(str(color))
                    shadow_strs.append(" ".join(parts))
            if shadow_strs:
                styles["box-shadow"] = ", ".join(shadow_strs)

    # 边框（最小 1px，避免 ÷3 后归零）
    stroke_color = node.get("strokeColor")
    stroke_width = node.get("strokeWidth")
    if stroke_color and stroke_width is not None:
        sw = max(1, round(scale_px(parse_px(stroke_width))))
        styles["border"] = f"{sw}px solid {stroke_color}"

    opacity = node.get("opacity")
    if opacity is not None and opacity != 1:
        styles["opacity"] = opacity

    return styles


def extract_text_styles(node):
    """提取 TEXT 节点的文字样式。"""
    styles = {}
    text_runs = node.get("textRuns") or []
    if not text_runs:
        return styles

    tr = text_runs[0]
    font = tr.get("font") or {}

    family = font.get("family")
    if family:
        styles["font-family"] = f'"{family}", {FONT_FALLBACK}'

    size = font.get("size")
    if size is not None:
        scaled = scale_px(size)
        styles["font-size"] = f"{math.ceil(scaled)}px"  # 字号向上取整

    line_height = font.get("lineHeight")
    if line_height is not None and line_height != "auto":
        if isinstance(line_height, (int, float)):
            styles["line-height"] = f"{round(scale_px(line_height))}px"
        elif isinstance(line_height, str):
            try:
                lh_num = float(line_height)
                styles["line-height"] = f"{round(scale_px(lh_num))}px"
            except ValueError:
                styles["line-height"] = line_height

    letter_spacing = font.get("letterSpacing")
    if letter_spacing is not None and letter_spacing != "auto":
        if isinstance(letter_spacing, str) and "%" in letter_spacing:
            try:
                pct = float(letter_spacing.replace("%", ""))
                styles["letter-spacing"] = f"{round(pct, 1)}%"
            except ValueError:
                styles["letter-spacing"] = letter_spacing
        elif isinstance(letter_spacing, (int, float)):
            styles["letter-spacing"] = f"{round(scale_px(letter_spacing))}px"

    # 字体粗细和样式
    parsed = parse_font_style(font.get("style"))
    # 也尝试从字族名推断粗细（长关键词优先匹配）
    family_name = font.get("family", "")
    family_lower = family_name.lower()
    weight_from_name = None
    for kw, w in sorted(STYLE_WEIGHT_MAP.items(), key=lambda x: -len(x[0])):
        if kw in family_lower:
            weight_from_name = w
            break
    fontWeight = parsed.get("fontWeight") or weight_from_name
    if fontWeight and fontWeight != 400:
        styles["font-weight"] = str(fontWeight)

    font_style = parsed.get("fontStyle")
    if font_style:
        styles["font-style"] = font_style

    color = tr.get("color")
    if color and color != "inherit":
        styles["color"] = color

    text_align = node.get("textAlign")
    if text_align and text_align != "left":
        styles["text-align"] = text_align

    text_mode = node.get("textMode")
    if text_mode == "single-line":
        styles["white-space"] = "nowrap"

    return styles


def parse_px(value):
    """解析 px 值，如 '33px' → 33。"""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.match(r"([\d.]+)\s*px", value)
        if m:
            return float(m.group(1))
        try:
            return float(value)
        except ValueError:
            return 0
    return 0


def scale_box_shadow(css_str):
    """对 box-shadow CSS 值中的 px 做 ÷3 换算。"""
    def replacer(m):
        val = float(m.group(1))
        return f"{round(val * SCALE, 2)}px"
    return re.sub(r"([\d.]+)px", replacer, css_str)


# ============================================================
# CSS 生成
# ============================================================

def styles_to_css(styles, indent=2):
    """将样式字典转为 CSS 规则块。"""
    if not styles:
        return ""
    prefix = " " * indent
    lines = [f"{prefix}{k}: {v};" for k, v in styles.items()]
    return "\n".join(lines)


class CSSGenerator:
    """从 Step 2 输出生成 components.css。"""

    ROLE_CLASS_MAP = {
        "frameTitle": "content-frame-title",
        "sectionTitle": "content-section-title",
        "body": "content-body",
        "sourceNote": "content-source",
    }

    def __init__(self, step2_path, modules_dir):
        with open(step2_path, "r", encoding="utf-8") as f:
            self.step2 = json.load(f)
        self.modules_dir = Path(modules_dir)
        # modules-classification.json 用来做 moduleIndex → 文件名的映射
        self.module_index_map = self._load_index_map()

    def _load_index_map(self):
        """从 _index.json 建立 moduleIndex → fileName 的映射。"""
        index_file = self.modules_dir / "_index.json"
        if not index_file.exists():
            return self._scan_modules()
        with open(index_file, "r", encoding="utf-8") as f:
            idx = json.load(f)
        mapping = {}
        for entry in idx.get("modules", []):
            mapping[entry["moduleIndex"]] = entry["fileName"]
        return mapping

    def _scan_modules(self):
        """退化方案：扫描 modules 目录建立映射。"""
        mapping = {}
        for f in sorted(self.modules_dir.glob("*.json")):
            if f.name == "_index.json":
                continue
            with open(f, "r", encoding="utf-8") as fh:
                mod = json.load(fh)
                mapping[mod["meta"]["moduleIndex"]] = f.name
        return mapping

    def generate(self):
        """主入口：生成完整 CSS 字符串。"""
        sections = []

        # 共享角色样式（跨模块合并）
        role_styles_all = defaultdict(list)

        # 模块专属样式
        module_css_blocks = []

        for mod in self.step2.get("modules", []):
            module_css = self._process_module(mod, role_styles_all)
            if module_css:
                module_css_blocks.append(module_css)

        # 生成共享角色样式
        shared_css = self._generate_shared_role_styles(role_styles_all)
        if shared_css:
            sections.append("/* ========================================")
            sections.append("   共享内容样式（role → class）")
            sections.append("   ======================================== */")
            sections.append(shared_css)

        # 生成模块专属样式
        if module_css_blocks:
            sections.append("")
            sections.append("/* ========================================")
            sections.append("   模块专属样式（壳 + 固定组件）")
            sections.append("   ======================================== */")
            sections.append("\n".join(module_css_blocks))

        return "\n".join(sections) + "\n"

    def _process_module(self, mod, role_styles_all):
        """处理单个模块，返回 CSS 字符串。"""
        module_indexes = mod.get("moduleIndexes", [])
        if not module_indexes:
            return ""

        # 找到代表模块的文件
        rep_idx = module_indexes[0]
        file_name = self.module_index_map.get(rep_idx)
        if not file_name:
            print(f"  [WARN] 找不到 moduleIndex={rep_idx} 对应的文件，跳过", file=sys.stderr)
            return ""

        module_path = self.modules_dir / file_name
        if not module_path.exists():
            print(f"  [WARN] 文件不存在: {module_path}，跳过", file=sys.stderr)
            return ""

        with open(module_path, "r", encoding="utf-8") as f:
            module_data = json.load(f)

        finder = NodeFinder(module_data["node"])
        group_id = mod.get("groupId", "unknown")
        namespace = to_kebab(group_id)

        blocks = []
        blocks.append(f"/* {mod.get('groupName', group_id)} */")

        # --- contentArea ---
        content_area = mod.get("contentArea", {})
        if content_area:
            pad_styles = {}
            for k in ("paddingTop", "paddingBottom", "paddingLeft", "paddingRight"):
                v = content_area.get(k, 0)
                if v:
                    css_k = re.sub(r"([A-Z])", r"-\1", k).lower()
                    pad_styles[css_k] = f"{math.ceil(scale_px(v))}px"
            if pad_styles:
                blocks.append(f".{namespace} .module-content {{")
                blocks.append(styles_to_css(pad_styles))
                blocks.append("}")

        # --- fixedGroups: decoration ---
        for fg in mod.get("fixedGroups", []):
            fg_type = fg.get("type", "")
            fg_node = finder.get(fg.get("groupId"))
            if not fg_node:
                continue

            if fg_type == "decoration":
                shell_styles = self._extract_shell(fg, fg_node, finder)
                if shell_styles:
                    is_main = self._is_main_card(fg, mod)
                    if is_main:
                        class_name = f".{namespace}"
                    else:
                        gname = to_kebab(fg.get("groupName", ""))
                        class_name = f".{namespace}__{gname}"
                    blocks.append(f"{class_name} {{")
                    blocks.append(styles_to_css(shell_styles))
                    blocks.append("}")

            elif fg_type == "fixedTexts":
                shell_styles = self._extract_shell(fg, fg_node, finder)
                child_texts = fg.get("childTexts", [])
                text_styles = {}
                for ct in child_texts:
                    text_node = finder.get(ct.get("nodeId"))
                    if text_node:
                        text_styles = extract_text_styles(text_node)
                        break

                gname = to_kebab(fg.get("groupName", ""))
                class_name = f".{namespace}__{gname}"

                if shell_styles:
                    blocks.append(f"{class_name} {{")
                    blocks.append(styles_to_css(shell_styles))
                    blocks.append("}")

                if text_styles:
                    blocks.append(f"{class_name}__text {{")
                    blocks.append(styles_to_css(text_styles))
                    blocks.append("}")

        # --- variableTexts: 收集 + 输出模块作用域样式 ---
        module_role_styles = defaultdict(list)
        for vt in mod.get("variableTexts", []):
            node_id = vt.get("nodeId")
            role = vt.get("role", "generic")
            text_node = finder.get_text_node(node_id)
            if not text_node:
                group_node = finder.get(node_id)
                if group_node:
                    text_node = finder._find_first_text(group_node)
            if not text_node:
                continue

            styles = extract_text_styles(text_node)
            if styles:
                styles["_nodeId"] = node_id
                styles["_module"] = mod.get("groupId")
                styles["_text"] = vt.get("text", "")
                role_styles_all[role].append(styles)
                module_role_styles[role].append(styles)

        # 模块级角色样式（作用域在 .{namespace} 下）
        if module_role_styles:
            blocks.append("")
            for role, styles_list in module_role_styles.items():
                class_name = self.ROLE_CLASS_MAP.get(role, f"content-{to_kebab(role)}")
                merged = self._merge_styles(styles_list)
                if merged:
                    blocks.append(f".{namespace} .{class_name} {{")
                    blocks.append(styles_to_css(merged))
                    blocks.append("}")

        return "\n".join(blocks) if blocks else ""

    def _extract_shell(self, fixed_group, group_node, finder):
        """提取固定组的"壳"视觉样式。

        优先从 descendantIds 中的第一个 LAYER 取样式，
        因为 GROUP 自身通常没有样式。
        """
        # 先看 GROUP 本身有没有样式
        shell = {}
        bg = format_background(group_node.get("fill"))
        if bg:
            shell["background"] = bg
        radius = group_node.get("borderRadius")
        if radius:
            shell["border-radius"] = f"{round(scale_px(parse_px(radius)))}px"

        # 再从 descendantIds 补充
        for did in fixed_group.get("descendantIds", []):
            dnode = finder.get(did)
            if not dnode:
                continue
            dtype = dnode.get("type", "")
            if dtype in ("LAYER", "PATH", "ELLIPSE", "SVG_ELLIPSE"):
                layer_styles = extract_layer_styles(dnode)
                for k, v in layer_styles.items():
                    if k not in shell:
                        shell[k] = v

        # 不写死宽度
        shell.pop("width", None)
        return shell

    def _is_main_card(self, fixed_group, module):
        """判断一个 decoration 是否为模块的主卡片底板。

        启发式：groupName 和模块 groupName 相同或相近。
        """
        gname = fixed_group.get("groupName", "")
        mname = module.get("groupName", "")
        return gname == mname or to_kebab(gname) == to_kebab(mname)

    def _generate_shared_role_styles(self, role_styles_all):
        """合并同 role 样式，生成共享 class（只保留跨模块公共值）。"""
        if not role_styles_all:
            return ""

        blocks = []
        for role, class_name in self.ROLE_CLASS_MAP.items():
            styles_list = role_styles_all.get(role, [])
            if not styles_list:
                continue

            # 合并：取所有样式的公共值
            merged = self._merge_styles(styles_list)
            if not merged:
                continue

            blocks.append(f".{class_name} {{")
            blocks.append(styles_to_css(merged))
            module_refs = set(s["_module"] for s in styles_list if s.get("_module"))
            if module_refs:
                blocks[-1] += f"  /* 来源模块: {', '.join(sorted(module_refs))} */"
            blocks.append("}")

        # 处理未映射的 role（如 generic）
        for role, styles_list in role_styles_all.items():
            if role in self.ROLE_CLASS_MAP:
                continue
            merged = self._merge_styles(styles_list)
            if not merged:
                continue
            class_name = f"content-{to_kebab(role)}"
            blocks.append(f".{class_name} {{")
            blocks.append(styles_to_css(merged))
            blocks.append("}")

        return "\n".join(blocks)

    def _merge_styles(self, styles_list):
        """合并多个样式字典，只保留在所有样式中同时存在且值相同的属性。"""
        if not styles_list:
            return {}
        if len(styles_list) == 1:
            merged = {k: v for k, v in styles_list[0].items() if not k.startswith("_")}
            return merged

        # 找出所有 key
        all_keys = set()
        for s in styles_list:
            all_keys.update(k for k in s if not k.startswith("_"))

        merged = {}
        for key in all_keys:
            values = set()
            first_val = None
            all_have = True
            for s in styles_list:
                v = s.get(key)
                if v is None:
                    all_have = False
                    break
                values.add(str(v))
                if first_val is None:
                    first_val = v
            if all_have and len(values) == 1 and first_val is not None:
                merged[key] = first_val

        return merged


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Step 3: 从模块 JSON 提取样式，生成 components.css"
    )
    parser.add_argument(
        "--step2", "-s",
        required=True,
        help="Step 2 输出 JSON 路径（v3 格式：slots-definition.json）",
    )
    parser.add_argument(
        "--modules", "-m",
        required=True,
        help="模块 JSON 目录路径",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="输出 CSS 文件路径",
    )
    args = parser.parse_args()

    gen = CSSGenerator(args.step2, args.modules)
    css = gen.generate()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(css)

    print(f"Generated: {output_path}")
    print(f"  {len(css.splitlines())} lines")


if __name__ == "__main__":
    main()

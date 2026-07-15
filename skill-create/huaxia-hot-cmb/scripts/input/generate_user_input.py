#!/usr/bin/env python3
"""
generate_user_input.py —— 读取 config/variability.json + 模块 JSON，生成 user-input.json。

规则：
  - fixed（含未标记的默认值）：不出现在输出中
  - variable：提取 textRuns[*].text
  - variable-all：提取 textRuns[*].text + layoutStyle + fill + stroke + path
  - 继承：祖先标记为 variable-all 的后代自动视为 variable-all

输出格式自文档化：
  - _guide：顶层使用说明
  - _section：每个模块的中文标签（用户一看看懂这个模块是页面哪一块）
  - _label：每个字段的人类可读描述（来自设计稿中的文字内容或节点名）
  - _pos：字段在模块内的纵坐标（越小越靠上，方便按页面位置查找）
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULES_DIR = os.path.join(ROOT, "data", "modules")
INDEX_PATH = os.path.join(MODULES_DIR, "_index.json")
CONFIG_PATH = os.path.join(ROOT, "config", "variability.json")
OUTPUT_DIR = os.path.join(ROOT, "data", "input")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "user-input.json")

_GUIDE = (
    "直接编辑各字段的值即可更新 H5 页面。"
    "当前值就是设计稿原文——看一眼就知道对应页面哪个位置。"
    "_section 是模块名。不要修改 _ 开头的字段。"
)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_classification(node_id, slug, config, ancestor_ids):
    """返回节点实际分类，考虑 variable-all 祖先继承。"""
    mod_cfg = config.get(slug, {})
    entry = mod_cfg.get(node_id, {})
    own = entry.get("classification", "fixed")

    for aid in ancestor_ids:
        a_entry = mod_cfg.get(aid, {})
        if a_entry.get("classification") == "variable-all":
            return "variable-all"

    return own


def extract_text(n):
    """提取节点的文本内容。"""
    tr = n.get("textRuns")
    if tr:
        return "".join(t.get("text", "") for t in tr)
    return ""


def extract_variable(n):
    """variable 节点：只提取文本。"""
    text = extract_text(n)
    return {"text": text} if text else {}


def extract_variable_all(n):
    """variable-all 节点：提取文本 + 形状数据。"""
    result = {}
    text = extract_text(n)
    if text:
        result["text"] = text

    ls = n.get("layoutStyle")
    if ls:
        result["width"] = ls.get("width")
        result["height"] = ls.get("height")

    fill = n.get("fill")
    if fill and isinstance(fill, list):
        result["fill"] = fill

    effect = n.get("effect")
    if effect:
        result["effect"] = effect

    stroke = {}
    for k in ("strokeColor", "strokeWidth", "strokeAlign", "strokeType"):
        if k in n:
            stroke[k] = n[k]
    if stroke:
        result["stroke"] = stroke

    path = n.get("path")
    if path:
        result["path"] = path

    return result


def process_module(mod_info, config):
    """从模块根节点名生成中文模块标签。"""
    name = node.get("name", "")
    if name:
        # 去掉过长的名称（如完整页面标题），只保留模块名
        short = name.split("（")[0].split("(")[0].strip()
        if short:
            return short
    return slug


def make_section_label(slug, node):
    """从模块根节点名生成中文模块标签。"""
    name = node.get("name", "")
    if name:
        short = name.split("（")[0].split("(")[0].strip()
        if short:
            return short
    return slug


def process_module(mod_info, config):
    """处理单个模块，返回有序的字段列表 + 模块标签。"""
    slug = mod_info["slug"]
    file_path = os.path.join(MODULES_DIR, mod_info["fileName"])

    with open(file_path, "r", encoding="utf-8") as f:
        module_data = json.load(f)

    root = module_data["node"]
    section_label = make_section_label(slug, root)

    # 收集所有 variable 节点：[(node_id, data, abs_y)]
    entries = []

    def walk(n, ancestors=None):
        if ancestors is None:
            ancestors = []

        nid = n["id"]
        cls = get_classification(nid, slug, config, ancestors)

        data = None
        if cls == "variable":
            data = extract_variable(n)
        elif cls == "variable-all":
            data = extract_variable_all(n)

        if data:
            ls = n.get("layoutStyle") or {}
            abs_y = ls.get("y", 0)

            entries.append({
                "id": nid,
                "data": data,
                "pos_y": abs_y,
            })

        new_ancestors = ancestors + [nid]
        for child in n.get("children", []):
            walk(child, new_ancestors)

    walk(root)

    if not entries:
        return None

    # 按页面位置从上到下排序
    entries.sort(key=lambda e: e["pos_y"])

    # 组装输出：有序的 {node_id: {text, ...}}，text 值本身就是原文，用户一看就知道是哪里
    result = {}
    for entry in entries:
        result[entry["id"]] = dict(entry["data"])

    return section_label, result


def generate():
    config = load_config()
    index = load_index()
    output = {"_guide": _GUIDE}

    for mod in index["modules"]:
        slug = mod["slug"]
        result = process_module(mod, config)
        if result is None:
            continue
        section_label, fields = result
        fields["_section"] = section_label
        output[slug] = fields

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_nodes = sum(
        len(v) - 1  # subtract _section key
        for k, v in output.items()
        if k != "_guide" and isinstance(v, dict)
    )
    modules_count = sum(1 for k in output if k != "_guide")
    print(f"Generated {OUTPUT_PATH}")
    print(f"  {modules_count} modules with variable nodes, {total_nodes} total variable nodes")


if __name__ == "__main__":
    generate()

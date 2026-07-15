#!/usr/bin/env python3
"""
generate_variability_config.py —— 遍历所有模块 JSON，生成 config/variability.json。

产出文件包含每个模块的全部节点，默认 classification="fixed"。
TEXT 节点附带当前 text 内容，方便人工识别。
用户手动将需要修改的节点改为 "variable" 或 "variable-all"。

注意：父节点 fixed → 子节点自动继承 fixed，不需要在配置文件中重复标记。
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULES_DIR = os.path.join(ROOT, "data", "modules")
INDEX_PATH = os.path.join(MODULES_DIR, "_index.json")
OUTPUT_PATH = os.path.join(ROOT, "config", "variability.json")


def load_modules_index():
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_nodes(module_node):
    """递归收集模块树中的所有节点，返回按 node id 排序的列表。"""
    nodes = []

    def walk(n):
        info = {
            "name": n.get("name", ""),
            "type": n.get("type", ""),
            "classification": "fixed",
        }
        tr = n.get("textRuns")
        if tr and len(tr) > 0:
            info["text"] = tr[0].get("text", "")

        nodes.append((n["id"], info))

        for child in n.get("children", []):
            walk(child)

    walk(module_node)
    # 按 id 排序，保证输出稳定
    nodes.sort(key=lambda x: x[0])
    return nodes


def generate():
    index = load_modules_index()
    output = {}

    for mod in index["modules"]:
        slug = mod["slug"]
        file_path = os.path.join(MODULES_DIR, mod["fileName"])

        with open(file_path, "r", encoding="utf-8") as f:
            module_data = json.load(f)

        nodes = collect_nodes(module_data["node"])
        output[slug] = dict(nodes)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total = sum(len(v) for v in output.values())
    print(f"Generated {OUTPUT_PATH}")
    print(f"  {len(output)} modules, {total} total nodes, all default to 'fixed'")


if __name__ == "__main__":
    generate()

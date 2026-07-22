#!/usr/bin/env python3
"""
step3_detect_repeats.py — 检测模板型 Frame 中的重复实例。

只检测 FRAME/GROUP 级别、子树节点数 >= 3 的组件级重复。
标记为 repeated 的子树内部不再递归检测。

用法：python scripts/step3_detect_repeats.py
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "input"
MERGED_DIR = PROJECT_ROOT / "data-output" / "frames-merged"
OUTPUT_DIR = PROJECT_ROOT / "data-output" / "repeats"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def node_count(node):
    """计算子树节点总数。"""
    n = 1
    for child in node.get("children", []):
        n += node_count(child)
    return n


def structural_fingerprint(node):
    """计算节点结构指纹（忽略文本内容）。"""
    node_type = node.get("type", "?")
    children = node.get("children", [])
    child_fps = tuple(structural_fingerprint(c) for c in children)
    return (node_type, len(children), child_fps)


def collect_texts(node):
    """收集子树中所有 TEXT 内容。"""
    texts = []
    if node.get("type") == "TEXT" and node.get("text"):
        texts.append(node["text"])
    for child in node.get("children", []):
        texts.extend(collect_texts(child))
    return texts


def extract_template_slots(template_node, all_instance_nodes):
    """从模板节点提取所有 TEXT → slot，并收集各实例的示例值。

    返回:
      slots: [{name, path, exampleValues}]
      templateTree: 节点树（TEXT 已替换为 slot 名称）
    """
    slots = []
    slot_index = 0

    def walk_template(node, path=""):
        nonlocal slot_index
        result = {
            "type": node.get("type"),
            "name": node.get("name", ""),
        }

        if node.get("type") == "TEXT":
            slot_name = f"slot_{slot_index}"
            # 收集各实例的对应位置文本
            examples = []
            for inst_node in all_instance_nodes:
                texts = collect_texts(inst_node)
                if slot_index < len(texts):
                    examples.append(texts[slot_index])

            slots.append({
                "name": slot_name,
                "path": path,
                "exampleValues": examples,
            })
            slot_index += 1
            result["slot"] = slot_name
            return result

        children = []
        for ci, child in enumerate(node.get("children", [])):
            child_path = f"{path}/{ci}" if path else str(ci)
            children.append(walk_template(child, child_path))

        result["children"] = children
        return result

    template_tree = walk_template(template_node)
    return slots, template_tree


def auto_name_slots(slots, parent_name):
    """根据示例值自动给 slot 命名（用第一个实例的值做参考）。"""
    names = []
    for s in slots:
        examples = s.get("exampleValues", [])
        first = examples[0] if examples else ""
        # 用第一个示例值做参考名
        name = first[:12].strip()
        if not name:
            name = s["name"]
        # 去重
        base = name
        counter = 1
        while name in names:
            name = f"{base}_{counter}"
            counter += 1
        names.append(name)
        s["displayName"] = name
    return slots
    """递归描述节点结构骨架。"""
    node_type = node.get("type", "?")
    name = node.get("name", "")
    text = node.get("text", "")
    pad = "  " * depth
    line = f"{pad}[{node_type}] {name}"
    if text:
        line += '  → "{{slot}}"'
    result = line

    for child in node.get("children", []):
        result += "\n" + describe_structure(child, depth + 1)

    return result


def find_repeated_components(node, parent_id="", results=None):
    """找同级子节点中结构相同但文字不同的 FRAME/GROUP 组件。

    只在当前层级检测，标记为 repeated 的子树内部不再递归。
    """
    if results is None:
        results = []

    children = node.get("children", [])
    if len(children) < 2:
        for child in children:
            find_repeated_components(child, node.get("id", ""), results)
        return results

    # 只取 FRAME 或 GROUP 类型、且有 >= 3 个节点的
    component_candidates = [
        (i, c) for i, c in enumerate(children)
        if c.get("type") in ("FRAME", "GROUP") and node_count(c) >= 3
    ]

    if len(component_candidates) < 2:
        for child in children:
            find_repeated_components(child, node.get("id", ""), results)
        return results

    # 对候选组件按结构指纹分组
    fp_groups = defaultdict(list)
    for i, child in component_candidates:
        fp = structural_fingerprint(child)
        fp_groups[fp].append(i)

    repeated_indices = set()
    for fp, indices in fp_groups.items():
        if len(indices) < 2:
            continue

        # 确认文字内容不同（否则不是重复实例，是完全相同）
        all_texts = [collect_texts(children[i]) for i in indices]
        if all(t == all_texts[0] for t in all_texts):
            continue

        repeated_indices.update(indices)

        group_children = [children[i] for i in indices]
        template_node = group_children[0]  # 第一个实例作为模板
        slots, template_tree = extract_template_slots(template_node, group_children)
        slots = auto_name_slots(slots, template_node.get("name", ""))

        results.append({
            "parentId": node.get("id", ""),
            "parentName": node.get("name", ""),
            "repeatKey": template_node.get("name", ""),
            "count": len(indices),
            "instances": [
                {
                    "index": i,
                    "id": group_children[j].get("id", ""),
                    "name": group_children[j].get("name", ""),
                    "texts": collect_texts(group_children[j]),
                }
                for j, i in enumerate(indices)
            ],
            "template": {
                "slots": slots,
            },
        })

    # 只递归非重复的子节点
    for child in children:
        if children.index(child) not in repeated_indices:
            find_repeated_components(child, node.get("id", ""), results)

    return results


def main():
    definitions_path = INPUT_DIR / "1-frame-definitions.json"
    if not definitions_path.exists():
        print(f"[ERR] 找不到 {definitions_path}")
        sys.exit(1)

    definitions = load_json(definitions_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_reports = {}

    for frame_id, frame_def in definitions.items():
        if frame_def["type"] != "template":
            continue

        print(f"\n{'='*60}")
        print(f"[{frame_id}] 检测重复实例...")

        merged_path = MERGED_DIR / f"{frame_id}.json"
        if not merged_path.exists():
            continue

        merged = load_json(merged_path)

        all_groups = []
        for mod in merged["modules"]:
            node = mod.get("node")
            if not node:
                continue

            groups = find_repeated_components(node)
            for g in groups:
                g["moduleFile"] = mod["fileName"]
                g["moduleId"] = mod["moduleId"]
                g["moduleName"] = mod["moduleName"]
            all_groups.extend(groups)

        # 打印供用户确认
        if all_groups:
            for g in all_groups:
                print(f"\n--- 重复组: {g['parentName']} → {g['count']} 个实例 ---")
                print(f"  模块: {g['moduleFile']}  可重复 key: {g['repeatKey']}")
                for inst in g["instances"]:
                    texts_preview = " | ".join(t[:25] for t in inst["texts"])
                    print(f"  [{inst['index']}] {inst['name']}  →  {texts_preview}")
                print(f"  Slot 定义:")
                for s in g["template"]["slots"]:
                    examples_preview = "  |  ".join(str(v)[:25] for v in s["exampleValues"])
                    print(f"    {{[{s['name']}]}}  ←  {examples_preview}")
        else:
            print(f"  (未检测到需要模板化的重复实例)")

        frame_report = {
            "frameId": frame_id,
            "repeatedGroupCount": len(all_groups),
            "groups": all_groups,
        }
        all_reports[frame_id] = frame_report

    # 输出 JSON 报告
    report_path = OUTPUT_DIR / "repeated-instances.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(all_reports, f, ensure_ascii=False, indent=2)

    # 输出 templates.json（提取模板 + slot 定义）
    templates = {}
    for frame_id, report in all_reports.items():
        frame_templates = []
        for g in report["groups"]:
            frame_templates.append({
                "repeatKey": g["repeatKey"],
                "count": g["count"],
                "parentId": g["parentId"],
                "parentName": g["parentName"],
                "slots": g["template"]["slots"],
            })
        if frame_templates:
            templates[frame_id] = frame_templates

    templates_path = OUTPUT_DIR / "templates.json"
    with open(templates_path, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"[DONE] 检测报告 → {report_path}")
    print(f"[DONE] 模板定义 → {templates_path}")


if __name__ == "__main__":
    main()

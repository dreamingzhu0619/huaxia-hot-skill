#!/usr/bin/env python3
"""
step4_generate_template.py — 基于 D2C HTML 生成模板。

对模板型 Frame：
1. 取合并后的 D2C HTML（已按模块拼接）
2. 在 HTML 中找可变文字 → 替换为 {{slot}}
3. 重复实例 → 识别 HTML 块 → 取第一块做模板 → {% for %} 包裹

用法：python scripts/step4_generate_template.py
"""

import json, sys, re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "input"
MERGED_DIR = PROJECT_ROOT / "data-output" / "frames-merged"
REPEATS_DIR = PROJECT_ROOT / "data-output" / "repeats"
OUTPUT_DIR = PROJECT_ROOT / "data-output" / "frames"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FIXED_WHITELIST = {
    "关联产品", "查看更多", "近期热点", "行业直击",
    "捕捉热点事件", "拆解产业逻辑", "精选关联产品",
    "产业基石", "价值核心", "需求源泉", "风险提示",
    "追求超额", "紧密跟踪", "主动研判 调仓灵活",
    "被动复制 持仓透明",
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_texts(node):
    texts = []
    if node.get("type") == "TEXT" and node.get("text"):
        texts.append(node["text"])
    for c in node.get("children", []):
        texts.extend(collect_texts(c))
    return texts


def normalize_text(t):
    """去掉换行和多余空格。"""
    return re.sub(r'\s+', '', t)


def find_html_block(html, texts, start_pos=0):
    """在 D2C HTML 中找包含这些文本的最近共同父 div 块。
    返回 (block_html, start, end) 或 None。"""
    # 在 HTML 中定位第一个文本
    first = normalize_text(texts[0])
    idx = html.find(first, start_pos)
    if idx == -1:
        # 尝试逐字符找
        for ch in first[:4]:
            idx = html.find(ch, start_pos)
            if idx != -1:
                break
    if idx == -1:
        return None

    # 向前找最近的 <div 开始标签
    div_start = html.rfind("<div", 0, idx)
    if div_start == -1:
        return None

    # 找匹配的 </div>
    depth = 0
    pos = div_start
    while pos < len(html):
        next_open = html.find("<div", pos)
        next_close = html.find("</div>", pos)

        if next_close == -1:
            break

        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6
            if depth == 0:
                return (html[div_start:pos], div_start, pos)

    return None


def main():
    definitions = load_json(INPUT_DIR / "1-frame-definitions.json")
    repeats_path = REPEATS_DIR / "templates.json"
    repeats = load_json(repeats_path) if repeats_path.exists() else {}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for frame_id, frame_def in definitions.items():
        if frame_def["type"] != "template":
            continue

        print("\n" + "=" * 60)
        print("[" + frame_id + "] D2C HTML → 模板...")

        merged = load_json(MERGED_DIR / (frame_id + ".json"))
        html = merged.get("d2c", {}).get("html", "")

        if not html:
            print("  [WARN] 无 D2C HTML，跳过")
            continue

        # 收集所有 TEXT
        all_texts = []
        for mod in merged["modules"]:
            if mod.get("node"):
                all_texts.extend(collect_texts(mod["node"]))

        frame_repeats = repeats.get(frame_id, [])

        # 构建 slot_map
        slot_map = {}
        repeat_texts = set()
        for tmpl in frame_repeats:
            for s in tmpl.get("slots", []):
                for v in s["exampleValues"]:
                    slot_map[v] = s["name"]
                    repeat_texts.add(v)

        single_texts = set()
        for t in set(all_texts):
            if t in FIXED_WHITELIST or t in repeat_texts:
                continue
            single_texts.add(t)

        single_idx = 0
        for t in sorted(single_texts, key=lambda x: -len(x)):  # 长文本优先匹配
            slot_map[t] = "slot_" + str(single_idx)
            single_idx += 1

        # 替换文本为 {{slot}}（只替换不在白名单中的文本）
        sorted_slots = sorted(slot_map.items(), key=lambda x: -len(x[0]))
        for text, slot_name in sorted_slots:
            if text in FIXED_WHITELIST:
                continue
            # 直接字符串替换
            html = html.replace(text, "{{ " + slot_name + " }}")

        # 处理重复实例：找到重复 block 并包裹 for 循环
        for tmpl in frame_repeats:
            slot_names = [s["name"] for s in tmpl["slots"]]
            first_slot = slot_names[0] if slot_names else ""
            if not first_slot:
                continue

            # 在 HTML 中找包含第一个 slot 的 div 块
            marker = "{{ " + first_slot + " }}"
            if marker not in html:
                continue

            idx = html.find(marker)
            # 向前找产品卡容器
            div_start = html.rfind("<div", 0, idx)
            # 再向前找两级（产品卡的根 div）
            for _ in range(3):
                prev = html.rfind("<div", 0, div_start - 1)
                if prev != -1:
                    div_start = prev

            # 找匹配的 </div>，获得完整产品卡 HTML
            depth = 0
            pos = div_start
            while pos < len(html):
                next_open = html.find("<div", pos)
                next_close = html.find("</div>", pos)
                if next_close == -1:
                    break
                if next_open != -1 and next_open < next_close:
                    depth += 1
                    pos = next_open + 4
                else:
                    depth -= 1
                    pos = next_close + 6
                    if depth == 0:
                        break

            card_html = html[div_start:pos]

            # 在 HTML 中删除第 2、3 个产品卡（保留第一个作为模板）
            # 找到 card_html 的所有出现位置
            occurrences = []
            search_from = 0
            while True:
                found = html.find(card_html, search_from)
                if found == -1:
                    break
                occurrences.append(found)
                search_from = found + 1

            if len(occurrences) >= 2:
                # 保留第一个，删除其余的
                for occ in reversed(occurrences[1:]):
                    html = html[:occ] + html[occ + len(card_html):]

                # 包裹第一个为 for 循环
                first_occ = occurrences[0]
                before = html[:first_occ]
                after = html[first_occ + len(card_html):]
                html = before + "{% for item in items %}\n" + card_html + "\n{% endfor %}" + after

                print("  产品卡模板: " + str(len(occurrences)) + " 个实例 → 1 模板 + for 循环")

        # 用百分比转换：D2C 的百分比是相对于 375×2880 页面，
        # 这里保持百分比不变（渲染时容器只需保持相同比例）
        # 包装为完整 HTML
        full_html = (
            '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
            '<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=375, initial-scale=1.0">\n'
            '<style>\n'
            '  *,*::before,*::after { box-sizing: border-box }\n'
            '  body { padding: 0; margin: 0 }\n'
            '  p { margin: 0 }\n'
            '</style>\n</head>\n<body>\n'
            + html +
            '\n</body>\n</html>'
        )

        frame_out = OUTPUT_DIR / frame_id
        frame_out.mkdir(parents=True, exist_ok=True)

        html_path = frame_out / "template.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(full_html)

        # schema.json
        schema = {
            "frameId": frame_id,
            "type": "template",
            "singleSlots": [
                {"name": slot_map[t], "example": t}
                for t in sorted(single_texts)
            ],
            "repeatGroups": [
                {
                    "repeatKey": "items",
                    "count": tmpl["count"],
                    "slots": tmpl["slots"],
                }
                for tmpl in frame_repeats
            ],
        }

        schema_path = frame_out / "schema.json"
        with open(schema_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, ensure_ascii=False, indent=2)

        print("  template.html (" + str(len(full_html)) + " bytes)")
        print("  schema.json")


if __name__ == "__main__":
    main()

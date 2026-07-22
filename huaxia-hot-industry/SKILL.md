# 华夏行业 H5 Skill

把 MasterGo 设计稿（行业主题 H5）提取为可复用的模板，更换行业内容后生成新的 H5。

## 输入

`data/input/1-frame-definitions.json` — 定义每个业务 Frame 的类型和包含的模块：

```json
{
  "1-banner": {
    "type": "template",
    "modules": ["06-矩形", "05-椭圆形", ...]
  }
}
```

- key：带序号的 frame id，序号代表页面从上到下的顺序
- `type`：`fixed` / `template` / `content`
- `modules`：该 frame 包含的模块文件名（对应 `data/modules/` 下的 JSON）

## Step 1：合并 Frame

运行 `scripts/step1_merge_frames.py`，读取 `1-frame-definitions.json`，把分散的模块 JSON 合并为业务 Frame，按 y 坐标排序，标上 type 和 zIndex。

输出：`data-output/frames-merged/{frame-id}.json`

## Step 2：生成节点树

运行 `scripts/step2_generate_tree.py`，读取合并后的 Frame JSON，输出按业务 Frame 重组的紧凑树状图。

输出：`data-output/normalized/tree.md`

## Step 3：检测重复实例（模板型）

运行 `scripts/step3_detect_repeats.py`，对 template 类型的 Frame 检测同级子节点中结构相同、仅文字不同的重复组件，提取模板和 slot 定义。

输出：
- `data-output/repeats/repeated-instances.json` — 检测报告（供确认）
- `data-output/repeats/templates.json` — 模板定义 + slot 列表（含各实例的示例值）

## Step 4：生成模板（模板型）

运行 `scripts/step4_generate_template.py`，对 template 类型的 Frame 分类所有 TEXT 节点（固定文字/单次 slot/重复模板 slot），生成 template.html 和 schema.json。

输出：`data-output/frames/{frame-id}/` — template.html + schema.json

## Step 5：处理内容型

> 待实现。对 content 类型的 Frame，以固定文字为锚点识别固定组件，其余归为内容区。

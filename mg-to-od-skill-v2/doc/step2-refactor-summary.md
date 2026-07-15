# Step 2 重构总结（2026-07-15）

## 背景

审阅了旧版 Step 2 产出的 `slots-definition.json`，发现两个核心问题：

**问题 1：层级冗余。** 父容器"组 5817"被判定为图表区后，其子节点（5803、矩形 1006、代码 拷贝等）又被单独列出来——重复了。

**问题 2（根本性）：不该预设内容类型。** 旧方案试图对非 TEXT 节点做语义分类，把一堆 GROUP/LAYER/RECTANGLE 归成 `"type": "chart"`。但这带来两个麻烦：
- 判断很难做准（会漏、会错）
- 一旦标记为 chart，模板就把那个区域锁死了——下一期想放文字也放不了

## 改动内容

**核心思路转变：从"分类区域"变成"只提取可变文字"。**

旧思路：对整个模块做区域划分 → 判断每个区域是 text slot 还是 chart slot 还是 fixed region

新思路：只遍历 TEXT 节点 → 判断每个 TEXT 是可变还是固定 → 提取可变文本的样式。非 TEXT 节点一概不碰，留给下一期的实际内容决定放什么。

**具体改动：**

1. **删掉了 `chart` 类型** —— 不再对非 TEXT 节点做语义分类
2. **删掉了 `fixed` 区域的 node 分组** —— 非文本的视觉结构归 Step 3/4 处理
3. **新增 `variableTexts` + `fixedTexts`** —— 替代原来的 `slots` + `fixed`
4. **新增 `style` 对象** —— 从 `textRuns[0].font.*` 提取字号、字体、颜色、行高、字间距等
5. **明确了因果链条** —— 行业热点 → 决定推荐产品 → 产品卡和推荐理由跟着变
6. **补充了易错场景** —— 含产品名的 TEXT 一定可变、风险警告里费率数值可变但合规声明固定

## 待做

- Step 3（generate-css）、Step 4（generate-template）、Step 5（generate-content-json）需要同步调整，适配新的输出格式（`variableTexts` / `fixedTexts` 替代旧的 `slots` / `fixed` / `chart`）
- 用新 Step 2 重新跑一次 huaxia-hot-citc 项目，产出新的 `slots-definition.json`

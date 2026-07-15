# Output Skill 结构定案

> 解决的问题：OD agent 用的 `-od` skill 到底长什么样——目录结构、文件职责、各文件之间的映射关系。

## 1. 核心模型：壳自包含 + 角色级文字样式共享

每个模块 = **壳** + **插槽**：

- **壳**：固定的装饰、背景、标签组件。视觉永远不会变（除了高度随内容撑开），DOM 和样式绑在一起，复制即带走
- **插槽**：可变文字（标题、正文、数据来源）。样式按角色（role）跨模块共享

## 2. 目录结构

```text
<project>-od/
├── SKILL.md
├── content.template.json
├── assets/
│   ├── template.html
│   ├── styles/
│   │   ├── reset.css
│   │   └── components.css
│   ├── images/
│   └── icons/
└── references/
    └── components-provenance.md
```

## 3. 文件职责

### `assets/template.html`

唯一的 HTML 权威。每个模块一个自包含区域：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="stylesheet" href="styles/reset.css">
  <link rel="stylesheet" href="styles/components.css">
</head>
<body>

<!-- ============================================ -->
<!-- 营销头图（壳 + 插槽）                        -->
<!-- ============================================ -->
<style>
  .hero__bg     { /* 头图背景 */ }
  .hero__deco   { /* 装饰图层 */ }
</style>

<section data-od-id="hero">
  <!-- 壳的 DOM -->
  <div class="hero__bg"></div>
  <div class="hero__deco"></div>

  <!-- 可变插槽 -->
  <div class="hero__titles">
    <h1 class="frameTitle">{{frameTitle}}</h1>
    <h1 class="frameTitle">{{subtitle1}}</h1>
    <h1 class="frameTitle">{{subtitle2}}</h1>
  </div>
</section>

<!-- ============================================ -->
<!-- 热点速递（壳 + 插槽）                        -->
<!-- ============================================ -->
<style>
  .hotspot__bg     { /* 背景渐变、圆角 */ }
  .hotspot__tag    { /* 热点速递标签：颜色、旋转、字号 */ }
  .hotspot__share  { /* 分享标签 */ }
</style>

<section data-od-id="hotspotExpress">
  <!-- 壳的 DOM -->
  <div class="hotspot__bg"></div>
  <span class="hotspot__tag">热点速递</span>
  <span class="hotspot__share">分享</span>

  <!-- 可变插槽 -->
  <h2 class="sectionTitle">{{sectionTitle}}</h2>
  <p class="body">{{body}}</p>
  <p class="sourceNote">{{sourceNote}}</p>
</section>

</body>
</html>
```

关键设计：
- **`<style>` 在 `<section>` 外面但紧贴它**。OD agent 复制 section 时 `<style>` 原样保留一次即可，不随 blueprint 重复
- **壳的 DOM 和样式在同一处**。想复制模块，整块注释 + `<style>` + `<section>` 一起搬
- **插槽用 `class="<role>"`**（如 `class="frameTitle"`），不是模块专属 class。样式由 `components.css` 统一定义
- **壳的 class 用模块前缀**（如 `.hotspot__tag`），在壳的 `<style>` 内定义，不污染共享样式

OD agent 的渲染规则：

```
遍历 template.html：
  <style> → 原样保留，全局生效
  <section data-od-id="xxx">
    → 在 content.template.json 中找到 key
      → 取数组 [N条]
        → N=0 → 跳过该 section
        → N≥1 → 复制 section 内 DOM N 次，填 {{slot}}
    → 找不到 key → 固定模块，section 内 DOM 原样保留
```

### `assets/styles/components.css`

**只放角色级文字样式**。来源是 Step 3 从样式来源节点提取的视觉属性：

| class | 对应 role | 来源 |
|-------|----------|------|
| `.frameTitle` | `frameTitle` | Step 3 从 styleSource 节点提取 |
| `.sectionTitle` | `sectionTitle` | 同上 |
| `.body` | `body` | 同上 |
| `.sourceNote` | `sourceNote` | 同上 |

生成原则：
- 只包含文字样式：字号、字重、行高、字间距、颜色、text-align
- **不包含壳的样式**（背景、标签、装饰等），壳的样式在 `template.html` 的 `<style>` 块
- 不写死容器高度 / 绝对 Y 坐标，交给浏览器 flow
- 所有值 ÷3 换算（1125px 设计稿 → 375px 逻辑宽度）

### `assets/styles/reset.css`

浏览器默认样式重置，不需要从设计稿生成，写固定的一份：

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif; }
```

### `content.template.json`

所有模块的数据，每个 key 对应一个数组：

```json
{
  "hero": [
    {
      "frameTitle": "市场开启震荡模式",
      "subtitle1": "\"反脆弱\"红利低波",
      "subtitle2": "\"反脆弱\"价值凸显"
    }
  ],
  "hotspotExpress": [
    {
      "sectionTitle": "红利低波反脆弱价值凸显",
      "body": "根据AI推荐，近期红利低波策略因估值优势...",
      "sourceNote": "数据来源：Wind，截至2026.5.22。"
    }
  ],
  "recommendations": [
    {
      "frameTitle": "左手红利 右手低波",
      "sectionTitle": "攻守兼备的组合底仓",
      "body": "中证红利低波动指数选取50只流动性好...",
      "sourceNote": "资料来源：华泰研究。"
    },
    {
      "frameTitle": "\"哑铃型\"策略 重构市场估值体系",
      "sectionTitle": "",
      "body": "从一季度持仓图谱看，险资坚定执行...",
      "sourceNote": "数据来源：Wind，截至2026.3.31。"
    }
  ],
  "bankEnding": [{}]
}
```

规则：
- 数组长度 = 该模块渲染几个实例
- 空数组 `[]` = section 不渲染
- 不在此文件中的 `data-od-id` = 没有可变数据，section 内 DOM 原样保留

### `assets/images/` + `assets/icons/`

位图、装饰图、SVG 图标。`template.html` 的壳 DOM 和壳 `<style>` 中通过 `url()` 引用。

### `references/components-provenance.md`

溯源表。记录每个 class 的数值来源：来自哪个 module JSON、哪个 node id、是否经过 scale 换算。

**OD agent 生成时不读取此文件。** 仅用于人工排查校正。

### `SKILL.md`

OD agent 的工作说明。明确它是移动端 H5 design-template，不自由设计。

## 4. 映射关系

### 模块级

```
data-od-id  =  content.template.json 的 key
```

固定模块没有 json key，只有 `data-od-id`。

### 样式级

```
Step 2 fixedGroups  →  壳的 DOM + 壳的 <style>  →  template.html（模块自包含）
Step 2 variableTexts →  role 级文字样式         →  components.css（跨模块共享）
```

### 字段级

```
content.template.json:  { "frameTitle": "左手红利 右手低波" }
                                ↓
template.html 插槽:      <h1 class="frameTitle">{{frameTitle}}</h1>
                                ↓
生成结果:                <h1 class="frameTitle">左手红利 右手低波</h1>
```

## 5. 生成链路

```
mg-to-od-skill-v2:
  Step 1: 模块拆分归类
    → modules-classification.json

  Step 2: 区分固定与可变（逐模块输出中间文件）
    → data/<project>/step2-slots/<groupId>/
        shell.html       ← 壳的 DOM
        shell.css        ← 壳的样式
        slots.json       ← 可变插槽定义（nodeId + role + styleSource）

  Step 3: 提取文字样式
    → 消费 slots.json，读取对应节点样式
    → data/<project>/step3-styles/<groupId>/slot-styles.css

  Step 4: 合成 template.html
    → 合并所有 shell.html + shell.css → 壳的 <style> 块 + 壳的 DOM
    → 插入插槽占位（{{slotName}}）
    → 接入 <link> 引用、meta 标签等骨架

  Step 5: 合成 components.css
    → 合并所有 slot-styles.css，按 role 去重合并

  Step 6: 生成 content.template.json + SKILL.md

OD agent:
  读 SKILL.md → 读 template.html → 遍历 section
    → 查 content.template.json
      → 有 → 取数组 → 遍历填 {{slot}} → 拼出 instance
      → 无 → 固定模块，DOM 原样保留
    → 输出 index.html
```

## 6. 中间产物目录

中间文件按 Step 分目录存放：

```
data/huaxia-hot-citc/
  step2-slots/                  ← Step 2 产出
    hero/
      shell.html
      shell.css
      slots.json
    hotspot/
      shell.html
      shell.css
      slots.json
    productCard/
      ...
    recommendations/
      ...
    riskDisclosure/
      ...
    bankEnding/
      ...

  step3-styles/                 ← Step 3 产出
    hero/
      slot-styles.css
    hotspot/
      slot-styles.css
    ...
```

好处：
- 每个模块独立一个目录，改一个不影响其他
- Step 4/5 合成时按 `modules-classification.json` 的 `moduleOrder` 拼接，调顺序只需调合成逻辑
- 增删模块 = 增删目录，不碰其他模块

## 7. 与旧版的关键差异

| | 旧版 | 新版 |
|---|---|---|
| 壳的样式位置 | `components.css` | `template.html` 内 `<style>` 块（模块自包含） |
| `components.css` 内容 | 壳样式 + 文字样式混合 | 只有角色级文字样式（frameTitle/body 等） |
| `references/component-templates.md` | 存在，放 HTML 片段 + slot | **已删除**，模板并入 `template.html` section |
| 模块自包含性 | 壳的 DOM 和样式分离在两个文件 | 壳的 DOM + `<style>` 在同一区域，复制即带走 |
| 中间产物 | 无 | per-module shell.html / shell.css / slots.json |
| data-od-mode | 三种 mode | 已删除 |

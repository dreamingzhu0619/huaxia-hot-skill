---
name: huaxia-hot-cmb-od
description: |
  华夏基金「热点速递」营销 H5（移动端）。按用户在对话里给的本期内容，
  依固定的组件模板拼出一张高保真的静态 index.html——热点正文、市场解读、推荐理由、
  图表数值、产品卡等内容随期变，样式/布局/装饰/合规条文全部锁死不变。高度随内容自适应。
  当用户要「出一期华夏热点速递 H5」「基金营销 H5」「换一期热点速递内容」时使用。
triggers:
  - "华夏热点速递"
  - "热点速递"
  - "基金营销 h5"
  - "华夏基金 h5"
  - "换一期热点速递"
od:
  mode: prototype
  platform: mobile
  scenario: design
  preview:
    type: html
    entry: index.html
  design_system:
    requires: false
---

# 华夏热点速递 H5（Open Design 版）

这个 skill **不从零画页面**，也不做运行时 JS 渲染。它的工作方式：
**拿到本期内容（用户在对话里说）→ 按 `references/component-templates.md` 的固定模板，
把每个组件拼成静态 HTML → 组装出 `index.html`。** 样式是 `components.css` 说了算，你只写内容。

保真原则：所有固定样式都精确取自原设计稿数据（见 `references/components-provenance.md` 的节点级溯源），
**不要**自行发挥字体/颜色/间距/装饰。内容之外一律不动。

## 本期内容从哪来：优先对话输入

**用户的本期内容主要通过对话给你**（例如「推荐理由 3 页，分别讲…；图表数据是…」）。
你的任务是把这些口述内容**映射到下面的内容结构（schema）**，再走 Workflow 生成。

`content.template.json` 是**内容结构的参考示例（schema 速查表）**，不是用户逐期编辑的文件——
它告诉你「一期内容包含哪些组件、每个组件有哪些字段、哪些是可多页的数组」。用它来对齐字段名与结构：
- **每个模块几页** = 带 `[ ]` 的数组：`recommendation`（推荐理由 N 页）、`market-analysis.points`（N 段分论点）、
  `compliance-notice.products`（N 只产品）。
- **每页内容** = `{}` 里的字段（title/body/source/chart 等）。`_` 开头字段是注释。
- 没出现在 schema 里的一切 = 锁死的固定样式/装饰/合规格式，不可改。

> 只有当用户**明确说「我改了 content.template.json / 用这个文件里的内容」**时，才去 Read 根目录那份 json 取值；
> 否则一律以对话内容为准（json 仅作字段结构参考）。

## 资源清单

```
huaxia-hot-cmb-od/
├── SKILL.md                          ← 你正在读
├── content.template.json             ← 内容结构参考示例（schema 速查：有哪些组件/字段/可多页数组）
├── assets/
│   ├── template.html                 ← 静态种子：8 模块完整骨架（含 3 个固定模块 + data-od-id）
│   └── styles/
│       ├── components.css            ← flow 组件样式权威（4 个可复制组件）
│       └── fixed/                     ← 3 个固定模块的原样式（banner/buy-fund-cmb/compliance-notice）
├── references/
│   ├── component-templates.md        ← 【核心】每组件的静态 HTML 模板 + 图表算法（拼装照它）
│   ├── components-schema.md           ← 7 大类组件的判定与 schema
│   └── components-provenance.md       ← 每处固定样式 ↔ 源节点 id 的溯源对照
└── example.html                      ← 画廊预览
```

## Workflow

### Step 0 —— 预读（动手前做一次）
1. 明确本期要生成的内容：**以对话里用户给的为准**（哪些组件、recommendation 有几页、产品是哪几只、图表数据）。
   需要核对内容结构/字段名时，参考 `content.template.json`（schema 示例）；仅当用户明确说「用 json 里的内容」时才 Read 它取值。
2. 读 `references/component-templates.md`——这是拼装配方：每个组件的静态 HTML、复用的角标/手 SVG、图表算法。
3. 读 `assets/template.html`，它是**上一期的完整成品**，含 3 个固定模块（banner/buy-fund-cmb/compliance-notice）
   的完整骨架。你的 index.html 以它为基准，只替换可变内容。

### Step 1 —— 起页
把 `assets/template.html` 复制为项目根 `index.html`，把 `assets/styles/` 复制为项目根 `css/`（保持 `<link>` 路径）。
先得到一份和设计稿一致、能正常加载样式的基线。

### Step 2 —— 逐组件替换内容（只改内容，不碰样式/结构）
按 `component-templates.md` 定位每个 `<section data-od-id="...">`，用本期内容（对话给的，字段结构对照 content.template.json）替换可变槽位：

- **banner**：只换两行标题 `titleLine1/titleLine2`；背景图/角标/装饰/分享按钮锁死。
  位图走 MasterGo 公开 CDN。头图"光"层/位图一(0:921/0:922/0:1317)同时需 `mix-blend-mode:screen` 与
  `background-blend-mode:screen`——后者 MCP 不返回(数据缺陷)、已手动补进 `fixed/00-banner.css`；勿加 background-color。
- **hotspot-frontline**：换 `body`、`source`；标题「热点前线」与角标固定。
- **market-analysis**：无独立导语；按 `points` 数组，每项拼一个 `.market-point`（金标 `heading` + 正文 `body`）；换 `disclaimer`。
- **recommendation**：`content` 是数组，每项拼一张 `.rec` 卡；`chart` 先归一成内部结构再按
  component-templates.md 的公式算成静态 SVG/div（不逐形状还原，数据驱动）。**`chart` 允许自然语言描述**，
  见下「Step 2.5 图表」。
- **related-products**：一张卡内 `big`（居中大 CTA，带奶油手 SVG）+ `small`（名左小 CTA 靠右）。
- **buy-fund-cmb**：完全不变。
- **compliance-notice**：**假表格（PATH 网格）不可改成自适应**，只换产品名/费率数字，且数字要对齐网格；
  风险提示与费率经合规审核，非用户明确要求不改。

### Step 2.5 —— 图表：按数据自由生成，遵守「图表样式契约」

recommendation 每页的 `chart` **不局限于固定图型**。你（agent）根据数据**自行选择或设计最合适的图型**
（柱状 / 分组柱 / 堆叠柱 / 折线 / 面积 / 饼 / 环 / 散点…），生成**干净的静态 SVG/HTML**——
但**必须遵守下面的「图表样式契约」**，让图和整张 H5 是同一套视觉语言。用户不必手写结构化 JSON。

**输入以自然语言为准（唯一通用入口）**：用户怎么说你就怎么听，如「柱状图：2021~2025 光伏装机（GW）
130、160、210、290、360」，或「画个饼图，A/B/C 三块分别占 50%、30%、20%」，或对话里口述。
**不要求用户套任何固定 JSON 结构**——因为图型五花八门，硬套一个 X/Y 的 schema 会削足适履
（饼/环没有轴、散点是两个数值维度、堆叠又是另一种关系）。你根据图型自己决定内部数据怎么组织。
> 结构化对象 `{ type, xLabel, yLabel, categories, series }` **只是 X/Y 类图（柱/线/面积）的可选快捷写法**，
> 用户给了就用；**别把它当通用接口**，更别拿它去套饼/环/散点。

**先定图型，再按图型抽对应的数据**（各图型要的数据形状不同）：
- **柱状 / 折线 / 面积**：类别（X 轴刻度）+ 每类一个数值；可多组（多柱/多线）。
- **分组柱**：同一批类别 + 多组数值并列比较。
- **堆叠柱/面积**：同一批类别 + 多组数值**累加**成总量。
- **饼图 / 环形图**：若干「名称 + 数值或占比」，**无 X/Y 轴**；占比不给就用数值自算百分比。
- **散点图**：若干 `(x, y)` 数值点对，**两个都是数值维度、没有类别轴**；可分组着色。
- 选型准则：随时间/连续趋势→折线/面积；离散比大小→柱；构成占比→饼/环；多组对比→分组柱；累计构成→堆叠。
  用户明说以用户为准；**拿不准（图型、单位、哪些算一组、缺了值）就问，别猜**。

**数据铁律**（项目一贯原则）：
- 该配对的数据必须配齐：柱/线的每组值数 = 类别数；散点每点要成对的 (x,y)；饼每块要有名称+值。
  **对不齐 / 缺数 → 停下来问用户，绝不编数、绝不补 0/占位近似**。
- 数值**去单位只留数字**，单位并进标题/图例。

**★ 图表样式契约（取自 `components.css`，务必照用，别自创配色/字号）：**
- **画幅**：卡内可用宽 **321px**（卡 355，左右各 17 padding）。折线/散点等 SVG 类建议 `viewBox="0 0 321 130"`、
  `svg{width:100%;height:130px}`；柱状用 flow `<div>`（高度自适应，不用固定画布）。
- **配色**（主蓝 + 暖橙，最多两三色循环）：折线/描边序列 `#2577E8` → `#FF8C4B`（第三色 `#1593FF`）；
  柱填充金 `#FFD282`（配 `border-radius:8px` + `inset 0 1px 3px rgba(255,255,255,.5)`）；饼/分组多色在
  `#2577E8 / #FF8C4B / #1593FF / #FFD282 / #7FB3F0` 里取。线宽 `stroke-width:2`。
- **字体/字号/色**：图标题 `FZLTCHJW--GB1` 10px `#333`；类别刻度 `FZLTHJW--GB1` 10px `#959595`；
  数值 `FZLTHJW--GB1` 12px `#884209`（暖色图元上）或 `#333`（中性）；字体名统一带回退 `,"PingFang SC",sans-serif`。
- **容器**：外层 `.rec-chart`（gap 9px、padding `4px 0 2px`）、标题 `.rec-chart-title`。能复用现成 class 就复用。
- **布局（居中 / 多图平分栏，默认规则）**：
  - **单张图**：图整体在卡内**水平居中**；图表标题（`.rec-chart-title`）**居中**放在图的**正上方**。
  - **多张图并排**：先取内容可用宽度（卡内 **321px**），按并排的图数**平均分栏**（2 图各约 155px、3 图各约 100px，
    含栏间 gap≈12px）；**每张图连同它的标题在自己那一栏内居中**。栏宽不够时优先缩图、别压字。
  - 以上是默认；用户若要别的排布（竖排、不等宽、某张更大、图配文字并排等），会用**自然语言**说明，以用户为准。
- **风格**：圆角柔和、必要处加 inset 高光；**纯静态 —— 不引图表库、不写 JS**，线/柱/扇形直接用 `<svg>`/div 画。

**样板参考**：`component-templates.md` 的 **bar、line 两段是"契约长什么样"的现成范例**——
常见柱/折线直接照它的算法与 class 出；需要它没有的图型时，仿照其配色/字号/画幅**自行设计** SVG，只要落在契约内即可。

### Step 3 —— 组装与自检
把所有 `<section>` 按顺序放进 `<div class="hx-stage">`，写出 `index.html`。自检：
① 只有可变内容变了，class/结构/样式未动；② 每模块 `<section data-od-id>` 保留（OD Comment AI 靠它定位）；
③ 页面能独立打开、`css/` 在同级、图片走 MasterGo 公开 CDN（无本地图）；④ 高度随内容自适应，无绝对定位残留。

### Step 4 —— 收尾
只发一句简短说明（改了哪几处），**不要**把整份 HTML 源码贴进对话。

## 硬规则
- **样式权威是 components.css + fixed/**，不引用外部设计系统（`design_system.requires: false`）——
  不要把注入的 DESIGN.md/tokens 往页面上套，会破坏还原度。
- **默认 fixed**：拿不准某处该不该改就不改，让用户显式要求。
- **可变即全部可变来源**：仅 `content.template.json` schema 里列出的字段（值以对话内容为准）；除此以外都别动。
- **保真取值有依据**：任何固定样式若需核对，顺 `components-provenance.md` 的 `0:xxx` 回溯到源 CSS/modules，
  不凭肉眼估值、不用占位近似。

## 输出契约
```
index.html
css/            ← 与 index.html 同级（components.css + fixed/），随种子拷入，勿改
```
Open Design 从写出的 `index.html` 生成预览。同一轮不要再额外输出 `<artifact>` 源码块。

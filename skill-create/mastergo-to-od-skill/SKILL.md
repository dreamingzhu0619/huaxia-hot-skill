---
name: mastergo-to-od-skill
description: |
  把一张 MasterGo 设计稿链接转成可装进 Open Design 的 OD design-template skill。
  输入：MasterGo 设计稿 URL + MCP 个人令牌。输出：一个自包含的 OD skill 目录，
  含 SKILL.md / content.template.json / assets（每组件 styles.css + decorations.html + template.html）/ page.html / 溯源表 / example.html。
  当用户说"把设计稿转成 skill""生成设计稿 skill""mastergo 转 od skill""设计稿生成 OD skill"时使用。
---

# MasterGo 设计稿 → OD Skill（meta-skill）

## 这个 skill 做什么

输入一张 MasterGo 设计稿链接 + MCP 令牌，经过 **数据抓取 → 模块拆分 → fixed/variable 判定 → 脚本生成 assets → 组装**，
输出一个对应该稿风格、可装进 Open Design 的 OD design-template skill。

核心复用 `pipeline-template/scripts/` 的通用脚本管线。

## 核心原则

### 能用精确数据的，不让 AI 生成

> **能机械提取的精确值绝不靠 AI 手写。AI 只做语义判断：什么东西会变、什么东西不变、哪些模块应该合并。**

| 脚本负责（机械） | AI 负责（判断） |
|---|---|
| MCP 抓取 → normalize → split → 融合全量数据 | 模块语义命名 |
| 骨架签名比对 → 合并候选 | 模块同类合并确认（读 `references/module-merging.md`） |
| 关键词匹配 → autoFixed/autoVariable 标记 | TEXT 节点 fixed/variable 判定（读 `references/variable-classification.md`） |
| 图表信号检测（强/中/辅助） | 图表区域确认（读 `references/chart-detection.md`） |
| 从 modules JSON 的 d2cCss 机械提取 → styles.css | slot 语义化重命名 |
| PATH→SVG, BITMAP→img, fixed GROUP 子树 → decorations.html | |
| 遍历节点树 + fixed/variable 标记 → template.html（DOM + {{slots}}） | |
| 读索引 → page.html（全局页面骨架） | |
| 组装（page.html + 各组件 template × N + decorations 嵌入）→ example.html | |

### 数据先行 + modules JSON 唯一数据源

**所有判断必须在 pipeline 数据到位之后。** agent 每一步都在读具体数据做决策。

`data/<project>/modules/` 下的 JSON 文件融合了所有 MCP 数据源（getDsl + getD2c + getDesignSvgs + extractSvg + getDesignTexts），是后续所有步骤的**唯一数据源**。提取样式、提取装饰、生成模板、组装——全部只读 modules JSON，**不再回到 raw/**。

- `data/modules/_index.json` → 模块清单、位置、节点数、designScale
- `data/modules/*.json` → 完整节点树（含 d2cCss）、TEXT 内容、PATH 装饰、bitmaps URL、SVG 资源
- `data/analysis/merge_groups.json` → 合并建议
- `data/analysis/diff_result.json` → invariant/variable 逐属性标记
- `data/analysis/singleton_texts.json` → 需人工判定的 TEXT 清单

### 默认 fixed 原则

**拿不准某处该不该变 → 不改。**

---

## 资源清单

```
mastergo-to-od-skill/
├── SKILL.md                              ← 你正在读
├── GROWTH.md                             ← 质量成长记录
├── IMPROVEMENT_PLAN.md                   ← 改进方案
├── .gitignore
│
├── scripts/                              ← 通用 pipeline 脚本（所有脚本接受 --project）
│   ├── fetch/fetch_mcp_data.py           ← MCP 7 步抓取
│   ├── normalize/normalize_to_tree.py    ← 归一化节点树
│   ├── prepare/split_modules.py          ← 拆分模块 + 融合全量 MCP 数据 + designScale 检测
│   ├── render/generate_module_css.py     ← 源 CSS 生成（支持 --auto-scale）
│   ├── analyze/diff_modules.py           ← 骨架签名比对 + diff + autoFixed 标记
│   ├── generate/extract_styles.py        ← 机械提取 → styles.css
│   ├── generate/extract_decorations.py   ← 提取 PATH/SVG/bitmaps + 固定 GROUP 子树 → decorations.html
│   ├── generate/generate_template.py     ← 遍历节点树 + 标记 → template.html
│   ├── generate/generate_page.py         ← 读索引 → page.html（全局骨架）
│   ├── assemble/build_html.py            ← 组装引擎
│   └── lib/css_core.py                   ← CSS 生成核心库
│
├── config/                               ← 项目配置骨架
│   ├── project.config.json               ← 骨架（填 designUrl）
│   └── local.secret.json                 ← 骨架（填 mcpToken）
│
├── assets/                               ← meta-skill 自身的共享资源
│   └── shared/
│       └── page.css                      ← 页面容器 + 全局字体模板
│
├── data/                                 ← 每个设计稿的工作数据
│   └── <name>/
│       ├── config/                       ← 该项目配置
│       ├── raw/                          ← MCP 原始响应（只读归档）
│       ├── normalized/                   ← tree.md + tree.json
│       ├── modules/                      ← 【唯一数据源】融合全量 MCP 数据的模块 JSON
│       └── analysis/                     ← merge_groups + diff_result + singleton_texts
│
├── output/                               ← 最终 OD skill 产物
│   └── <name>-od/
│       ├── SKILL.md                      ← OD skill 入口
│       ├── content.template.json         ← 内容结构参考
│       ├── assets/
│       │   ├── shared/
│       │   │   ├── page.css              ← 页面容器 + 全局字体
│       │   │   └── page.html             ← 全局页面骨架（<html> + <head> + 容器 + 组件占位）
│       │   └── <component>/
│       │       ├── styles.css            ← 精确视觉值（从 modules JSON 的 d2cCss 提取）
│       │       ├── decorations.html      ← 装饰元素（PATH→SVG + BITMAP→img + 固定 GROUP 子树）
│       │       └── template.html         ← DOM 骨架 + {{slots}}（脚本生成）
│       ├── output/
│       │   ├── example.html              ← 填入示例数据的完整页面
│       │   └── template.html             ← 未填数据的种子模板
│       └── references/
│           ├── component-templates.md    ← 组件拼装配方 + 图表算法
│           ├── components-schema.md      ← 组件分类 + fixed/variable 判定记录
│           └── components-provenance.md  ← 样式 ↔ 源节点溯源表
│
└── references/                           ← meta-skill 方法论文档
    ├── pipeline.md                       ← 脚本运行细节
    ├── gotchas.md                        ← 排查清单（持续沉淀）
    ├── od-skill-spec.md                  ← OD skill 安装与注入规范
    ├── module-merging.md                 ← 模块同类合并判断规则
    ├── variable-classification.md        ← fixed/variable 判定规则
    └── chart-detection.md               ← 图表区域识别规则
```

---

## 数据架构

### 全流程总览

```
data/raw/                        ← MCP 抓取，归档不动
    │
    ▼  split_modules.py（融合 getDsl + getD2c + getDesignSvgs + extractSvg + getDesignTexts）
data/modules/*.json               ← 【唯一数据源】每个节点含完整 d2cCss + assets.svgs + bitmaps URL
    │
    ├─── Step 4: fixed/variable 判定（脚本初筛 + AI 确认）
    │     判定结果标记到每个节点：fixed / variable / variable-all
    │
    ├─── Step 5a: extract_styles.py → styles.css
    │     从每个节点的 d2cCss / fill / font 字段机械提取视觉属性
    │
    ├─── Step 5b: extract_decorations.py → decorations.html
    │     机械提取 PATH→SVG, BITMAP→img
    │     + 纳入判定为 fixed 的完整 GROUP 子树
    │
    ├─── Step 5c: generate_template.py → template.html
    │     遍历节点树 + 读 fixed/variable 标记 → 规则翻译 → DOM + {{slots}}
    │
    ├─── Step 5d: generate_page.py → page.html
    │     读 _index.json 组件顺序 → 拼 <html> 骨架 + <link> 列表
    │
    └─── AI 审核：slot 语义化重命名
    │
    ▼  build_html.py
output/example.html               ← page.html + 各组件 template × 实例数 + decorations 嵌入
```

### 数据融合说明

`split_modules.py` 在拆分模块时，将以下数据源融合到每个节点中：

| 数据源 | 融合到节点的字段 | 用途 |
|--------|----------------|------|
| getDsl | `type`, `name`, `children`, `fill`, `font`, `text`, `textRuns`, `path`, `layoutStyle` | 节点树结构 + TEXT 内容 + PATH 路径数据 |
| getD2c | `d2cCss`（每个节点的完整 CSS 属性） | styles.css 的权威值来源（精确的 line-height, letter-spacing, font-weight 等） |
| getDesignSvgs | `assets.svgs[nodeId]`（SVG 字符串） | decorations.html 的内联 SVG |
| extractSvg | 提取后的 SVG 文件内容 | 补充 assets.svgs |
| getDesignTexts | TEXT 节点内容 | 补充/校验 getDsl 的 text 字段 |

### 输出结构

```
output/<name>-od/
├── SKILL.md                    ← OD skill 入口
├── content.template.json       ← 内容结构参考（schema 速查表）
├── assets/
│   ├── shared/
│   │   ├── page.css            ← 页面容器 + 背景 + 全局字体
│   │   └── page.html           ← 全局页面骨架
│   ├── <component-1>/
│   │   ├── styles.css          ← 精确视觉值（机械提取）
│   │   ├── decorations.html    ← 装饰元素（PATH→SVG + BITMAP→img + 固定 GROUP 子树）
│   │   └── template.html       ← DOM 骨架 + {{slots}}
│   └── ...
├── output/
│   ├── example.html            ← 填了示例数据的完整页面（画廊预览）
│   └── template.html           ← 未填数据的种子模板
└── references/
    ├── component-templates.md  ← 组件拼装配方 + 图表算法
    ├── components-schema.md    ← 组件分类体系 + fixed/variable 判定记录
    └── components-provenance.md ← 样式 ↔ 源节点溯源表
```

### 四个核心文件的分工

```
styles.css              decorations.html           template.html             page.html
──────────              ────────────────           ─────────────             ────────
从哪里来：              从哪里来：                  从哪里来：                 从哪里来：
modules/*.json          modules/*.json              modules/*.json            _index.json
的 d2cCss/fill/        的 PATH→assets.svgs         遍历节点树 +              组件顺序
font/border 字段       的 BITMAP→exportImage       fixed/variable 标记
                       的 fixed GROUP 完整子树      规则翻译每个节点

放什么：                放什么：                    放什么：                   放什么：
不可变的精确             不可变的装饰元素             FRAME → <section>         <!DOCTYPE html>
视觉属性                 固定 GROUP 子树             TEXT(variable)→{{slot}}   <head> + meta
#FCCC89 不是 #FCC       完整进入（含其中的 TEXT）    TEXT(fixed)→原文           <link> 列表
55.85px 不是 56px                                 图表→{{chart}}             <body> + 容器

加载方式：              加载方式：                  引用 styles.css 的 class    组装时的外骨架
<link> 引入             组装时嵌入到                 引用 decorations.html      各组件 HTML
                       template.html              的 SVG/img                 插入到容器内
                       的对应位置
```

---

## 判定体系

三个参考文档定义了完整的判定规则，在对应 Step 中必须读取：

- **`references/module-merging.md`** — 哪些模块应该合并为同一组件类型（三步排查法）
- **`references/variable-classification.md`** — 每个节点的 fixed / variable / variable-all 判定（四原则 + 脚本规则 + AI 流程）
- **`references/chart-detection.md`** — 图表区域识别（强/中/辅助信号 + 整块 variable-all 处理）

---

# 工作流

按顺序执行。🧑 = 需要用户确认。

---

## Step 0 —— 输入 & 建工作区

拿到两个必填输入：
1. **MasterGo 设计稿链接**（`designUrl`）
2. **MCP 个人令牌**（`mcpToken`，MasterGo 个人设置 → 安全设置 → 个人访问令牌，需团队版）

```bash
NAME="<name>"   # 设计稿英文 slug
mkdir -p "data/$NAME/config"
cp config/project.config.json "data/$NAME/config/"
cp config/local.secret.json "data/$NAME/config/"
# 编辑 data/<name>/config/project.config.json → designUrl
# 编辑 data/<name>/config/local.secret.json → mcpToken
```

连通性检查：
```bash
python scripts/fetch/fetch_mcp_data.py --project $NAME --check
```

---

## Step 1 —— 抓取（脚本）

```bash
python scripts/fetch/fetch_mcp_data.py --project $NAME        # → data/$NAME/raw/
```

MCP 7 步抓取原理详见 `references/pipeline.md`。

**关键规则**：
- getDsl 必须最先调用（否则 path.data / textRuns 永久丢失）
- 批次间内置延迟防限流：section 批次间 3s，Step 5 前 10s，Step 7 前 5s
- 所有工具调用必须全部 ok，不接受部分失败

---

## Step 2 —— 归一化 + 模块拆分（脚本 + 命名确认）

```bash
python scripts/normalize/normalize_to_tree.py --project $NAME  # → data/$NAME/normalized/
python scripts/prepare/split_modules.py --project $NAME        # → data/$NAME/modules/
```

### 2a. normalize_to_tree.py

从 raw getDsl 提取所有节点的 type/id/name/text，按层级缩进输出为 `tree.md`。用于人工核对设计稿的层级结构。

### 2b. split_modules.py（核心脚本）

按设计稿顶级 FRAME 切分模块，融合全量 MCP 数据：

**数据融合**：每个模块 JSON 包含此模块的完整数据——节点树（getDsl）+ 每个节点的 d2cCss（getD2c）+ assets.svgs（getDesignSvgs + extractSvg）+ bitmaps URL + TEXT 内容（getDesignTexts）。

**自动检测**：
- `designScale`：根据页面宽度与 375/390/414/360/320 比对，推断 @1x/@2x/@3x
- `outlinedText`：GROUP 节点名含 CJK 字符 + 子树无 TEXT 节点 → 标注
- 所有数值缩放到逻辑像素（÷ designScale）

**产物**：
```
data/<name>/modules/
├── _index.json           ← 模块索引：序号、fileName、moduleName、position、nodeCount、designScale
├── 00-背景图.json         ← 完整子树 + d2cCss + assets + bitmaps URL
├── 01-产品卡.json
└── ...
```

`_index.json` 中 `meta.designScale` 字段记录缩放比。`meta.page.width/height` 为原始像素。

### 2c. 模块命名确认 🧑

1. 读 `data/modules/_index.json` + `data/normalized/tree.md`
2. 给每个模块英文 slug（看 FRAME 名称 + 看内容），按 position.y 排序
3. 列出清单给用户确认：序号、英文 slug、中文名称、图层名、尺寸

---

## Step 3 —— 源 CSS + 设计稿缩放（脚本）

```bash
python scripts/render/generate_module_css.py --project $NAME           # → 源 CSS（原始分辨率）
python scripts/render/generate_module_css.py --project $NAME --auto-scale  # → 逻辑像素 CSS
```

产物：每模块精确源 CSS（`position:absolute` + `.n-0-xxx` class），用于后续还原度校验。

**如果 `designScale` ≠ 1，必须跑 `--auto-scale`**：所有 px 值 ÷ scale。

---

## Step 4 —— 同类合并 + fixed/variable 判定 🧑

**这是整个 pipeline 最核心的判断环节。必须在生成 assets 之前完成，因为判定结果决定了 decorations.html 的范围（哪些 GROUP 整组进入）和 template.html 的结构（哪些 TEXT 是 {{slot}}）。**

### 4a. 脚本：骨架签名比对（diff_modules.py）

```bash
python scripts/analyze/diff_modules.py --project $NAME   # → data/$NAME/analysis/
```

- 对所有模块做骨架签名比对（只看节点 type 层级，忽略坐标、文本、图表内部结构）
- 签名相同的标记为候选合并组
- 自动标 fixed：`type ≠ TEXT` → fixed；合规关键词 → fixed；费用表头 → fixed
- 自动标 variable：日期格式 → variable；纯数字+% → variable；含"数据来源"→ variable

产物：
- `merge_groups.json` — 合并组候选 + singleton 清单
- `diff_result.json` — 合并组内 invariant/variable 逐属性标记
- `singleton_texts.json` — 按模块列出 autoFixed + needsReview 的 TEXT 清单

### 4b. AI：模块合并确认

**读 `references/module-merging.md`。**

三步排查法（从易到难）：
1. **看 FRAME 名称**：是否含相同前缀 + 字母/数字后缀？（如"推荐理由A/B/C"）
2. **看正文内容**：语义上是否属于同一主题？（都在描述"为什么推荐这个产品"）
3. **看固定元素/层级**：背景底框 fill/颜色是否一致？骨架签名是否一致？

确认合并后，合并组只产生 1 套 assets。推荐理由 A/B/C → 1 个 `recommendation/` 组件目录。

### 4c. AI：TEXT 节点 fixed/variable 判定

**读 `references/variable-classification.md`。**

对 `singleton_texts.json` 中 `needsReview` 的每个 TEXT 节点，回答三个问题：
- 这个文字从哪里来？（行情数据？用户填写？品牌方提供？合规部门？）
- 这个文字在页面里担任什么角色？（标题？正文？标签？按钮？角标？）
- 下一期换内容，这个文字需要改吗？

**特别关注固定装饰 GROUP**：如果一个 GROUP 的 TEXT 子节点是模块固有的装饰文字（如"热点速递"角标、"小试一笔"CTA），则整个 GROUP → fixed → 完整进入 decorations.html。

### 4d. AI：图表区域识别

**读 `references/chart-detection.md`。**

三档信号：
- **强信号**：附近有"数据来源"/"资料来源"/"统计区间"等 TEXT
- **中信号**：GROUP 内含 ≥ 5 个 LAYER 或 ≥ 3 个 PATH/SVG_ELLIPSE
- **辅助信号**：同级有标题类 TEXT、`name` 含"图表""统计"等

图表 → `variable-all` → template.html 中暴露为 `{{chart}}`，不逐节点 diff 内部结构。

### 4e. 用户确认 🧑

逐模块展示判定结果，用户确认或调整。**用户意见与启发式规则冲突时以用户为准。**

判定结果写入模块 JSON 或单独的 variability 配置文件，Step 5 脚本读取这些标记。

---

## Step 5 —— 生成 assets（全部脚本）

**此步骤全部由脚本完成，不需要 AI 手写任何 DOM 或 CSS。**

### 5a. extract_styles.py → styles.css

```bash
python scripts/generate/extract_styles.py --project $NAME
```

从 merged 组件代表模块的每个节点的融合数据中（优先 d2cCss，补充 getDsl fill/font/textRuns）机械提取视觉属性：

```
数据源                    →  CSS 输出
────────────────────────────────────────────
d2cCss.background        →  background / background-image
d2cCss.border-radius     →  border-radius
d2cCss.border            →  border
d2cCss.font-family       →  font-family
d2cCss.font-size         →  font-size
d2cCss.color             →  color
d2cCss.line-height       →  line-height
d2cCss.letter-spacing    →  letter-spacing
d2cCss.box-shadow        →  box-shadow
getDsl fill              →  补充（d2cCss 缺失时）
getDsl font              →  补充（d2cCss 缺失时）
getDsl textRuns[].color  →  补充（d2cCss 缺失时）
```

每条 CSS 规则带溯源注释：`/* 0:51 LAYER -- 矩形 23 拷贝 14 */`

位置属性（left/top/position:absolute）只保留在源 CSS 中用于校验，最终输出的 styles.css 使用 flow 布局（flex + margin）。

### 5b. extract_decorations.py → decorations.html

```bash
python scripts/generate/extract_decorations.py --project $NAME
```

两层提取逻辑：

**第一层：机械提取装饰节点**

| 节点类型 | 处理方式 |
|----------|----------|
| PATH | 内联 SVG（从 `assets.svgs[nodeId]` 取，预做渐变合法化） |
| BITMAP | `<img src="...">`（从 `assets.bitmaps` 的 URL） |
| 装饰 LAYER | `<div>` + class（样式已在 styles.css） |
| outlinedText GROUP | `<span>` + `background-clip:text` 渐变（文字来自节点 name） |
| Gradient Overlay PATH | 叠加在对应 TEXT 上的 SVG 渐变层 |

SVG 后处理：`fill="linear-gradient(...)"` → `<defs>` + `fill="url(#id)"`；注入 `shape-rendering="crispEdges"`；viewBox 非零起点 → 注入 `position:absolute`。

**第二层：纳入判定为 fixed 的 GROUP 子树**

读 Step 4 的判定结果：
- 如果整个 GROUP 被判定为 `fixed`（所有子节点含 TEXT 都是 fixed）→ 该 GROUP 的完整子树递归渲染到 decorations.html
- 典型场景："热点速递拷贝"角标 GROUP（含 PATH + LAYER + TEXT"热点速递"）、""按钮"GROUP（含红色背景 LAYER + TEXT"小试一笔"）

产物：`output/<name>-od/assets/<component>/decorations.html`

### 5c. generate_template.py → template.html

```bash
python scripts/generate/generate_template.py --project $NAME
```

遍历节点树 + 读 Step 4 的 fixed/variable 标记，按规则翻译每个节点为 DOM：

```
节点类型 / 标记          →  template 输出
──────────────────────────────────────────────────
FRAME (根)               →  <section data-od-id="组件名">
FRAME (子)               →  <div class="...">
LAYER (fixed, 装饰)      →  不在 template 中（已在 styles.css / decorations.html）
LAYER (fixed, 背景框)    →  <div class="...">（样式在 styles.css）
TEXT (variable)          →  <span class="...">{{slotName}}</span>
TEXT (fixed)             →  <span class="...">固定文字</span>
GROUP (含 variable 子节点) →  <div class="..."> 递归包裹子节点
GROUP (全 fixed)         →  不在 template 中（整体已在 decorations.html）
PATH / BITMAP            →  不在 template 中
图表 GROUP (variable-all) →  <div class="...">{{chart}}</div>
```

slot 名初稿使用节点 ID：`{{text_0_76}}`、`{{text_0_57}}`。AI 审核后改为语义化名称。

产物：`output/<name>-od/assets/<component>/template.html`

### 5d. generate_page.py → page.html

```bash
python scripts/generate/generate_page.py --project $NAME
```

读 `_index.json` 获取合并后的组件类型和页面顺序 → 拼出全局页面骨架：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{pageTitle}}</title>
  <link rel="stylesheet" href="assets/shared/page.css">
  <link rel="stylesheet" href="assets/<component-1>/styles.css">
  <link rel="stylesheet" href="assets/<component-2>/styles.css">
  ...  ← 每个组件一条 <link>
</head>
<body>
  <div class="page-container">
    <!-- 组件按 position.y 顺序在此处插入 -->
  </div>
</body>
</html>
```

`page.css` 的容器宽度 = `designScale.logicalWidth`（如 375px）。

### 5e. AI 审核：slot 语义化重命名 🧑

脚本生成的 slot 名是 `{{text_0_76}}`、`{{text_0_57}}`，AI 根据节点 name、文本内容、树位置 → 语义化重命名：

| 脚本产出 | AI 重命名 | 依据 |
|----------|----------|------|
| `{{text_0_76}}` | `{{mainTitle}}` | 推荐理由主标题 |
| `{{text_0_57}}` | `{{productName}}` | 产品全称 |
| `{{text_0_63}}` | `{{productCode}}` | 产品代码 |
| `{{text_4_269}}` | `{{returnValue}}` | 涨跌幅数值 |

---

## Step 6 —— 组装（脚本）

```bash
python scripts/assemble/build_html.py --project $NAME
```

1. 读 `page.html`（全局骨架）
2. 读每个组件的 template.html → 按实例数复制（单实例 ×1；多实例按 `content.template.json` 数组长度） → 用数据填充 `{{slots}}`
3. 在 `<!-- decorations -->` 标记处嵌入 decorations.html
4. 按页面顺序将所有组件的 HTML 插入 `page.html` 的容器内
5. `viewport` = `width=device-width, initial-scale=1.0`，容器宽度 = `designScale.logicalWidth`
6. 输出 `example.html`（填了示例数据）+ `template.html`（种子模板，slots 保留）

---

## Step 7 —— 验收

自检：`example.html` 能独立打开、`data-od-id` 齐、CSS 对应、多实例模块高度自适应。

对照设计稿逐模块核对还原度。偏差 → 查 `references/gotchas.md`。

还原度标准：**无 emoji、无默认 0、无占位近似、无取整近似**（55.85px 不能写成 56px）。

额外检查项：
- [ ] `styles.css` 每条规则有溯源注释
- [ ] `decorations.html` PATH/SVG 数与模块 JSON 的 `assets.svgs` 键数匹配
- [ ] `decorations.html` 包含所有 `outlinedText` 节点 + 所有判定为 fixed 的 GROUP 子树
- [ ] `template.html` `{{slot}}` 名语义化（不是 `.n-0-xxx`）
- [ ] `page.html` `<link>` 列表与组件数量一致
- [ ] `example.html` viewport 为 `width=device-width`，容器宽度为 logicalWidth
- [ ] 所有 px 值为逻辑像素（设计 px / scale）
- [ ] 固定模块源 CSS 规则数 = HTML 中对应 DOM 元素数

---

## Step 8 —— 装进 OD（可选）

```bash
# Windows OD 桌面版 v0.13.0
cp -r "output/<name>/<name>-od" "$LOCALAPPDATA/../Local/Programs/open-design/data/design-templates/"
```
重启 OD 即出现在 design-template 列表。安装细节见 `references/od-skill-spec.md`。

---

## 迭代

- **设计稿变了**：重跑 Step 1~3 → 重判 Step 4 → 重跑 Step 5~6
- **只换一期内容**：不需要本 meta-skill，用产出的 OD skill 在对话里说新内容即可
- **新坑**：追加到 `GROWTH.md`；可抽象的通用规则沉淀到 `references/gotchas.md`

## Windows 注意事项

- `python`（非 python3）；读文件用 Read tool（UTF-8，避 GBK 乱码）；bash 用 Git Bash，路径正斜杠

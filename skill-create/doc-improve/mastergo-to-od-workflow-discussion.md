# MasterGo to OD Skill Workflow Discussion

本文整理关于 `mastergo-to-od-skill` 优化方向的讨论结论。核心目标是：从 MasterGo 设计稿生成一个可在 Open Design 中使用的 H5 output skill，并让该 output skill 能按新一期内容稳定生成页面，而不是只复刻当前设计稿。

## 核心原则

整个流程要分清两类能力：

- **精确提取**：凡是 MCP / 设计稿数据能确定的值，都必须机械提取，不能让 AI 猜。
- **AI 抽象判断**：凡是涉及业务语义、组件复用、fixed/variable 边界的内容，需要 AI 做一次性判断，并把判断结果固化成中间产物和 output skill 的 Markdown 规则。

最重要的边界是：

- `mastergo-to-od-skill` 阶段允许 AI 做组件抽象。
- output skill 在 Open Design 中运行时，应尽量减少 AI 自由判断，只按已生成的 MD 规则填内容、复制组件、生成图表。

## 总流程

```text
MasterGo MCP
  ↓
1. raw 全量抓取
  ↓
2. modules 全量融合
  ↓
3. layout 精确测量
  ↓
4. AI 抽象判断：frame 分组、fixed/variable、slot、高度策略
  ↓
5. 固化 component-spec
  ↓
6. 生成 output skill
  ↓
7. output skill 在 Open Design 中按 MD 规则生成每期 H5
```

## Data 目录建议

```text
data/<project>/
├── raw/
│   ├── getDsl/
│   ├── getMeta/
│   ├── getDesignSections/
│   ├── getDesignTexts/
│   ├── getDesignSvgs/
│   ├── extractSvg/
│   └── getD2c/
├── normalized/
│   ├── tree.json
│   └── tree.md
├── modules/
│   ├── _index.json
│   ├── 00-xxx.json
│   ├── 01-xxx.json
│   └── ...
├── layout/
│   ├── page-layout.json
│   └── measurements.json
└── analysis/
    ├── frame-groups.json
    ├── variability.json
    └── component-spec.json
```

### raw

`raw/` 存 MCP 所有 tool 的原始返回，不做解释，不做抽象，不漏任何 tool。至少包括：

- `getDsl`
- `getMeta`
- `getDesignSections`
- `getDesignTexts`
- `getDesignSvgs`
- `extractSvg`
- `getD2c`

这一层是证据库。任一关键 raw 缺失，都不应该继续生成 output skill。

### normalized

`normalized/` 用于方便查看树结构，例如 `tree.md` 和 `tree.json`。它是辅助阅读产物，不应该成为最终渲染事实来源。

### modules

`modules/` 是后续所有判断的主要事实来源。每个模块 JSON 都应该融合所有 MCP 数据，包括：

- 节点树
- node id / name / type
- bounds / layout
- text / textRuns
- fill / font / effect
- d2cCss
- SVG / bitmap / CDN URL
- section index 对应关系
- design scale 后的 logical px

原始模块切分规则：先按设计稿顶层 frame 全部切成 module，不急着合并。

### layout

`layout/` 存精确测量结果，不应混在 `analysis/` 里。为了正确生成 H5，必须知道：

- 页面 logical width
- design scale
- 模块顺序
- 不同模块之间的 gap
- 同一类模块不同实例之间的 item gap
- 每个模块原始宽高
- 可测量的 padding / internal gap / minHeight

这些应尽量由脚本计算，不靠 AI 目测。

示例：

```json
{
  "page": {
    "logicalWidth": 375,
    "designScale": 3
  },
  "frames": [
    {
      "moduleName": "营销头图",
      "fileName": "05-营销头图.json",
      "order": 1,
      "y": 0,
      "height": 313,
      "gapAfter": 18
    }
  ],
  "sameTypeGaps": [
    {
      "candidateType": "recommendation",
      "sourceModules": ["产品推荐理由A", "产品推荐理由B", "产品推荐理由C"],
      "itemGap": 16
    }
  ]
}
```

### analysis

`analysis/` 存 AI 或规则判断后的抽象结果。

- `frame-groups.json`：哪些原始 frame 属于同一类组件。
- `variability.json`：每个组件中哪些 fixed、variable、variable-all。
- `component-spec.json`：最终 output skill 生成依据。

## Frame 怎么分

先按 MasterGo 顶层 frame 切原始 module。例如：

```text
背景图
营销头图
热点速递
产品卡
产品推荐理由A
产品推荐理由B
产品推荐理由C
风险警告
银行结束语
```

之后再在分析阶段把原始 module 归类：

- **页面级固定层**：背景图，不进入普通 flow。
- **固定一次模块**：银行结束语等品牌尾部。
- **flow 一次模块**：热点速递、营销头图等，出现一次但内容可变。
- **repeatable 模块**：推荐理由、产品卡等，使用一个模板按内容数量复制。
- **特殊固定结构模块**：风险警告、合规假表格等，局部文字可变，但结构不能 flow 化。

不要一开始就试图直接切成最终 component。

## 是否需要判断 single / array

不建议把重点放在“这个组件未来到底有几个”。output skill 真正需要知道的是：

> 这个 frame 是否允许被复制。

也就是判断 `repeatable` 或 `renderMode`。

示例：

```json
{
  "id": "recommendation",
  "renderMode": "repeatable"
}
```

可选 render mode：

- `background`
- `fixed-once`
- `flow-once`
- `repeatable`
- `absolute-fixed`

推荐理由本期 3 个、下一期 2 个或 5 个，都使用同一个 repeatable 模板按内容数组长度复制。

## 哪些东西精确提取

以下内容必须来自 MCP / modules / layout 的精确数据：

- 页面宽度、design scale
- 模块顺序
- 不同模块之间的 gap
- 同类模块实例之间的 item gap
- 固定视觉值：颜色、字体、字号、行高、圆角、阴影、边框、背景
- 固定装饰：SVG、PATH、位图、logo、背景纹理
- 固定模块的 HTML/CSS
- 源节点溯源：哪个 CSS/装饰来自哪个 node id
- 原设计稿示例文字，用于生成 `example.html` 和 `content.template.json` 初稿

## 哪些需要 AI 判断

以下内容需要 AI 做一次性判断，并固化到 `analysis/` 或 output skill 的 Markdown 里：

- 哪些 frame 是同一类组件，例如 `产品推荐理由A/B/C` 合并为 `recommendation`
- 每种组件是否 repeatable
- 哪些 TEXT 是可变内容，哪些 TEXT 是固定 UI 文案
- 哪些复杂区域应该整块 `variable-all`，例如图表
- slot 命名，例如 `text_0_76` 重命名为 `title`
- 高度策略：`fixed` / `auto` / `bounded-auto` / `absolute-fixed`
- flow 版 HTML 模板如何组织
- output skill 的 `content.template.json` 字段结构
- `component-templates.md` 的组件拼装规则

## Fixed / Variable 判断

不要只从节点类型开始判断。应先问：

> 下一期内容换了，这个内容会不会改？

节点层面的默认原则：

- `PATH / SVG / bitmap / 装饰 LAYER` 默认 fixed。
- `TEXT` 需要语义判断。
- `GROUP` 如果递归子节点全 fixed，整组 fixed。
- `GROUP` 如果含业务文字，保留结构并暴露 slot。
- 图表/复杂数据区域不逐节点抽象，整块 `variable-all`。

推荐理由示例：

```text
产品推荐理由A
├── 背景卡片：fixed
├── 标题装饰：fixed
├── 标题文字：variable -> title
├── 正文：variable -> body
├── 图表区域：variable-all -> chart
├── 资料来源：variable -> source
```

## 高度和间距策略

最终 H5 不能依赖设计稿中的绝对 y 坐标来拼模块。外部页面应使用 flow 布局：

- 模块之间的距离来自原设计稿测量得到的 `gapAfter`。
- 同类实例之间的距离来自原设计稿测量得到的 `itemGap`。
- repeatable 模块按内容数组长度复制。
- 后续模块自然随前面模块高度变化下移。

高度模式建议：

- `fixed`：高度固定，例如纯装饰头图、银行结束语。
- `auto`：高度随内容增长，例如热点正文。
- `bounded-auto`：保留设计稿最小高度，内容多时撑开，例如推荐理由卡片。
- `absolute-fixed`：保留绝对定位，例如合规假表格、固定网格。

设计稿绝对坐标的用途不是直接排版，而是提取：

- padding
- gap
- minHeight
- fixed decoration position
- special fixed grid position

## component-spec.json 的作用

`component-spec.json` 是最关键的中间产物。它把精确测量和 AI 判断固化下来，后续 output skill 只按它生成。

它至少应包含：

- page width / scale
- render order
- module gap / item gap
- component list
- source modules
- render mode
- layout measurements
- height mode
- slots
- fixed fragments
- variable-all regions
- provenance links

示例：

```json
{
  "id": "recommendation",
  "displayName": "产品推荐理由",
  "sourceModules": ["产品推荐理由A", "产品推荐理由B", "产品推荐理由C"],
  "representativeModule": "产品推荐理由A",
  "renderMode": "repeatable",
  "itemGap": 16,
  "heightMode": "bounded-auto",
  "slots": {
    "title": { "type": "text", "required": true },
    "body": { "type": "richText", "required": true },
    "chart": { "type": "visual", "mode": "variable-all" },
    "source": { "type": "text", "required": false }
  },
  "fixed": [
    "background-card",
    "title-decoration",
    "typography",
    "border-radius"
  ]
}
```

## Output Skill 结构方向

参考已在 Open Design 中效果较好的 `huaxia-hot-cmb-od`，output skill 不一定需要每个模块一个 assets 目录。更适合 Open Design 的结构是：

```text
output/<name>-od/
├── SKILL.md
├── content.template.json
├── assets/
│   ├── template.html
│   └── styles/
│       ├── components.css
│       └── fixed/
│           ├── 00-marketing-header.css
│           ├── 06-bank-ending.css
│           └── 07-risk-warning.css
├── references/
│   ├── component-templates.md
│   ├── components-schema.md
│   └── components-provenance.md
└── example.html
```

各文件职责：

- `SKILL.md`：总调度，告诉 Open Design workflow、哪些文件必须读、哪些内容不能改。
- `content.template.json`：内容 schema，只列可变字段。没出现的都锁死。
- `assets/template.html`：完整种子页面，保留固定模块、页面骨架、`data-od-id`。
- `assets/styles/components.css`：所有 flow / repeatable 组件的统一样式权威。
- `assets/styles/fixed/`：不能自适应或必须原样保留的固定模块样式。
- `references/component-templates.md`：核心拼装说明，精确规定每个组件 HTML、重复规则、slot 映射、图表算法、间距规则。
- `references/components-schema.md`：说明组件类型、repeatable、fixed/variable、哪些模块合并成一个组件。
- `references/components-provenance.md`：样式和节点溯源。

## Output Skill 运行时允许 AI 做什么

output skill 在 Open Design 中运行时允许 AI 做：

- 把用户口述内容映射到 `content.template.json` 的字段。
- 按数组长度复制 repeatable 组件。
- 按 `component-templates.md` 生成静态 HTML。
- 根据用户数据生成图表 SVG/HTML。
- 数据缺失、图型不清、数值对不齐时追问用户。

不允许 AI 做：

- 重新判断组件合并。
- 重新定义 slot。
- 改固定样式。
- 改模块顺序。
- 改 fixed 文案，除非用户明确要求。
- 编造缺失数据。

## 图表策略

图表通常不应逐节点还原，而应作为 `variable-all` 区域，由 output skill 根据新一期数据生成静态 SVG/HTML。

但图表生成必须受样式契约约束：

- 画幅
- 配色
- 字号
- 字体
- 线宽
- legend / title 规则
- 容器 padding / gap

用户输入以自然语言为准，例如：

```text
环形图：2025年电网投资结构占比，配电网 35%、特高压 28%、智能变电 22%、其他 15%
```

如果数据缺失或无法配对，output skill 应追问，不得补 0 或编造。

## 当前待定问题

仍需要继续讨论并落地：

1. `component-spec.json` 的正式 schema。
2. `layout/page-layout.json` 和 `measurements.json` 的字段结构。
3. `frame-groups.json` 如何表示“候选”和“确认后分组”。
4. `variability.json` 是单独存在，还是直接合并进 `component-spec.json`。
5. output skill 是否继续沿用 `huaxia-hot-cmb-od` 的集中式结构，还是为某些复杂模块增加单独资源目录。
6. `components.css` 如何从绝对定位 CSS 转成 flow CSS，并保留设计稿间距和最小高度。


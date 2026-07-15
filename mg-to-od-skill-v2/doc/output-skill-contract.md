# Output Skill Contract Draft

> 目的：先定义最终交付给 Open Design 使用的 H5 design-template skill 长什么样，再倒推 `mg-to-od-skill-v2` 内部 pipeline 应该生成哪些中间产物。

## 1. 核心判断

最终 output 不是一个从 D2C HTML 直接改出来的页面，而是一个给 Open Design agent 使用的 skill。

Open Design 生成 H5 时，主要读取 `SKILL.md` 的正文来决定怎么工作。因此，所有关键规则都必须在 `SKILL.md` 里说清楚：读哪些资源、哪些文件是权威、哪些内容可变、哪些样式不能动、如何根据数组重复模块、如何输出 `index.html`。

D2C 返回的 HTML 只能作为数值采样来源，不能作为最终模板直接使用。原因是它把根容器、顶层模块和内部文本都写成了绝对定位，导致模块数量、文字长度、模块高度变化时无法自然排版。

最终方向应该是：

- 精确数值用于视觉规则：宽度、字号、颜色、圆角、阴影、padding、gap、固定装饰位置。
- 自适应用于内容流：文本容器高度、模块高度、页面总高度、模块在根容器中的 y 位置。
- 顶层模块使用正常文档流排列，不再写死 `top`。
- 同类模块实例复用同一套 class，只替换文字、图标、图表数据等可变内容。

## 2. 建议的 Output Skill 目录结构

```text
<project>-od/
├── SKILL.md
├── content.template.json
├── example.html
├── assets/
│   ├── template.html
│   ├── styles/
│   │   ├── components.css
│   │   └── fixed/
│   │       └── *.css
│   ├── images/
│   └── icons/
└── references/
    ├── component-templates.md
    ├── components-schema.md
    └── components-provenance.md
```

## 3. 文件职责

### `SKILL.md`

`SKILL.md` 是 Open Design agent 的主工作说明。

它必须定义：

- 这个 skill 是生成移动端 H5 的 design-template。
- 本 skill 不从零设计，不自由发挥视觉样式。
- 运行时先读取用户输入或 `content.template.json`，再按 `references/component-templates.md` 拼静态 HTML。
- 样式权威是 `assets/styles/components.css` 和 `assets/styles/fixed/*`。
- 可变字段权威是 `content.template.json`。
- 结构权威是 `references/component-templates.md`。
- 没出现在 schema 里的内容默认 fixed。
- 数组字段的长度决定模块实例数量。
- 顶层模块必须走 flow 布局，禁止整页绝对定位。
- 只输出项目根目录的 `index.html`，并保证 Open Design 可预览。

需要特别注意：OD 主要注入 `SKILL.md` 正文，`references/` 和 `content.template.json` 只有被 `SKILL.md` 点名后，agent 才更可能读取。因此关键硬规则不能只写在 reference 里。

### `content.template.json`

`content.template.json` 只描述可变内容，不描述固定样式。

原则：

- 每个顶层 key 对应一类业务模块。
- 数组表示可重复模块，例如产品卡、推荐理由、热点速递。
- 数组长度就是实例数量。
- 每个对象里的字段就是允许替换的 slot。
- `_` 开头字段只作为说明，生成时忽略。
- 没有出现在此文件里的内容，默认锁死。

示意：

```json
{
  "productCards": [
    {
      "name": "产品名称",
      "code": "021483",
      "risk": "较高风险",
      "metricLabel": "近一年涨跌幅",
      "metricValue": "2.80%",
      "cta": "小试一笔"
    }
  ],
  "recommendations": [
    {
      "title": "推荐理由标题",
      "body": "正文内容",
      "chart": {},
      "source": "资料来源"
    }
  ]
}
```

### `assets/template.html`

`template.html` 是完整页面种子，但不是 D2C 的绝对定位 HTML。

它应该只保留稳定页面骨架、模块顺序、必要的 `data-od-id` 和 class。

示意：

```html
<main class="h5-page">
  <section class="module marketing-header" data-od-id="marketing-header"></section>
  <section class="module hotspot-express-list" data-od-id="hotspot-express"></section>
  <section class="module product-card-list" data-od-id="product-card"></section>
  <section class="module recommendation-list" data-od-id="recommendation"></section>
  <section class="module risk-warning" data-od-id="risk-warning"></section>
  <section class="module bank-ending" data-od-id="bank-ending"></section>
</main>
```

顶层模块之间的间距由 CSS 控制，例如 `gap` 或 section 的 margin。模块高度由内容撑开。

允许局部使用绝对定位的场景：

- 模块内部固定装饰。
- 背景纹理。
- 角标。
- 不随文本变化的 SVG/path/image。

禁止使用绝对定位的场景：

- 根容器总高度。
- 顶层模块的 `top`。
- 同类模块实例的位置。
- 因文本长度变化而应自适应的 group 高度。

### `assets/styles/components.css`

`components.css` 是 flow 组件的样式权威。

它应该把 D2C / MasterGo 中的视觉数值抽象成 class，而不是让每个元素 inline style。

例如：

- 标题 class。
- 正文 class。
- 产品卡 class。
- 推荐理由卡 class。
- 标签 class。
- CTA class。
- 图表 class。
- 来源说明 class。

同类模块的不同实例必须复用同一套 class。实例之间只能变内容，不变样式。

### `assets/styles/fixed/*`

用于承载不适合 flow 化、或者业务上必须原样保留的固定模块样式。

例如：

- 背景大图。
- 银行结束语。
- 某些合规风险声明的固定表格。
- 复杂且不随内容变化的装饰模块。

是否进入 `fixed/` 的判断标准不是“D2C 里是 absolute”，而是“业务上是否确实应该固定、不需要随内容变化”。

### `references/component-templates.md`

这是组件拼装配方。

它应该明确：

- 每类组件的 HTML 片段。
- 每个 slot 从 `content.template.json` 哪个字段取。
- 数组如何重复渲染。
- 空数组如何处理。
- 图表数据如何转换成静态 SVG/HTML。
- 哪些固定装饰片段必须照抄。

示意：

```html
<article class="recommendation-card">
  <header class="recommendation-card__header">
    <h2 class="recommendation-card__title">{{title}}</h2>
  </header>
  <p class="recommendation-card__body">{{body}}</p>
  {{chart}}
  <p class="recommendation-card__source">{{source}}</p>
</article>
```

### `references/components-schema.md`

这是模块语义和可变性说明。

它应该记录：

- 有哪些组件。
- 组件顺序。
- 每个组件是 fixed、single 还是 array。
- 每个组件开放哪些字段。
- 哪些 TEXT 虽然在设计稿里是文字，但业务上应该锁死。

示意：

```text
product-card
- mode: array
- width: fixed
- height: auto
- variable: name, code, risk, metricLabel, metricValue, cta
- fixed: card background, border, tag style, CTA style
```

### `references/components-provenance.md`

这是溯源表。

它应该记录每个重要 class 或固定模块的数值来源：

- 来自哪个 module JSON。
- 来自哪个 node id。
- 来自哪个 D2C CSS 片段。
- 是否经过 scale 3 -> 375px 的换算。

这个文件主要用于排查和校正，不一定每次生成 H5 都要读。

## 4. SKILL.md 应先回答的问题

正式写 output skill 的 `SKILL.md` 时，应先回答以下问题。

### 4.1 这个 skill 怎么生成 H5？

读取用户对话内容或 `content.template.json`，按 `component-templates.md` 拼出静态 `index.html`。

### 4.2 哪些文件是权威？

- 样式权威：`assets/styles/components.css` 和 `assets/styles/fixed/*`
- 结构权威：`references/component-templates.md`
- 可变内容权威：用户对话内容或 `content.template.json`
- 溯源权威：`references/components-provenance.md`

### 4.3 哪些事情绝对不能做？

- 不从零设计。
- 不自由发挥字体、颜色、间距、圆角、阴影。
- 不使用整页绝对定位。
- 不把模块实例数量写死。
- 不根据内容手算根容器高度。
- 不给每个元素单独写 inline style。
- 不修改 fixed 模块的固定装饰。

### 4.4 如何处理精确数值和动态高度的矛盾？

精确数值用于视觉约束：

- 页面宽度。
- 模块宽度。
- padding。
- gap。
- 字号。
- 行高。
- 颜色。
- 圆角。
- 阴影。
- 固定装饰位置。

动态计算交给浏览器 flow：

- 文本容器高度。
- 模块高度。
- 页面总高度。
- 顶层模块 y 位置。

### 4.5 最终输出什么？

只输出：

```text
index.html
assets/ 或 css/
```

`index.html` 必须能被 Open Design 直接预览。

## 5. 倒推 `mg-to-od-skill-v2` 内部流程

`mg-to-od-skill-v2` 不应该以“修 D2C HTML”为核心，而应该以“生成 output skill”为核心。

推荐 pipeline：

```text
raw/mastergo + getD2C
→ normalized tree
→ modules/*.json
→ component classification
→ variable slot schema
→ exact CSS extraction / scale 3 to 375
→ flow component templates
→ output/<project>-od/
```

每一步的目标产物：

### 5.1 原始数据采集

输入：

- MasterGo DSL。
- getDesignSections。
- getDesignTexts。
- getDesignSvgs。
- extractSvg。
- getD2C。

目标：

- 保留所有可溯源数据。
- 不在这一层判断最终模板。

### 5.2 模块拆分

输入：

- normalized tree。
- module index。

目标：

- 每个顶层 frame 生成一个 module JSON。
- module JSON 内包含节点树、文本、资源、D2C 匹配信息。

### 5.3 组件分类

输入：

- modules/*.json。
- component-config.json。
- 人工确认。

目标：

- 判定每个模块是 fixed、single 还是 array。
- 判定哪些 TEXT 是 variable。
- 判定哪些 TEXT 是 fixed。
- 判定哪些 group 因包含 variable TEXT 而必须 auto height。

### 5.4 内容 schema 生成

输出：

- `content.template.json`
- `references/components-schema.md`

目标：

- 只暴露 variable 字段。
- 数组字段对应多实例模块。
- fixed 内容不暴露。

### 5.5 样式 class 化

输出：

- `assets/styles/components.css`
- `assets/styles/fixed/*.css`
- `references/components-provenance.md`

目标：

- 从 MasterGo / D2C 取精确视觉数值。
- 缩放到 375 逻辑宽。
- 合并同类实例样式。
- 抽象成稳定 class。
- 避免元素级 inline style。

### 5.6 HTML 模板生成

输出：

- `assets/template.html`
- `references/component-templates.md`
- `example.html`

目标：

- 顶层模块 flow 排列。
- array 组件可重复。
- 文本容器 auto height。
- 固定装饰保留精确位置。
- 可变 slot 使用统一占位。

### 5.7 Output SKILL.md 生成

输出：

- `SKILL.md`

目标：

- 把 OD agent 的工作流写清楚。
- 点名要求读取必要 resources。
- 明确硬规则。
- 明确输出契约。

## 6. 当前阶段建议

现在应先写 output skill 的契约版 `SKILL.md`，再倒推 pipeline。

原因：

- 只有先定义 OD agent 最终该怎么工作，才能判断内部需要生成哪些文件。
- 否则很容易继续被 D2C 的绝对定位 HTML 牵着走。
- `SKILL.md` 是 OD 真正会优先读的文件，它决定这个 output skill 能不能稳定生成 H5。

建议下一步讨论顺序：

1. 先确认 output skill 的目录结构。
2. 再确认 `SKILL.md` 的 workflow 和硬规则。
3. 再确认 `content.template.json` 的 schema 设计。
4. 再确认 `component-templates.md` 如何写组件模板。
5. 最后再讨论 `mg-to-od-skill-v2` 的脚本和 pipeline 怎么生成这些文件。


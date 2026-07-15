# Step 2: 区分固定与可变

## 你要做什么

对一个模块，三步走：

1. **计算内容区**——用脚本算出 padding，确定"可以写字"的范围
2. **区分固定与可变**——固定元素归入 fixedGroups（后续直接复制到模板，不做变量暴露），可变文字记录 nodeId、内容和语义角色
3. **对可变文字分类并归纳样式源头**——同一 role 的多个 text 节点，只取一个有代表性的去 Step 3 提取样式

## 输入

1. `data/<project>/modules/*.json` —— 每个模块的完整 node 树
2. Step 1 输出的 `modules-classification.json`

## 只处理代表模块

Step 1 已经把同类模块归到一个 group 里（如推荐理由 A、B、C 归为 `recommendation` 组）。这些模块的**壳结构、内容区边距、文字样式完全相同**，只是内容不同。

因此，对每个 group，**只取第一个模块（`moduleIndexes[0]`）做分析**。其余模块的 node 树不需要遍历。

例如 Step 1 输出：

```json
{ "groupId": "recommendation", "moduleIndexes": [3, 4, 5] }
```

→ Step 2 只分析 `moduleIndexes[0]`（即 index 3 对应的模块），输出一份 `fixedGroups` + `variableTexts` + `contentArea`。

## 必须处理所有模块（包括纯装饰模块）

**每个 Step 1 输出的 group 都必须出现在 Step 2 输出中**，即使它没有任何 variableTexts。

典型容易被遗漏的模块：
- **背景图**：可能只有 1 个 LAYER（纯色填充/渐变/图片），没有 TEXT。但它决定了整页的背景色/背景图，**必须作为 `fixedGroups[type=decoration]` 输出**，Step 3 才能提取 CSS。
- **银行结束语**：可能只有矢量 PATH，没有 TEXT。同样需要进 fixedGroups。
- **装饰分割线/品牌 logo 区**：同上。

规则：**variableTexts 可以为空数组，fixedGroups 不能为空**。每个模块至少输出一个 fixedGroup。

---

## 第一步：计算内容区

先用脚本 `scripts/calc_content_area.py` 算出 content area 的 padding。这一步的目的是**确定后续可变文字的活动范围**——以后的标题、正文、数据来源都在这个区域内排版。

**脚本用法：**

```bash
python scripts/calc_content_area.py data/<project>/modules/01-产品卡.json \
  --exclude-ids "0:51,0:52,0:53,0:62"
```

- `--exclude-ids`：传入所有固定节点的 ID（逗号分隔）。这些节点及其子节点会被排除，不参与包围盒计算。

**脚本计算逻辑：**

1. 以模块根节点 `node.bounds` 为 frame 边界
2. 遍历 `node.children`，跳过排除节点及其子树
3. 收集剩余叶子节点（TEXT / LAYER / PATH / ELLIPSE / SVG_ELLIPSE）的 bounds
4. 取 union bounding box，计算四条边到 frame 边界的距离

```
paddingTop    = min(bounds.y) - frame.y
paddingBottom = (frame.y + frame.height) - max(bounds.y + bounds.height)
paddingLeft   = min(bounds.x) - frame.x
paddingRight  = (frame.x + frame.width) - max(bounds.x + bounds.width)
```

单位统一用设计稿 px。由 Step 3 做 ÷3 换算。

> **注意**：计算内容区之前需要先知道哪些是固定节点（才能传 `--exclude-ids`），所以严格来说需要先做第二步的容器级判断。实际操作时，可以先快速扫一遍模块找出明显的固定装饰层（纯 LAYER/PATH/ELLIPSE 的 GROUP），排除这些后算 padding，然后再做详细的 TEXT 级别判断。顺序不必死板。

---

## 第二步：区分固定与可变

固定元素直接写死进模板（HTML/CSS），可变元素记录文字内容和角色，交给 Step 3 提取样式。

### 判断逻辑

```
对一个 GROUP / 嵌套 FRAME：
  ├── 子节点全是 LAYER/PATH/ELLIPSE/SVG_ELLIPSE/位图 → 纯装饰，整个 fixed
  ├── 子节点有 TEXT，但每个 TEXT 都是固定文案     → 整个 fixed（如按钮组）
  └── 子节点有 TEXT，且存在可变 TEXT              → 不固定，逐个判断每个 TEXT

对不在 fixed 容器里的独立 TEXT：
  ├── 产品名/基金代码/风险等级/费率数值/收益率/百分比
  │   热点正文/行业动态描述/资金流向/推荐标题/分析正文
  │   策略解读/营销标题/数据来源/图表内数据文本      → variable
  └── 按钮文案/模块装饰标签/表头/字段标签
      品牌广告语/合规声明/客服电话                    → fixed
```

### 2a. 从 GROUP / FRAME 级别判断

先看模块根节点下的每个直接子 GROUP 和嵌套 FRAME。一个容器如果整体固定，它的子节点（包括里面的 TEXT）都不需要再逐个判断。

**纯装饰容器：**

如果 GROUP/FRAME 的子节点全部是 `LAYER` / `PATH` / `ELLIPSE` / `SVG_ELLIPSE` 类型（或者只有少量含位图 URL 的 LAYER），没有任何 TEXT → 纯装饰，整个容器标记为 `fixedGroups[type=decoration]`。

例如：
- 背景渐变层、圆角矩形底板
- 图标、分割线
- 位图装饰

**Gradient Overlay / 文字特效的判断：**

文字上叠加的 PATH/LAYER 特效分两种：

1. **均匀作用于整段文字**（如整个标题所有字统一叠加同一个渐变层）→ **固定**。它本质是这段文字的 CSS 样式（`background-clip: text` / `text-shadow`），换文字内容后效果保持不变。放入 `fixedGroups`，由 Step 3 提取。
2. **只凸显特定字符**（如标题 8 个字里只有"反脆弱"3 个字有渐变变色）→ **不固定**。换一个标题，凸显哪几个字完全不一样，甚至可能不需要这个效果。**不放入 fixedGroups**。

**判断方法（数据驱动）**：对比 PATH 和它所在 GROUP 内 TEXT 的 `bounds.width`：

- **PATH.width / TEXT.width ≈ 1（如 99%）** → 覆盖整段文字全部宽度 → 均匀文字样式 → **固定**
- **PATH.width / TEXT.width ≈ 0（PATH 宽度为 0 或远小于 TEXT）** → 只覆盖特定字符位置 → 选择性凸显 → **不固定**

如果 GROUP 内没有 TEXT 子节点（文字被转成了矢量 PATH），则取 GROUP 自身的 `bounds.width` 与 PATH 的宽度比较。

**含固定文案的容器：**

如果 GROUP/FRAME 里面有 TEXT，但读完全部 TEXT 后发现都是固定文案（按钮、标签、表头等），那整个容器也标记为 `fixedGroups[type=fixedTexts]`，连同内部的 TEXT 一并记录。

例如：
- 按钮组（背景矩形 + 文案"小试一笔"）→ 整个固定
- 模块标签组（"热点速递"标签装饰）→ 整个固定

### 2b. 判断剩余的 TEXT 节点

对于不在 fixed GROUP 里的独立 TEXT，逐个判断可变还是固定。

**可变文本的特征：**

这类文字跟当前的业务语境绑定，换一个热点主题或换一个基金产品就得换。

完整的因果链条：这是一个基金产品营销 H5，逻辑是：当前的**行业热点**决定了推荐什么产品 → **产品卡**的个数、种类随之变化 → **推荐理由**也跟着产品的变化而变化。这个链条上的所有 TEXT 都是可变的。

具体包括：

- **产品信息**：产品名称、基金代码、风险等级、费率数值、收益率
- **热点资讯**：热点正文、行业动态描述、资金流向数据
- **推荐理由**：推荐标题、分析正文、策略解读
- **营销主题**：头图标题、策略 slogan、价值主张文案
- **数据来源**：含"数据来源"、"资料来源"、"Wind"、"截至"、"以上观点由……提供"等关键词的标注文字

**警惕"含产品名"的 TEXT：**

如果你发现一个 TEXT 里面包含了具体的产品名称，它几乎一定是可变的。例如：

> "华夏中证红利低波动ETF发起式联接C，费率如下"

这句话里出现了具体产品名称，换一个产品就得换。即使部分文字是固定格式（"费率如下"），但因为产品名嵌在里面，整个 TEXT 节点就是可变的。

**固定文本的特征（UI 标签）：**

这类文字是 UI 组件或 frame 装饰的一部分，属于"画框"而不是"画"：

- 按钮文案："小试一笔"、"立即购买"、"查看更多"
- 模块装饰标签："热点速递"、"热点快传"、"分享"
- 表头/字段标签："费用类别"、"管理费"、"托管费"、"收费方式/年费率"
- 指标名称 / 字段标签："近一年涨跌幅"、"近5年年化收益率"、"最大回撤"
  - **特别注意**：这类文字虽然位置在内容区里，但它只是指标的"名字"，不随产品变化。例如"近一年涨跌幅"这七个字，无论产品怎么换、数值怎么变，标签文字本身不变。它旁边的数值（如"2.80%"）虽然是可变的，但属于图表数据，不记录
- 品牌广告语："买基金来招行"、"费率低、品类全"
- 合规声明："基金非存款，产品有风险，投资须谨慎……"等风险提示长文、客服电话——这些是监管要求的固定内容，如实写进模板，不做变量暴露

**特殊情况——风险警告里的费率数值：**

风险警告模块里的合规声明（"基金非存款，产品有风险，投资须谨慎……"）是固定的，但**费率的数值**（如 0.15%、0.20%、0.05%）会随产品变化。不能因为"这个模块是风险提示"就把里面所有 TEXT 标为固定——费率数值必须单独拎出来作为可变文本。

---

## 第三步：可变文字归类与样式归纳

### 3a. 按语义角色归类

对每个 variable TEXT，按语义标注 role。**只分四类**：

| role | 判断方式 | 示例 |
|------|---------|------|
| `frameTitle` | 位置在 frame 内容区最顶部 + 内容随产品/行业/热点变化 | "左手红利 右手低波"、"市场开启震荡模式" |
| `sectionTitle` | 嵌入在 body 段落之间，位于各段落顶部 + 内容随产品/行业/热点变化 | "从国内看景气度看"、"从政策环境看" |
| `body` | 文字个数多（一段话），且位置不在 frame 最顶部 | "中证红利低波动指数选取50只流动性好…" |
| `sourceNote` | 含"数据来源"、"资料来源"、"Wind"、"截至"等关键词 | "数据来源：Wind，截至2026.5.22。" |

> **图表内的文字（数字、百分比、年份等）不记录。** 图表反正要重画，这些数字的样式也千变万化，记了没用，还占地方。

#### 各 role 的详细判断

**frameTitle（总标题）：**

同时满足两点：
1. **位置**：在这个 frame 的内容区里，它是最靠顶部的 TEXT（比所有其他文字都更靠近 frame 上边缘）
2. **内容**：一看就是随产品、行业或热点变化而变化的文字

> 注意区分 frameTitle 和固定装饰标签：如果文字距离 frame 顶部很近，但内容是固定的模块标签（如"市场解读"、"热点速递"），那是 fixed，不是 variable frameTitle。

每个 frame 最多有一个 `frameTitle`。如果 frame 顶部没有可变标题，就没有。

**sectionTitle（段落小标题）：**

同时满足两点：
1. **位置**：位于 body 段落之间，比 body 靠上但不在 frame 最顶部。通常会看到多个 sectionTitle 交替出现在 body 之间
2. **内容**：随产品、行业或热点变化而变化

一个 frame 可以有 0 到 N 个 `sectionTitle`。

> 如果 sectionTitle 外层包着一个装饰框（如 PATH/LAYER 组成的背景框），那个框本身属于 fixedGroups（壳固定），但框里的 sectionTitle 文字是 variable。

**body（正文）：**

文字个数明显多（通常超过 20 个字），是一段完整的话，并且位置在 frame 中段或偏下（不在最顶部）。

**sourceNote（数据/资料来源）：**

非常明显——文字里包含"数据来源"、"资料来源"、"Wind"、"截至"、统计区间（如"2021.5.23-2026.5.22"）、"以上观点由……提供"等。

如果遇到不确定归哪类的，用 `generic`，并在 `reason` 字段里说明。

### 3b. 同一 role 内的样式归纳

归类完成后，**同一模块内、同一 role 的多个 text 节点，只取一个有代表性的提取样式**。道理很简单：

> 它们既然是同一个语义角色（比如都是标题），那它们的字号、字重、颜色、行高应该一样。设计稿中个别文字的特殊处理（如"反脆弱"3 个字变渐变）只是本期文案特有的一笔，不是普适样式。

**归纳规则：**

1. 遍历同一 role 的所有 variableText 节点
2. 选出**样式来源节点**（同时满足）：
   - 是真正的 TEXT 节点（非 PATH 矢量文字，能读到 font/style 属性）
   - 不含字符级特效（没有仅覆盖部分文字的 Gradient Overlay / PATH）
3. 其余节点设置 `styleSource` 指向样式来源节点
4. 如果某个 role 只有一个节点，且是 TEXT（非 PATH），它自己就是样式来源，无需设 `styleSource`

**样式来源节点的判断方法：**

- 检查该 TEXT 所在 GROUP 内是否有 PATH.width / TEXT.width ≈ 0 的 Gradient Overlay → 有则说明含字符级特效，不适合做样式来源
- 检查该节点类型是否为 TEXT（而非 PATH）→ PATH 矢量文字无 font/style，无法提取

**以中信银行营销头图为例：**

标题被设计稿拆成了 4 个部分：

| 节点 | 内容 | 类型 | 字符级特效？ |
|------|------|------|------------|
| 0:10 | "市场开启震荡模式" | TEXT | 无（有 uniform Gradient Overlay 0:11，已进 fixedGroups） |
| 0:13 | "反脆弱红利低波" | GROUP（PATH 矢量） | 有（0:14 仅凸显"反脆弱"） |
| 0:16 | "反脆弱价值凸显" | GROUP（PATH 矢量） | 有（0:17 仅凸显"反脆弱"） |

→ 4 个都是标题 → 都标 `frameTitle`
→ 0:10 是唯一有真实 TEXT 节点、无字符级特效的 → **它是样式来源**
→ 0:13、0:16 设 `styleSource: "0:10"`

Step 3 看到 `styleSource`，只从 0:10 提取标题的字号/字重/行高/颜色，其他的跳过样式提取、复用 0:10 的。0:11 的 uniform Gradient Overlay 照样通过 fixedGroups 进 CSS。

**为什么其他三个是 GROUP 而非 TEXT：** 设计工具中，"反脆弱"等文字被转成了矢量路径（PATH），不在任何 TEXT 节点内。Step 2 看到的 nodeId 是包裹这些 PATH 的 GROUP。这不影响角色判断，但意味着 Step 3 无法从它们身上提取文字样式——这也正是需要 `styleSource` 的原因。

---

## 提取 TEXT 节点的方法

遍历模块 JSON 的 `node` 树。**先处理容器（GROUP/FRAME），再处理剩余 TEXT**：

1. 对模块根节点的每个直接子 GROUP 和嵌套 FRAME → 判断整个容器是 fixed 还是含可变内容
2. 对每个 fixed 容器 → 如果含 TEXT，记录内部所有 TEXT 的 nodeId 和文字内容
3. 对不在 fixed 容器里的 TEXT → 判断可变/固定，对可变 TEXT 标注 role
4. 对同一 role 的可变 TEXT → 选样式来源节点，其余设 `styleSource`

每个 TEXT 节点需要读取：

| 字段 | 用途 |
|------|------|
| `id` | 唯一标识，Step 3 用它定位取样式 |
| `name` | 节点名称，辅助人工审阅 |
| `text` | 完整文字内容 |

（样式提取是 Step 3 的事，Step 2 不碰 `textRuns`、`font`、`color` 等字段）

---

## 不需处理的节点类型

以下节点类型不包含业务内容，在遍历时跳过（不需要出现在 fixedGroups 或 variableTexts 中）：

| 类型 | 说明 |
|------|------|
| MASK | 蒙版 |
| COMPONENT / INSTANCE | Figma 组件/实例引用 |

如果这些节点被包裹在一个 fixed GROUP 内部，它们会被自动包含在 `descendantIds` 里。

---

## 输出格式

```json
{
  "modules": [
    {
      "groupId": "hero",
      "groupName": "营销头图",
      "moduleIndexes": [5],

      "contentArea": {
        "paddingTop": 215.25,
        "paddingBottom": 514.34,
        "paddingLeft": 53.14,
        "paddingRight": 228.6,
        "note": "所有值为设计稿原始 px，Step 3 统一 ÷3 换算"
      },

      "fixedGroups": [
        {
          "groupId": "0:6",
          "groupName": "图层 745",
          "type": "decoration",
          "descendantIds": ["0:6"],
          "reason": "头图背景底图（IMAGE），纯装饰"
        },
        {
          "groupId": "0:11",
          "groupName": "Gradient Overlay（主标题）",
          "type": "decoration",
          "descendantIds": ["0:11"],
          "reason": "主标题'市场开启震荡模式'的均匀渐变叠层，PATH.width/TEXT.width≈1，换标题后效果不变"
        }
      ],

      "variableTexts": [
        {
          "nodeId": "0:10",
          "text": "市场开启震荡模式",
          "role": "frameTitle",
          "reason": "头图主标题，位于内容区最顶部，随市场主题变化"
        },
        {
          "nodeId": "0:13",
          "text": "\"反脆弱\"红利低波",
          "role": "frameTitle",
          "styleSource": "0:10",
          "reason": "标题第二行（PATH矢量文字），含字符级Gradient Overlay特效，样式从0:10继承"
        },
        {
          "nodeId": "0:16",
          "text": "\"反脆弱\"价值凸显",
          "role": "frameTitle",
          "styleSource": "0:10",
          "reason": "标题第三行（PATH矢量文字），含字符级Gradient Overlay特效，样式从0:10继承"
        }
      ]
    },
    {
      "groupId": "recommendations",
      "groupName": "产品推荐理由",
      "moduleIndexes": [2],

      "contentArea": {
        "paddingTop": 41.18,
        "paddingBottom": 52.24,
        "paddingLeft": 42.53,
        "paddingRight": 46.0,
        "note": "基于代表模块 index=2 计算"
      },

      "fixedGroups": [
        {
          "groupId": "0:69",
          "groupName": "矩形 1000",
          "type": "decoration",
          "descendantIds": ["0:69", "0:70", "0:71", "0:72", "0:73"],
          "reason": "外层红色渐变底框 + Clip 蒙版图片，纯装饰"
        },
        {
          "groupId": "0:77",
          "groupName": "Gradient Overlay（主标题）",
          "type": "decoration",
          "descendantIds": ["0:77"],
          "reason": "主标题的均匀渐变叠层，PATH.width/TEXT.width=99.2%，换标题后效果不变"
        },
        {
          "groupId": "0:85",
          "groupName": "组 5817",
          "type": "decoration",
          "descendantIds": ["0:85"],
          "reason": "图表可视化区域，整个 GROUP 为图表组件，由下游 Agent 重新绘制"
        }
      ],

      "variableTexts": [
        {
          "nodeId": "0:76",
          "text": "左手红利 右手低波",
          "role": "frameTitle",
          "reason": "推荐理由总标题，位于内容区最顶部，随推荐主题变化"
        },
        {
          "nodeId": "0:80",
          "text": "攻守兼备的组合底仓",
          "role": "sectionTitle",
          "reason": "副标题，位于 frameTitle 下方、body 上方，随推荐策略变化"
        },
        {
          "nodeId": "0:84",
          "text": "中证红利低波动指数选取50只流动性好、连续分红、红利支付率适中…",
          "role": "body",
          "reason": "推荐理由正文长文（>20字），位于 frame 中段，随产品和行业热点变化"
        },
        {
          "nodeId": "0:177",
          "text": "资料来源：华泰研究。",
          "role": "sourceNote",
          "reason": "含\"资料来源\"关键词，随数据来源变化"
        }
      ]
    }
  ]
}
```

### 字段说明

**contentArea：**

| 字段 | 说明 |
|------|------|
| `paddingTop` | 内容区顶部到 frame 顶部的距离（设计稿 px） |
| `paddingBottom` | 内容区底部到 frame 底部的距离（设计稿 px） |
| `paddingLeft` | 内容区左边到 frame 左边的距离（设计稿 px） |
| `paddingRight` | 内容区右边到 frame 右边的距离（设计稿 px） |
| `note` | 可选，注明换算说明 |

**fixedGroups 每个条目：**

| 字段 | 说明 |
|------|------|
| `groupId` | GROUP 节点的 id |
| `groupName` | GROUP 节点名称，辅助审阅 |
| `type` | `decoration`（纯装饰，无文字）或 `fixedTexts`（含固定文案） |
| `descendantIds` | 该 GROUP 内所有子节点的 id 列表（不含 TEXT，TEXT 在 childTexts 里） |
| `childTexts` | 仅 `type=fixedTexts` 时有，记录内部 TEXT 的 nodeId 和文字内容 |
| `reason` | 为什么判定为固定的 |

**variableTexts 每个条目：**

| 字段 | 说明 |
|------|------|
| `nodeId` | TEXT 节点的 id，Step 3 用它去 JSON 里取样式 |
| `text` | 当前设计稿的文字内容，Step 5 用作默认值 |
| `role` | 语义角色：`frameTitle` / `sectionTitle` / `body` / `sourceNote` |
| `styleSource` | 可选。当设置时，Step 3 不从该节点提取样式，直接复用 `styleSource` 指向节点的样式 |
| `reason` | 为什么判定为可变的 |

---

## 注意

- 先判断容器（GROUP/FRAME）级别的固定性，再判断剩余 TEXT 的可变性——不要跳过容器直接逐 TEXT 判断
- 不在 fixed GROUP 里的 LAYER/PATH（如独立的背景矩形）也纳入 fixedGroups
- 图表/图片区域不在此步骤输出——图表内的文字如有 TEXT 节点则正常判断，无 TEXT 节点的纯视觉图表不需要记录
- 数据来源的文字即使每期会变（换了统计区间），也标为 variable，role 用 `sourceNote`
- `paddingTop` 和 `paddingBottom` 不需要极其精确，关键是 `paddingLeft` 和 `paddingRight`——这两个值决定文字的左右边界，必须准确
- 如果某模块没有任何 fixedGroups（极少见），`fixedGroups` 为空数组 `[]`
- 如果某模块没有任何 variableTexts（如纯装饰模块），`variableTexts` 为空数组 `[]`
- **归纳比逐个提取更可靠**：同一 role 的多个 variableText，选一个干净的 TEXT 节点作为样式源头，其余设 `styleSource`。设计稿的字符级特效是一期一变的，不要当成通用样式提取

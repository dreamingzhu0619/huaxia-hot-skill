# mastergo-to-od-skill 重构方案

## 1. 当前问题

现在的流程：

```
raw → modules/*.json → 源CSS(absolute) → agent 手写 flow CSS → agent 手写 HTML
                                              ↑
                                    精度丢失的关键环节
```

agent 在把 absolute CSS 转成 flow CSS 时，靠人眼读源 CSS → 理解 → 手写新 CSS。这个过程必然漏 PATH 的 SVG、近似颜色值、跳过"看起来不重要"的图层。GROWTH.md 里 #1~#5 全部是这类问题的变体。

核心原则修正：

> **能用原始数据精确提取的，不让 AI 生成。AI 只做语义判断：什么东西会变、什么东西不变。**

---

## 2. 数据全流程：从 raw 到 assets

以产品卡为例，跟踪数据在每一步的变化。

### Step A：抓取 → `data/raw/`

MCP 7 步抓取，所有原始响应原样归档。

```
data/raw/
├── 01-getDsl/getDsl.json          ← 完整节点树 + 样式引用
├── 02-getMeta/getMeta.json         ← 文件元信息
├── 03-getDesignSections/            ← 设计稿分区
├── 05-getDesignSvgs/                ← 所有 SVG 资源
├── 05-getDesignTexts/               ← 所有 TEXT 内容
├── 05-extractSvg/                   ← 提取的 SVG 文件
├── 07-getD2c/                       ← getD2c 的 CSS 产物
└── mastergo-mcp-raw.json           ← 全量合并
```

### Step B：拆分模块 → `data/modules/`

`split_modules.py` 遍历节点树，按顶级 FRAME 切分。每个模块得到一个完整 JSON，包含其下所有子节点的完整数据。

```
data/modules/
├── _index.json              ← 所有模块的索引 + 元信息
├── 00-背景图.json
├── 01-产品卡.json            ← 18 个节点，完整子树
├── 02-产品推荐理由A.json     ← 92 个节点，完整子树
├── 03-产品推荐理由B.json     ← 62 个节点，完整子树
└── ...
```

单个模块 JSON 的结构（以产品卡为例）：

```json
{
  "meta": { "nodeCount": 18, "textCount": 6, "position": {...} },
  "node": {
    "id": "13:390",
    "type": "FRAME",
    "fill": null,
    "children": [
      {
        "id": "0:51",
        "type": "LAYER",
        "fill": "linear-gradient(90deg, #FCCC89, #EB8F2C)",
        "borderRadius": "33px",
        "layoutStyle": { "relativeX": 0, "relativeY": 0, "width": 1075, "height": 531 }
      },
      {
        "id": "0:58",
        "type": "TEXT",
        "text": "华夏中证红利低波动ETF发起式联接C",
        "textRuns": [{
          "font": { "family": "MiSans", "size": 57, "lineHeight": "1.3" },
          "color": "#6D2807"
        }],
        "layoutStyle": { "relativeX": 56, "relativeY": 56, "width": 963, "height": 74 }
      }
      // ... 16 more nodes
    ]
  }
}
```

每个节点的 `relativeX/Y` 是相对于父级 FRAME 的坐标。此时所有数据都是 @3x 原始像素。

### Step C：缩放 → 逻辑像素

`generate_module_css.py --auto-scale` 读取 `_index.json` 的 `designScale`（@3x），将所有 px 值除以 3。

```
@3x: width=1075, font-size=57, relativeY=56
        ↓ ÷ 3
@1x: width=358.33, font-size=19, relativeY=18.67
```

后续所有步骤都在逻辑像素上进行。

### Step D：同类合并 + diff → 组件分组

`diff_modules.py` 比对所有模块的骨架签名。签名只看节点 type 层级，不看坐标和文本：

```
01-产品卡:          FRAME → [LAYER, LAYER, GROUP→[LAYER,TEXT], TEXT, TEXT, TEXT, TEXT, TEXT]
02-产品推荐理由A:   FRAME → [GROUP+LAYER..., TEXT, GROUP, GROUP, LAYER, GROUP, ...]
03-产品推荐理由B:   FRAME → [GROUP+LAYER..., TEXT, GROUP, GROUP, LAYER, GROUP, ...]
04-产品推荐理由C:   FRAME → [GROUP+LAYER..., TEXT, GROUP, GROUP, LAYER, GROUP, ...]
                        ↑ 02/03/04 签名相同 → 候选合并
```

合并后对每组做 diff——每个节点的每个属性值，在各实例间是否相同：

```
推荐理由: 标题 TEXT
├── text 内容        → "左手红利..." / "行业龙头..." / "哑铃型..."    → variable
├── font.family      → "MiSans" / "MiSans" / "MiSans"              → invariant
├── font.size        → 44 / 44 / 44                                 → invariant
└── color            → #6D2807 / #6D2807 / #6D2807                  → invariant
```

输出：每个组件类型的完整标记——每个节点/属性是 invariant 还是 variable。

### Step E：提取样式 → `styles.css`

`extract_styles.py` 从代表模块 JSON 中机械提取所有 invariant 视觉属性。

**E1：提取视觉属性（纯机械）**

```
LAYER →
  fill: "linear-gradient(90deg, #FCCC89, #EB8F2C)"  →  background: linear-gradient(...)
  borderRadius: "33px"                                →  border-radius: 11px   /* ÷3 */
  strokeColor: "#E4973D"                              →  border-color: #E4973D
  strokeWidth: "1px"                                  →  border-width: 0.33px  /* ÷3 */

TEXT →
  textRuns[0].font.family: "MiSans"                   →  font-family: 'MiSans'
  textRuns[0].font.size: 57                           →  font-size: 19px        /* ÷3 */
  textRuns[0].color: "#6D2807"                        →  color: #6D2807
  textRuns[0].font.lineHeight: "1.3"                  →  line-height: 1.3
```

**E2：计算 flow 间距（脚本计算 + AI 确认）**

这是 absolute → flow 转换的核心。对于同一个容器内的兄弟节点，按 `relativeY` 排序后的间距计算：

```
产品卡 FRAME 内的直接子节点（按 relativeY 排序）：

0:51 外框 LAYER      y=0,    h=531   (底层背景)
0:58 产品名 TEXT     y=56,   h=74    ← 第一个可见元素
0:60 代码 TEXT       y=146,  h=40    ← 距产品名底部: 146 - (56+74) = 16px
0:310 风险 TEXT      y=196,  h=28    ← 距代码底部:   196 - (146+40) = 10px
0:62 涨跌幅标签 TEXT y=264,  h=34    ← 距风险底部:   264 - (196+28) = 40px
0:63 涨跌幅值 TEXT   y=310,  h=110   ← 距标签底部:   310 - (264+34) = 12px
0:53 CTA按钮 GROUP   y=375,  h=108   ← 距数值底部:   375 - (310+110) = -45px(重叠)
```

脚本算出相邻元素间距，转换为 CSS margin：

```css
.product-card__name       { margin-bottom: 16px; }
.product-card__code       { margin-bottom: 10px; }
.product-card__risk       { margin-bottom: 40px; }
.product-card__return-label { margin-bottom: 12px; }
.product-card__return-value { margin-bottom: 24px; }  /* CTA 间距需 AI 确认 */
```

**AI 在这一步做的事：**
- 审视脚本算出的 margin 值是否合理（重叠/异常间距需要确认）
- 决定布局的组织方式：所有子元素纵向排列？还是有横向排列的行？
- 对于水平排列的元素（如同一行的代码 + 风险标签），转成 flex row

### Step F：提取装饰 → `decorations.html`

`extract_decorations.py` 遍历节点树，对 decoration 类型节点做处理。

产品卡无 decoration 节点，跳过。以营销头图为例：

```
遍历节点树：
├── 0:7 图层586 GROUP (华夏基金logo) → BITMAP 子节点 → <img src="...">
├── 0:11 Gradient Overlay PATH       → PATH → <svg><path d="..." fill="url(#g)"/></svg>
├── 0:14 Gradient Overlay PATH       → PATH → <svg>...</svg>
├── 0:17 Gradient Overlay PATH       → PATH → <svg>...</svg>
└── 0:13 "反脆弱"红利低波 GROUP      → outlinedText → <span>反脆弱红利低波</span>
```

输出：

```html
<!-- 0:11 标题渐变叠加 -->
<svg class="header-title-overlay" viewBox="0 0 288.67 28.33">
  <defs>
    <linearGradient id="g0:11">
      <stop offset="0%" stop-color="#6A290D"/>
      <stop offset="100%" stop-color="rgba(166,99,69,0.996)"/>
    </linearGradient>
  </defs>
  <path d="M1.73,0.5 L287.09,0.5..." fill="url(#g0:11)"/>
</svg>
<!-- 0:14 装饰文字渐变层 -->
<svg class="header-deco-left" viewBox="0 0 191.33 28.33">...</svg>
```

### Step G：生成模板 → `template.html`

遍历节点树，对每个节点按角色翻译。**AI 负责 class 命名和 slot 命名。**

```
产品卡 FRAME
├── LAYER 0:51 (外框)       → decoration → 不在此出现（已在 styles.css + decorations.html）
├── LAYER 0:52 (内卡)       → decoration → 不在此出现
├── TEXT 0:58 产品名         → variable   → <h2 class="product-card__name">{{name}}</h2>
├── TEXT 0:60 代码           → variable   → <span class="product-card__code">{{code}}</span>
├── TEXT 0:310 风险          → variable   → <span class="product-card__risk">{{riskLevel}}</span>
├── TEXT 0:62 涨跌幅标签     → variable   → <div class="product-card__return-label">{{returnLabel}}</div>
├── TEXT 0:63 涨跌幅值       → variable   → <div class="product-card__return-value">{{returnValue}}</div>
├── GROUP 0:53 按钮          → 容器       → <div class="product-card__cta">
│   ├── LAYER 0:54 (背景)    → decoration →   不在此出现（样式在 styles.css）
│   └── TEXT 0:55 CTA文字    → variable   →   <span class="product-card__cta-text">{{cta}}</span>
└──                           关闭容器    → </div>
```

输出：

```html
<section data-od-id="product-card">
  <div class="product-card__frame">
    <div class="product-card__inner">
      <h2 class="product-card__name">{{name}}</h2>
      <div class="product-card__tags">
        <span class="product-card__code">{{code}}</span>
        <span class="product-card__risk">{{riskLevel}}</span>
      </div>
      <div class="product-card__return">
        <div class="product-card__return-label">{{returnLabel}}</div>
        <div class="product-card__return-value">{{returnValue}}</div>
      </div>
      <div class="product-card__cta">
        <span class="product-card__cta-text">{{cta}}</span>
      </div>
    </div>
  </div>
</section>
```

### Step H：组装 → `example.html`

`build_html.py`：读 `_index.json` 按 `position.y` 排序组件 → 读每个组件的 template.html → 按实例数复制 → 用示例数据填充 `{{}}` → 嵌入 decorations.html → 拼接 → 输出。

---

### 全流程总览

```
data/raw/                        ← MCP 抓取，归档不动
    │
    ▼  split_modules.py
data/modules/NN-*.json           ← 每模块完整节点树，@3x 原始像素
    │
    ▼  --auto-scale
逻辑像素数据                      ← 所有 px ÷ scale
    │
    ├─── diff_modules.py ──────→  组件分组 + invariant/variable 标记
    │
    ├─── extract_styles.py ──→  styles.css
    │     • E1: 抄 fill/border/font/color（机械）
    │     • E2: absolute y → flow margin 计算（脚本算 + AI 确认布局）
    │
    ├─── extract_decorations.py → decorations.html
    │     PATH→SVG, BITMAP→img, LAYER装饰→div, outlinedText→span
    │
    └─── AI 生成 ──────────────→  template.html
          遍历节点树 + 角色标记 → DOM骨架 + {{slot}}
          AI 负责 class 命名、slot 命名、布局组织
    │
    ▼  build_html.py
example.html                     ← 按顺序 + 数据填充 + decorations 嵌入
```

每一步输入什么、输出什么、谁（脚本/AI/用户）负责什么，边界清晰。

---

## 3. 新的数据架构

### 总览

```
output/<name>/
├── data/
│   ├── raw/                    ← MCP 原始数据，只归档不加工
│   └── modules/                ← 脚本拆分，每模块完整 JSON
│       ├── _index.json
│       ├── 00-背景图.json
│       ├── 01-产品卡.json
│       └── ...
├── assets/                     ← ★ 核心新层：按合并后的组件组织
│   ├── shared/
│   │   └── page.css            ← 页面容器 + 背景 + 全局字体
│   ├── marketing-header/
│   │   ├── styles.css          ← 设计稿精确视觉值，机械提取
│   │   ├── decorations.html    ← PATH/SVG/位图 装饰元素
│   │   └── template.html       ← DOM 骨架 + {{slot}} 插槽
│   ├── hotspot-express/
│   │   ├── styles.css
│   │   ├── decorations.html
│   │   └── template.html
│   ├── product-card/
│   │   ├── styles.css
│   │   └── template.html       ← 无装饰元素，不需要 decorations.html
│   ├── recommendation/
│   │   ├── styles.css
│   │   ├── decorations.html
│   │   └── template.html
│   ├── risk-warning/
│   │   ├── styles.css
│   │   └── template.html
│   └── bank-ending/
│       ├── styles.css
│       ├── decorations.html    ← 53 个 PATH 节点的 SVG
│       └── template.html
├── schema/
│   └── content.template.json   ← 纯粹的可变字段声明
├── output/
│   ├── example.html            ← 用示例数据组装出的完整页面
│   └── template.html           ← 未填数据的种子模板
├── references/
│   ├── components-schema.md    ← 组件分类体系 + 固定/可变判定记录
│   ├── components-provenance.md ← 溯源表（每个 CSS 值对应哪个节点 ID）
│   └── component-templates.md  ← 图表生成算法（仅图表部分）
└── SKILL.md                    ← OD skill 入口
```

### 三个核心文件的分工

```
styles.css         decorations.html        template.html
──────────         ────────────────        ─────────────
从哪里来：          从哪里来：               从哪里来：
modules/*.json     modules/*.json          节点树 + diff 结果
的 fill/font/      的 PATH→assets.svgs     遍历节点树，按规则
border/radius/     BITMAP→exportImage      翻译每个节点：
textRuns 字段      装饰 LAYER                 
                                          
放什么：            放什么：                 • FRAME → <section>
不可变的精确         不可变的装饰元素          • TEXT(variable) → {{slot}}
视觉属性            <svg> / <img>           • TEXT(fixed) → 原文
                   / 独立 <div>            • GROUP → 包裹 <div>
#FCCC89 不是                                      • PATH/LAYER(装饰)
#FCC，55.85px                                   → 不在此出现
不是 56px                                       （已在上面两个文件中）
                                          
加载方式：          加载方式：               引用 styles.css 的 class
<link> 引入        组装时嵌入到               引用 decorations.html
                   template.html            的 SVG/img
                   的对应位置
```

---

## 4. 判定体系：什么可变、什么不变

### 3.1 同类模块 diff（≥2 个实例时）

对于推荐理由 A/B/C 这类被合并的同类模块，**按树位置匹配节点**（不是按节点 id，不是按叶子节点逐个比）。

**匹配规则：** 同一个组件类型的不同实例，节点树结构相同（骨架签名一致），所以第 N 层的第 M 个子节点在不同实例间是对应的。

```
推荐理由 A           推荐理由 B           推荐理由 C
root.children:       root.children:       root.children:
  [0] 标题 TEXT        [0] 标题 TEXT        [0] 标题 TEXT        → 位置匹配 ✅
  [1] 副标题 TEXT      [1] (无此节点)        [1] (无此节点)        → 位置匹配，B/C 缺失
  [2] 正文 TEXT        [2] 正文 TEXT        [2] 正文 TEXT        → 位置匹配 ✅
  [3] 图表区 GROUP     [3] 图表区 GROUP     [3] 图表区 GROUP     → 位置匹配 ✅
  [4] 来源 TEXT        [4] 来源 TEXT        [4] 来源 TEXT        → 位置匹配 ✅
```

**三种 diff 结果：**

| 情况 | 处理 |
|------|------|
| 叶子节点值相同（字体、颜色、边框参数） | → invariant，进 styles.css |
| 叶子节点值不同（TEXT 内容、数据值） | → variable，进 template.html {{slot}} |
| GROUP 节点位置匹配但**内部子节点结构不同**（如图表 A 有 8 个矩形，图表 B 有 12 个 PATH） | → 整个 GROUP 标记为"复杂可变块"，整体作为 {{slot}}，内部不逐节点 diff |

**图表识别的辅助信号：**

如果一个 GROUP 满足以下多个条件，AI 应判定为图表区域：

| 信号 | 说明 |
|------|------|
| GROUP 内含 ≥ 5 个 PATH/LAYER 子节点 | 复杂图形，不是简单装饰 |
| GROUP 内部结构在实例间不同 | 内容在变化，不是固定装饰 |
| **同级或附近节点中有"数据来源""资料来源""数据来源：Wind"等 TEXT** | ★ 最强信号——图表几乎总是跟着数据来源 |
| GROUP 的前一个兄弟节点是标题类 TEXT（如"现金分红统计"） | 图表上方通常有小标题 |
| `name` 含"图表""统计""图示"等词 | 辅助信号 |

**一旦判定为图表 GROUP → 天然就是 {{slot}}。** 不需要 diff 内部结构，不需要提取内部 PATH。只提取 GROUP 本身的容器样式（尺寸、背景、圆角）进 styles.css，内容整体暴露为图表插槽。

对不上不一定是坏事——对不上恰恰说明这个 GROUP 是变量内容（图表），应该整体放进 {{slot}}。

### 3.2 对节点属性的逐字段粒度 diff

不是整个节点判 invariant，而是**节点内部的每个属性分别判**：

```
TEXT 节点 "产品名"
├── text 内容 → 实例间不同 → variable → {{name}}
├── font.family "MiSans" → 实例间相同 → invariant → styles.css
├── font.size 57 → 实例间相同 → invariant → styles.css
├── color #6D2807 → 实例间相同 → invariant → styles.css
└── layoutStyle.width 可变 → 如果内容变长宽度可能变 → 不设固定宽度
```

### 3.3 Singleton 模块（无同类可比）

只有一个实例的模块（如营销头图、热点速递），diff 不可用。

**判定方法：问一句话——「换一期内容、换一个产品，这个会变吗？」**

基本规律：

| 会变 | 不会变 |
|------|--------|
| 具体的热点资讯正文 | 栏目标签/角标文字（"热点速递"） |
| 行业知识/分析内容 | UI 操作提示 |
| 产品名称、代码、数据 | 品牌固定 CTA（"小试一笔"） |
| 产品的推荐理由 | 合规条文（"基金非存款..."） |
| 标题文字 | 表格列头（"管理费""托管费"） |
| 数据来源和日期 | 装饰 PATH/LAYER/BITMAP |

脚本先自动标无条件 fixed：
- `type` 不是 `TEXT` 的节点 → invariant
- 含「风险」「投资须谨慎」「基金合同」「不保证」等合规关键词的 TEXT → fixed
- 含「管理费」「托管费」「赎回费」「销售服务费」等费用表头 → fixed

剩余 TEXT 节点列出清单，用户逐条标记 fixed / variable。

### 3.4 节点类型与判定规则

MasterGo 设计稿中有六种节点类型。先理解每种 type 的本质，再决定它去向哪里。

#### 每种 type 是什么

| type | 自带视觉属性？ | 有子节点？ | 本质 |
|------|--------------|-----------|------|
| **FRAME** | 有（fill/border/radius） | 有 | 设计画板/区域。顶级 FRAME = 一个模块 |
| **GROUP** | **没有**（fill 永远是 null） | 有 | 纯文件夹，组织子元素。自己不产生任何视觉 |
| **LAYER** | 有（fill/stroke/shadow） | 无 | 矩形层。设计稿里画的一个矩形块 |
| **TEXT** | 有（font/color/content） | 无 | 文字 |
| **PATH** | 有（path 数据 + fill） | 无 | 矢量路径。可能是圆角矩形，也可能是不规则曲线 |
| **BITMAP** | 有（图片数据） | 无 | 位图/图片 |

#### 核心区分：有 visual 的节点 vs 没有 visual 的 GROUP

**LAYER / TEXT / PATH / BITMAP —— 自带视觉属性：**

这些节点自己有 fill、font、path 数据。按角色判定：

| 角色 | 去向 | 例子 |
|------|------|------|
| invariant 视觉值 | `styles.css` | 颜色、字号、边框、渐变参数 |
| 装饰元素 | `decorations.html` | PATH→SVG、BITMAP→img、装饰 LAYER→div |
| 固定文字 | `template.html` 原文 或 `decorations.html` | "热点速递"、"管理费" |
| 可变文字 | `template.html` → `{{slot}}` | 产品名、正文、收益率 |

**GROUP —— 自己没有视觉属性：**

GROUP 的 fill 永远是 null。它只是一个透明容器。**GROUP 的去向完全由它的子节点构成决定：**

| GROUP 的子节点构成 | GROUP 去向 | 例子 |
|--------------------|-----------|------|
| 全是 PATH/LAYER/BITMAP/固定装饰 TEXT | → `decorations.html`，作为完整装饰单元 | "热点速递拷贝"角标 |
| 包含 variable TEXT | → `template.html`，作为结构容器 `<div>`，包裹 {{slot}} | 产品卡的内容区 |
| 既有装饰子节点又有 variable 子节点 | → `template.html`，装饰部分引用 decorations.html | 推荐理由（边框装饰 + 可变正文） |

#### 两个 GROUP 的实例

**"热点速递 拷贝" GROUP（0:35）→ decorations.html：**

```
0:35 "热点速递 拷贝"  GROUP   ← 自己没有视觉
├── 0:38 圆角矩形6      PATH   ← 红色药丸形状
├── 0:41 圆角矩形6      PATH   ← 蒙版
├── 0:40 图层737       LAYER  ← 纹理位图
├── 0:42 形状4         PATH   ← 红色装饰
├── 0:43 形状3         PATH   ← 金色装饰
├── 0:44 ef-redian...  LAYER  ← 图标位图
├── 0:46 "热点速递"     TEXT   ← 固定装饰文字
└── 0:47 Gradient...   PATH   ← 文字渐变叠加

全部子节点 = 装饰性质 → 整个 GROUP 进 decorations.html
```

**"按钮" GROUP（0:53）→ template.html：**

```
0:53 "按钮"           GROUP   ← 自己没有视觉
├── 0:54 矩形18       LAYER   ← 红色渐变背景 → 样式进 styles.css
└── 0:55 "小试一笔"   TEXT    ← 固定按钮文字

包含功能性 TEXT → 进 template.html 作为结构容器
LAYER 背景样式在 styles.css，TEXT 文字在 template.html
```

#### 固定装饰 TEXT vs 固定内容 TEXT

| 归入 decorations.html | 归入 template.html |
|------------------------|---------------------|
| "热点速递" 角标文字 | "管理费" 列头标签 |
| "小试一笔" 按钮标签 | "风险提示：基金非存款..." 合规条文 |
| 属于某个视觉装饰组件的文字 | 独立存在或属于内容区域的文字 |

放错不会导致渲染错误——两个文件最终都嵌入 HTML。拿不准时放 template.html。

#### outlined text 处理

设计稿中文字被转成轮廓（GROUP 名含中文，子树全是 PATH/Gradient Overlay，无 TEXT）：

- `split_modules.py` 已检测这类节点并标注 `outlinedText: true` + `outlinedTextFont`
- 文字内容从 `name` 字段取，字体从兄弟 TEXT 节点推断
- 在 `decorations.html` 中作为真实 `<span>` 文本 + CSS 渐变还原
- 文字内容从 `name` 字段取
- 字体从兄弟 TEXT 节点推断
- 在 `decorations.html` 中作为带 CSS 的真实 `<span>` 文本（用 `background-clip: text` 还原渐变效果）

---

## 5. 三个核心文件的生成方式

### 4.1 styles.css —— 脚本机械提取

输入：`data/modules/<合并后的代表模块>.json`

提取规则（按节点类型）：

**LAYER / FRAME / GROUP（容器类）：**

```
fill          → background / background-image
borderRadius  → border-radius
strokeColor   → border-color
strokeWidth   → border-width
effect        → box-shadow / filter
opacity       → opacity
width/height  → width / height（需要 ÷ designScale）
```

**TEXT（文字类）：**

```
textRuns[].font.family        → font-family
textRuns[].font.size          → font-size（需要 ÷ designScale）
textRuns[].font.lineHeight    → line-height
textRuns[].font.letterSpacing → letter-spacing
textRuns[].font.weight        → font-weight
textRuns[].color              → color
textAlign                     → text-align
```

**每个 CSS 规则必须带溯源注释：**

```css
/* 0:58 TEXT — 产品名称 */
.product-card__name {
  font-family: 'MiSans', sans-serif;
  font-weight: 600;
  font-size: 19px;           /* textRuns[0].font.size: 57px ÷ @3x */
  color: #6D2807;            /* textRuns[0].color */
  letter-spacing: -0.0225em; /* textRuns[0].font.letterSpacing: -2.25% */
}
```

### 4.2 decorations.html —— 脚本提取 + 规则判定

遍历模块节点树，按 3.4 节的判定规则处理每个节点：

**有 visual 的叶子节点（PATH / BITMAP / 装饰 LAYER）：**

```html
<!-- 0:43 形状3 PATH | 金色装饰 -->
<svg class="hs-deco-shape3" viewBox="0 0 105.12 82.72">
  <path d="M0,0 L105.12,0..." fill="#C29B6C"/>
</svg>

<!-- 0:44 ef-redian-gongju LAYER | 图标位图 -->
<img class="hs-deco-icon" src="<exportImage URL>" alt="">

<!-- 0:38 圆角矩形6 PATH | 药丸背景 -->
<div class="hs-badge-pill"></div>
<!-- 样式在 styles.css：.hs-badge-pill { background: linear-gradient(...); } -->
```

**装饰 GROUP（子节点全是装饰性质）：**

整个 GROUP 作为独立装饰单元输出，保留内部层级结构：

```html
<!-- 0:35 "热点速递 拷贝" GROUP — 完整角标装饰组件 -->
<div class="hs-badge">
  <!-- 0:38 药丸背景 PATH → SVG -->
  <svg class="hs-badge-pill" viewBox="0 0 341.69 97.09">...</svg>
  <!-- 0:42 红色装饰 PATH → SVG -->
  <svg class="hs-deco-red" viewBox="0 0 76.13 36.80">...</svg>
  <!-- 0:43 金色装饰 PATH → SVG -->
  <svg class="hs-deco-gold" viewBox="0 0 105.12 82.72">...</svg>
  <!-- 0:44 图标 LAYER → img -->
  <img class="hs-deco-icon" src="...">
  <!-- 0:46 固定装饰 TEXT → span -->
  <span class="hs-badge-text">热点速递</span>
  <!-- 0:47 渐变叠加 PATH → SVG -->
  <svg class="hs-badge-overlay" viewBox="...">...</svg>
</div>
```

**固定装饰 TEXT：**

属于某个装饰组件的固定文字，硬编码在 decorations.html 中。

### 4.3 template.html —— 遍历节点树 + 规则翻译

遍历模块的 `node.children` 树，对每个节点按类型翻译。**GROUP 的去向由子节点构成决定（见 4.4 节）。**

```
节点类型           →  template 输出
──────────────────────────────────────────
FRAME (根)         →  <section data-od-id="组件名">
FRAME (子)         →  <div class="...">
LAYER (装饰)       →  不在 template 中（已在 styles.css 或 decorations.html）
TEXT (variable)    →  <span/h2/p class="...">{{slotName}}</span/h2/p>
TEXT (fixed,内容)  →  <span/h2/p class="...">固定文字</span/h2/p>

GROUP (子节点含 variable)    →  <div class="..."> 包裹子节点
GROUP (子节点全装饰)         →  不在 template 中（整组已在 decorations.html）
PATH / BITMAP                →  <!-- decorations 占位 --> 或不在 template 中
图表 GROUP                   →  <div class="...">{{chart}}</div>
```

**GROUP 在 template.html 中的处理示例：**

```
"按钮" GROUP (0:53)
├── 0:54 LAYER (装饰)  → 不在 template 中（样式在 styles.css）
└── 0:55 TEXT (fixed)  → <span class="...">小试一笔</span>

→ GROUP 子节点含功能性 TEXT → 进 template.html：
  <div class="product-card__cta">
    <span class="product-card__cta-text">小试一笔</span>
  </div>
```

**class 命名规则：** AI 读节点的 name、树位置、内容 → 推断语义 → 起名 `.product-card__name`（而非脚本只能产出的 `.n-0-58`）。需要理解中文和业务上下文。

**slot 命名规则：** 同理，`{{text_0_58}}` 不可读，`{{name}}` 才有意义。AI 把节点名映射为有意义的 slot 名。

**布局组织：** 脚本能算出相邻元素间的 y 坐标差，但不知道两个元素应该是上下排列还是同一行。

```
产品代码 "021483"   y=146
风险等级 "较高风险"  y=196

脚本算出间距 10px，可能判为"上下排列"。
但实际上它们应该在同一行：[021483] [较高风险]  ← flex row
```

AI 判断"上下"还是"左右"的依据：y 坐标差很小（在同一行高范围内）、业务上属于同一信息组。AI 决定 flex 方向、容器包裹关系、哪些元素合并到同一行。

---

## 6. 组装引擎

### 5.1 组件的页面顺序

直接从 `data/modules/_index.json` 的 `position.y` 排序决定，无需 agent 判断。

### 5.2 组装过程

```python
# 伪代码
sorted_components = sort_by_position_y(components)

output_html = page_head()  # <!DOCTYPE> + <head> + 加载所有 styles.css + shared/page.css

for component in sorted_components:
    template = read(f"assets/{component.name}/template.html")
    decorations = read(f"assets/{component.name}/decorations.html")  # 可能为空
    
    instances = user_data.get(component.data_key)
    
    for instance_data in instances:
        section = template
        # 替换 {{slot}}
        for slot_name, slot_value in instance_data.items():
            section = section.replace(f"{{{{{slot_name}}}}}", slot_value)
        # 嵌入 decorations
        section = section.replace("<!-- decorations -->", decorations)
        output_html += section

output_html += page_foot()  # </body></html>
```

### 5.3 多实例处理

用户在 `content.template.json` 的数组里加一个 `{}` = 多一页；删一个 = 少一页。组装引擎按数组长度自动复制 section。

### 5.4 viewport 与设计稿缩放

- 先读 `_index.json` → `meta.designScale`
- 移动端设计稿（@2x / @3x）：`<meta name="viewport" content="width=device-width, initial-scale=1.0">`，页面容器宽度 = `designScale.logicalWidth`（如 375px）
- 所有 px 值已由 pipeline 的 `--auto-scale` 缩放为逻辑像素
- 禁止把 @2x/@3x 的原始像素直接写进 viewport

---

## 7. 工作流重构

旧流程（7 步）→ 新流程（8 步）。🧑 = 需用户确认。

### Step 0 —— 输入 & 建工作区

不变。拿到 designUrl + mcpToken，创建 `output/<name>/pipeline/`。

### Step 1 —— 抓取（脚本）

不变。fetch_mcp_data.py → normalize_to_tree.py → split_modules.py。

### Step 2 —— 模块审阅 🧑

不变。读 `_index.json` + `tree.md`，命名、排序、确认边界。

### Step 3 —— 源 CSS + 设计稿缩放（脚本）

不变。generate_module_css.py + --auto-scale。

### Step 4 —— 同类模块合并 🧑

**新步骤，替代旧的 Step 4a/4b/5。**

4a. 脚本列出所有模块，对两两模块做骨架签名比较（只看节点 type 层级，忽略坐标和文本内容）。签名相同的标记为候选合并组。

4b. agent 展示合并建议，用户确认或调整。

4c. 合并后的每组：
  - 如果 ≥ 2 个实例 → **脚本 diff**，自动标记 invariant / variable
  - 如果 = 1 个实例 → **列出 TEXT 清单**，用户逐条标记 fixed / variable

4d. agent 展示判定结果，用户确认。

**输出：每个组件类型的完整标记——哪些节点/属性是 invariant，哪些是 variable。**

### Step 5 —— 生成 assets（脚本 + agent）

**新步骤。这是替代旧 Step 6 的核心产出环节。**

5a. **脚本生成 `styles.css`**：从合并组的代表模块 JSON 中机械提取所有 invariant 视觉属性，写出带溯源注释的 CSS。用户无需确认（纯机械）。

5b. **脚本生成 `decorations.html`**：从模块 JSON 中提取 PATH→SVG、BITMAP→img、LAYER 装饰→div。用户无需确认（纯机械）。

5c. **agent 生成 `template.html`**：遍历节点树，按第 5.3 节的规则翻译为 DOM + {{slot}}。需要 agent 做的是：
  - 给节点起语义化 class 名
  - 给 slot 起有意义的名称
  - 处理特殊布局结构（如 flex 容器包裹）

5d. 用户确认 template.html 的 slot 名称和结构 🧑。

### Step 6 —— 组装（脚本）

**新步骤，纯机械。**

6a. 读 `_index.json` 获取模块顺序（按 position.y 排序）。

6b. 读 `content.template.json` 获取用户示例数据。

6c. 按顺序遍历组件，对每个组件：读 template.html → 按实例数量复制 → 用数据填充 {{slot}} → 嵌入 decorations.html → 拼接。

6d. 输出 `output/example.html`。

### Step 7 —— 验收

对照设计稿逐模块核对。偏差 → 查 gotchas.md。还原度标准：无 emoji、无默认 0、无占位近似、无取整近似（55.85px 不能写成 56px）。

### Step 8 —— 装进 OD（可选）

不变。复制到 OD 安装目录。

---

## 8. 旧结构 → 新结构的映射

| 旧 | 新 | 变化 |
|----|-----|------|
| Step 4a 实例数判定 | Step 4 同类合并 + diff | 不再靠 agent 猜，靠数据 diff |
| Step 4b TEXT 可变性判定 | Step 4c/4d diff + 用户确认 | 同类模块自动判定，singleton 用户确认 |
| Step 5 组件 schema | 合并到 Step 4 | schema 是 diff 的自然产物 |
| Step 6a lift CSS | Step 5a 脚本生成 styles.css | 不再是"原封复制"，而是"机械提取" |
| Step 6b 手写 flow CSS | Step 5a 脚本生成 styles.css | **不再手写**，从 JSON 提取精确值 |
| Step 6c/6d/6e/6f | Step 5c agent 生成 template.html | 简化，聚焦于 DOM 骨架 + slot 标注 |
| Step 6g 拼 HTML | Step 6 组装引擎 | 从手工拼装变为脚本机械组装 |
| 无 | Step 5b decorations.html | **新增**，PATH/SVG/位图独立管理 |

---

## 9. GROWTH 历史问题的根治

| GROWTH # | 问题 | 新设计如何根治 |
|----------|------|---------------|
| #1 内容驱动高度 | agent 判错 CSS 策略 | Step 4 diff 自动识别 variable TEXT → 强制 flow，高度由内容撑开 |
| #2 抓取限流 | MCP 限流导致数据缺失 | 抓取脚本已有延迟，不影响结构 |
| #3 设计稿缩放 | @3x 像素直接写进 viewport | Step 3 --auto-scale 强制缩放；Step 5a 所有 px 值已缩放过 |
| #4 源 CSS 规则→HTML 必须一一对应 | agent 跳过 PATH/SVG | Step 5b decorations.html 机械提取，不遗漏；Step 5c 遍历节点树，不跳过任何节点 |
| #5 outlined text | 文字转路径未检测 | Step 5b decorations.html 处理 outlinedText 节点 |

---

## 10. AI 需要判断的三层结构

脚本负责机械提取（从 JSON 抄数值到 styles.css、从 PATH 提取 SVG 到 decorations.html、按 position.y 排序组装）。

AI 负责语义判断，分三层：

---

### 第一层：组件归并

**原始模块 → 组件类型。这一步同时决定两件事：哪些模块合并 + 合并后是单实例还是多实例。**

脚本做骨架签名比对——只看节点 type 层级（FRAME → GROUP → LAYER/TEXT/PATH），忽略坐标和文本内容。签名相同的标记为候选合并组。

AI 确认合并建议。比如推荐理由 A/B/C 骨架相同 → 合并为 `recommendation`。决定合并的瞬间，多实例属性就自然确定了——因为合并的动机就是"它们骨架一样，只是内容不同"。

**合并后两种不同的增长方式：**

内容会变，但变化的形态不同：

| 增长方式 | 行为 | 例子 |
|----------|------|------|
| **拉高高度** | 还是一块，内容变长→高度增加 | "热点速递"正文 300 字变 500 字，板块变高，下方的推荐理由跟着往下移 |
| **复制实例** | 数量不固定，有 1 个、2 个还是 3 个的并列关系 | 本期推荐 2 个产品→2 张产品卡；下期推荐 3 个→3 张产品卡 |

"拉高高度"对应的是 singleton（一个组件，只出现一次，高度自适应）。
"复制实例"对应的是 multi-instance（一个组件类型，出现 N 次，N 不固定）。

**一个组件是否完全不变，不需要单独判断。** 它是第二层角色判定的自然结果——如果组件里所有节点都归入"装饰"或"固定文本"，没有可变插槽，那这个组件就是完全不变的（如银行结束语：53 个 PATH 全是装饰）。

---

### 第二层：元素角色

**组件内的每个节点 → 落到 assets 的哪个文件。四种角色：**

| 角色 | 去向 | 判定方式 | 例子 |
|------|------|----------|------|
| **样式** | `styles.css` | 数值机械提取 + AI 组织 | 颜色、字号、边框、渐变、圆角、间距、阴影 |
| **装饰** | `decorations.html` | 节点类型规则 + AI 确认 | PATH 形状、Gradient Overlay、BITMAP 装饰图、outlined text |
| **固定文本** | `template.html` 原文保留 | diff（同类模块）/ 用户确认（singleton） | "热点速递"角标、"小试一笔"CTA、"管理费"列头、合规条文 |
| **可变插槽** | `template.html` → `{{slot}}` | diff（同类模块）/ 用户确认（singleton） | 产品名称、收益率、正文、数据来源 |

**样式虽然数值是脚本从 JSON 机械提取的，但 AI 需要决定：**
- 哪些节点需要独立 CSS class，哪些合并到父元素
- class 命名怎么跟 template.html 的 DOM 结构对应
- flow 布局怎么组织（flex 方向、容器包裹关系、间距体系）

**装饰的判定规则：**

| 条件 | 说明 |
|------|------|
| `type == "PATH"` | 矢量形状装饰 |
| `type == "BITMAP"` 且不在 TEXT 子树中 | 位图装饰（如右上角浮动图） |
| `type == "LAYER"` 且有复杂 fill + 无 TEXT 子节点 | 独立装饰层 |
| `type == "GROUP"` 且 name 含 CJK + 子树全 PATH/Gradient Overlay + 无 TEXT | outlined text（文字转轮廓） |
| `type == "GROUP"` 且子树全是 PATH/LAYER 装饰节点 | 整体装饰组件 |

**固定文本 vs 可变插槽的判定：**

- **同类模块 ≥ 2 个** → 脚本 diff，值不同的 TEXT 自动标 variable，值相同的标 fixed。AI 确认。
- **Singleton 模块** → 脚本先自动标无条件 fixed（PATH/LAYER 节点、合规文本、费用表头），剩余 TEXT 列清单，用户逐条标记。

---

### 第三层：可变类型

**被标记为 `{{slot}}` 的内容，用户可以改什么？**

| 可变类型 | 例子 |
|----------|------|
| **文本替换** | 标题、正文、产品名、CTA 文案 |
| **数值替换** | 费率 0.15%、涨跌幅 2.80% |
| **图表描述** | 自然语言描述图表类型 + 数据，OD agent 负责渲染 |
| **图片替换** | 产品配图、头像（如果有 bitmap 被标记为 variable） |
| **条件显示** | 某个区块（如副标题）有/无，跟着数据走 |

**图表区域的处理：**

图表识别见 4.1 节判定信号（最强信号：同级有"数据来源""资料来源"TEXT）。一旦判定为图表：
- `styles.css`：只提取容器壳——尺寸（由设计稿决定，但 OD 中可调整）、背景色、圆角、标题字体
- `decorations.html`：不涉及——图表内部 PATH 不提取
- `template.html`：整个图表区暴露为一个 `{{chart}}` 插槽
- OD 用户在 OD 中用自然语言描述图表类型 + 数据，OD agent 负责渲染
- 图表渲染规则写在产出 OD skill 的 SKILL.md 中，不属于本 meta-skill

---

## 11. 需要新建/修改的文件

### 新建脚本

| 脚本 | 用途 |
|------|------|
| `scripts/analyze/diff_modules.py` | 合并同类模块 + diff invariant/variable |
| `scripts/generate/extract_styles.py` | 从模块 JSON 机械提取 → styles.css |
| `scripts/generate/extract_decorations.py` | 从模块 JSON 提取 PATH/SVG/位图 → decorations.html |
| `scripts/assemble/build_html.py` | 按组件顺序 + 用户数据 → 组装完整 HTML |

### 修改现有脚本

| 脚本 | 修改 |
|------|------|
| `scripts/prepare/split_modules.py` | 确保 outlined text 检测、designScale 写入、assets.svgs 完整 |

### 修改 SKILL.md

按第 7 节的新工作流重写。

### 废弃/合并

| 旧文件 | 处理 |
|------|------|
| `references/module-classification.md` | 合并到新 SKILL.md Step 4 |
| `references/component-authoring.md` | 不再需要——CSS 从 JSON 机械提取，不再手写 |
| `references/component-templates.md` 的图表算法部分 | 移到 `assets/od-skill-template/SKILL.md`，作为 OD skill 的图表渲染指引 |
| `assets/od-skill-template/` | 保留框架，内容由脚本生成替代 |

### references 精简后

```
references/
├── pipeline.md        ← 保留：脚本运行细节 + MCP 原理
├── gotchas.md         ← 保留：排查清单（持续沉淀）
└── od-skill-spec.md   ← 保留：OD 安装规范
```

从 5 个文件缩减到 3 个。模块分类和手写 CSS 的方法论不再需要，图表算法归入 OD skill 模板。

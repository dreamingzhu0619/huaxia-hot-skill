# Step 3 操作手册：提取样式 & 生成 CSS

## 前置条件

- Step 2 已完成，`data/<project>/output/step2-04_slots-definition.json` 存在。
- `data/<project>/modules/*.json` 有完整的 node 树数据（含 font、fill、effect 等样式字段）。

## 输出约定

本阶段产物统一写入 `data/<project>/output/`。

---

## 核心思路

三种 frameType，三种处理策略：

| frameType | CSS 策略 | 文字样式提取方式 |
|-----------|---------|----------------|
| `content`（内容型） | 字号最大→标题 / 字数最多→正文 / 关键词→来源 | **粗暴规则**，不需要 AI |
| `template`（模板型） | 逐个 slot 从原始节点取样式 | 直接读 TEXT node |
| `fullyFixed`（固定模块） | 不生成 CSS | 原样保留即可 |

---

## 流程总览

```
Step 2 输出（step2-04_slots-definition.json）
    │
    ├── Step 3.0a [公共模块] 帧内重复检测 ─────────────┐
    │  （所有 frameType 共用，在样式提取之前执行）        │
    │                                                   │
    │  ┌──────────────────────────────────────────────┐ │
    │  │ 对每个 frame 的 node 树：                      │ │
    │  │  1. 计算每个子节点的结构指纹（递归 type 序列）  │ │
    │  │  2. 找出兄弟中指纹相同的 FRAME/GROUP          │ │
    │  │  3. 保留第一个 → 代表实例                       │ │
    │  │  4. 其余 → 标记为 repeatInstance（不提取样式）  │ │
    │  │ 输出：去重后的节点列表 + repeatGroups 标注     │ │
    │  └──────────────────────────────────────────────┘ │
    │                                                   │
    ├── Step 3.0b [公共模块] 文字背景形状检测 ──────────┐
    │  （所有 frameType + fixedGroups 共用）             │
    │                                                   │
    │  ┌──────────────────────────────────────────────┐ │
    │  │ 输入：modules/*.json 的 node 树 + TEXT nodeId │ │
    │  │ 检测两种模式：                                 │ │
    │  │  · 兄弟型：sibling PATH/LAYER 紧包裹 TEXT     │ │
    │  │  · 包裹型：TEXT 所在 GROUP 内有紧包裹的 PATH  │ │
    │  │ 输出：text → backgroundShape 映射             │ │
    │  └──────────────────────────────────────────────┘ │
    │                                                   │
    ├── content frames ─────────────────────────────┐   │
    │                                                 │   │
    │  ┌────────────────────────────────────────────┐ │   │
    │  │ 对每个 zone（已去重，只含代表实例）：         │ │   │
    │  │  1. 过滤：文字含"数据来源/资料来源" → source │ │   │
    │  │  2. 剩余文字中，字号最大 → 标题样式          │ │   │
    │  │  3. 剩余文字中，字数最多 → 正文样式          │ │   │
    │  │  4. 其余 → 图表标签，不管                    │ │   │
    │  │  5. skeletonLayers → 背景/圆角/阴影         │ │   │
    │  │  6. 调用 Step 3.0b 检测每个 slot 的文字背景  │ │   │
    │  └────────────────────────────────────────────┘ │   │
    │                                                 │   │
    ├── template frames ────────────────────────────┐   │
    │                                                 │   │
    │  ┌────────────────────────────────────────────┐ │   │
    │  │ 对每个 slot（已去重，只含代表实例）：         │ │   │
    │  │  1. 从 modules/*.json 按 nodeId 查 TEXT node│ │   │
    │  │  2. 读 textRuns[0].font / color / align     │ │   │
    │  │  3. 调用 Step 3.0b 检测文字背景              │ │   │
    │  │  4. 样式完全相同的 slot → 合并为同一 class   │ │   │
    │  │  5. fixedGroups → 装饰元素样式               │ │   │
    │  │     （fixedGroups 里的 TEXT 也走 3.0b）      │ │   │
    │  └────────────────────────────────────────────┘ │   │
    │                                                 │   │
    └── fullyFixed ─── 跳过（但 fixedGroups 可调用    │   │
                       3.0a/3.0b）                     │   │
```

---

## Step 3.0a [公共模块] 帧内重复检测

**定位**：`scripts/step3_detect_repeats.py`，独立模块。在样式提取之前运行，对所有 frameType 的 node 树做帧内重复检测。

**做什么**：一个 frame 内部可能有重复的子结构——设计师做了一个卡片/条目，然后复制了几份。这些重复实例结构完全相同，只是文字内容不同。Step 3 只需要提取一份样式，其余标记为 repeatable 即可。

### 典型场景：industry "编组 54"

```
FRAME 编组 54
  ├── LAYER 矩形备份 3                 ← unique（顶部背景）
  ├── TEXT (body paragraph)            ← unique
  ├── LAYER 矩形备份 31                ← unique
  ├── TEXT "半导体是什么？"             ← unique（标题）
  ├── FRAME 编组 58 ────────────────┐ ← repeat instance 1（代表）
  │   ├── FRAME 编组 53              │
  │   │   ├── LAYER 矩形              │   结构:
  │   │   └── TEXT "上游 - 设备与材料" │   FRAME[ FRAME[LAYER,TEXT], FRAME[FRAME,TEXT] ]
  │   └── FRAME 编组 57              │
  │       ├── FRAME 编组 20           │
  │       └── TEXT "产业基石"         │
  ├── FRAME 编组 58备份 ─────────────┘ ← repeat instance 2（结构相同，文字不同）
  │   ├── FRAME 编组 53
  │   │   ├── LAYER 矩形
  │   │   └── TEXT "中游 - 芯片设计、制造与封测"
  │   └── FRAME 编组 57
  │       ├── FRAME 编组 20
  │       └── TEXT "价值核心"
  ├── FRAME 编组 18                    ← unique（图表）
  ├── FRAME 编组 34                    ← unique（标签）
  └── FRAME 编组 59                    ← unique（另一个内容区）
```

编组 58 和编组 58备份 结构完全一致，只需提取编组 58 的样式。

### 检测算法

#### 第一步：计算结构指纹

对 node 树中每个节点，计算结构指纹（structure hash）：

```python
def structure_fingerprint(node):
    """递归编码节点的类型结构，忽略文字内容"""
    child_types = tuple(
        structure_fingerprint(c) for c in node.get('children', [])
    )
    return (node['type'], child_types)
```

例如：

```
编组 58 的指纹:
  ("FRAME", (
      ("FRAME", (("LAYER", ()), ("TEXT", ()))),
      ("FRAME", (("FRAME", ()), ("TEXT", ())))
  ))

编组 58备份 的指纹:
  ("FRAME", (
      ("FRAME", (("LAYER", ()), ("TEXT", ()))),
      ("FRAME", (("FRAME", ()), ("TEXT", ())))
  ))
```

→ 指纹相同 → 判定为重复实例。

> 指纹只编码 `type` 序列，不编码 name / text / fill 等具体值。因为重复实例的文字内容不同，但结构骨架一样。

#### 第二步：按 sibling 分组

对每个父节点，将其 children 按结构指纹分组：

```
parent.children
  → group by structure_fingerprint
  → 每组 ≥ 2 个成员的 → 这就是一个 repeatGroup
  → 每组第 1 个 → 代表实例（representative）
  → 其余 → 重复实例（repeatInstances），不提取样式
```

#### 第三步：输出

对每个 frame，输出：

```json
{
  "frameId": "0:1853",
  "frameName": "编组 54",
  "repeatGroups": [
    {
      "structureFingerprint": "FRAME[FRAME[LAYER,TEXT],FRAME[FRAME,TEXT]]",
      "count": 2,
      "representativeNodeId": "0:1858",
      "representativeName": "编组 58",
      "repeatInstanceNodeIds": ["0:1868"],
      "repeatInstanceNames": ["编组 58备份"]
    }
  ]
}
```

### 与 Step 2 重复检测的区别

| | Step 2.3（frame 级） | Step 3.0a（帧内） |
|------|------|------|
| 检测范围 | 跨 frame：不同 module 之间 | 帧内：同一个 frame 的 children |
| 检测对象 | 整个 frame 的 node 树 | frame 内直接的子 FRAME/GROUP |
| 用途 | 判断一个 frame 是否需要作为"模板"处理 | 避免重复提取相同的子结构样式 |
| 示例 | 5 张产品卡 → repeatable=true, repeatCount=5 | 编组 58/58备份 → 只提取编组 58 的样式 |

### 调用时机

Step 3.1 在提取样式之前，对每个 frame 先调用 Step 3.0a 做帧内去重。提取样式时只遍历代表实例和 unique 节点。

---

## Step 3.0b [公共模块] 文字背景形状检测

**定位**：`scripts/step3_detect_backgrounds.py`，独立模块，被 Step 3.1 调用。所有 frameType 和 fixedGroups 的 TEXT 都通过它检测是否有背景形状。

**做什么**：给定 node 树和一个 TEXT nodeId，判断该文字下面是否垫了背景形状，如果有则返回形状的样式信息。

### 两种检测模式

#### 模式 1：兄弟型（shape 和 TEXT 是兄弟节点）

CMB 市场分析中的典型结构：

```
FRAME "市场分析"
  ├── PATH "形状结合备份"   bounds=(27, 551, 104, 23)  fill=渐变
  ├── TEXT "从政策环境看"   bounds=(35, 555, 84,  20)
  ├── PATH "形状结合备份 2" bounds=(27, 651, 142, 23)  fill=渐变
  └── TEXT "从海外市场看"   bounds=(35, 655, 126, 20)
```

TEXT 和背景 PATH 在同一个 FRAME 下平级排列。

#### 模式 2：包裹型（TEXT 和 shape 被包在同一个 GROUP 里）

CITC 产品卡中的典型结构：

```
GROUP "代码"
  ├── SHAPE "矩形 16"   bounds=(x, y, w, h)  fill=#FFEEDB
  └── TEXT "021483"     bounds=(x+8, y+4, w-16, h-8)

GROUP "风险等级"
  ├── SHAPE "矩形 16 拷贝"  fill=#FFEEDB
  └── TEXT "较高风险"
```

设计师显式把文字和它的背景形状编组在一起，GROUP 名本身就是这个"文字组件"的语义。

### 核心检测算法

两种模式共用同一套判定逻辑——**shape 紧包裹 text**：

```
函数: detect_text_background(node_tree, text_node_id) → BackgroundInfo | None

步骤:
  1. 定位 TEXT node
  2. 获取候选 shape 列表:
     · 兄弟型: text.parent.children 中 type ∈ {PATH, LAYER} 的节点
     · 包裹型: 若 text.parent.type == GROUP,
               则 text.parent.children 中 type ∈ {PATH, LAYER} 的节点
               （排除 text 自己）
  3. 对每个候选 shape，检查:
     a. shape.bounds 包含 text.bounds
     b. 四边间距都在 [0, 20px] 范围内
     c. shape.fill ≠ null 且 ≠ IMAGE
     d. shape.mask == null
  4. 多个候选 → 取面积最小的（最紧包裹）
  5. 返回:
     {
       nodeId: shape.id,
       nodeName: shape.name,
       mode: "sibling" | "group",
       backgroundColor: shape.fill,
       borderRadius: shape.borderRadius,
       padding: { top, bottom, left, right }  // bounds 间距
     }
```

### 为什么两种模式都要检测

| | 兄弟型 | 包裹型 |
|------|------|------|
| 设计师操作 | 画个矩形，上面放文字，不对齐编组 | 画个矩形，上面放文字，Ctrl+G 编组 |
| 树结构 | siblings | GROUP.children |
| 检测难度 | 候选 shape 多（同层所有 PATH/LAYER） | 候选 shape 少（GROUP 内只有少数几个） |
| 例子 | CMB 三个小标题 | CITC 产品卡的"代码""风险等级"标签 |

> 两种模式不是互斥的——同一个 TEXT 可能同时满足（GROUP 内有紧包裹 shape，且 sibling 也有）。此时取面积最小的。

### 输入输出

**输入**：

| 参数 | 说明 |
|------|------|
| `node_tree` | 完整的 module node 树（递归结构） |
| `text_node_id` | 要检测的 TEXT nodeId（如 "0:979"） |

**输出**：`BackgroundInfo` 对象或 `None`（无背景形状）。

### 调用方

| 调用方 | 场景 |
|------|------|
| `step3_extract_styles.py` | content 帧 zone 内 slot、template 帧 slot |
| `step3_extract_styles.py` | template 帧 fixedGroups 中的 TEXT（按钮、标签等） |
| （未来）Step 4 模板生成 | 需要知道哪些文字自带背景，CSS class 已包含 |

---

## Step 3.1 [脚本] 提取样式

**做什么**：读取 slots-definition + 原始 module JSON。先对每个 frame 调用 Step 3.0a 做帧内重复检测（去重），再提取样式值（未 scale），对每个 TEXT slot 调用 Step 3.0b 检测背景形状。输出中间 JSON 方便调试。

**运行**：`scripts/step3_extract_styles.py`

**输入**：

| 文件 | 来源 |
|------|------|
| `data/<project>/output/step2-04_slots-definition.json` | Step 2 最终输出 |
| `data/<project>/modules/*.json` | 原始设计稿 node 数据 |

**输出**：

| 文件 | 说明 |
|------|------|
| `data/<project>/output/step3-01_extracted-styles.json` | 所有提取出的原始样式值 |

---

### 内容型 frame 的提取规则

对每个 zone，遍历 `zone.slots`：

#### 第一步：识别来源标注

```
slot.text 包含 "数据来源" 或 "资料来源"
  → role = "source"
  → 从该 slot 对应的 TEXT node 提取样式
```

来源标注的样式独立提取，不参与字号排名。

#### 第二步：标题 → 最大字号，正文 → 最多字数

把**非来源**的 slot 按规则分类：

```
zone 内非来源 slot：
  → 按对应 TEXT node 的字号（textRuns[0].font.size）排序
  → 字号最大的一组 → role = "title"

  → 按 slot.text 的字符数排序
  → 字符数最多的一条 → role = "body"
     （从该 slot 对应的 TEXT node 提取正文样式）

  → 其余 → role = "chart-label"（不管）
```

**为什么正文用字数而不是字号**：zone 内图表标签的字号可能比正文还大（如"红利因子"41px vs 正文 38px），但图表标签都是短文本，正文才是长段落。字数是最可靠的正文本体信号。

**边界情况**：
- zone 只有一个非来源 slot → 它就是 title（同时也是最长文本，title 优先）
- zone 只有一个字号且所有 slot 都是短文本（≤8 字）→ 无 body，title 取最大字号
- 所有非来源 slot 字符数一样（如都是标签）→ 无 body，仅 title

#### 第三步：检测文字背景形状

对 zone 内每个 slot，调用 **Step 3.0b 公共模块** `detect_text_background()` 检测。检测到背景形状 → 合并 `backgroundColor` / `borderRadius` / `padding` 到该 slot 的样式中。

> 详细算法见 Step 3.0b，此处不重复。

#### 第四步：提取骨架样式

对 `zone.skeletonLayers` 中每个节点，从原始 node 提取：

| 属性 | 来源字段 | 说明 |
|------|---------|------|
| `backgroundColor` | `fill` | 纯色/渐变/图片 |
| `borderRadius` | `borderRadius` | 四角圆角 |
| `boxShadow` | `effect.boxShadow` | 阴影 |
| `border` | `strokeColor` + `strokeWidth` + `strokeAlign` | 边框 |
| `opacity` | `opacity` | 透明度 |

> zone 的 contentArea 已在 Step 2 算好（boundary 内缩 24px），padding/textAlign 直接沿用，不需要重新提取。

---

### 模板型 frame 的提取规则

#### 文字样式：逐个 slot 提取

对 `module.slots` 中每个 slot，通过 `nodeId` 在 `modules/*.json` 中查到原始 TEXT node：

| 属性 | 来源字段 |
|------|---------|
| `fontFamily` | `textRuns[0].font.family` |
| `fontSize` | `textRuns[0].font.size` |
| `fontWeight` | `textRuns[0].font.style`（如 "Bold"） |
| `lineHeight` | `textRuns[0].font.lineHeight` |
| `letterSpacing` | `textRuns[0].font.letterSpacing` |
| `color` | `textRuns[0].color` |
| `textAlign` | `textAlign` |

**样式合并**：提取后，比较所有 slot 的样式。完全相同的（fontFamily + fontSize + fontWeight + color + lineHeight + letterSpacing + textAlign）→ 共用同一个 class。

#### 文字背景形状检测

模板型 slot 和 fixedGroups 中的 TEXT 同样调用 **Step 3.0b 公共模块**检测。

#### 装饰元素：fixedGroups

对 `module.fixedGroups` 中 `role` 为 `brand-badge` / `fixed-texts` / `fixed-label` 的组，提取组内所有非 TEXT 节点的视觉样式（背景、圆角、阴影、边框），以及 TEXT 节点的文字样式。

| role | 提取重点 |
|------|---------|
| `brand-badge` | 按钮背景色、圆角、按钮文字样式 |
| `fixed-texts` | 标签文字样式、表头样式 |
| `fixed-label` | 标签文字样式、标签背景 |
| `mask` | 蒙版内的 IMAGE → 忽略（装饰图） |

---

### 输出格式：step3-01_extracted-styles.json

```json
{
  "meta": {
    "designWidth": 1125,
    "logicalWidth": 375,
    "scale": 3
  },
  "contentFrames": {
    "产品推荐理由": {
      "frameType": "content",
      "zones": [
        {
          "id": "zone-0",
          "textStyles": {
            "title": {
              "fontFamily": "MiSans-Bold",
              "fontSize": 57,
              "fontWeight": "Bold",
              "lineHeight": "57",
              "letterSpacing": "-2.25%",
              "color": "#FFFFFF",
              "textAlign": "center",
              "sampleText": "左手红利 右手低波"
            }
          },
          "skeleton": {
            "backgroundColor": "#FFFFFF",
            "borderRadius": "12px",
            "boxShadow": "0px 2px 8px rgba(0,0,0,0.1)"
          }
        },
        {
          "id": "zone-1",
          "textStyles": {
            "title": {
              "fontFamily": "MiSans-Bold",
              "fontSize": 46,
              "fontWeight": "Bold",
              "lineHeight": "46",
              "letterSpacing": "0%",
              "color": "#6D2807",
              "textAlign": "left",
              "sampleText": "红利低波组合的投资逻辑"
            },
            "body": {
              "fontFamily": "PingFang SC",
              "fontSize": 38,
              "fontWeight": "Regular",
              "lineHeight": "57",
              "letterSpacing": "0%",
              "color": "#6D2807",
              "textAlign": "left",
              "sampleText": "中证红利低波动指数选取50只流动性好…"
            },
            "source": {
              "fontFamily": "PingFang SC",
              "fontSize": 28,
              "fontWeight": "Regular",
              "lineHeight": "42",
              "letterSpacing": "0%",
              "color": "#999999",
              "textAlign": "left",
              "sampleText": "资料来源：华泰研究。"
            }
          },
          "skeleton": {
            "backgroundColor": "#FFF9F5",
            "borderRadius": "12px"
          }
        }
      ]
    }
  },
  "templateFrames": {
    "营销头图": {
      "frameType": "template",
      "slots": [
        {
          "nodeId": "0:10",
          "text": "市场开启震荡模式",
          "styleClass": "hero__title",
          "fontFamily": "MiSans-Bold",
          "fontSize": 85,
          "fontWeight": "Bold",
          "lineHeight": "85",
          "letterSpacing": "-2.25%",
          "color": "#DFD3B1",
          "textAlign": "left"
        },
        {
          "nodeId": "0:13",
          "text": "\"反脆弱\"红利低波",
          "styleClass": "hero__subtitle",
          "fontFamily": "MiSans-Bold",
          "fontSize": 28,
          "fontWeight": "Bold",
          "lineHeight": "28",
          "letterSpacing": "0%",
          "color": "#DFD3B1",
          "textAlign": "left"
        }
      ],
      "decorative": {
        "dividers": [
          {
            "nodeId": "0:9",
            "style": "linear-gradient(...)",
            "height": 1
          }
        ]
      }
    },
    "产品卡": {
      "frameType": "template",
      "slots": [
        {
          "nodeId": "0:57",
          "text": "华夏中证红利低波动ETF发起式联接C",
          "styleClass": "product-card__name",
          "fontFamily": "MiSans-Bold",
          "fontSize": 42,
          "fontWeight": "Bold",
          "lineHeight": "63",
          "letterSpacing": "0%",
          "color": "#1A1A1A",
          "textAlign": "left"
        },
        {
          "nodeId": "0:63",
          "text": "021483",
          "styleClass": "product-card__code",
          "fontFamily": "PingFang SC",
          "fontSize": 28,
          "fontWeight": "Regular",
          "lineHeight": "42",
          "letterSpacing": "0%",
          "color": "#666666",
          "textAlign": "left"
        }
      ],
      "fixedGroups": {
        "按钮": {
          "role": "brand-badge",
          "background": "#E50D09",
          "borderRadius": "20px",
          "textStyle": {
            "fontFamily": "PingFang SC",
            "fontSize": 28,
            "fontWeight": "Medium",
            "color": "#FFFFFF"
          }
        }
      }
    }
  }
}
```

---

## Step 3.2 [脚本] 生成 CSS

**做什么**：读取 `step3-01_extracted-styles.json`，scale 换算（÷3），生成 `components.css`。

**运行**：`scripts/step3_generate_css.py`

**输入**：

| 文件 | 来源 |
|------|------|
| `data/<project>/output/step3-01_extracted-styles.json` | Step 3.1 |

**输出**：

| 文件 | 说明 |
|------|------|
| `data/<project>/output/assets/styles/components.css` | 最终 CSS |

---

### Scale 换算

设计稿宽度 1125px → 逻辑宽度 375px。

所有 `px` 值 **÷ 3**，保留 1 位小数：

```
fontSize: 57  →  CSS: 19px
fontSize: 85  →  CSS: 28.3px
width: 1076   →  CSS: 358.7px
borderRadius: 12 → CSS: 4px
```

`%` 和 `letterSpacing` 百分比值不缩放。

---

### CSS class 命名规范

#### 内容型 frame

按 typographic role 生成**跨 frame 共享**的语义 class：

| role | class 名 | 说明 |
|------|---------|------|
| `title` | `.module-title` | zone 内最大字号的标题样式 |
| `body` | `.module-body` | zone 内最长文本的正文样式 |
| `source` | `.module-source` | 数据来源标注样式 |
| skeleton | `.module-card` | zone 骨架（背景/圆角/阴影） |

如果不同 content frame 的同一 role 样式不同，则加 frame 前缀覆盖：

```css
/* 共享默认 */
.module-title { font-size: 19px; font-weight: 700; }
/* 特定 frame 覆盖 */
.recommendation__title { font-size: 15.3px; color: #6D2807; }
```

#### 模板型 frame

按 `groupName` 自动生成前缀，合并相同样式后按序号或语义命名：

```css
/* 营销头图 */
.hero__title { font-size: 28.3px; ... }
.hero__subtitle { font-size: 9.3px; ... }

/* 产品卡 */
.product-card__name { font-size: 14px; ... }
.product-card__code { font-size: 9.3px; ... }
.product-card__risk { font-size: 9.3px; ... }
.product-card__return { font-size: 14px; color: #E50D09; ... }
```

命名规则：
- 前缀：驼峰化的 `groupName`（如 `产品卡` → `product-card`）
- 后缀：样式相同则合并，不同的按 slot 文本内容推断语义（名称/代码/风险/费率/按钮）

---

### CSS 输出规则

- 颜色保留设计稿原值（渐变、rgba 等），不自行调整为品牌色
- 字体 family：设计稿字体 → `"PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif` fallback
- 如果设计稿用了特殊字体（如 `MiSans`、`AlibabaPuHuiTi`），作为首选，后面加 fallback
- 容器高度不写死（浏览器 flow 自动撑开）
- 绝对定位坐标不写入（顶层模块流动排列）

---

## 特殊处理

### 图表文字识别

正文已通过**最长文本**确定，图表标签不再干扰正文检测。仅需在 title 判定时排除图表干扰：

```
如果 "最大字号组" 的所有文本都是 ≤ 8 个字的短文本
  → 该 zone 无 title，跳过
  → 继续找下一个字号组作为 title
```

例如 zone-1 中：
- 46px → "红利低波组合的投资逻辑"（10 字）→ **标题**
- 最长文本 → "中证红利低波动指数选取50只…"（90+ 字）→ **正文样式**
- 41px → "红利因子"、"低波动因子"（≤4 字）→ 图表标签，不管

### contentArea 和 padding

Step 2 已输出每个 zone 的 `contentArea` 和 `padding`（24px），CSS 中直接使用：

```css
.module-card {
  /* skeleton 样式 */
  background: #FFF9F5;
  border-radius: 4px;
  /* contentArea 用 padding 实现 */
  padding: 8px;  /* 24px ÷ 3 */
}
```

### 重复帧（repeatable）

Step 2 已经做了去重——`repeatable: true` 的帧在 `step2-04_slots-definition.json` 中**只保留第一个代表实例**，重复实例不会出现在输出中。因此 Step 3 天然只提取一份样式，不需要额外处理。

Step 4 模板生成时通过循环渲染多个实例，复用同一套 CSS。

---

## 脚本速查表

| 步骤 | 脚本 | 类型 | 输入 | 输出 |
|------|------|------|------|------|
| 3.0a | `step3_detect_repeats.py` | **公共模块** | node tree（任意 frameType） | repeatGroups 标注 + 去重后节点列表 |
| 3.0b | `step3_detect_backgrounds.py` | **公共模块** | node tree + text_node_id | BackgroundInfo \| None |
| 3.1 | `step3_extract_styles.py` | 主脚本 | `step2-04_slots-definition.json` + `modules/*.json` | `step3-01_extracted-styles.json` |
| 3.2 | `step3_generate_css.py` | 主脚本 | `step3-01_extracted-styles.json` | `assets/styles/components.css` |

> Step 3.1 内部先调用 Step 3.0a 做帧内重复检测（去重），再调用 Step 3.0b 为每个 TEXT 检测背景形状。

---

## 技术参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 设计稿宽度 | 1125px | 所有 frame 统一 |
| 逻辑宽度 | 375px | 目标屏幕 |
| scale 比例 | ÷3 | 所有 px 值统一缩放 |
| 内容区内边距 | 24px（设计稿）/ 8px（CSS） | 来自 Step 2 的 contentArea.padding |
| 图表标签阈值 | ≤ 8 字 | title 候选若全是短文本则跳过；正文不受此限制（正文始终取最长文本） |
| 文字背景检测：最大间距 | 20px | shape 与 text 的四边间距 ≤ 此值才算紧包裹 |
| 文字背景检测：间距均匀阈值 | 6px | 四边间距 max-min ≤ 此值则取均值 padding |

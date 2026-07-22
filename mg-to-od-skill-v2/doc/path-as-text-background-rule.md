# PATH/LAYER 作为 TEXT 背景的合并规则

## 背景

MasterGo 设计稿中，不存在"给文字加背景色"这个原子操作。设计师要给文字加背景，只能手动在文字下面叠加一个矩形（LAYER）或形状（PATH），然后分别调整两个图层的坐标来对齐。此外，MasterGo 的"图层样式 → 渐变叠加/颜色叠加"在导出时也会被拆成独立的 PATH（Gradient Overlay / Color Overlay），挂在文字旁边。

这些 PATH/LAYER 在视觉上和文字是一体的，但在 DSL 数据中是两个平级节点。生成 HTML 时应将它们合并为一个带 `background` 样式的文本元素，避免冗余 DOM。

---

## 核心规则

> 同一父容器下，若 LAYER/PATH 节点在空间上**包含** TEXT 节点，且自身无独立语义，则将 LAYER/PATH 的 fill/effect 合并为 TEXT 的 CSS `background` 样式。

## 判定条件（全部满足才合并）

| # | 条件 | 判定方式 | 阈值 |
|---|------|----------|------|
| 1 | **包含关系** | LAYER/PATH 的 bounding box 包围 TEXT 的 bounding box | 容差 ±2px |
| 2 | **名称无独立语义** | 名称匹配通用模式（见下表），不含 icon/logo/箭头/图表等语义 | 正则匹配 |
| 3 | **尺寸关联** | LAYER/PATH 宽 ≈ TEXT 宽 + 水平 padding（≤30px），高 ≈ TEXT 高 + 垂直 padding（≤20px） | 宽差 ≤30px，高差 ≤20px |
| 4 | **居中对齐** | TEXT 在 LAYER/PATH 内水平/垂直居中，偏移偏差 ≤3px | 偏差 ≤3px |

### 条件 2 补充：哪些名称算"无独立语义"

**应合并**（通用形状名）：

- `矩形` / `矩形备份` / `矩形拷贝` / `矩形 N`
- `形状结合` / `形状结合备份` / `形状结合备份 N`
- `Gradient Overlay` / `Color Overlay` ← 文字特效导出产物
- `蒙版` / `路径 N` / `形状 N`

**不应合并**（有独立语义）：

- `icon-*` / `箭头` / `duigou-*` ← 图标
- `椭圆` / `椭圆形` ← 通常是独立装饰
- 名称与文字内容无关的独立图形

---

## 为什么 PATH 和 LAYER 都要纳入规则

根据 MasterGo 节点类型：

| 类型 | 本质 | 设计师怎么画出来的 |
|------|------|-------------------|
| **LAYER** | 矩形 | 按 R 键画矩形，填色 |
| **PATH** | 矢量路径 | 画不规则形状；**或者**给文字加"图层样式→渐变叠加"，导出时被拆成 PATH |

两者几何底子都是形状，都可以充当文字背景。特别是 `Gradient Overlay` PATH，它是 MasterGo 导出的副产品，不是设计师手动画的独立图形，必须合并回文字。

---

## DSL 字段 → CSS 字段完整映射

### 依赖的 Tool

| Tool | 提供什么 | 用在哪一步 |
|------|----------|-----------|
| **getDSL** (`getDsl.json`) | `styles` 字典：`paint_XXX` / `effect_XXX` / `font_XXX` → 实际 CSS 值 | 把引用解析成 CSS 值 |
| | 节点树：节点类型、父子关系、节点名称 | 找到 PATH/LAYER + TEXT 平级对 |
| | `layoutStyle`：x, y, width, height | 算包含关系 + padding |
| | `borderRadius`、`strokeColor`、`strokeWidth`、`strokeAlign` | 直接映射到 CSS |
| | `opacity` | 透明度 |
| | `path[].data`：PATH 的路径数据（**经常为空 `""`**） | 判断矩形 vs 复杂形状 |
| | `path[].transform`：矩阵变换 | 还原变换后的形状 |
| **getDesignSvgs** (`getDesignSvgs.json`) | 每个 PATH/LAYER 渲染后的 SVG，含真实 `d=` 贝塞尔路径 | `path.data` 为空时，补全形状几何，判断是否简单矩形 |
| **getDesignTexts** (`getDesignTexts.json`) | 文本引用 "T2\|0:968" → 实际文字内容 | DSL 里 TEXT 的 `text[].text` 经常是引用而非真实文字 |
| **getDesignSections** (`section-XX.json`) | fill/effect 已 resolve 为内联 CSS 值的节点树（可选，比 getDSL 方便） | 替代 getDSL，省去手动查 styles 字典 |

### 来源 Tool → DSL 原始字段 → 最终 CSS 属性

#### 1. fill → `background`

**来源 Tool**：`getDSL`（styles 字典）或 `getDesignSections`（已 resolve）

```
DSL 原始数据:
  PATH/LAYER:
    fill: "paint_0:149"          ← 引用，需进 styles 字典查表
    # 或已 resolve（section JSON）:
    fill: "linear-gradient(180deg, #FFEABE -22%, #FFF9ED 100%)"

解析:
  if fill 是引用 "paint_0:XXX":
    → 查 getDSL.styles[paint_0:XXX].value[0]
    → 得到 "linear-gradient(...)" 或 "#RRGGBB" 或 "rgba(...)"

输出 CSS:
  background: linear-gradient(180deg, #FFEABE -22%, #FFF9ED 100%);
```

特殊处理：

| fill 用途 | 处理方式 |
|-----------|---------|
| PATH name = "Gradient Overlay" | `background: ...; -webkit-background-clip: text; color: transparent;`（渐变叠到文字上） |
| PATH name = "Color Overlay" | `color: <fill值>`（纯色覆盖文字颜色） |
| PATH/LAYER 名称为通用形状名 | `background: <fill值>`（普通背景） |

#### 2. effect → `box-shadow` / `filter`

**来源 Tool**：`getDSL`（styles 字典）或 `getDesignSections`（已 resolve）

```
DSL 原始数据:
  PATH/LAYER:
    effect: "effect_0:201"       ← 引用

解析:
  查 getDSL.styles[effect_0:201].value[]
  → ["box-shadow: inset 0px -1px 2px 0px rgba(255,255,255,0.5)"]

输出 CSS:
  box-shadow: inset 0px -1px 2px 0px rgba(255,255,255,0.5);
```

注意：`effect` 的 value 是**数组**，可能含多条（如同时有 `box-shadow` + `filter: blur(...)`），全部拼接。

#### 3. borderRadius → `border-radius`

**来源 Tool**：`getDSL`

```
DSL 原始数据:
  LAYER:
    borderRadius: "2px"          ← 直接是 CSS 值

PATH:
    (无 borderRadius 字段，需从 SVG path d= 推算)

输出 CSS:
  border-radius: 2px;
```

LAYER 直接取 `borderRadius`。PATH 无此字段，需从 `getDesignSvgs` 的 SVG `d=` 数据判断：若 `d=` 描述的是圆角矩形，提取圆角半径；若是不规则形状，不合并。

#### 4. strokeColor + strokeWidth + strokeAlign → `border`

**来源 Tool**：`getDSL`

```
DSL 原始数据:
  LAYER:
    strokeColor: "paint_0:10"    ← 引用，查 styles
    strokeWidth: "1px"           ← 直接 CSS 值
    strokeAlign: "inside"        ← "inside" | "center" | "outside"

解析:
  strokeColor 查 styles → "#E5E5E5"
  strokeWidth → "1px"
  strokeAlign → "inside" → border-box / "center" → outline / "outside" → box-shadow 模拟

输出 CSS:
  border: 1px solid #E5E5E5;
  box-sizing: border-box;   (对应 strokeAlign: "inside")
```

#### 5. path.data + path.transform → 形状类型判定 + `border-radius`

**来源 Tool**：`getDSL` + `getDesignSvgs`

```
DSL 中:
  PATH:
    path[0].data: ""             ← 常常为空！
    path[0].transform: "matrix(1,0,0,-1,0,130.47)"   ← 有矩阵变换

getDesignSvgs 中:
  svgs["S2:市场解读|0:959"] → "<svg><path d=\"M25,65.235...\"/></svg>"
                              ← 真实的贝塞尔路径在 SVG 里

解析:
  1. 从 getDesignSvgs 取 SVG
  2. 解析 <path d="..."> → 判断形状类型：
     - 圆角矩形 → 提取 rx/ry 作为 border-radius，可以合并
     - 不规则贝塞尔曲线 → 不能简单用 border-radius，可能需要作为 SVG 或不合并
     - 直线 (M...L...) → 线条状，不是背景

  transform 处理:
    matrix(1,0,0,-1,0,130.47) → Y 轴镜像翻转
    → 最终形状是翻转后的，但布局坐标已是翻转后的，CSS 可直接用

输出 CSS（圆角矩形情况）:
  border-radius: 6px;    ← 从 SVG path d= 弧线参数提取
```

#### 6. layoutStyle 坐标差 → `padding`

**来源 Tool**：`getDSL`

```
DSL 原始数据:
  PATH:  x=17, y=42.24, w=128, h=23
  TEXT:  x=25, y=46.24, w=112, h=20

计算:
  padding-top    = TEXT.y - PATH.y = 4
  padding-right  = (PATH.x+PATH.w) - (TEXT.x+TEXT.w) = 145-137 = 8
  padding-bottom = (PATH.y+PATH.h) - (TEXT.y+TEXT.h) = 65.24-66.24 = -1 → 0
  padding-left   = TEXT.x - PATH.x = 8

输出 CSS:
  padding: 4px 8px 0 8px;
```

#### 7. opacity → `opacity`

**来源 Tool**：`getDSL`

直接透传，LAYER/PATH 的透明度合并为 TEXT 所在元素的整体透明度。

---

### 不需要的字段

TEXT 自身的样式（`font`、`textColor`、`textAlign` 等）保持不变，不参与此次合并。

PATH/LAYER 的以下字段在此次合并中**忽略**：

| 字段 | 原因 |
|------|------|
| `name` | 仅用于判定条件，不转为 CSS |
| `id` | 内部标识，不输出 |
| `type` | 仅用于判定是 LAYER 还是 PATH |
| `mask` | 蒙版模式，合并时忽略（背景不需要蒙版） |
| `fillType` | 内部字段，fill 值已表达 |

---

### 完整数据流总览

```
1. getDSL (或 getDesignSections)
   → 遍历节点树，找到所有 PATH/LAYER 与 TEXT 平级对
   → 运行 should_merge_shape_as_text_background() 判定

2. 判定通过后，提取并转换：

   getDSL.styles[paint_XXX]  →  background
   getDSL.styles[effect_XXX] →  box-shadow / filter
   getDSL.borderRadius       →  border-radius   (LAYER 直接取)
   getDesignSvgs[svg_key]    →  path d= 分析 → border-radius (PATH 需推算)
   getDSL.strokeColor        →  border-color
   getDSL.strokeWidth        →  border-width
   getDSL.opacity            →  opacity
   getDSL.layoutStyle 坐标差 →  padding
   getDesignTexts[ref]       →  文字内容 (当 TEXT 为引用时)

3. 将上述 CSS 合并注入 TEXT 节点，删除原 PATH/LAYER 节点
```

---

## 合并策略

```
合并后 TEXT 节点新增属性：
  background      ← LAYER/PATH 的 fill（纯色/渐变）
  borderRadius    ← LAYER 直接取 borderRadius；PATH 从 getDesignSvgs 的 SVG d= 推算
  padding         ← { top: TEXT.y - SHAPE.y, right: (SHAPE.x+SHAPE.w) - (TEXT.x+TEXT.w),
                      bottom: (SHAPE.y+SHAPE.h) - (TEXT.y+TEXT.h), left: TEXT.x - SHAPE.x }
  boxShadow       ← LAYER/PATH 的 effect（阴影）
  border          ← LAYER/PATH 的 strokeColor + strokeWidth
  opacity         ← LAYER/PATH 的 opacity
```

---

## Few-Shot 示例

### 示例 1 — Gradient Overlay（应合并）

```
场景：MasterGo 图层样式 → 渐变叠加，导出后拆成独立 PATH
来源：中信银行 citc，sec=2

输入:
  GROUP: name="左手红利 右手低波"
  ├─ TEXT: name="左手红利 右手低波", content="左手红利 右手低波"
  └─ PATH: name="Gradient Overlay", fill="linear-gradient(...)"

判定:
  ✓ 包含: PATH 贴合 TEXT 轮廓
  ✓ 名称: "Gradient Overlay" 是文字特效产物
  ✓ 尺寸: 贴合文字
  ✓ PATH 在 GROUP 内是 TEXT 的唯一兄弟（非文本节点）

输出: PATH 合并为 TEXT 的文字渐变
  → CSS: background: linear-gradient(...); -webkit-background-clip: text; color: transparent;
```

### 示例 2 — LAYER 矩形 + TEXT（应合并）

```
场景：设计师画了一个圆角矩形，上面叠了文字代码
来源：华夏行业 huaxia-hot-industry，sec=12

输入:
  FRAME: name="编组 20"
  ├─ LAYER: name="矩形", x=0, y=0, w=52, h=20, fill="#F5F7FA", borderRadius=4
  └─ TEXT: name="025209", x=6, y=2, w=40, h=16, content="025209"

判定:
  ✓ 包含: TEXT bounds(6,2→46,18) 在 LAYER bounds(0,0→52,20) 内
  ✓ 名称: "矩形" 无独立语义
  ✓ 尺寸: 52≈40+12 (padding 左6 右6), 20≈16+4 (padding 上2 下2)
  ✓ 居中: 水平偏左=6, 偏右=52-46=6 → 水平居中; 垂直偏上=2, 偏下=20-18=2 → 垂直居中

输出: 合并为 TEXT + background
  → CSS: background: #F5F7FA; border-radius: 4px; padding: 2px 6px;
  → HTML: <span class="tag">025209</span>
```

### 示例 3 — PATH 形状结合 + TEXT（应合并）

```
场景：设计师画了渐变药丸形状，上面叠了标题文字
来源：招商银行 CMB，section-02

输入:
  PATH: name="形状结合", x=17, y=42.24, w=128, h=23,
        fill="linear-gradient(180deg, #FFDA92 12%, #FFF1D4 99%)",
        effect="box-shadow: inset 0px -1px 2px 0px rgba(255,255,255,0.5)"
  TEXT: name="从国内看景气度看", x=25, y=46.24, w=112, h=20,
        content="从国内看景气度看", color="#7B431C"

判定:
  ✓ 包含: TEXT bounds(25,46.24→137,66.24) 在 PATH bounds(17,42.24→145,65.24) 内（容差1px）
  ✓ 名称: "形状结合" 无独立语义
  ✓ 尺寸: 128≈112+16 (padding 左8 右8), 23≈20+3
  ✓ 居中: 水平偏左=25-17=8, 偏右=(17+128)-(25+112)=8 → 水平居中;
          垂直偏上=46.24-42.24=4, 偏下=65.24-66.24≈-1 → 基本居中

输出: 合并为 TEXT + background
  → CSS: background: linear-gradient(180deg, #FFDA92 12%, #FFF1D4 99%);
          box-shadow: inset 0px -1px 2px 0px rgba(255,255,255,0.5);
          padding: 4px 8px; border-radius: 4px; color: #7B431C;
  → HTML: <span class="badge">从国内看景气度看</span>
```

### 示例 4 — 同组多对（批量应合并）

```
场景：招商银行 CMB section-02 中，三组文字各有对应的形状背景
来源：招商银行 CMB，section-02

输入:
  PATH: name="形状结合",       x=17, y=42.24,  w=128, h=23
  TEXT: name="从国内看景气度看",  x=25, y=46.24,  w=112, h=20

  PATH: name="形状结合备份",    x=17, y=140.24, w=104, h=23
  TEXT: name="从政策环境看",     x=25, y=144.24, w=84,  h=20

  PATH: name="形状结合备份 2",  x=17, y=240.24, w=142, h=23
  TEXT: name="从海外市场需求上看", x=25, y=244.24, w=126, h=20

三者横跨 100px 间距，但 PATH-TEXT 配对规律完全一致（左padding 8px，上padding 4px）

输出: 三组全部合并
```

### 示例 5 — 应合并（PATH 作为卡片背景包裹多个元素）

```
场景：一个 PATH 矩形作为背景，包裹了多个 TEXT 和子元素
来源：华夏行业 huaxia-hot-industry，sec=65

输入:
  FRAME: name="编组"
  ├─ PATH: name="形状结合", w=331, h=190, fill="...", borderRadius=...
  ├─ TEXT: name="365亿美元！...", content="365亿美元！半导体设备销售创新高"
  ├─ TEXT: name="SEMI报告显示...", content="SEMI报告显示，2026年Q1..."
  └─ TEXT: name="资料来源：...", content="资料来源：财联社..."

判定:
  ✓ 包含: PATH 的 bounding box 包围全部三个 TEXT
  ✓ 名称: "形状结合" 无独立语义
  ✓ 尺寸: PATH 足够大，作为卡片容器包裹多个元素
  ✓ PATH 是 FRAME 内唯一背景形状

输出: PATH 合并为 FRAME 的背景（或合并为外层容器背景）
  → CSS: background: ...; border-radius: ...;
  → 如果是外层容器则给容器加上背景，如果是 FRAME 内则抽出为独立卡片背景
```

### 示例 6 — 不应合并（PATH 是图标）

```
场景：PATH 是对勾图标，虽然和文字在同一个 FRAME，但是独立语义元素
来源：华夏行业 huaxia-hot-industry，sec=7

输入:
  FRAME: name="编组 55"
  ├─ TEXT: name="捕捉热点事件", content="捕捉热点事件"
  └─ GROUP: name="duigou-3备份"
      └─ PATH: name="形状结合"

判定:
  ✗ 名称: "duigou-3备份" (GROUP名) 表明这是对勾图标
  ✗ 语义: PATH 是对勾的矢量图形，和文字是"图标+标题"关系，不是"背景+文字"

输出: 不合并，PATH 作为独立图标渲染
```

### 示例 7 — 不应合并（PATH 有独立图表语义）

```
场景：PATH 是图表中的柱状图/折线
来源：中信银行 citc，sec=20

输入:
  PATH: name="形状 6", w=..., h=..., 处于图表区域中
  (周围有大量 TEXT 标注数字和年份)

判定:
  ✗ 语义: PATH 是图表的数据图形，有独立信息
  ✗ 不是装饰性背景

输出: 不合并，作为图表的独立图形元素
```

---

## 伪代码

```python
def should_merge_shape_as_text_background(shape, text, tolerance=2):
    """
    shape: LAYER 或 PATH 节点
    text: TEXT 节点
    """
    # 条件 1: 包含关系
    if not (text.x + tolerance >= shape.x
            and text.y + tolerance >= shape.y
            and text.x + text.width - tolerance <= shape.x + shape.width
            and text.y + text.height - tolerance <= shape.y + shape.height):
        return False

    # 条件 2: 名称无独立语义
    generic_names = [
        r'^矩形(备份|拷贝)?(\s*\d+)?$',
        r'^形状结合(备份|拷贝)?(\s*\d+)?$',
        r'^(Gradient|Color)\s*Overlay$',
        r'^蒙版$',
        r'^路径\s*\d*$',
        r'^形状\s*\d*$',
    ]
    if not any(re.match(p, shape.name) for p in generic_names):
        return False

    # 条件 3: 尺寸关联（shape 不会比 text 大太多）
    h_padding = shape.width - text.width
    v_padding = shape.height - text.height
    if h_padding > 30 or v_padding > 20:
        return False

    # 条件 4: 居中对齐
    left_gap = text.x - shape.x
    right_gap = (shape.x + shape.width) - (text.x + text.width)
    top_gap = text.y - shape.y
    bottom_gap = (shape.y + shape.height) - (text.y + text.height)
    if abs(left_gap - right_gap) > 3 or abs(top_gap - bottom_gap) > 3:
        return False

    return True
```

---

## 三类文件中的实际覆盖

| 数据来源 | Gradient Overlay | LAYER 矩形包裹 | PATH 形状包裹 | 总计 |
|----------|:---:|:---:|:---:|:---:|
| 招商银行 CMB (section-02) | 0 | 0 | 3 | 3 |
| 中信银行 CITC | 6 | ~10 | 0 | ~16 |
| 华夏行业 Industry | 0 | ~8 | 5 | ~13 |

全部符合"同一父容器下，形状包围文字，无独立语义"的核心规则，仅名称和节点类型不同。

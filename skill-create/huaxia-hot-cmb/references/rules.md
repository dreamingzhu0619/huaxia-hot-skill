# 规则沉淀

记录实际运行过程中定下的约定与已知局限。

---

## CSS 生成（generate_module_css.py + css_core.py）

### 选择器契约（供 generate_html.py 复用同名 class）

- **模块根节点** → `.m-{序号:02d}-{slug}`，如 `.m-00-banner`。根是定位上下文（`position:relative`）。
- **其余每个节点** → `.n-{id 冒号转横线}`，如 `0:937` → `.n-0-937`。
- HTML 阶段：模块最外层元素挂 `m-{序号}-{slug}`，其余节点挂 `n-{id}`。

### 取值来源

- getDsl 解析值为唯一基底，绝大多数属性从这里算。
- 仅 3 个 getDsl 结构上给不出的属性从同一节点的 `d2cCss` 补（非空时）：
  `mix-blend-mode`、`overflow`、`object-fit`。
- 定位用 getDsl 原生绝对 px：后代 `position:absolute; left=relativeX; top=relativeY`；
  `rotate` → `transform:rotate(Ndeg); transform-origin:0 0`。

### 已知局限（生成时如实输出，不做"漏抓"判断，留人肉眼核对）

- **line-height**：getDsl `lineHeight="-1"`（auto）→ 输出 `normal`；数字才转 px。
  真实行高由设计软件计算，auto 情况下 CSS 拿不到精确值。
- **letter-spacing**：`"auto"` → `normal`。
- **z-index**：getDsl 无显式 z-index，按兄弟顺序（children 下标）注入，近似不保证与设计完全一致。
- **PATH 节点**：`path[].data`/渐变走内联 SVG（`assets.svgs` 或后续 SVG 资源），
  CSS 只出 position/size 盒子，注释标 `PATH→内联SVG`。
- **mask=alpha/outline**：CSS 表达不了，由导出资源实现；注释标 `mask=...`，CSS 只出盒子。
- **object-fit**：对 div + background-image 无效（仅对 `<img>` 生效），此处按 d2cCss 如实带上，
  HTML 阶段若改用 `<img>` 再生效；当前用 `background-size:cover` 达到等价裁切。
- **font.style**：观测值恒为 `"0"`（regular），仅当是合法字重数字（100–900）才输出 `font-weight`。
- **损坏渐变**：`sanitize_gradient` 修 `rgba(...,NaN)`→alpha `1`、`NaN%`→`0%`
  （NaN 目前只出现在 PATH 的 `path[].fill`，node 级 fill 无）。

---

## 渲染阶段（generate_html.py）

### 内联 SVG 渐变必须转成 `<defs>`（否则渐变全丢）

- **坑**：`data/modules/*.json` 的 `assets.svgs` 里所有内联 SVG，都用了 SVG **不支持**的写法
  `<path fill="linear-gradient(...)"/>` / `radial-gradient(...)`。SVG 原生 `fill` 不认 CSS
  渐变函数 → 浏览器渲染时渐变全部失效、形状变透明/无色。这是全站性问题。
- **修复**（渲染层，`data/modules` 原始数据不动）：`render_node` 内联 SVG 前调用
  `css_core.inline_svg_fix_gradients(svg, uid_prefix=节点id)`，把 `fill="...gradient(...)"`
  转成 `<linearGradient>/<radialGradient>` 定义（注入 `<defs>`）+ `fill="url(#id)"`。
- **角度换算**：CSS 0deg 向上、顺时针；SVG objectBoundingBox（y 向下）端点
  `dx=sin(rad); dy=-cos(rad); (x1,y1)=(.5-dx*.5, .5-dy*.5); (x2,y2)=(.5+dx*.5, .5+dy*.5)`。
  path 的 `transform="matrix(1,0,0,-1,...)"`（Y 翻转）**无需处理**——objectBoundingBox
  归一化对翻转不敏感（与 MasterGo D2C 的规范 SVG 输出一致）。
- **id 唯一**：`grad_{节点id下划线}_{段内序号}`，保证多段 SVG 拼进同一 HTML 后不撞。
- radial 简化为 `cx/cy`(来自 `at X% Y%`) + 单 `r=max(rx,ry)`；解析前先 `sanitize_gradient` 清 NaN。

### hasSvg 节点的子节点：局部烘焙，双判据跳过重复渲染

- **坑**：`hasSvg` 的 SVG 是 MasterGo 已把蒙版/渐变/描边烘焙好的最终矢量，其纯图形子节点
  是构成 SVG 的**原始素材**。若内联 SVG 后仍无条件递归渲染子节点，素材会被 CSS 背景/
  阴影**重复画一遍**（如 01 椭圆 `0:956` 的 `#6CE8FF` 蓝块、被蒙版遮住的路径5 露出）。
- **不能简单全跳**：烘焙是**局部**的。很多 `hasSvg` 帧内部嵌有必须保留的 TEXT（04 年份
  文字、06 合规表格），或嵌有独立的图形容器 / 靠 CSS 上色的柱状图（04 `0:1127` 图表、
  柱子）。「无 TEXT 就整支跳」会误删这些内容。
- **正确规则（双判据，缺一不可）**：
  1. **full-bake leaf 帧**：`hasSvg` 节点若 `不含TEXT` 且 `不含嵌套hasSvg` → 其 SVG 已完整
     表达整树 → 跳过全部子孙（`under_baked_leaf` 只在此情况下传）。
  2. **被烘焙的纯图形**：容器帧内，非 TEXT 节点若 `子树无TEXT` 且 `path[0].data 指纹命中
     某祖先 SVG`（`ancestor_svgs` 累积）→ 跳过。
  TEXT 及「子树含 TEXT」的支永不跳。

### PATH 的 CSS 背景兜底：不做

- PATH 视觉归内联 SVG。根因修好后 SVG 正确显示，且被烘焙的 PATH 会被上面双判据跳过渲染；
  若 CSS 再给 `background` 会重影/溢出，且矩形 background 无法还原异形路径。保持 `css_core`
  对 PATH「只出定位盒子」的现状。

### 内联 SVG 必须按 viewBox 原点偏移（否则整段 SVG 错位）

- **坑**：MasterGo 导出的每段 SVG，`viewBox` 起点常常不是 `(0,0)`——它把溢出节点框的装饰
  （左耳朵、发光、超界贴片、甚至整组前景图形）也包进 viewBox，于是 `minX/minY` 变成负数或
  较大正数。渲染时若把 `<svg>` 直接塞进节点 div 的文档流（等于摆在 div 的 0,0），viewBox 里
  的所有图形会整体平移 `(-minX, -minY)`。`minX≈0` 的模块看不出问题，`minX` 大的会明显错位：
  - `n-0-950` 热点前线白卡 `minX=-31` → 白卡右移+被 `.page` 裁 → **看着变窄**；
  - `m-02` 市场解读根 SVG（三个药丸形状）`min=(17,42)` → 药丸左移上移，**没框住那三行小标题**；
  - `m-05` 买基金来招行根 SVG（路径2金色小勾+分隔线）`min=(105,12)` → 金勾跑到按钮左上角，
    被误判成「**颜色不对**」（其实填充色三处数据一致、渐变换算也对，纯粹是位置错了）。
- **判断依据**：`03/07` 的白卡 SVG `viewBox min≈-1`，几乎无偏移，所以从来没出问题；出问题的
  永远是 `viewBox min` 绝对值大的模块。定位这类 bug 先扫全站 SVG 的 `viewBox` 起点。
- **修复**（渲染层，`css_core.position_inline_svg`）：给 `<svg>` 注入
  `position:absolute; left=minX*scale; top=minY*scale`，把 viewBox 坐标 `(X,Y)` 对齐到节点本地
  div 的 `(X,Y)`——与该节点子节点用的坐标系一致。`scale=width属性/viewBox宽`，兜底 width/height
  与 viewBox 尺寸不一致（本数据集恒 1:1）。节点 div 已是 `absolute/relative`，能作定位上下文。
- **正则要吃科学计数法**：viewBox 里会出现 `-6.2172489e-15` 这种带**负指数**的值。解析用的浮点
  正则必须是 `[-+]?(?:\d*\.?\d+)(?:[eE][-+]?\d+)?`；早期用 `[-?\d.eE+]+`（`-` 不在字符类里）会
  在 `e-15` 的第二个 `-` 处断裂，导致整条 viewBox 匹配失败、SVG 静默不加定位。

### 被烘焙进父级 SVG 的「前景图形」层级会塌到底：给内联 SVG 补 z-index

- **坑**：MasterGo 常把「父帧的直接子矢量图形」（02 三个药丸 `0:969/972/975`、05 路径2+分隔线）
  烘焙进**父帧自己**的 SVG。这段 SVG 在 `render_node` 里作为第一个子节点渲染，属静态/文档流层，
  会被后面带 `z-index` 的兄弟（如白卡 `z-index:0`）盖住 → 图形消失或串层。光修位置不够。
- **修复**：只对**非 full-bake-leaf 容器**（含 TEXT 或含嵌套 hasSvg 的帧）计算 z-index：扫它
  被 `_is_baked` 跳过的直接子图形，取它们的**最小子序号**作为该内联 SVG 的 `z-index`
  （02 药丸→3，05 金勾→3）。full-bake-leaf 帧的 SVG 是整体背景，不给 z-index（由节点 div 自身
  层级决定），否则可能把「卡片背景烘焙层」抬到文字之上，**遮住正文**（`n-0-985` 就是这种，
  它的蒙版在子序号 0，用 min 才安全）。
- **已知残留（用 min 的代价，可接受）**：若被烘焙的子图形横跨某个未烘焙兄弟的序号，单一 z-index
  无法完美还原。如 05 分隔线设计序号 5/6/7 高于正文 `z4`，但和金勾一起被压到 `z3`，会落到正文
  **之下**；因分隔线是 0.33px 细线、多在文字间隙，观感影响很小。宁可如此也不用 max（max 会遮正文）。

### LAYER 节点不能随 full-bake leaf 一起跳过（CSS 渲染的视觉不在 SVG 中）

**通用规则：** `hasSvg` 帧在判定 "full-bake leaf"（其 SVG 已完整表达整树，子孙全跳过）时，
必须排除含 LAYER 类型子孙的情况。LAYER 节点的视觉（边框、背景色、阴影、旋转）完全通过 CSS
渲染，MasterGo 导出的 baked SVG **不包含** LAYER 子节点的视觉内容——SVG 里没有对应的
`<rect>` 或 `<path>` 来表达 LAYER 的描边/填充。

**为什么会漏：** 原 `is_leaf` 判据只检查「不含 TEXT」+「不含嵌套 hasSvg」。
LAYER 节点不是 TEXT，也不是 hasSvg，会被误判为「已被 SVG 表达」，随 full-bake leaf
整支跳过，导致 CSS 渲染的矩形/菱形等元素消失。

**识别信号：**
1. 节点 `type == "LAYER"`（区别于 PATH/FRAME/TEXT）
2. LAYER 的视觉来源：`strokeColor`+`strokeWidth`（→ CSS `border`）、`fill`（→ CSS
   `background-color`）、`effect`（→ CSS `box-shadow`）
3. 父帧 `hasSvg=true` 且 baked SVG 中**没有**对应 LAYER 的 `<rect>` 或等效 `<path>`
4. 同级有其他元素（如 PATH 直线）正常显示 → 说明烘培跳过了 LAYER

**处理策略：**
- `is_leaf` 判据增加 `not _subtree_has_layer(node)`：帧的子树含任何 LAYER 节点 → 不作为
  full-bake leaf → 子节点正常渲染
- LAYER 子节点靠 CSS 规则输出视觉（已在 CSS 生成阶段产出），HTML 阶段只渲染空的 `<div>`
  搭配 class，CSS 自动接管边框/背景/阴影
- 同级的 PATH 子节点若 path 指纹命中父 SVG，仍会被 `_is_baked` 跳过（避免双重渲染）

**Bad case —— 模块 03 编组 8 的菱形矩形（`0:993`、`0:995`）：**

```
节点结构（tree.md）：
  0:992 编组 8  type=FRAME  hasSvg=true
  ├─ 0:993 矩形  type=LAYER  strokeColor=#2577E8  strokeWidth=0.7px  rotate=45
  ├─ 0:994 直线  type=PATH   path[0].data=...（渐变横线）
  └─ 0:995 矩形  type=LAYER  fill=#2577E8  rotate=45

修复前：
  is_leaf = True（无TEXT，无嵌套hasSvg）
  → 子孙全跳 → HTML 输出：
    <div class="n-0-992"><svg>...(仅横线)</svg></div>
  → 浏览器：只看到直线，两个菱形矩形"消失"

修复后：
  is_leaf = False（_subtree_has_layer 检测到 LAYER 子孙）
  → 子孙正常渲染 → HTML 输出：
    <div class="n-0-992">
      <svg>...(横线, z=1)</svg>       <!-- PATH 0:994 被 _is_baked 跳过 -->
      <div class="n-0-993"></div>      <!-- LAYER: CSS border 渲染 0.7px 描边菱形 -->
      <div class="n-0-995"></div>      <!-- LAYER: CSS background-color 渲染填充菱形 -->
    </div>
  → 浏览器：直线 + 两个蓝色菱形，与设计稿一致

影响范围：
  模块 03 的 0:992/0:996 两处编组8（共 4 个 LAYER 矩形），模块 04 的 0:1112/0:1116 两处编组8，
  模块 07 的 0:1321/0:1325 两处编组8。全站共 12 个 LAYER 节点受益。
```

### 含蒙版子节点的帧不能作为 full-bake leaf + 需 overflow:hidden 裁剪

**通用规则：** 当 `hasSvg` 帧的直接子节点中存在 `mask="outline"` 或 `mask="alpha"` 的蒙版
节点时，该帧**不能**作为 full-bake leaf 跳过子孙。同时，该帧的 CSS 必须注入
`overflow: hidden`（以及可从蒙版 path 提取的 `border-radius`），用 CSS 裁剪来近似蒙版效果。

**为什么 baked SVG 不能替代蒙版：** MasterGo 的 SVG 导出**不会**把 outline/alpha mask
转成 SVG `<clipPath>`。它只是把蒙版形状和其他子图形平铺成独立的 `<path>`，各画各的。
原本被蒙版裁剪掉的溢出部分（如向左延伸 31px 的装饰曲线）在 SVG 里完整可见。

**为什么 overflow:hidden 能近似：** outline 蒙版的形状通常与父帧尺寸一致（如 355×390
的圆角矩形卡片背景）。蒙版的效果就是"帧内可见、帧外裁剪"。CSS `overflow: hidden`
恰好实现这个语义。若蒙版 path 是圆角矩形，额外提取 `border-radius` 使裁剪边角也匹配。

**识别信号：**
1. 帧的直接子节点中，存在 `mask` 字段为 `"outline"` 或 `"alpha"` 的 PATH 节点
2. 该蒙版 PATH 的尺寸通常与父帧一致（width/height 相同）
3. 该蒙版 PATH 的 `path[0].data` 如果是圆角矩形（`M{R},0 L{W-R},0 C{...}`），
   其 border-radius ≈ R
4. 同级其他 PATH 子节点的 `relativeX`/`relativeY` 可能为负数（溢出帧边界，靠蒙版裁剪）

**处理策略：**
1. **CSS 生成** (`generate_module_css.py`)：遍历到帧节点时调用 `has_mask_child(node)`
   - 检测到蒙版子节点 → CSS 注入 `overflow: hidden`
   - 尝试从蒙版 path 提取圆角 → `border-radius: {R}px`
2. **HTML 渲染** (`generate_html.py`)：`is_leaf` 判据增加 `not _has_mask_child(node)`
   - 含蒙版子节点的帧 → 不是 full-bake leaf → 子节点正常渲染
   - 被子节点中 path 指纹命中父 SVG 的，仍走 `_is_baked` 跳过（避免双重渲染）
   - 不在父 SVG 中的子节点（如 SVG_ELLIPSE）正常渲染

**Bad case —— 模块 02 市场解读的白色卡片（`0:960`）：**

```
节点结构（tree.md）：
  0:960 矩形  type=FRAME  hasSvg=true  width=355  height=390
  ├─ 0:961 蒙版     type=PATH  mask="outline"  （圆角矩形，r≈10px）
  ├─ 0:962 矩形备份 7  type=PATH  （装饰曲线，已烘焙进父 SVG）
  ├─ 0:963 矩形备份 8  type=PATH  relativeX=-31  （装饰曲线，溢出左边界 31px）
  ├─ 0:964 路径 5     type=PATH
  ├─ 0:965 路径 5备份  type=PATH
  └─ 0:966 椭圆形     type=SVG_ELLIPSE

修复前：
  is_leaf = True（无TEXT，无嵌套hasSvg，无LAYER，无蒙版检测）
  → 子孙全跳，只输出 baked SVG
  → CSS 无 overflow:hidden
  → 浏览器：baked SVG 中 0:963 的蓝色曲线完整显示（x=-31 到 x=122），
    没有被蒙版裁剪，左上角保持原始弧形而非直角

修复后：
  is_leaf = False（_has_mask_child 检测到 0:961 蒙版）
  → 子孙正常渲染（0:962/0:963 被 _is_baked 跳过，已在父 SVG 中）
  → CSS 输出 overflow:hidden + border-radius:10.1px（从蒙版 path 提取）
  → 浏览器：父 div 裁剪溢出内容，x<0 的曲线部分被隐藏，左上角呈直角（被圆角框裁剪）

影响范围：
  模块 01 热点前线 0:950 矩形（同结构，蒙版+装饰曲线）
  模块 02 市场解读 0:960 矩形
  全站共 2 处含蒙版子节点的帧受益。
```

### 蒙版圆角提取（`_extract_corner_radius_from_mask_path`）

**通用规则：** outline 蒙版的 `path[0].data` 如果是标准圆角矩形，其 path data 以
`M{R},0 L{W-R},0` 开头（R 为左上角圆角半径，W 为宽度减去 R）。提取 R 作为父帧
CSS `border-radius` 的值，配合 `overflow: hidden` 实现与设计稿一致的圆角裁剪效果。

**提取方法：**
1. 取蒙版节点的 `path[0].data`
2. 正则匹配开头 `M{num},{num}` — 第一个数字为 X 坐标，第二个为 Y 坐标
3. 若 Y≈0 且 X>0 → X 即为左上角圆角半径 → 输出 `{X}px`
4. 其他情况（非圆角矩形蒙版）返回 None，仅靠 `overflow:hidden` 做矩形裁剪

**已知局限：** 只处理简单圆角矩形蒙版（四角等半径）。异形蒙版、多半径蒙版不提取
border-radius，仅靠 overflow:hidden 做矩形裁剪（边框处可能不够精确，但溢出部分
已被裁剪）。

---

## 文本渲染

### 单行文本要 `white-space:nowrap`，防字体回退挤换行

- **坑**：设计里单行的文本（如产品全称「华夏中证电网设备主题ETF发起式联接C」，框宽 294px、
  17px 字），浏览器缺 `FZLTZHJW--GB1` 回退到更宽字体后，整行宽度超过设计框，末尾字符（那个
  「C」）被挤到第二行。getDsl 里**没有**「自动宽度/单行」这类标记可直接用。
- **修复**（`css_core.font_to_css`）：用启发式判定单行——设计框高 `height <= 行高单位×1.6` 时
  输出 `white-space:nowrap`。行高单位取数字 `line-height`（px），`normal/auto` 时按 CJK 经验
  `字号×1.4`。阈值 1.6 落在「单行(~1.0–1.5)」与「两行(~2.0)」之间，实测不会误伤多行段落
  （已加校验：所有 nowrap 命中项的 高/行高比 均 ≤1.6）。
- **权衡**：这是全局启发式，好处是顺带防住其它单行文本被挤换行；极少数「矮框但本意想换行」
  的文本会被误判成不换行（本项目未出现）。

### 白色下移阴影「反客为主」是缺字体的观感问题，不是数据 bug（`text-shadow` 依赖重黑字体）

- **现象**：banner 标题（0:936/0:937 橘色、相关产品 0:1329 蓝色）等带
  `text-shadow: 0px 1px 0px #FFFFFF` 的字，在本机浏览器里看着**白色比橘/蓝主体还多**，
  跟设计稿相反（设计稿里白色只是笔画底部一丝白边）。
- **根因：缺字体，不是提取/生成错。** 逐字比对 `07-getD2c`（MasterGo 自己的权威 design-to-code）：
  我们的 CSS 与它**完全一致**——同样 `font-family: FZZDHJW--GB1` + `text-shadow: 0px 1px 0px #FFFFFF`，
  getD2c **也没有 font-weight、也没有 @font-face/字体 URL**；raw / getD2c / getMeta 全站**无任何字体文件资源**
  （woff/ttf/otf 一个都没有）。`FZZDHJW--GB1` 是方正一款**重黑显示体**，字重来自字体文件本身
  （"regular/style=0" 在重黑体里也很粗）。本机没装 → 回退成细体。
- **为什么缺字体会让白色占大头（机理）**：
  - 橘/蓝色 = **字的笔画本身**（`background-clip:text` 把渐变填进字形），粗细**跟字体走**。
  - 白色 = `text-shadow` 把整个字形复制一份填纯白、**往下挪固定 1px**垫在字后面，位移量**跟字体无关**。
  - 白色露出的永远只是「橘色盖不住的那 1px 底边」。装重黑体时笔画 4~5px 粗，1px 白只是压边细线；
    回退成细体后笔画只剩 1~1.5px，那**固定的 1px 白边**就跟笔画差不多宽，加上纯 #FFF 垫在蓝底上对比极强 → 白色抢戏成主体。
  - 一句话：**白阴影粗细固定 1px，彩色主体粗细随字体变；字体越细，固定白边越抢戏，比例就反过来。**
- **判定 & 处理**：这是**渲染环境**问题，不是数据/管线 bug，`css_core` 不改（改了反而偏离 getD2c）。
  - 若目标环境（如 Open Design / 手机 webview）装了 MasterGo 字体 → 现状直接可用。
  - 若目标环境也缺字 → 属"渲染环境适配"，再考虑 `@font-face` 内嵌真字体（最忠实，但需拿到字体文件/授权，
    raw 里没有该 URL），或退而求其次给重黑字体补 `font-weight`/加粗降级字体栈（CSS-only 近似）。
    这类适配等在目标环境实测缺字后再落地，与数据抓取正确性无关。
- **排查提示**：遇到「颜色/阴影观感不对」先分清是数据错还是缺字——比 `07-getD2c`，若我们的 CSS 与它一致，
  且该字用了非常见中文字体（FZ 开头的方正字体等），基本就是缺字体，别去动 css_core。

### 多词合并文本检测与拆分

**通用规则：** MasterGo 导出时，经常把设计稿里多个独立 TEXT 图层合并成一个 TEXT 节点，
中间只用空白字符隔开。遇到这种数据，不能当普通文本直接渲染——必须拆回多个独立元素，
各自定位，否则位置会和旁边的分隔线/图标对不上。

**识别信号（满足越多越可能是合并文本）：**

1. `textMode == "single-line"` —— 单行文本
2. 文本内容可用 `\s{2,}` 拆出 2–6 个词段
3. 同级存在窄高 PATH 节点（竖线分隔符），且它们的 X 坐标落在文本横向范围内
4. `textColor` 数组呈现重复的颜色模式，每段对应一个词（侧面印证原本是分开的图层）
5. 文本不含 `\n`（排除正常多行段落）

**处理策略（✅ 已实现于 `generate_html.py` `_merged_text_column_centers`）：**

- 按 `\s{2,}` 拆分文本，得到独立词段；每段渲染为一个 `position:absolute` 的 span
- **用兄弟竖线分隔符的真实 `relativeX` 算列中心**：取落在文本横向范围内的窄高 PATH
  （宽<2px 且 高>宽×3）作为列边界，把 `[文本左, 文本右]` 切成 N 段，各段中心（相对文本框宽的 %）
  即为该词 span 的 `left`。**只有竖线数量恰为 词数-1 时才拆**；不匹配则**保持原文本不拆**
  （不再用等分占位近似——宁可不拆也不猜位置）。
- override（user-input 提供的文本）也走同一拆分：override 是同一合并串，不能因有 override 就跳过拆分
  （否则 HTML `white-space:normal` 把多空格塌成单空格，四词挤到左边、既不居中也对不上竖线）。
- 父 div 保留 font-family/size/color 等 CSS（自动级联到 span）
- 若文本含 `\n` → 不拆（是正常多行段落，不是合并文本）
- 竖线本身通常已被父帧 baked SVG 表达（如 05 的 0:1208），在真实位置渲染，无需单独出 div。

**Few-shot 示例 —— 模块 05「买基金来招行」：**

```
输入数据（getDsl）：
  节点 0:1252  TEXT  textMode="single-line"
  text = "费率低      品类全      策略优      服务好"
  bounds = { x:43, width:273 }（父帧 0:1208 坐标系；词区间 [43, 316]）
  textColor 数组含 13 段逐字颜色（重复模式：2字棕→1字红→空格→4空格→1空格→...）
  
同级 PATH 竖线（父帧 0:1208 坐标系，已 baked 进 0:1208 SVG）：
  0:1254  relativeX=105.41  width=0.33  height=16  （竖线1）
  0:1253  relativeX=178.07  width=0.33  height=16  （竖线2）
  0:1255  relativeX=252.07  width=0.33  height=16  （竖线3）

判断：
  ✓ textMode=single-line ✓ 无 \n ✓ \s{2,} 拆出 4 段 ✓ 3 个窄高 PATH 在文本 X 范围内
  ✓ 竖线数(3) == 词数(4)-1 → 用真实竖线位置拆分

处理（用真实竖线位置，非等分）：
  列边界(文本本地坐标 = relativeX - 43)：[0, 62.41, 135.07, 209.07, 273]
  列中心 = 相邻边界中点 / 273：
    列1 → 11.46% "费率低"   列2 → 36.23% "品类全"
    列3 → 63.09% "策略优"   列4 → 88.32% "服务好"
  每词: <span style="position:absolute;left:XX%;top:0;
          transform:translateX(-50%);white-space:nowrap;text-align:center">词</span>
  → 每词居中于真实竖线定义的列，竖线正好落在相邻两词之间（对齐设计稿）。

排查经验：症状是"四词挤左、不居中、竖线看着没在两词中间"。根因不是竖线没渲染（竖线一直
在 baked SVG 里的真实位置显示），而是①文本走了 override 分支没拆分 ②HTML 把多空格塌成单空格。
两问题同源，用真实竖线位置拆分后一并解决。
```

---

## SVG 渲染

### 表格边框 SVG 的 path 双 subpath 同向 → 实心矩形遮挡内容

**通用规则：** MasterGo 导出的表格边框 SVG，经常用一条 path 绘制外框+内框两个矩形来形成
边框效果。但两个子路径的绘制方向可能相同——SVG 默认 `fill-rule="nonzero"` 下同向子路径
不会形成镂空，导致整个矩形被实心填充，遮住表格里所有文字和线条。

**识别信号：**

1. `<path>` 的 `d` 属性包含恰好 2 个子路径（以 `M` 开头，`Z` 结尾）
2. 有 `fill` 属性且值为实色（非 `none`、非 `url(#)`、非 `gradient`、非白色透明）
3. 两个子路径的坐标走向相同（同顺时针或同逆时针）→ `nonzero` 下无镂空
4. 多出现在表格/列表容器的 `assets.svgs` 中

**处理策略：**

- 渲染层在 `inline_svg_fix_gradients` 之后调用 `fix_svg_frame_fill`
- 检测 2 子路径 + 实色 fill 的 path → 添加 `fill-rule="evenodd"`
- evenodd 下内框和外框的奇偶性不同 → 仅边框被填充，内部留空
- 单子路径、渐变填充（已转 `url(#)`）、透明/白色 fill 均跳过（不改动）

**Few-shot 示例 —— 模块 06 合规表格三（`2:849`）：**

```
输入数据（assets.svgs["2:849"]）：
  <path d="M-0.5,-0.5 L-0.5,70.5 L355.5,70.5 L355.5,-0.5 Z
           M0,0 L0,70 L355,70 L355,0 Z"
        fill="#81B8EB"/>

子路径分析：
  外框: (-0.5,-0.5)→(-0.5,70.5)→(355.5,70.5)→(355.5,-0.5)→闭合
        走向: 左上→左下→右下→右上 = 顺时针 ✓
  内框: (0,0)→(0,70)→(355,70)→(355,0)→闭合
        走向: 左上→左下→右下→右上 = 顺时针 ✓
  → 两者同向，nonzero 规则下整个矩形被 #81B8EB 填满

修复后：
  <path fill-rule="evenodd" d="M-0.5,-0.5 ... Z M0,0 ... Z" fill="#81B8EB"/>
  → evenodd 下仅边框区域被填充，内部文字可见

影响范围：
  本页面共 4 个表格（表格一/二/三/四），全部命中此规则，共修复 15 处。
```

---

## CSS 生成（css_core.py）

### rotate=180 的 Frame 必须用 `transform-origin: center`，不能用 `0 0`

**通用规则：** 当 FRAME 节点有 `rotate=180`（或任意 180° 的奇数倍），CSS 的
`transform-origin` 必须设为 `center`。`transform-origin: 0 0` 会使元素绕自身
左上角旋转 180°，导致视觉位置偏移 `(-width, -height)`——装饰元素会被移到完全
错误的位置（如从标题右侧偏移到标题内部）。

**为什么 `0 0` 对 45° 菱形可以、对 180° 对称装饰不行：**
- 45° 旋转的菱形（如编组8 里的 7×7 方块）：绕左上角旋转相当于绕角翻转，菱形
  的中心点偏移量很小（≈3px），视觉效果可接受。
- 180° 旋转的装饰帧（如标题两侧的对称编组8）：帧实际宽 55–92px。绕左上角旋转
  后整个元素往左上方偏移一个帧宽/帧高，从"标题右侧"跑到了"标题内部"甚至左侧。
- `transform-origin: center` 让元素绕自身中心旋转 180°（等价于原地镜像翻转），
  不改变元素在父级中的视觉位置。

**如何判断（在 css_core.py 中）：**
```
abs(rot) % 180 == 0 and abs(rot) % 360 != 0  →  transform-origin: center
其他 rot 值                                    →  transform-origin: 0 0
```

**Bad case —— 模块 03 推荐理由A 的右侧编组8（0:996）：**

```
节点数据：
  0:996  type=FRAME  rotate=180
  relativeX=257  width=55.45  height=9.9

修复前 CSS：
  .n-0-996 {
    left: 257px;              /* 元素锚点在 (257, 12.24) */
    transform: rotate(180deg);
    transform-origin: 0 0;    /* 绕左上角旋转 → 视觉位置偏移到 (201.55, 2.34) */
  }
  → 装饰线出现在标题"电网设备：外部需求激增"(left=16,width=281) 的内部区域，
    而非标题右侧。与左侧编组8（left=0,无旋转）完全不对称。

修复后 CSS：
  .n-0-996 {
    left: 257px;
    transform: rotate(180deg);
    transform-origin: center;  /* 绕自身中心旋转 → 视觉位置保持在 (257, 12.24) */
  }
  → 装饰线出现在标题右侧 (257–312)，与左侧编组8 (0–55) 形成对称。
```

**影响范围：** 全站 3 处 180° 旋转的编组8（模块 03/04/07 各一处），及 `<rect>`
等 rotate=180 的元素。非 180° 倍数的旋转（如 45° 菱形）行为不变。

---

## 文本渲染（generate_html.py）

### 多行 TEXT 的 `\n` 必须转为 `<br>`，否则 HTML 会合并成一行

**通用规则：** MasterGo 导出的 TEXT 节点中，`\n` 表示设计稿里的手动换行（如
表格第三列三行文本："基金管理人和销售机构\n基金托管人\n销售机构"）。HTML
的默认 `white-space: normal` 会把源码中的 `\n` 折叠成空格，导致三行文本被
浏览器渲染成一行，再被容器宽度强制断行，造成行序错乱/内容溢出/末尾行消失。

**识别信号：** TEXT 节点 `text` 字段包含 `\n` 字符。

**处理策略：** 在 `render_text_inner` 中，`html.escape()` 之后将 `\n` 全局
替换为 `<br>`。单 `<br>` 在行内元素中即可产生换行，不影响 CSS 的
`text-align`/`line-height` 等属性。

**Bad case —— 模块 06 合规提示表格四的收取方列（0:1266）：**

```
节点数据：
  0:1266  type=TEXT  text="基金管理人和销售机构\n基金托管人\n销售机构"
  width=90  height=49  line-height=16.2

修复前 HTML：
  <div class="n-0-1266">基金管理人和销售机构
  基金托管人
  销售机构</div>
  → 浏览器渲染结果：单行文本 "基金管理人和销售机构 基金托管人 销售机构"
    （\n 被折叠为空格）
  → 单行约 20 个 CJK 字符 ≈ 180px，在 90px 宽的 div 内强制换行为 2 行
  → "销售机构" 可能被挤到第 3 行，超出 49px 高度 → 被裁剪/不可见

修复后 HTML：
  <div class="n-0-1266">基金管理人和销售机构<br>基金托管人<br>销售机构</div>
  → 浏览器渲染结果：精确三行，行高 16.2×3=48.6 < 49，全部可见
```

**影响范围：** 全站所有含 `\n` 的 TEXT 节点（表格多行文本、图例等），共约 6 处。

---

## SVG 渲染（css_core.py）

### 细线 SVG path（<1px）必须加 `shape-rendering="crispEdges"`，否则抗锯齿使其不可见

**通用规则：** MasterGo 导出的表格边框/分隔线 SVG，常通过 matrix 旋转把
水平矩形 path（高 0.5px）转成竖线（宽 0.5px）。浏览器默认 `shape-rendering="auto"`
会对 0.5px 宽的填充路径做抗锯齿，把 #81B8EB 这样的浅色渲染成半透明，
在白色背景上几乎不可见（人眼看着就像"线丢了"）。

**识别信号：** SVG 内 path 的包围盒宽度或高度 < 1px（通常 0.5px），且使用
`fill` 而非 `stroke` 绘制线条。

**处理策略：** 渲染层在所有内联 SVG 的 `<svg>` 根标签上注入
`shape-rendering="crispEdges"`。此属性关闭抗锯齿，使细线吸附到最近整像素
（0.5px → 1px），保证最小可见线宽。本项目 SVGs 以矩形/直线为主，crispEdges
对少量曲线的观感影响可忽略。

**Bad case —— 模块 06 合规提示表格二的竖线分隔符（0:1310）：**

```
节点数据：
  0:1310  type=PATH  name="路径 12备份 9"
  path[0].data = "M93.7148...,0.5346...L180.9553...,0.5346...L180.9553...,1.0346...
                  L93.7148...,1.0346...Z"
  path[0].transform = "matrix(6.12e-17,1,-1,6.12e-17,94.0,-93.43)"
  → 这是一个 87.24×0.5px 的水平矩形，经 matrix(≈rotate 90°) 旋转为 0.5×87.24px 的竖线。
  → 该 path 被 _is_baked 判定命中祖先 SVG → 跳过单独渲染，仅存在于父级 SVG 中。

修复前（父级 SVG）：
  <svg viewBox="-0.43 -0.5 356 89" width="356" height="89">  <!-- 无 shape-rendering -->
    <path ... fill="#81B8EB" transform="matrix(...)"/>
  </svg>
  → 浏览器对 0.5px 填色抗锯齿 → #81B8EB 浅蓝渲染成 ≈#C0DCF5 半透明 → 在白底上极淡
  → 用户观察：表格二的竖线分隔符"没有正确展示"

修复后（父级 SVG）：
  <svg ... shape-rendering="crispEdges">                      <!-- 关闭抗锯齿 -->
    <path ... fill="#81B8EB" transform="matrix(...)"/>
  </svg>
  → 0.5px 路径吸附到 1px 整像素 → 颜色保持 #81B8EB → 清晰可见
```

**影响范围：** 全站所有内联 SVG（表格、装饰线、图标等），共约 30 处。对非表格
SVG（如手形图标、按钮渐变）的观感影响微小。

---

## 数据流失修复

以下三条规则记录 pipeline 中数据流失的根因与修复位置，防止同类问题重现。

### 1. `SVG_ELLIPSE` 必须输出 `border-radius: 50%` — `css_core.py`

- **丢在哪里**：`css_core.py:node_to_css()` line 313，只检查 `node.get("borderRadius")`，
  SVG_ELLIPSE 节点的 `borderRadius` 为 null → 不输出 border-radius → 椭圆变正方形。
- **修复**：`elif node.get("type") == "SVG_ELLIPSE": css["border-radius"] = "50%"`
- **影响**：全站 4 处（01/02/07 模块各 1-2 个椭圆）

### 2. PATH 的 `fill` 在 `split_modules.py` 中被丢弃 — 需从 `path[0].fill` 提升到 `node.fill`

- **丢在哪里**：`split_modules.py:resolve_node()` line 575 取 `node.get("fill")`。
  PATH 节点的 fill 写在 `path[0].fill`（如 `paint_0:763 → #FF8F4F`），
  `node.fill` 为 null → `fill_val = null` → CSS 不输出 `background-color`。
- **修复**：`path_resolved` 构建完后，若 `fill_val is None`，从 `path_resolved[0].fill` 提升。
- **影响**：所有带 fill 的 PATH 子节点（其 CSS div 原来只有 filter 没有背景色）

### 3. PATH 的 `effect(filter:blur)` 在内联 SVG 中丢失 — `css_core.py` + `generate_html.py`

- **丢在哪里**：`css_core.py:inline_svg_fix_gradients()` 只把 CSS `linear-gradient()`
  转成 SVG `<linearGradient>`，完全不处理 effect。PATH 子节点的 `filter: blur(Npx)`
  在 CSS 层正确输出（`effect_to_css`），但 CSS 只作用于空 div；内联 SVG 的 `<path>`
  没有对应的 SVG `<filter>` → 硬边形状覆盖下层元素。
- **修复**（两处）：
  - `css_core.py`：新增 `inject_svg_filters(svg_text, parent_node)` —— 扫描 hasSvg
    帧的子节点，对带 blur 效果的 PATH 子节点生成 `<filter id="blur_{id}">` +
    `<feGaussianBlur>`，注入 `<defs>`，并在对应索引的 `<path>` 上添加
    `filter="url(#blur_{id})"`。子节点→SVG path 索引映射：mask 子节点占 2 个 path，
    非 mask PATH 子节点占 1 个 path。
  - `generate_html.py`：在 `render_node()` 的 SVG 后处理链中（渐变→边框→细线修复之后）
    调用 `css_core.inject_svg_filters(fixed, node)`。
- **影响**：模块 07 两个按钮的 4 个带 blur 的 PATH（椭圆形备份3×2 + 矩形备份9×2），
  以及未来所有带 effect 的 PATH 子节点被烘焙进内联 SVG 的场景。

### 4. `rotateX` 在 CSS transform 中被丢弃 — `css_core.py`

- **丢在哪里**：`css_core.py:node_to_css()` line 290，只读 `layout.get("rotate")`，
  完全忽略 `layout.get("rotateX")`。MasterGo 导出中 `rotateX` 表示绕 X 轴的 3D 翻转
  （如 `rotateX=180` = 垂直镜像），不与 2D `rotate` 等价。
- **修复**：`rot_x = layout.get("rotateX") or 0`，若非零则追加 `rotateX(Ndeg)` 到
  `transform` 值中。transform-origin 判定仍以 2D `rotate` 为准。
- **影响**：全站 4 处（banner 1 个 LAYER 位图 `0:1317` rotate=90/rotateX=180；
  编组8 装饰 `0:996/0:1116/0:1325` rotate=180/rotateX=180）。编组8 因对称性视觉不变，
  位图节点 flip 方向现在与设计一致。

### 5. 多值 fill（多层填充叠加）的层序 — `css_core.py`

- **原始问题**：`fill_to_css()` 早期对 fill 数组只取 `fill[0]`，其余层（渐变叠加、
  纹理等）全部丢弃。抽取 `_single_fill_to_css()` 处理单层后，改为遍历全部层拼接
  逗号分隔的 `background-image`。
- **层序订正（重要）**：早期实现假设 MasterGo fill 数组是 `[底→顶]`，于是**倒序**
  拼接。经 raw getDsl 核对 + 用户确认，实际是 **`[顶→底]`**（index 0 = 最上层），
  与 CSS `background-image`（第一项=顶层）**同序**。故**不再倒序**，按数组原序拼接；
  多值中最底层纯色仍走 `background-color`（迭代到底、取最后一个纯色）。
- **为什么早期倒序是 bug**：产品卡 `0:1369` fill=`[蓝白渐变, 暖白渐变]`（蓝白在上）。
  倒序后暖白（近白、不透明）排到最上层盖住蓝白 → 卡片错误地显**偏黄**；用户实际
  期望是"从上到下 淡蓝→白"（即蓝白层在上）。去掉 `reversed()` 后蓝白回到顶层，正确。
- **排查依据**：raw `paint_0:738.value` 与 modules `fill` 均为 `[蓝白, 暖白]`（顶→底），
  唯独早期 CSS 输出成 `[暖白, 蓝白]` → 定位到 `fill_to_css` 的倒序。
- **影响**：全站仅 2 个多层 fill 节点（`0:952` 角标 `paint_0:130`、`0:1369` 产品卡
  `paint_0:738`）。`0:952` 两层皆蓝、层序无关观感；`0:1369` 修复后显蓝白（对）。
  （另需配合规则 #6，让该 PATH 节点的 CSS div 真正被渲染。）

### 6. 含多值 fill 的 PATH 节点被 `_is_baked` 跳过，CSS 多层渐变永不生效 — `generate_html.py`

- **丢在哪里**：`generate_html.py:render_node()` 的判据②，当 PATH 节点的 path 指纹
  命中祖先 baked SVG 时，`_is_baked` 返回 True → 整个节点跳过 → CSS（含正确的多层
  `background-image`）不生效。**CSS 输出正确但 HTML 中从未被渲染。**

- **为什么会丢**：MasterGo 导出的 **baked SVG 对每个 `<path>` 只保留 fill 数组的
  最后一个值**。例如 `path[0].fill = ["gradA", "gradB"]` → baked SVG 中对应 `<path>`
  的 `fill` 只写 `"gradB"`，"gradA" 那一层完全丢失。
  
  此时若 `_is_baked` 仍然跳过该节点（因为 path 指纹确实命中了祖先 SVG），视觉就只剩
  baked SVG 里残缺的单层——多值中的其他渐变/颜色层全部缺失，底层元素（如蒙版背景色）
  透上来，导致颜色"不对"。

- **识别信号**：
  1. 节点 `type == "PATH"`，且某条 `path[].fill` 是一个 list（length ≥ 2）
  2. 该节点是某个 `hasSvg` 帧的子孙
  3. CSS 中该节点的规则有正确的多层 `background-image`
  4. 但浏览器中 HTML 没有该节点的 `<div>` → CSS 从未被应用

- **排查方法（三步法）**：
  1. **Raw 数据**：`data/raw/01-getDsl/getDsl.json` 中查节点，看 `path[].fill` 解析
     paint 引用后是否为多值数组（≥2 层）
  2. **Modules JSON**：`data/modules/*.json` 中查节点，`fill` 字段是否保留了多值数组
  3. **CSS**：`assets/styles/modules/*.css` 中该节点的规则是否有逗号分隔的多层
     `background-image`（说明 `fill_to_css` 已正确处理）
  4. **HTML**：`output/fund-h5/index.html` 中搜索 `class="n-{节点id}"` 是否存在
     ——若只在 CSS 有但 HTML 无 → 被 `_is_baked` 跳过

- **处理策略**：
  - 新增 `_has_multi_value_fill(node)` ：只检查原始 `path[].fill` 是否为数组
    （不检查 `node.fill`，因其可能由多 path 合并为数组，不代表 baked SVG 数据丢失）
  - 在 `render_node()` 的判据②中增加 `and not _has_multi_value_fill(node)`：
    有多值 fill → 不跳过 → 渲染 CSS `<div>`（其多层 `background-image` 覆盖 baked SVG
    的残缺单层）
  - CSS div 的 `position:absolute` 定位与 baked SVG 的 path 完全重叠，z-index 由
    原有 CSS 规则控制（与跳过前一致）

- **Bad case —— 模块 07 产品卡的矩形（`0:1369`）**

  ```
  节点数据（modules JSON）：
    0:1369 矩形  type=PATH
    fill = ["linear-gradient(359deg, #FFFFFF 1%, #F0F8FF 98%)",    ← 多值 fill: 2 层
            "linear-gradient(0deg, #FFFCF4 0%, #FFFAEF 100%)"]
    path[0].fill = 同上（2 层）
    path[1].fill = ["#C7E5FF",                                      ← 多值 fill: 2 层
                    "linear-gradient(180deg, #BDE3FF 0%, rgba(255,255,255,0) 100%)"]
    父节点: 0:1368 产品卡  hasSvg=True

  Baked SVG（assets.svgs["0:1368"]）只有单值：
    <path fill="linear-gradient(0deg, #FFFCF4 0%, #FFFAEF 100%)"/>  ← 丢了 #FFFFFF→#F0F8FF
    <path fill="#C7E5FF"/>                                          ← 丢了 BDE3FF 渐变

  修复前 CSS（层序已按规则 #5 订正为顶→底；此前因 `_is_baked` 未被应用）：
    .n-0-1369 {
      background-image: linear-gradient(359deg, #FFFFFF 1%, #F0F8FF 98%),   ← 顶层: 蓝白
                        linear-gradient(0deg, #FFFCF4 0%, #FFFAEF 100%);     ← 底层: 暖白
    }
    → HTML 中无 <div class="n-0-1369"> → CSS 从未生效

  修复前浏览器渲染：
    → baked SVG 只画了奶油渐变 + 纯蓝边框
    → 缺少的白色-淡蓝渐变层使得底下蒙版（0:1330，蓝色渐变）透上来
    → 用户看到"蒙版的颜色"而非矩形自己的颜色

  修复后：
    _has_multi_value_fill(0:1369) = True（path[0].fill 是 2 层数组）
    → _is_baked 不跳过
    → HTML: <svg>...</svg><div class="n-0-1369"></div>
    → CSS div（z-index:0, 321×171px）用正确的双层渐变覆盖 baked SVG 残缺层
    → 产品卡背景显示：顶层白色-淡蓝渐变（从上到下 淡蓝→白）+ 底层暖白（与设计稿一致）
  ```

- **影响范围**：全站 2 个节点（`0:952` 矩形备份7、`0:1369` 产品卡矩形），
  分布在模块 01 和 07。修复后这两处的多层渐变不再丢失。

### 8. CSS 渐变的越界色标（负 / 超 100% offset）转 SVG 后被浏览器错误夹紧 — `css_core.py`

- **通用规则**：CSS 渐变允许 `-10%` / `110%` 这类越界色标，语义是"沿渐变线插值"。
  但 SVG `<stop offset>` 只接受 `[0,1]`，浏览器对越界值**直接夹紧且保留端点的
  颜色/透明度**——与 CSS 的插值语义不符。转 SVG 前必须把越界色标按线性插值
  重算回 `[0%,100%]`。
- **丢在哪里**：`css_core.inline_svg_fix_gradients` → `_gradient_to_def` → `_parse_stops`
  直接把 CSS 色标位置原样写进 `<stop offset>`。遇到 `#FFFFFF -10%` 就输出
  `<stop offset="-10%" stop-opacity="1">`，浏览器夹成 `0%` 且仍满白 → 高光偏白偏硬。
- **修复**：新增 `_normalize_stops_range(stops)`，在 `_gradient_to_def` 生成
  `<stop>` 前调用（linear/radial 两分支都接入）：把 `<0%` / `>100%` 的色标按相邻
  色标线性插值出 `0%` / `100%` 处的颜色+透明度，替换越界项。
- **识别信号**：output 里 `<stop offset="-N%"...>`（负 offset）；raw / modules / 生成的
  module CSS 里该渐变值都正确，唯独最终烘焙 SVG 的 stop offset 越界。
- **Bad case —— 模块 07 CTA 按钮高光矩形（`0:1363`，路径：相关产品→按钮2备份→
  编组3→矩形+矩形蒙版→矩形）**：

  ```
  raw paint_0:779 / modules fill / module CSS 均为：
    linear-gradient(180deg, #FFFFFF -10%, rgba(255,255,255,0) 56%)   ← 正确

  修复前（output 烘焙 SVG，0:1363 走 SVG 不走 div）：
    <linearGradient id="grad_0_1349_4" x1="0.5" y1="0" x2="0.5" y2="1">
      <stop offset="-10%" stop-color="#FFFFFF" stop-opacity="1"/>    ← 负 offset
      <stop offset="56%"  stop-color="rgb(255,255,255)" stop-opacity="0"/>
    </linearGradient>
    → 浏览器夹 -10%→0% 且保留 opacity=1 → 按钮顶部满白偏硬（应为插值后 ≈0.85）

  修复后：
    <stop offset="0%"  stop-color="rgb(255,255,255)" stop-opacity="0.8485"/>  ← 插值
    <stop offset="56%" stop-color="rgb(255,255,255)" stop-opacity="0"/>
    → 高光柔和，与设计稿一致
  ```

- **影响范围**：全页 4 个负 offset stop（两个 CTA 按钮高光 `0:1362/-9%`、`0:1363/-10%`，
  大小按钮各一组 `0:1377/0:1378`）。对任意设计稿的越界色标通用。

### 7. 多 path 节点的 fill 只提升 path[0] — `split_modules.py`

- **通用规则**：PATH 节点的 `fill` 信息通常写在 `path[].fill` 而非 `node.fill`。
  `split_modules.py` 将 `path[0].fill` 提升到 `node.fill` 供 CSS 生成使用。
  对于有多条 path 的节点（如蒙版：path[0]=外层轮廓、path[1]=内层轮廓），
  **只提升 path[0]**（主体形状的 fill）。后续 path[1+] 的 fill（内层描边/叠加）
  由 baked SVG 表达——CSS 无法用单一矩形 `<div>` 还原多条 path 的不同几何形状。

- **为什么不合并所有 path fill**：path[0] 和 path[1] 是不同的几何轮廓。
  将两者的 fill 合并到 `node.fill` 数组，CSS `background-image` 会把所有层
  叠加到同一个矩形 div 上，导致"内层颜色盖住外层"或"边框渐变混入背景"。
  path[1] 的视觉交给 baked SVG 处理更准确。

- **Bad case —— 模块 07 的蒙版（`0:1350`）**：

  ```
  节点数据：
    0:1350 蒙版  type=PATH  mask=outline
    path[0].fill = "linear-gradient(90deg, #FF5B00 17%, #F13816 85%)"   ← 外层: 橙红渐变
    path[1].fill = "linear-gradient(121deg, #FFFCF6 17%, #FFF0CF 84%)"   ← 内层: 奶油渐变

  正确行为：
    node.fill = path[0].fill = "linear-gradient(90deg, #FF5B00 17%, #F13816 85%)"
    → CSS 只输出外层橙红渐变（作为主体色近似）
    → 完整的双层渐变 + 内外轮廓由 baked SVG 渲染

  若错误合并所有 path fill：
    node.fill = ["橙红渐变", "奶油渐变"]
    → CSS 输出双层 background-image
    → 奶油渐变在顶层覆盖整个 div → div 变成纯奶油色
    → 且 div 被渲染后可能遮盖 baked SVG 的模糊效果（0:1355/0:1358 的 blur）
  ```

### 9. `assets.svgs` 透传 extractSvg 的非法渐变 fill，坏 SVG 落进 `data/modules` — `split_modules.py`

- **根因**：`05-extractSvg` 导出的内联 SVG，其 `<path>` 的 `fill` 常是 **CSS 渐变串**
  `fill="linear-gradient(123deg, #FEFBF5 11%, ...)"`（radial 还可能带 `NaN`，如手 `0:1384`
  的指尖）。这是**非法 SVG**（SVG 只认 `fill="url(#id)"` + `<linearGradient>` def），浏览器不渲染。
  此前 `split_modules.py` 把 extractSvg 的 svg 串**原样透传**进 `data/modules` 的 `assets.svgs`，
  只有 `generate_html.py` 渲染阶段才用 `inline_svg_fix_gradients` 修 → **最终 H5 是好的，但
  `data/modules` 里存的是坏 SVG**。任何直接读 modules 的下游（如 Open Design skill）都会拿到非法图形。

- **判定**：这不是"数据缺陷"。同一份渐变/几何数据在 raw 里**存在且有合法版**——`01-getDsl` 节点
  `fill`（标准 CSS 渐变串）+ `07-getD2c` 的合法 `<linearGradient>` svgIcon。属**提取/脚本问题**
  （raw 有、提取阶段没正确呈现），按铁律改脚本 + 重生成，不在下游产物打补丁。

- **修复**：`split_modules.py` 新增 `_sanitize_inline_svg(svg, node_id)`，在把 svg 存入 `assets.svgs`
  前应用与渲染同源的合法化：`inline_svg_fix_gradients`（渐变→`<defs>`+`url(#id)`，`sanitize_gradient`
  已处理 NaN）+ `fix_svg_frame_fill` + `fix_svg_thin_lines`。这些变换**幂等**，渲染阶段再调也是 no-op。
  `inject_svg_filters`（子节点 blur）/ `position_inline_svg`（定位）依赖节点树/布局，属渲染层，不前移。

- **影响范围**：18 个节点、37 处 `linear-gradient` + 手 `0:1384` 的 3 处 `radial-gradient(NaN)`。
  修复后全 modules `assets.svgs` 零残留非法 fill / NaN，18 个 svg 带合法 `<linearGradient>/<radialGradient>` defs；
  最终 H5 输出不变（渲染阶段本就在修，现为幂等）。

### 10. 头图 banner 混合/定位三连坑 + 调试方法论 — `css_core.py`

> **✅ 已落地（2026-07-11）**：坑 B/C 已在 css_core 根治并全量重生成；坑 A 经 diff 核实
> **本就不是 css_core bug**（d2cCss 已提供正确 `mix-blend-mode`，`d2c_supplement` 已在取）。
> 落地方式与精准判据见每坑末尾的「根治」。**方法论仍是本条最大价值，务必读。**

排查「头图位图发黑、光束不显示」时暴露的 css_core 根因。
**先讲方法论（最重要）**：这类"MasterGo 渲染不对"的问题，**别猜 CSS 行为**——要用数据：
①**量真实像素**（下载图统计颜色/透明度/亮区位置，就知道每层本该什么效果）；
②**做对照实验**（隔离单变量的最小 HTML，实测哪种写法生效）；
③**比 `07-getD2c` 权威值**（d2c 是 MasterGo 自己的 design-to-code 输出＝"正确渲染"的标准答案，css_core 生成结果与它不一致处就是 bug）。
本轮我先靠猜错了 4~5 次（3D 破坏混合、透明父隔离、加不透明基色…全错），改用上述三招后才定位。

**方法论补充（本轮"根治"复盘，通用）**：
- **先 diff 再动手**：把「当前管线产物」vs「已知正确版（手改CSS）」逐行 diff，直接看出"管线到底差什么"，
  别只凭交接文档就假设 bug 存在。本轮靠 diff 发现坑 A 根本不是 bug（d2cCss 已给对），省掉一次无谓修改。
- **改判据前先全站扫描定命中面**：坑 B/C 的触发判据（"结构组+子树含blend" / "d2c.transform 非空"）都是先扫
  全站数据、确认命中极小（各 1~3 个节点、不误伤编组8/菱形/年份文字）后才定，做成外科手术级修复——
  判据边界靠数据划，不靠直觉。切忌"纯结构组一律去 z-index / 有 rotate 一律用 d2c"这类粗判据（会误伤）。
- **多个症状先怀疑同源**：模块05「四词不居中」+「竖线没在两词中间」看似两个问题，实为同一根因
  （文本没拆分 + HTML 多空格塌成单空格），竖线其实一直正常渲染。别急着分头修，先找共同根因。

**坑 A —— 图层混合该用 `mix-blend-mode` 而非 `background-blend-mode`**：MasterGo 的图层混合（滤色/柔光）
= 该层与**下层**混合，浏览器等价写法是 `mix-blend-mode`。`background-blend-mode` 是元素**自身 bg-image 与
bg-color** 混合，单图层无基色时**浏览器空转**（等于没混）。**核实结论**：本数据集的 d2cCss 里这几个
节点(0:921/922/933/1317)的 blend 就存在 `mix-blend-mode` 键（screen/soft-light），`d2c_supplement` 已如实取，
管线产物本就正确——坑 A 是当初手改调试时误把 mix 改成 background 造成的，**非 css_core bug**，无需改。
（若未来遇到 d2cCss 只给 `background-blend-mode` 的数据，再在 `d2c_supplement` 把它映射成 `mix-blend-mode`。）

**坑 B —— 结构组的 z-index 造层叠上下文，隔离子层的 mix-blend-mode**：css_core 给几乎每个节点都发
z-index 排层；定位元素带 z-index 会**形成独立层叠上下文**。于是「编组7(0:919, z-index:0)」把内部"光"层
(深灰图 39,39,39, mix-blend-mode:screen) 隔离在组内，screen 混不到页面蓝、保持深灰→成为压在上层所有图
背后的"深色底"→上层 screen 图也跟着黑。**去掉编组7的 z-index**（解除隔离）后光层混出蓝光、全 banner 变亮。
**✅ 根治（css_core.node_to_css）**：只对「`_is_structural_container`(FRAME/GROUP 且无 fill/effect/opacity/
mask/hasSvg) 且 `_subtree_has_blend`(子树含 d2c mix-blend-mode)」的节点**不发 z-index**。这个双判据精准命中
0:919、放过同为结构组但无 blend 子树的 0:947(保留 z-index:3)，全站仅 0:919 一处受影响，不打乱其它层序。
（治标误区：给编组7硬塞 background-color 当基色——被否，因为不解决隔离本质。）

**坑 C —— 带 rotate 的节点定位错：裸用 relativeX/Y 当 left/top、且乱加 rotateX**：位图一(0:1317)
layoutStyle=rotate90/rotateX180/relativeX174.5/relativeY-119.65。css_core 直接把 relativeX/Y 当
px left/top **并加 rotateX(180deg)**，**没补偿旋转导致的位移**→整框被甩到 banner 上方裁掉，光束完全不显示。
而 d2c 的权威值是 `transform:rotate(90deg)`（**无 rotateX**）+ `left:103.8% top:-20.42%`（已补偿旋转的百分比定位）。
**✅ 根治（css_core.node_css_full → `_apply_d2c_rotate_position`）**：判据是 **`d2cCss.transform` 非空**——
只有"真旋转位图/手"(0:935/0:1317/0:1380)符合，用 d2c 的 left/top/transform/transform-origin 覆盖 raw 值
（天然丢掉多余 rotateX）。45°菱形、180°编组8、-46°年份文字的 `d2c.transform=None` → 不触发，保留 css_core
的 raw-px + transform-origin 逻辑（rules #3 已验证正确）。**注**：0:935/0:1380 因此从 raw px 改为 d2c 百分比
（旧手改版留了未补偿的 px，d2c 才是补偿后的正确值，属改进）。

**另（-od skill 侧，非 css_core）**：lift 原 output 的 banner 时，其位图 CSS 引用本地 `../images/*.png`
（generate_html 下载到本地了），需改回 MasterGo CDN url；且头图"光"层的混合基准等 raw 给不出的渲染规则，
凡需 agent 执行的要写进 SKILL.md 正文（OD 只注入 SKILL.md，CSS 注释不被语义理解）。




### 11. 逐字颜色 `textColor` 的 paint 引用未解析 — `split_modules.py` + `generate_html.py`

- **通用规则**：MasterGo 把一个 TEXT 节点里不同字符的颜色存在 `textColor:[{start,end,color}]`，
  `color` 是 paint 引用（如 `paint_0:626`）。单 textRun 场景下这些逐字颜色**无法塞进 textRuns**
  （`resolve_text_runs` 遍历时后段颜色会覆盖同一个 run，最终 run.color 只剩最后一段 → 整段变单色）。
- **丢在哪里**：`split_modules.py` 早期 `"textColor": node.get("textColor")` **原样透传未解析的 paint 引用**，
  modules JSON 里 textColor 是 `paint_0:626` 而非 hex；且 generate_html 拆合并文本时只按词上色、忽略逐字。
  结果模块05「费率低 品类全 策略优 服务好」整段渲染成 run 的单色（红 #EE0815），丢了"前2字棕"。
- **判定**：raw getDsl 的 paint 表里有这些颜色（`paint_0:626=#732207`、`paint_0:628=#EE0815`），
  只是提取/渲染没用上 → **脚本 bug**，改脚本重生成。
- **修复**（两处）：
  - `split_modules.py` 新增 `resolve_text_color(node, styles)`：把 textColor 每段 `color` 用
    `resolve_paint` 解析成 hex，写进 modules JSON（自包含，OD 取数也能直接用）。
  - `generate_html.py` 新增 `_colorize_by_textcolor(word, start_idx, text_color)`：拆合并文本时
    用 `re.finditer(r"\S+")` 拿每个词及其在原文的起始索引，按 textColor 区间给每个字符上色
    （连续同色合并为一个 `<span style="color:hex">`）；渐变色不作 CSS color（跳过）。override 未改
    文本时才逐字上色（改了文本则索引错位 → 不上色，回退父级色）。
- **Bad case —— 模块05 `0:1252`**：textColor 每词"前2字 `#732207` 棕 + 末1字 `#EE0815` 红"
  （费率=棕/低=红，品类=棕/全=红，策略=棕/优=红，服务=棕/好=红），空格段颜色不可见忽略。
- **影响范围**：全站含多段 `textColor` 的 TEXT 节点（本项目主要是模块05 的四词标语）。

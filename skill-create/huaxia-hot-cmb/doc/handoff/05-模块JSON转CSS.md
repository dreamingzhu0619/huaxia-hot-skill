# 05-模块 JSON 转 CSS

> 从 `data/modules/*.json` 生成每模块 `.css`，供肉眼对照 MasterGo 设计稿找出数据漏抓。
> 最后更新：2026-07-09

---

## 0. 产出文件

| 文件 | 说明 |
|---|---|
| `scripts/lib/css_core.py` | 核心：`node_to_css()` 把单节点转成 CSS dict |
| `scripts/render/generate_module_css.py` | 生成器：读模块 JSON → 遍历树 → 写 `.css` |
| `references/rules.md` | 选择器契约 + 已知局限 |
| `assets/styles/modules/00-banner.css` ~ `07-related-products.css` | 8 个模块 CSS，共 416 条规则 |

---

## 1. 取值原则

每个节点存了两套数据——getDsl 解析真值与 D2C 的 `d2cCss`。生成 CSS 时：

- **getDsl 为唯一基底**：定位、尺寸、填充、阴影、圆角、描边、字体全从 getDsl 字段算。
- **D2C 只补 getDsl 结构上给不出的 3 个属性**（非空时）：`mix-blend-mode`、`overflow`、`object-fit`。这些来自**同一个模块 JSON 里的 `node.d2cCss`**，不是外部对账。
- **定位 = getDsl 原生绝对 px**：根节点 `position:relative`，后代 `position:absolute; left=relativeX; top=relativeY`；`rotate` → `transform:rotate(); transform-origin:0 0`。

---

## 2. 选择器契约（供后续 generate_html.py 复用）

| 节点 | 选择器 | 示例 |
|---|---|---|
| 模块根 | `.m-{序号:02d}-{slug}` | `.m-00-banner` |
| 其余每个节点 | `.n-{id 冒号转横线}` | `0:937` → `.n-0-937` |

每条规则前带一行定位注释：`/* 0:937 电网进入高景气周期 [TEXT] */`，图片/SVG/PATH/mask 节点额外标注资源来源。

---

## 3. node_to_css 映射速查

| getDsl 字段 | CSS | 备注 |
|---|---|---|
| 根/后代 | `position` | root=`relative`，其余=`absolute` |
| layoutStyle.relativeX/Y | `left`/`top` | round px |
| layoutStyle.width/height | `width`/`height` | float round px |
| layoutStyle.rotate≠0 | `transform: rotate(Ndeg)` | `transform-origin: 0 0` |
| opacity | `opacity` | null 不输出；值 round 3 dp |
| fill 纯色（非TEXT） | `background-color` | |
| fill 渐变（非TEXT） | `background-image` | `sanitize_gradient` 修 NaN |
| fill IMAGE | `background-image: url()` + `background-size: cover` + `no-repeat` | |
| TEXT 纯色 | `color` | |
| TEXT 渐变 | `background-image` + `-webkit-background-clip: text` + `background-clip: text` + `text-fill-color: transparent` | 渐变文字三件套 |
| effect.boxShadow 非TEXT | `box-shadow` | |
| effect.boxShadow 于 TEXT | `text-shadow` | 去掉 spread（第4值） |
| effect.filter | `filter` | |
| borderRadius | `border-radius` | |
| strokeColor + strokeWidth | `border` / `-webkit-text-stroke` | TEXT 用 text-stroke |
| textRuns[0].font | `font-family/size/weight/line-height/letter-spacing/text-align/decoration/transform` | `lineHeight="-1"`→`normal`; `letterSpacing="auto"`→`normal` |
| 兄弟顺序 | `z-index` | children 下标注入 |

---

## 4. D2C 补充属性

`css_core.py` 的 `d2c_supplement()` 只从 `node.d2cCss` 补以下属性（非空时）：

```
mix-blend-mode
overflow
object-fit
```

> **已确认：`background-blend-mode` 是漏抓。**D2C 原始 HTML 里也没有这个属性值。需要在 `split_modules.py` 的 `ALL_CSS_PROPS` 和 `css_core.py` 的补充列表里加入，重新跑管线。

---

## 5. 已知局限（CSS 里如实输出，不做判断，留人肉眼核对）

- **line-height**：`"-1"`（auto）→ `normal`，无法拿到设计软件的精确 px 值。
- **letter-spacing**：`"auto"` → `normal`。
- **z-index**：getDsl 无显式 z-index，按兄弟顺序近似。
- **PATH 节点**：`path[].data` / 渐变走内联 SVG，CSS 只出 position/size 盒子，注释标 `PATH→内联SVG`。
- **mask=alpha/outline**：CSS 表达不了，注释标 `mask=...`。
- **font.style**：观测值恒为 `"0"`，仅 100–900 合法字重才输出 `font-weight`。
- **opacity**：getDsl 为 null 时不输出。D2C 也没有 opacity（D2C HTML 的 inline style 中无此属性）。

---

## 6. 运行

```bash
# 全量生成
python scripts/render/generate_module_css.py

# 预览（不写文件）
python scripts/render/generate_module_css.py --dry-run

# 只生成某个模块
python scripts/render/generate_module_css.py --module 0

# 只校验输入
python scripts/render/generate_module_css.py --check
```

---

## 7. 对照中发现的缺口

| 缺口 | 节点 | 现象 | 原因 |
|---|---|---|---|
| `background-blend-mode` | 0:919（编组7） | MasterGo 面板有，CSS 无 | D2C HTML 没输出；ALL_CSS_PROPS 未收录 |
| opacity | 0:1317（位图一） | 用户肉眼看有透明感，CSS 无 | getDsl 给 null；D2C 也未输出；可能实际是 `mix-blend-mode: screen` 的视觉效果 |

---

## 8. 下一步：fixed / variable 区分

> 引用 `doc/skill-design.md`：
> > `generate_user_input.py` 根据 modules 中标记为 variable 的字段，自动生成用户可编辑的输入文件。
> > 用户只需要修改 variable 内容，fixed 内容不会进入该文件。

即对每个模块 JSON 里的每个节点、每个字段，标注它是固定不变（fixed）还是每期可变（variable）。

### 需要决定的核心问题

| 类别 | 典型 fixed | 典型 variable | 待用户确认 |
|---|---|---|---|
| 文本内容 | — | 标题、数字、日期、基金名、收益率 | ✓ |
| 文本样式 | 字体、大小、颜色、行高、对齐 | — | 颜色可能不同主题换 |
| 图片 | 装饰光效、背景纹理 | 产品图、走势图、banner 大图 | ✓ |
| 布局 | 所有 position/size | — | 结构固定 |
| 视觉 | 渐变、阴影、圆角、描边、opacity | — | 品牌视觉固定 |

### 实现思路

1. 定规则：在模块 JSON 或一份独立配置里标记每个字段是 fixed 还是 variable。
2. 写 `scripts/input/generate_user_input.py`：提取所有 variable 字段 → 输出到 `data/input/user-input.json`，格式让用户只看到可变内容。
3. 最终 `generate_html.py`：把用户输入里的 variable 值合并回 fixed 模板，生成完整页面。

### 后续步骤汇集

1. 把 `background-blend-mode` 加入 `split_modules.py` 的 `ALL_CSS_PROPS` + `css_core.py` 的 `D2C_SUPPLEMENT_PROPS`，重新跑管线。
2. 继续肉眼对照其余模块 CSS，标记差异。
3. 用户定义 variable 边界 → 实现 `generate_user_input.py`。
4. 对所有缺口分类：上游 MCP 没给 → 无法修；解析丢弃 → 修 `split_modules.py`；CSS 遗漏 → 修 `css_core.py`。

# 04-模块 JSON 字段说明

> 每个 `data/modules/{序号}-{语义名}.json` 的结构与字段完整说明。
> 最后更新：2026-07-09

---

## 0. 文件产出

| 文件 | 说明 |
|---|---|
| `data/modules/_index.json` | 模块清单（供下游脚本索引） |
| `data/modules/00-banner.json` ~ `07-related-products.json` | 每个模块一份完整设计数据 |

脚本：`python scripts/prepare/split_modules.py`

---

## 1. 顶层结构

```jsonc
{
  "meta":     { /* 模块元信息 */ },
  "sections": [ /* 归属本模块的分段列表 */ ],
  "assets":   { /* 集中化的资源 */ },
  "node":     { /* 解析后的节点树，每个节点固定 28 key */ },
  "d2c":      { /* D2C 渲染级片段（如果匹配到） */ }
}
```

## 2. meta — 模块元信息

| 字段 | 类型 | 说明 |
|---|---|---|
| `moduleIndex` | int | 模块序号（0 起） |
| `moduleId` | string | 模块根节点 ID，如 `"2:796"` |
| `moduleName` | string | 模块中文名，如 `"头图banner"` |
| `slug` | string | 英文语义名，如 `"banner"` |
| `fileName` | string | 文件名，如 `"00-banner.json"` |
| `position` | {x,y,width,height} | 模块在页面中的位置 |
| `nodeCount` | int | 原始节点总数 |
| `resolvedNodeCount` | int | 解析后节点数（应等于 nodeCount） |
| `textCount` | int | 文本节点数 |
| `textsResolved` | int | 被替换的占位符文本数 |
| `sectionIndexes` | [int] | 归属的分段下标 |
| `styleCounts` | {paints,fonts,effects} | 引用的样式数 |
| `assetCounts` | {bitmaps,svgs,d2cSvgIcons,d2cExportImages} | 资源数 |
| `d2cMatched` | bool | 是否匹配到 D2C 片段 |
| `d2cMatchDistance` | float | D2C 片段位置对齐距离 |
| `d2cNodeCssCount` | int | 匹配到 D2C CSS 的节点数 |
| `missingStyleRefs` | [string] | 缺失的样式引用键 |

## 3. assets — 集中化资源

```jsonc
{
  "bitmaps": [
    { "styleKey": "paint_1:3889", "url": "https://image-resource.mastergo.com/..." }
  ],
  "svgs": {
    "0:925": "<?xml version=\"1.0\"...<svg>...</svg>"
  }
}
```

- `bitmaps`：从 paint 样式引用里提取的位图 URL
- `svgs`：按 nodeId 索引的 SVG 字符串（来自 extractSvg + getDesignSvgs），节点层通过 `hasSvg` 判断是否存在

## 4. node — 解析后的节点树（核心）

每个节点固定 **28 个 key**（children 不计入），所有 key 跨所有节点、跨所有模块完全一致。有值填解析值，无值填 `null`。

### 4.1 身份/结构

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `id` | string | getDsl | 节点 ID，如 `"0:937"` |
| `name` | string | getDsl | 节点名，如 `"热点速递"` |
| `type` | string | getDsl | `FRAME` / `GROUP` / `LAYER` / `PATH` / `SVG_ELLIPSE` / `TEXT` |

### 4.2 几何

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `layoutStyle` | {width, height, relativeX, relativeY, rotate, rotateX} | getDsl | 原始布局数据，rotate 单位是度 |
| `bounds` | {x, y, width, height} | getDsl 累加计算 | 页面绝对坐标（累加父 relativeX/Y） |

### 4.3 视觉（已解引用，可以直接生成 CSS）

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `opacity` | number\|null | getDsl | 不透明度 0~1 |
| `fill` | 见下方 | getDsl 解引用 paint_ | 填充值 |
| `effect` | 见下方 | getDsl 解引用 effect_ | 效果（阴影/模糊） |
| `borderRadius` | string\|null | getDsl | 圆角，如 `"8px"` |
| `strokeAlign` | string\|null | getDsl | 描边对齐 `"inside"` / `"outside"` |
| `strokeColor` | string\|null | getDsl 解引用 paint_ | 描边颜色 |
| `strokeType` | string\|null | getDsl | 描边类型，通常 `"solid"` |
| `strokeWidth` | string\|null | getDsl | 描边宽度，如 `"1px"` |
| `mask` | string\|null | getDsl | 蒙版类型 `"alpha"` / `"outline"` |

**fill 的可能值：**

```
null
"#FF0000"                                           // 纯色
"linear-gradient(180deg, #F75901 0%, #F37D4C 79%)"  // 渐变
"radial-gradient(...)"                               // 径向渐变
{"type":"IMAGE", "url":"https://..."}                // 图片填充
```

**effect 的可能值：**

```jsonc
null
{
  "boxShadow": ["box-shadow: 0px 1px 0px 0px #FFFFFF;"],
  "filter": ["filter: blur(6.64px);"],
  "backdropFilter": [],
  "raw": ["box-shadow: 0px 1px 0px 0px #FFFFFF;"]
}
```

### 4.4 路径（仅 PATH 节点有值）

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `path` | [{data, fill, transform}]\|null | getDsl | SVG 路径数据列表，每个子路径含 `data`（path 字符串）、`fill`（解析后的颜色/渐变）、`transform`（matrix） |

### 4.5 文本（仅 TEXT 节点有值）

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `text` | string\|null | getDsl 拼接 | 纯文本内容（textRuns 拼接结果） |
| `textRuns` | [{text, font, color}]\|null | getDsl 解引用 | 分段文本数组，每段含 `text`、`font`（完整字体对象）、`color`（解析后的颜色值） |
| `textAlign` | string\|null | getDsl | 文本对齐 `"center"` / `"left"` / `"right"` |
| `textMode` | string\|null | getDsl | `"auto-height"` / `"single-line"` |
| `textColor` | [{start,end,color}]\|null | getDsl | 原始 textColor 数组（保留 style ref 供审计） |

**textRuns[].font 结构：**

```jsonc
{
  "family": "FZZDHJW--GB1",
  "size": 30.95400047302246,
  "style": "0",
  "lineHeight": "-1",            // "-1" 表示 auto
  "letterSpacing": "-1.47px",
  "case": "none",
  "decoration": "none"
}
```

### 4.6 SVG / 导出图

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `hasSvg` | bool | extractSvg / getDesignSvgs | 该节点是否有 SVG 资源 |
| `exportImage` | {fileName, format, ...}\|null | D2C image 清单 | 该节点在 D2C 中的导出图片信息 |

> SVG 字符串本身在 `assets.svgs[node.id]`，不在节点里。

### 4.7 D2C CSS（D2C 独有属性）

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `d2cCss` | dict(34 props) | D2C HTML 匹配 | 该节点对应的 D2C CSS 属性。匹配到就填值，没匹配到每个属性都是 null |
| `d2cMatch` | string\|null | 匹配方式 | `"img-src"`（文件名精确匹配）/ `"geometry"`（坐标匹配）/ null（未匹配） |

**d2cCss 的 34 个属性：**

```
-webkit-background-clip  -webkit-text-fill-color
background              background-clip          background-image
border                  border-bottom-left-radius  border-radius
border-top-left-radius  bottom                   box-shadow
color                   filter                   flex
font-family             font-size                height
left                    letter-spacing           line-height
mix-blend-mode          object-fit               opacity
overflow                position                 right
text-align              text-fill-color          text-shadow
top                     transform                transform-origin
width                   z-index
```

> 其中 **`mix-blend-mode`** 和 **`overflow`** 是 getDsl 完全无法提供的，必须从 D2C 提取。其余属性 getDsl 解析后也能得到（通过 layoutStyle / fill / effect / textRuns 等）。

### 4.8 审计/溯源

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `styleRefs` | {fill, effect, font, textColors, strokeColor}\|null | getDsl | 原始样式引用键（保留供审计，值内联后仍可追溯） |
| `componentDefinition` | dict\|null | getDsl | 组件定义（本设计稿无实例，恒为 null） |
| `sources` | [string] | 综合 | 该节点命中了哪些数据源，如 `["getDsl","getD2c","extractSvg"]` |
| `captureStatus` | string | 综合 | `"complete"` / `"partial"`（partial 表示某些该有的数据没取到） |
| `children` | [node] | getDsl | 递归子节点，结构完全一致 |

---

## 5. sections — 归属分段

```jsonc
[
  {
    "sectionIndex": 0,
    "id": "2:796",
    "name": "头图banner",
    "type": "FRAME",
    "nodeCount": 23,
    "x": 25, "y": 52,
    "width": 352.59, "height": 88.9
  }
]
```

## 6. d2c — D2C 渲染级片段

```jsonc
{
  "html": "<div style=\"...\">...</div>",     // 模块对应的 HTML 片段
  "svgIcons": { "svg_xxx.svg": "<svg>..." }, // 内联图标
  "exportImages": {                          // 导出图片清单
    "位图一-0-1317.svg": { "kind": "node-export", "nodeId": "0:1317", "format": "SVG" }
  }
}
```

仅在 D2C 匹配到该模块时存在。

---

## 7. 节点字段速查表

所有 28 个 key（children 不单独列出）：

```
① id              ② name            ③ type
④ layoutStyle     ⑤ bounds
⑥ opacity         ⑦ fill            ⑧ effect          ⑨ borderRadius
⑩ strokeAlign     ⑪ strokeColor     ⑫ strokeType      ⑬ strokeWidth
⑭ mask            ⑮ path            ⑯ text            ⑰ textRuns
⑱ textAlign       ⑲ textMode        ⑳ textColor
㉑ hasSvg          ㉒ exportImage     ㉓ styleRefs
㉔ componentDefinition
㉕ d2cCss          ㉖ d2cMatch
㉗ sources         ㉘ captureStatus
```

---

## 8. 数据流总览

```
extractSvg ──┐
getDesignSvgs ─┤
              ├── hasSvg / assets.svgs
getDsl ───────┤
  ├─ nodes ───┼── id, name, type, layoutStyle, bounds,
  │           │   opacity, borderRadius, mask, stroke*, path, textColor
  │           └── fill/effect/strokeColor ──► resolve_paint/effect ─► 实际值
  │           └── text[]/textColor[] ───────► resolve_text_runs ───► textRuns
  └─ styles ──┼── paint_[].url ──► assets.bitmaps
              └── font_ ─────────► resolve_font ─► textRuns[].font
              └── effect_ ───────► resolve_effect ─► effect.boxShadow/filter

getDesignTexts ──► resolve_texts_inplace ──► textRuns[].text

D2C ────────────► parse_d2c_node_css ──────► d2cCss (34 props)
  └─ image ─────► match_export_image ───────► exportImage
```

---

## 9. 下一步：CSS 生成

有了这份固定 Schema 的模块 JSON，下一步是写 `node_to_css()` 把每个节点转为 CSS，跟 D2C 的 CSS 对照，找出差距。

核心映射关系：见本仓库 `data/audit/union-schema.json`。

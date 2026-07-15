# mastergo-mcp-raw.json 结构说明

`data/raw/mastergo-mcp-raw.json` 是 `scripts/fetch/fetch_mcp_data.py` 抓取后生成的合并文件，
汇总了一次 MasterGo MCP 抓取的全部原始数据。顶层只有两个键：`captureManifest` 和 `responses`。

- **元数据 / 抓取清单** → 看 `captureManifest`
- **真正的设计数据** → 看 `responses`

同样的内容在 `data/raw/` 下还**按工具分文件夹**各存了一份独立文件（见下方「落盘目录结构」），方便单独查看；`_capture-manifest.json` 则是 `captureManifest` 的单独副本。

---

## 落盘目录结构

`data/raw/` 每个工具一个子文件夹，根目录只保留合并文件与清单。`list[N]` 为本次实测数量。

```
data/raw/
├── mastergo-mcp-raw.json          # 合并文件（captureManifest + responses）
├── _capture-manifest.json         # captureManifest 单独副本
├── 01-getDsl/getDsl.json
├── 02-getMeta/getMeta.md          # markdown，非 JSON
├── 03-getDesignSections/          # 概览 + 逐段，全部收这里
│   ├── overview.json
│   └── section-00.json … section-85.json      # 每段一条(sectionIndex)
├── 05-getDesignSvgs/getDesignSvgs.json
├── 05-getDesignTexts/getDesignTexts.json
├── 05-extractSvg/extractSvg.json
├── 06-getComponentLink/           # 无组件文档链接时不生成此目录
│   └── link-00.json …
└── 07-getD2c/
    ├── getD2c.json
    └── d2c-out/                   # getD2c 工具自带导出：html + 图标/图片 SVG
```

> 命名规则：`{步骤号}-{工具名}/`。步骤 5 的三个工具（svgs/texts/extractSvg）共用前缀 `05-`。

---

## 结构总览（树状图）

> 下面的 `list[N]` 是本次实测数量（12 工具 / 93 步 / 86 段），换设计稿会变。

```
mastergo-mcp-raw.json
├── captureManifest                 # 抓取清单 / 元数据（不含设计数据本身）
│   ├── capturedAt                  # 抓取时间
│   ├── projectName / mcpPackage / apiBaseUrl
│   ├── fileId / layerId / sourceLayerId / shortLink
│   ├── toolInventory   list[12]    # 服务器暴露的 12 个工具及各自 inputProps
│   ├── steps           list[93]    # 93 次调用逐条状态(step/tool/status/args)
│   ├── totalSections   86
│   ├── componentDocumentLinks list[0]
│   └── unresolved      list[0]     # 未解决项（现在为空）
│
└── responses                       # 各工具的原始返回（真正的设计数据都在这）
    ├── getDsl                      dict      ← 完整节点树 + 样式引用（最核心）
    ├── getMeta                     dict      ← 站点/页面配置(markdown)
    ├── getDesignSections_overview  dict      ← 分段概览，得到 totalSections
    ├── getDesignSections_sections  list[86]  ← 逐段 DSL，每段一条(按 sectionIndex)
    ├── getDesignSvgs               dict      ← 补回 PATH svgHtml
    ├── getDesignTexts              dict      ← 补回长文本原文(占位符 T{i}|{id})
    ├── extractSvg                  dict      ← PATH 合成带色 SVG
    ├── getComponentLink            list[0]   ← 组件文档(无组件实例则为空)
    └── getD2c                      dict      ← D2C 编译产物(HTML+CSS)，补渲染属性

每个 responses.* 的 record 统一字段:
    { isError, text, json, _args (, sectionIndex | url) }
```

---

## 1. captureManifest — 抓取清单 / 元数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `capturedAt` | string | 抓取时间（本地时区 ISO8601，如 `2026-07-09T09:30:59+08:00`） |
| `projectName` | string | 项目名，来自 `project.config.json` |
| `mcpPackage` | string | 使用的 MCP 包，如 `@mastergo/magic-mcp` |
| `apiBaseUrl` | string | MasterGo API 地址，如 `https://mastergo.com` |
| `fileId` | string | 设计文件 ID |
| `layerId` | string | 根节点 ID（如 `0:917`） |
| `sourceLayerId` | string | 源图层 ID（无则空串） |
| `shortLink` | string | 短链（用短链抓取时才有） |
| `toolInventory` | list | 服务器暴露的全部工具（本次 12 个），每项含 `name` 与 `inputProps`（该工具接受的参数名） |
| `steps` | list | 每次工具调用的逐条记录（本次 93 条），每项含 `step` / `tool` / `status` / `args` 等 |
| `totalSections` | number | 分段总数（本次 86） |
| `componentDocumentLinks` | list | getDsl 返回的组件文档链接（为空表示无组件实例） |
| `unresolved` | list | 未解决项（被跳过的调用及原因；正常应为空） |

### steps 单条结构

```json
{
  "step": "4.0",
  "tool": "getDesignSections",
  "status": "ok",              // ok / ERROR / MISSING
  "args": { "fileId": "...", "layerId": "0:917", "sectionIndex": 0, "format": "json" },
  "sectionIndex": 0            // 仅分段调用才有；其它步骤可能带 totalSections/componentLinks/code 等
}
```

### toolInventory 单条结构

```json
{
  "name": "mcp__getDsl",
  "inputProps": ["fileId", "format", "layerId", "shortLink", "sourceLayerId"]
}
```

---

## 2. responses — 各工具原始返回

设计数据全部在这里。键与抓取序列一一对应：

| 键 | 类型 | 对应工具 / 内容 |
|----|------|----------------|
| `getDsl` | record | 完整节点树 + 样式引用（paint/font/effect）+ componentDocumentLinks（**最核心**） |
| `getMeta` | record | 站点 / 页面级配置规则（markdown 文本） |
| `getDesignSections_overview` | record | 分段概览（totalSections、各 section 的 bbox / nodeCount 等） |
| `getDesignSections_sections` | list | 逐段 DSL，每段一条，按 `sectionIndex` 排列（本次 86 条） |
| `getDesignSvgs` | record | 补回被 Section 剥离的 PATH `svgHtml` |
| `getDesignTexts` | record | 补回被占位符（`T{index}\|{nodeId}`）替换的长文本原文 |
| `extractSvg` | record | PATH 几何 + paint 合成的带色完整 SVG |
| `getComponentLink` | list | 组件文档内容（`componentDocumentLinks` 为空时该列表为空） |
| `getD2c` | record | D2C 编译产物（HTML + CSS），补 blendMode / rotation / clip 等 DSL 不提供的渲染属性 |

### 每个响应 record 的统一字段

无论哪个工具，单条响应都是同一套结构：

| 字段 | 类型 | 说明 |
|------|------|------|
| `isError` | bool | 该次调用是否出错 |
| `text` | string | 工具返回的**原始文本**（未加工） |
| `json` | object \| null | 把 `text` 解析成的 JSON 对象；解析失败则为 `null` |
| `_args` | object | 本次调用实际传入的参数 |
| `sectionIndex` | number | **仅 `getDesignSections_sections` 里的分段条目**才有 |
| `url` | string | **仅 `getComponentLink` 里的条目**才有，标记对应组件文档链接 |

示例（`getDsl`）：

```json
{
  "isError": false,
  "text": "{ ...原始 JSON 字符串... }",
  "json": { "dsl": { ... }, "componentDocumentLinks": [], "rules": "..." },
  "_args": { "fileId": "195787688623601", "layerId": "0:917", "format": "json" }
}
```

---

## 读取建议

- 想拿**元数据 / 校验抓取是否完整** → 读 `captureManifest`（尤其 `steps`、`unresolved`、`totalSections`）。
- 想拿**设计数据做后续还原** → 读 `responses`，优先用各 record 的 `json` 字段；`json` 为 `null` 时再退回 `text`。
- 分段数据在 `responses.getDesignSections_sections`，按 `sectionIndex` 定位具体某一段；对应独立文件是 `data/raw/03-getDesignSections/section-NN.json`。
- 单独查看某个工具的产物时，直接打开 `data/raw/` 下对应工具文件夹里的文件更轻量（避免加载整个 2MB 合并文件）。

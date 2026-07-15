# 交接文档 · MasterGo → H5 Skill（huaxia-hot-cmb）

> 给下一个窗口的 context。读完这份就能接手，无需回看上一个窗口的对话。
> 最后更新：2026-07-09

---

## 0. 一句话背景

做一个 Claude Code **Skill**：输入 MasterGo 设计稿链接 + MasterGo MCP，自动提取样式，生成**同风格的营销长图 H5**。

- 业务场景：招商银行（CMB）营销长图。这类长图**背景和每个 part 的版式高度统一**，风格固定，实际每期只需要**替换具体的图表和文字**。
- 所以核心思路是：把设计稿拆成「固定模板(fixed) + 可变内容(variable)」，用户只改 variable，就能产出新一期 H5。
- Skill 根目录：`C:\Users\dream\Desktop\skill-create\huaxia-hot-cmb\`
- 完整目录设计见：`doc/skill-design.md`（**权威设计文档，先读它**）

---

## 1. 总体 Workflow（4 步）

1. **提取与保存数据**：MasterGo MCP 抓原始数据 → 保存 → 原始数据 + 直观的树状结构
2. **JSON → CSS**：把节点 JSON 转成 CSS。
3. **区分 fixed / variable**：判断哪些固定、哪些要改；可变部分交给用户输入。
4. **生成最终 H5**：按每块模板 + 用户输入，产出最终 H5。

**当前进度：第 1 步的「MCP 抓取」子环节已完成并跑通。其余全部待做。**

---

## 2. 已完成的工作

### 2.1 抓取脚本 `scripts/fetch/fetch_mcp_data.py` ✅

- **架构**：独立 MCP 客户端脚本。用官方 `mcp` Python SDK（stdio）拉起 `npx @mastergo/magic-mcp` 子进程，脚本自己按序调用全部工具。**不是**靠 Claude 手动调 MCP。
  - 这是和用户确认过的选型：`独立 MCP 客户端脚本` + `官方 mcp SDK`。
- **配置驱动**，从以下文件读参数：
  - `config/project.config.json`：`designUrl`（脚本自动解析出 fileId+layerId）、`apiBaseUrl`、`sectionBatchSize` 等。
  - `config/local.secret.json`：`mcpToken`（也支持环境变量 `MG_MCP_TOKEN`）。**此文件已被 .gitignore，勿提交。**
- **用法**：
  ```bash
  cd huaxia-hot-cmb
  python scripts/fetch/fetch_mcp_data.py            # 完整抓取
  python scripts/fetch/fetch_mcp_data.py --check    # 只校验配置/依赖/URL解析，不联网
  # 可用 --design-url / --file-id / --layer-id / --token / --url / --section-batch 覆盖
  ```
- **7 步抓取序列**（关键，见第 4 节）：getDsl → getMeta → getDesignSections(概览) → getDesignSections(逐段,分批并发) → getDesignSvgs/getDesignTexts/extractSvg → getComponentLink(条件) → getD2c(条件)。
- **健壮性设计**：
  - 用 `list_tools()` **动态发现工具**，按后缀匹配真实名（真实名带 `mcp__` 前缀，如 `mcp__getDsl`），并按各工具 `inputSchema` **过滤参数**——抗版本差异。
  - 单个工具失败不中断整体；结果统一记 `isError`。
  - Windows 适配：`npx.cmd` 解析、stdout 强制 UTF-8。

### 2.2 真实抓取已跑通 ✅

- 设计稿：`fileId=195787688623601`，`layerId=0:917`（招行-热点速递 中心化场景页）。
- 结果：**93 次工具调用全部 ok，0 失败，0 unresolved**；`totalSections=86`；`componentDocumentLinks=0`。
- 关键校验：getDsl **未 skipped**，含 `path.data` / `textColor` / `styles`；getDesignTexts 正确返回长文本原文（占位键 `T{index}|{nodeId}`）；getD2c 成功（`code=00000`）。

### 2.3 输出落盘结构 ✅

`data/raw/` 下**每个工具一个子文件夹**，根目录只留合并文件与清单：

```
data/raw/
├── mastergo-mcp-raw.json          # 合并文件：顶层只有 captureManifest + responses
├── _capture-manifest.json         # captureManifest 单独副本
├── 01-getDsl/getDsl.json          # 完整节点树 + 样式引用（最核心，~200KB json）
├── 02-getMeta/getMeta.md          # 站点/页面配置（markdown）
├── 03-getDesignSections/
│   ├── overview.json              # 概览（含 totalSections）
│   └── section-00.json … section-85.json   # 86 段逐段 DSL
├── 05-getDesignSvgs/getDesignSvgs.json
├── 05-getDesignTexts/getDesignTexts.json   # 长文本原文
├── 05-extractSvg/extractSvg.json
├── 06-getComponentLink/           # 无组件链接时不生成
└── 07-getD2c/
    ├── getD2c.json                # D2C 编译产物(HTML+CSS)，补渲染属性
    └── d2c-out/                   # getD2c 工具自带导出：html + 图标/图片 SVG
```

- 合并文件 `mastergo-mcp-raw.json` 结构详解见：`doc/mastergo-mcp-raw结构说明.md`。
- 每条响应 record 统一字段：`{ isError, text, json, _args (, sectionIndex | url) }`。`json` 是 `text` 解析后的对象；优先用 `json`，为 `null` 再退回 `text`。

### 2.4 环境（已就绪，无需重装）

- Node `v24`、npx `11`；Python `3.11.9`。
- 已安装 `mcp 1.28.1`；已有 `httpx 0.28.1`、`pillow 11.0.0`、`anthropic 0.107.0`。

### 2.5 已产出文档

- `doc/skill-design.md`：Skill 完整目录结构设计（**权威**）。
- `doc/mastergo-mcp-raw结构说明.md`：原始数据文件结构说明。
- `doc/mcp数据提取.md`：**当前为空**（方法论已并入本交接文档第 4 节）。
- 根目录 `mastergo_full_node_tree.md`：上一轮产出的**完整节点树样例**（人类可读格式，可作 normalize 的输出参照）。

---

## 3. 待办（建议顺序）

对应 `doc/skill-design.md` 里的 `scripts/`：

1. **`scripts/normalize/normalize_to_tree.py`（建议先做）**：把 `data/raw/` 原始数据转成轻量层级树 `data/normalized/tree.json`（父子关系/层级/顺序/类型/模块划分，不存完整样式）。可参照 `mastergo_full_node_tree.md` 的呈现风格。
2. `scripts/prepare/split_modules.py`：按页面层级树识别业务模块，从原始数据提取每个模块完整设计数据 → `data/modules/{序号}-{语义名}.json`。
3. `scripts/prepare/download_assets.py`：下载图片资源 → `assets/images/`。
4. `scripts/input/generate_user_input.py`：把模块里标记为 `variable` 的字段生成用户可编辑文件 `data/input/user-input.json`（fixed 不进此文件）。
5. `scripts/render/generate_page_css.py` / `generate_module_css.py` / `generate_html.py`：生成页面级/模块级 CSS 与最终 HTML。
6. `scripts/audit/generate_audit.py`：检查报告（模块拆分/图片/字段丢失/CSS 转换/variable 替换）。
7. `SKILL.md`：Skill 入口说明（还没写）。

**注意**：第 3、4 步（fixed/variable 区分 + 用户输入）是这个 Skill 的**业务核心**——长图模板固定、每期只换图表和文字，怎么切分 fixed/variable 需要和用户对齐。

---

## 4. 下一个窗口必须知道的技术事实

### 4.1 MasterGo MCP 工具清单与参数

真实名都带 `mcp__` 前缀；脚本按后缀匹配。fileId 从 URL `file/<id>` 取，layerId 形如 `0:917`。

| 工具 | 真实名 | 参数 | 用途 |
|------|--------|------|------|
| getDsl | `mcp__getDsl` | fileId, layerId, sourceLayerId?, shortLink?, format? | 完整节点树+样式引用+componentDocumentLinks |
| getMeta | `mcp__getMeta` | **fileId, layerId**(必填), sourceLayerId?, format? | 站点/页面配置(markdown) |
| getDesignSections | `mcp__getDesignSections` | fileId, layerId, shortLink?, sourceLayerId?, **sectionIndex?**, format? | 不传 index=概览；传 index=逐段 DSL |
| getDesignSvgs | `mcp__getDesignSvgs` | fileId, layerId, sourceLayerId?, shortLink?, format? | 补回被剥离的 PATH svgHtml |
| getDesignTexts | `mcp__getDesignTexts` | 同上 | 补回长文本原文(占位符) |
| extractSvg | `mcp__extractSvg` | 同上 + backgroundColor? | PATH 合成带色 SVG |
| getComponentLink | `mcp__getComponentLink` | **url**(必填) | 组件文档；仅 componentDocumentLinks 非空时调 |
| getD2c | `mcp__getD2c` | **contentId, documentId**(必填), outDir? | D2C 编译产物；补 DSL 不提供的渲染属性 |

- getD2c 的 `contentId = "{fileId}-{layerId 把 : 换成 -}"`，`documentId = fileId`。
- 另有 4 个未纳入：getComponentGenerator / getFlutterGenerator / c2d / version_0_2_2。

### 4.2 调用顺序铁律：getDsl 必须最先调 ⚠️

MCP 服务器按 `token+fileId` 缓存状态。**若先调了 getDesignSections，再调 getDsl 会返回 `skipped:true`**，导致 `path.data`、`textRuns` 等完整几何/富文本**永久丢失**。所以序列固定为 getDsl 打头。

### 4.3 数据补全与合并优先级（做 normalize/merge 时的保护规则）

Section DSL 是**精简版**：PATH 的 svgHtml 被剥离、长文本(>50字)替换为占位符 `T{index}|{nodeId}`、path.data 可能清空、relativeX/Y 可能归零。合并时「先来的更全，全的不能被缺的覆盖」：

| 数据 | 权威来源 | 规则 |
|------|---------|------|
| 结构 parentId/childrenIds | getDsl | 不被覆盖 |
| 几何 bounds/layoutStyle | getDsl | 不被 Section 归零值覆盖 |
| text | getDsl > getDesignTexts > Section | 占位符不覆盖真实文字 |
| textRuns(多色多段文字) | getDsl 首次 | 不被 Section 占位符版覆盖 |
| path.data | getDsl | 不被 Section 清空版覆盖 |
| svg | getDesignSvgs + extractSvg | 不覆盖已有非空值 |
| blendMode/rotation/rotationX/rotationY/clipsContent | **D2C 唯一来源** | DSL 完全不提供 |
| effect/borderRadius/opacity | DSL 优先，D2C 补空 | D2C 只回填空值 |
| fill | D2C 已解析色值 > DSL paint 引用 | 已解析优先 |

### 4.4 只有 D2C 才有的 5 个字段

`blendMode`、`rotation`、`rotationX`、`rotationY`、`clipsContent` —— DSL / getMeta / getDesignSections 都不返回，必须从 `07-getD2c/getD2c.json` 的 HTML/CSS 里解析回填。NodeId 映射：从 HTML 的 `id`/`data-node-id`/`data-id`/`class` 匹配，尝试 `0:919`、`0-919`、`node-0-919` 等格式。

---

## 5. 文件位置速查

```
huaxia-hot-cmb/
├── SKILL.md                         # 待写
├── config/
│   ├── project.config.json          # designUrl 等（已填真实设计稿）
│   └── local.secret.json            # mcpToken（勿提交）
├── scripts/fetch/fetch_mcp_data.py  # ✅ 已完成
├── data/raw/                        # ✅ 已抓取（见 2.3）
├── doc/
│   ├── skill-design.md              # 权威目录设计
│   ├── mastergo-mcp-raw结构说明.md
│   ├── mcp数据提取.md               # 空
│   └── HANDOFF.md                   # 本文档
└── mastergo_full_node_tree.md       # 节点树样例（在 skill-create 根目录）
```

---

## 6. 协作注意事项 / 已知坑

- **用中文沟通**（用户明确要求，包括澄清性提问）。
- **getD2c 是否成功看返回信封的 `code` 字段**（`00000`=成功），**不要**用子串匹配 `"404"/"10009"` 判断——D2C 正文 HTML/CSS 里会误命中（此坑已修）。
- section 数量可能很多（本次 86），已改成 `03-getDesignSections/` 分文件夹存放，避免根目录爆炸。
- 重新抓取前建议清空 `data/raw/`（该目录是可再生的 gitignore 产物）。
- `doc/mcp数据提取.md` 目前是空文件；若需要，可把第 4 节内容回填进去。
- 换其它设计稿：改 `config/project.config.json` 的 `designUrl` 即可；需 MasterGo **团队版及以上** token，且设计文件在**团队项目**里（草稿箱访问不到）。

---
name: huaxia-hot-cmb
description: 把 MasterGo 上的基金营销 H5 设计稿转换成可交付的静态页面。核心不是脚本管线（提取数据、拆分模块、生成 CSS），而是教会 agent 如何正确判断设计稿中哪些内容是每期固定不变的、哪些是随每期变化的，从而让「换一期内容」变成一次简短对话而非重新切图。
---

# 华夏基金热点速递 H5

## 这个 skill 做什么

输入一张 MasterGo H5 设计稿，经过数据提取 → 模块拆分 → **fixed/variable 分类** → 用户填写 → 生成 H5。

脚本管线处理数据提取和渲染（这是工程问题，已解决）。**本 skill 的核心是 fixed/variable 分类——这是判断力问题。**

## 两个必填输入

| 输入 | 位置 | 说明 |
|---|---|---|
| MasterGo 设计稿链接 | `config/project.config.json` 的 `designUrl` | 脚本自动解析 fileId + layerId |
| MCP 个人令牌 | `config/local.secret.json` 的 `mcpToken` | MasterGo 个人设置页获取，需团队版 |

开始前确认这两项已填好。

## 环境依赖

- Python 3.11+ + `pip install mcp`（仅抓取阶段）
- Node.js / npx（仅抓取阶段）
- 其余脚本只依赖 Python 标准库

---

# 核心方法论：如何判断 fixed 与 variable

这是整个 skill 最有价值的部分。脚本可以无差别提取数据，但只有人能判断"哪些东西下期会变"。本方法论让 agent 具备这个判断力，且规则通用——换一个设计稿也适用。

## 三档分类

| 标记 | 含义 | 用户可改什么 |
|---|---|---|
| `fixed` | 完全不变 | 无 |
| `variable` | 只改文字 | `text` |
| `variable-all` | 整块可变 | text + 尺寸 + 颜色 + 描边 + path |

`variable-all` 的父节点自动向下继承，子节点不必逐个标记。

## 判断原则

判断的核心问题是：**「下一期再做一张同样的 H5，这个内容会变吗？」**

### 原则一：按内容来源判断

内容的来源决定了它会不会变。从设计稿里看文本内容，追问「这段文字是从哪里来的」：

| 来源 | 判断 | 原因 |
|---|---|---|
| **实时行情数据**（收盘价、涨跌幅、指数点位） | `variable` | 每期必然不同 |
| **新闻资讯正文**（"截止 X 日收盘，XX 板块走强…"） | `variable` | 每期重写 |
| **日期/时间戳**（"2026.03.05"、"截止3月5日"） | `variable` | 每期更新 |
| **数据来源标注**（"信息来源：东方财富资讯，日期截止…"） | `variable` | 来源和日期都变 |
| **图表数值**（柱状图高度、饼图扇区、折线图点位） | `variable-all` | 数据变 → 图形变 |
| **研究报告引用**（"资料来源：长城证券《…》作者：…"） | 看情况 | 如果每期引用不同报告 → `variable`；如果是固定免责 → `fixed` |

### 原则二：按文本功能判断

不看文本内容，看它在页面里**担任什么角色**：

| 功能 | 判断 | 原因 |
|---|---|---|
| **标题/副标题**（概括本期主题） | `variable` | 主题每期不同 |
| **正文段落**（展开论述） | `variable` | 内容每期不同 |
| **CTA 按钮文案**（"小试一笔"） | 看情况 | 品牌固定用语 → `fixed`；活动相关 → `variable` |
| **品牌标语**（"买基金 来招行"） | `fixed` | 品牌资产，不会每期改 |
| **风险提示**（"基金有风险，投资须谨慎…"） | `fixed` | 合规条文，逐字审核，不随意改 |
| **费用表格**（管理费率、托管费率、赎回费率） | `fixed` | 基金合同约定，不随营销周期变化 |
| **表格列头/标签**（"费用类型"、"收费方式/费率"） | `fixed` | 结构信息，不变 |
| **产品名称**（"华夏中证电网设备主题ETF发起式联接C"） | `variable` | 每期推荐的产品可能不同 |
| **产品代码**（"025833"） | `variable` | 随产品变化 |
| **风险等级标签**（"R5高风险"） | `fixed` | 产品固有属性，同一产品不变 |
| **装饰文字**（"分享"、"热点速递"） | `fixed` | 纯 UI 标签 |

### 原则三：按视觉元素类型判断

| 类型 | 判断 | 原因 |
|---|---|---|
| **PATH（贝塞尔曲线、图标、装饰线）** | `fixed` | 设计稿的视觉语言，不随内容变 |
| **LAYER（带填充/描边的矩形/圆形）** | `fixed` | 装饰元素，除非是图表中的数据柱 |
| **FRAME（容器/编组）** | `fixed` | 结构框架，除非内含图表数据 |
| **SVG_ELLIPSE（椭圆）** | `fixed` | 装饰元素 |
| **TEXT** | 逐一判断 | 唯一需要逐节点分析的节点类型 |
| **位图/图片** | `fixed` | 装饰图不改；若包含需要替换的数据图表截图则需重新导出 |

### 原则四：看同一模块内 TEXT 节点的"邻居关系"

把同一模块里的全部 TEXT 节点拉出来对比看，更容易判断：

1. **标题 + 正文**：标题和正文通常同为 `variable`
2. **标签 + 值**：标签（"变压器出口金额"）通常是 `fixed`，值（"90.36"）是 `variable`
3. **表格**：表头（列名）是 `fixed`，数据单元格是 `variable`
4. **图表坐标轴**：轴标签和年份刻度是 `fixed`（坐标系不变），数据柱是 `variable-all`

### 几条硬规则

以下内容**无条件标 `fixed`**，不需要让用户确认：

- 包含「风险」「投资须谨慎」「基金合同」「招募说明书」等合规关键词的文本
- 包含「管理费」「托管费」「赎回费」「申购费」「销售服务费」的费用表格
- 品牌标识类文本（需对照具体品牌确认，如招行的"买基金 来招行"）
- `type` 不是 `TEXT` 且不是图表数据组件的节点

---

# 工作流

按顺序执行。🧑 = 需要用户参与。

## 阶段 0 —— 配置校验

```bash
python scripts/fetch/fetch_mcp_data.py --check
```

## 阶段 1 —— MCP 数据抓取

```bash
python scripts/fetch/fetch_mcp_data.py
```

7 步序列拉取 MasterGo 全量数据。`getDsl` 必须最先调（否则 path.data / textRuns 永久丢失）。产物：`data/raw/`。

## 阶段 2 —— 归一化层级树 + 模块拆分

```bash
python scripts/normalize/normalize_to_tree.py
python scripts/prepare/split_modules.py
```

产物：`data/normalized/tree.md`（人工核对结构）、`data/modules/`（8 个模块完整设计数据 + `_index.json`）。

## 阶段 3 —— 字段完整性审计（可选）

```bash
python scripts/audit/scan_all_fields.py
python scripts/audit/extract_union_schema.py
```

## 阶段 4 —— 生成全量节点清单

```bash
python scripts/input/generate_variability_config.py   # → config/variability.json
```

全部约 416 个节点，默认标 `fixed`。

## 阶段 5 —— fixed / variable 分类 🧑

**这是整个 skill 最需要人类判断的步骤。** 步骤如下：

### 5.1 提取 TEXT 节点

读 `config/variability.json`，过滤出 `type: "TEXT"` 的节点。每个模块的 TEXT 节点数量大致是：banner 4 个、hotspot-frontline 3 个、market-analysis 8 个、recommendation-a 13 个、recommendation-b 24 个、buy-fund-cmb 1 个、compliance-notice 34 个、related-products 11 个。

### 5.2 逐模块应用判断原则

对每个模块的 TEXT 节点，按上面的**四原则**逐个判断。以列表形式呈现给用户，每行包含：节点 ID、节点名（设计稿图层名）、当前文本内容、建议分类、判断依据。

例如 `market-analysis` 模块：

| 节点ID | 图层名 | 当前文本 | 建议 | 依据 |
|---|---|---|---|---|
| 0:967 | 市场解读 | 市场解读 | variable | 模块标题，每期可能换 |
| 0:968 | … | 随着"十五五"规划落地… | variable | 正文段落 |
| 0:978 | 从国内看景气度看 | 从国内看景气度看 | fixed | 段落小标题，结构固定 |
| 0:979 | 从政策环境看 | 从政策环境看 | fixed | 段落小标题，结构固定 |
| 0:980 | 从海外市场需求上看 | 从海外市场需求上看 | fixed | 段落小标题，结构固定 |
| 0:981 | … | 行业处于政策高度友好… | variable | 正文段落 |
| 0:982 | … | 近期美国迎来史诗级… | variable | 正文段落 |
| 0:983 | … | 以上观点由华夏基金提供 | variable | 数据来源标注 |

`compliance-notice` 模块则是另一个极端——34 个 TEXT 节点几乎全部是合规条文、费用表格的列头/数值，**全部 `fixed`**。

### 5.3 用户确认

用户逐模块确认或调整。如果用户意见和启发式规则冲突，**以用户为准**——用户最了解自己的业务。

### 5.4 生成用户输入

确认后编辑 `config/variability.json`，然后：

```bash
python scripts/input/generate_user_input.py           # → data/input/user-input.json
```

## 阶段 6 —— 填写本期内容 🧑

用户编辑 `data/input/user-input.json`，替换为新一期文案。只改值，不动 `_` 开头的字段。

## 阶段 7 —— 生成

```bash
python scripts/render/generate_module_css.py
python scripts/render/generate_html.py
```

产物：`output/fund-h5/`（`index.html` + `css/` + `images/`）。

---

# 迭代

- **只换一期内容**：跳过阶段 0-5，直接改 `data/input/user-input.json` → 阶段 7
- **设计稿结构变了**：重跑阶段 1-2 → 阶段 4（**会覆盖 `variability.json`，先备份！**）→ 阶段 5-7
- **渲染问题**：查 `references/rules.md`

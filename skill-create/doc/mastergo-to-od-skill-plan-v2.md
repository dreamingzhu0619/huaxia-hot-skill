# 计划 v2：mastergo-to-od-skill（把 MasterGo 设计稿变成 OD skill 的 meta-skill）

> 生成时间：2026-07-13 ｜ 状态：待评审
> 基于 v1 评审 Q&A（`doc/mastergo-to-od-skill-review-qa.md`）重写

---

## 一、Context

输入一张 MasterGo 设计稿链接 + MCP 令牌，输出一个对应该稿风格、可装进 Open Design 的 OD design-template skill。

核心复用：`huaxia-hot-cmb/scripts/` 的通用脚本（抓数据 + 生成精确源 CSS），打包进 meta-skill 的 `pipeline-template/`，每张新稿复制一份跑。

**脚本能做的 vs agent 必须做的：**

| 脚本负责（机械） | agent 负责（判断） |
|---|---|
| fetch → normalize → split → 源 CSS | 模块语义命名与排序 |
| 全量节点清单生成 | 单实例/多实例判定 → CSS 策略 |
| 字段审计 | 品牌标语 vs 可变文本判定 |
| | 绝对定位 CSS → flow CSS 手工重写 |
| | 装饰 PATH/SVG → 内联 SVG 或 CSS 伪元素 |
| | 组件类型判定与 schema 设计 |
| | 写出 5 份 OD skill 文件 |

---

## 二、meta-skill 目录结构

```
mastergo-to-od-skill/
├── SKILL.md                       # meta-skill 入口：引导式工作流
├── GROWTH.md                      # 质量成长记录（每次被指出问题后追加）
├── pipeline-template/             # 通用 pipeline 脚本模板，每张稿复制一份
│   ├── config/
│   │   ├── project.config.json    # 骨架（designUrl=""、apiBaseUrl）
│   │   └── local.secret.json      # 骨架（mcpToken=""）
│   ├── .gitignore                 # ignore local.secret.json
│   └── scripts/
│       ├── fetch/fetch_mcp_data.py
│       ├── normalize/normalize_to_tree.py
│       ├── prepare/split_modules.py        # SLUG_MAP 清为 {}（sanitize 兜底）
│       ├── audit/scan_all_fields.py
│       ├── audit/extract_union_schema.py
│       ├── input/generate_variability_config.py
│       ├── render/generate_module_css.py
│       └── lib/css_core.py
├── data/                          # ★ pipeline 数据产出（raw / modules / tree / 源 CSS）
├── references/                    # 通用方法论（4+1 篇，不绑任何具体设计稿）
│   ├── pipeline.md                # 脚本运行顺序、产物、MCP 7 步原理、环境
│   ├── module-classification.md   # 单实例/多实例判定 + 品牌标语识别
│   ├── component-authoring.md     # 绝对→flow 转换 + 装饰元素处理 + 组件类型判定 + 图表契约
│   ├── od-skill-spec.md           # OD skill 通用骨架（frontmatter/SKILL.md/输出契约/安装）
│   └── gotchas.md                 # 通用排查清单（识别信号→排查方向→治本策略）
├── assets/
│   └── od-skill-template/         # OD 交付物思路框架（教 agent 怎么写，不给具体内容）
│       ├── SKILL.md               # 框架：frontmatter 骨架 + Workflow 结构 + 硬规则 + 输出契约
│       ├── content.template.json  # 框架：schema 组织方式 + 填写指引
│       └── references/
│           ├── component-templates.md   # 框架：模板写法规范
│           ├── components-schema.md     # 框架：组件类型分类体系
│           └── components-provenance.md # 框架：溯源表格式
└── output/                        # 最终交付的 OD skill
    └── .gitkeep
```

### 每张稿的运行期产物

```
output/<name>/
├── pipeline/                      # 工作区（从 pipeline-template 复制）
│   ├── config/  scripts/
│   ├── data/{raw,modules,normalized}
│   └── assets/styles/modules/*.css
└── <name>-od/                     # 最终交付的 OD skill（自包含）
    ├── SKILL.md
    ├── content.template.json
    ├── example.html
    ├── assets/
    │   ├── template.html
    │   └── styles/
    │       ├── components.css     # flow 组件样式
    │       └── fixed/             # 单实例模块原样 CSS
    └── references/
        ├── component-templates.md
        ├── components-schema.md
        └── components-provenance.md
```

---

## 三、核心方法论（meta-skill 教给 agent 的判断力）

### 3.1 两个正交的判断轴

**轴一：实例数 → 决定 CSS 策略**

| 模块类型 | CSS 策略 | 原因 |
|---|---|---|
| 单实例（banner、结束语、合规区） | 源 CSS 原封搬进 `fixed/` | 永远只有一份，即使标题每期会变 |
| 多实例（推荐产品 N 页、分论点 N 段） | 手写 flow CSS 进 `components.css` | 同一套样式重复 N 次，必须自适应高度 |

**轴二：TEXT 可变性 → 决定 content.template.json 暴露什么**

| TEXT 类型 | 处理 |
|---|---|
| 品牌标语/装饰文字（"热点速递"、"买基金来招行"） | 硬编码在模板里，不暴露 |
| 其余所有 TEXT（含 banner 标题、正文、日期、数据来源） | 暴露为 content.template.json 的可填字段 |

两轴正交——banner 是单实例（CSS 进 fixed/），但标题是 variable（字段暴露）。

### 3.2 绝对定位 → flow CSS 的转换方法

源 CSS（`css_core.py` 产出）是全量 `position:absolute; left:Xpx; top:Ypx`。多实例模块需要重写：

1. **从源 CSS 提取视觉数值**：颜色、字号、行高、字重、阴影、渐变参数、border-radius、opacity
2. **用 flexbox 重建布局**：`display:flex; flex-direction:column; gap:Npx` + `padding` 近似原始间距
3. **固定宽度保留，高度改为 auto**：容器宽度（如 355px 白卡）保留；高度由内容撑开
4. **装饰元素处理**：
   - 简单装饰（高光、分隔线）→ CSS 伪元素（`::before`/`::after`）
   - 复杂装饰（角标梯形、手形 SVG）→ 从 modules JSON 的 `path[].data` 提取路径数据，手写内联 SVG
5. **语义 class 命名**：不保留 `.n-{id}`，用 `.hot-body`、`.market-point` 等语义名

### 3.3 数据先行原则

所有判断必须在 pipeline 数据到位之后。agent 每一步都在**读具体数据**做决策：

- `tree.md` → 知道模块数量、层级、节点结构
- `modules/*.json` → 知道 TEXT 节点、PATH 装饰、SVG 资源、颜色/字体
- `assets/styles/modules/*.css` → 知道精确视觉数值，提取后填入 flow CSS

---

## 四、实施步骤

### Step 1 —— 搭骨架 + 复制脚本

- 建 `mastergo-to-od-skill/` 下所有一级目录
- 从 `huaxia-hot-cmb/scripts/` 用 shell `cp` 复制 8 个通用脚本到 `pipeline-template/scripts/`
  - **不复制** `generate_html.py`、`generate_user_input.py`（绑死华夏 H5 渲染）
- 复制 `project.config.json` + `local.secret.json` 骨架，清空 URL/Token
- 编辑 `split_modules.py`：`SLUG_MAP = {}`（注释说明可选填）
- 写 `.gitignore`：ignore `local.secret.json`

### Step 2 —— 写 references（从华夏素材抽象通用方法论）

| 文件 | 内容 | 华夏素材 |
|---|---|---|
| `pipeline.md` | 脚本运行顺序、产物说明、MCP 7 步原理、环境依赖 | `huaxia-hot-cmb/SKILL.md`(工作流/环境) + `doc/mcp数据提取.md`(7步/raw结构) |
| `module-classification.md` | 如何判定单实例/多实例、如何识别品牌标语 vs 可变文本 | `huaxia-hot-cmb/SKILL.md`「核心方法论」四原则的通用部分 |
| `component-authoring.md` | 绝对→flow 转换五步法、装饰元素处理（伪元素 vs 内联 SVG）、组件类型判定（文本/图表/表格/卡片）、图表样式契约 | 华夏实践中总结的通用做法 + rules.md 里可抽象的规则 |
| `od-skill-spec.md` | OD frontmatter 格式、SKILL.md 结构规范、输出契约、安装目录 | `huaxia-hot-cmb-od/SKILL.md`(od 块/工作流/契约) + 记忆 `reference_od_skill_injection` + `reference_od_client_install_dir` |
| `gotchas.md` | 通用排查清单：每类问题的识别信号 + 排查方向 + 治本策略。从 rules.md 的 11 条抽象，去华夏节点 ID。 | `huaxia-hot-cmb/references/rules.md` #1~#11 |

文风统一：**规则 + 判据 + 示例**（不绑具体设计稿的通用示例）。

### Step 3 —— 写 od-skill-template 思路框架

5 份文件，每份只教 agent **怎么写**，不给具体内容：

| 文件 | 内容 |
|---|---|
| `SKILL.md` | OD frontmatter 骨架（`od:` 块各字段说明）+ Workflow 通用结构（Step 0~4）+ 硬规则（样式权威、默认 fixed、保真取值）+ 输出契约格式 |
| `content.template.json` | schema 组织方式（每模块一档、数组=多页、`_` 开头=注释字段）+ 填写指引 |
| `component-templates.md` | 模板写法规范（每组件一节、静态 HTML 骨架 + 图表算法伪代码 + 可变槽位标注 `{{ }}`） |
| `components-schema.md` | 组件类型分类体系（文本型/图表型/表格型/卡片型…）的判定标准与 schema 格式 |
| `components-provenance.md` | 溯源表格式（样式 ↔ 源节点 id 的对照表结构） |

### Step 4 —— 写 meta-skill SKILL.md（引导式工作流）

frontmatter：`name: mastergo-to-od-skill` + description（触发词：把 MasterGo 设计稿转成 skill / 生成设计稿 skill / mastergo 转 od skill 等）。功能类 skill，无 `od:` 块。

工作流（🧑 = 人工确认点）：

| Step | 内容 | 数据依赖 |
|---|---|---|
| **0 输入&建工作区** | 拿 designUrl+token → 复制 `pipeline-template` → `output/<name>/pipeline/` → 填 config → `fetch --check` | 无 |
| **1 抓取(脚本)** | fetch → normalize → split → 得 raw/modules/tree | 无 |
| **2 模块审阅 🧑** | 读 tree.md + _index.json；语义命名 + 按 position.y 排序；用户确认 | tree.md, _index.json |
| **3 源CSS(脚本)** | generate_variability_config + generate_module_css → 源 CSS + 全量节点清单 | modules/*.json |
| **4a 实例数判定 🧑** | 逐模块判断单实例/多实例 → 决定 CSS 策略（fixed/ vs flow） | tree.md, 源 CSS |
| **4b 品牌标语识别 🧑** | 逐模块列出 TEXT 节点；标出品牌标语/装饰文字（fixed）；其余 variable；用户确认 | modules/*.json |
| **5 组件 schema 🧑** | 判定组件类型、定 content schema（多页数组 vs 单页）；用户确认 | modules/*.json, 4a/4b 结论 |
| **6 产出 OD skill** | 从 `od-skill-template` 思路框架出发，逐文件写出 5 份交付物 | 以上全部 |
| 6a | lift 单实例模块 CSS → `fixed/`（原封复制） | 源 CSS, 4a 结论 |
| 6b | 手写 flow CSS → `components.css`（提取视觉值 + flex 布局 + 装饰处理） | 源 CSS, modules JSON, 4a 结论 |
| 6c | 写 component-templates.md（每个多实例组件手写静态 HTML 模板 + 图表算法） | modules JSON, 4a/4b/5 结论 |
| 6d | 写 components-schema.md + components-provenance.md | 以上全部 |
| 6e | 写 content.template.json（暴露 variable 字段，隐藏 brand-slogan） | 4b 结论 |
| 6f | 写 SKILL.md（填 frontmatter、组件描述、工作流、硬规则） | 以上全部 |
| 6g | 拼 template.html + example.html | 源 CSS, components.css, fixed/ |
| **7 验收** | 开 example.html；对照 live MasterGo 逐处核还原度；查 OD 契约 | |
| **8 装进 OD（可选）** | 按 `od-skill-spec.md` 把 `<name>-od/` 拷进 OD design-templates | |

迭代：设计稿变了重跑 Step 1~3；新坑沉淀到 `gotchas.md`。

---

## 五、复用的现有资产

| 用途 | 现有文件 |
|---|---|
| 抓取脚本 | `huaxia-hot-cmb/scripts/fetch/fetch_mcp_data.py` |
| 归一化/拆分 | `scripts/normalize/normalize_to_tree.py`、`scripts/prepare/split_modules.py` |
| 精确源 CSS 引擎 | `scripts/render/generate_module_css.py` + `scripts/lib/css_core.py` |
| 节点清单/审计 | `scripts/input/generate_variability_config.py`、`scripts/audit/*` |
| 方法论素材 | `huaxia-hot-cmb/SKILL.md`（核心方法论）、`huaxia-hot-cmb-od/`（OD skill 范本） |
| MCP 数据结构 | `huaxia-hot-cmb/doc/mcp数据提取.md` |
| 坑与调试 | `huaxia-hot-cmb/references/rules.md`（#1~#11） |

**不复制**：`generate_html.py`、`generate_user_input.py`（绑死华夏 H5 渲染，OD 路线不用）。

---

## 六、验证方式

1. **脚本可跑**：`python output/<name>/pipeline/scripts/fetch/fetch_mcp_data.py --check` 通过
2. **数据落盘**：跑完 fetch→normalize→split，`data/{raw,modules,normalized}` 有产物
3. **源 CSS**：`generate_module_css.py` 产出 `assets/styles/modules/*.css`
4. **交付 skill 自洽**：`<name>-od/example.html` 能独立打开，`<section data-od-id>` 齐
5. **还原度**：对照 live 设计稿逐模块核对，无 emoji/默认0/占位近似
6. **冒烟**：用华夏 URL 跑一遍，产出逼近 `huaxia-hot-cmb-od`（证明方法论迁移成立）。有第二张设计稿更好。

---

## 七、已知风险

- `split_modules.py` 的 d2c 片段匹配可能需人工核对（非华夏稿的模块↔d2c 对齐）
- 缺少通用 ground-truth 渲染器（`generate_html.py` 未打包）。缓解：验收对照 live 设计稿
- 仅用华夏一张稿验证泛化能力。缓解：风险标注，后续用第二张稿冒烟
- Windows：`python`（非 python3）；读文件用 Read tool（避 GBK 乱码）；bash 用 Git Bash 正斜杠

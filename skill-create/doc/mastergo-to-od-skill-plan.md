# 计划：mastergo-to-od-skill（把 MasterGo 设计稿变成 OD skill 的 meta-skill）

> 生成时间：2026-07-13 ｜ 状态：待评审
> 一句话：写一个 meta-skill，输入「MasterGo 设计稿链接 + MCP 令牌」，输出一个对应该稿风格、可装进 Open Design 的 OD design-template skill（形如 `huaxia-hot-cmb-od`）。复用 `huaxia-hot-cmb/scripts/` 那套「抓精确数据 + 生成精确源 CSS」的脚本。

---

## 一、Context（为什么做）

现状是「一张设计稿 → 手工做一个 OD skill」，已在 `huaxia-hot-cmb`（pipeline 工作区）+ `huaxia-hot-cmb-od`（交付的 OD skill）这对目录上跑通并沉淀了大量方法论。设计稿一多，手工做不过来。

- **输入**：一个 MasterGo 设计稿链接 + MasterGo MCP 个人令牌。
- **输出**：一个对应该设计稿风格、可交付/可装进 Open Design 的 OD design-template skill。
- **复用点（用户诉求）**：`huaxia-hot-cmb/scripts/` 里「把最精确数据抓下来 + 生成精确源 CSS」的脚本基本通用，要**打包进 meta-skill 作为模板**，对任意新稿复用。

探查确认的关键事实：

- **通用脚本**：`fetch_mcp_data.py`（URL+token→raw，7 步序列、getDsl 优先零丢失）、`normalize_to_tree.py`、`split_modules.py`（模块=根 FRAME 直接子节点；只有 `SLUG_MAP` 是华夏专属，有 sanitize 兜底）、`render/generate_module_css.py` + `lib/css_core.py`（精确源 CSS 引擎）、`audit/*`、`input/generate_variability_config.py`。跑一遍即得「精确数据 + 源 CSS」。
- **脚本给不了、必须 agent 判断/手写**：模块语义命名与顺序（按 position.y）、fixed/variable 分类、组件类型与 schema、把固定模块 CSS lift 出来 + flow 化、写 `component-templates.md`、写 OD `SKILL.md`、`content.template.json`、`example.html`、溯源表。
- **华夏专属、不打包**：`render/generate_html.py`、`input/generate_user_input.py`（绑死华夏 user-input schema，是「第一类纯 H5」渲染器；OD 路线用不到——OD 让 agent 现场写静态 HTML）。

用户已确认三点：① **引导式 + 人工确认点**（非一把梭）；② **打包通用脚本模板副本**（自包含、可移植）；③ 单拎一个 **`output/`**，产出的 skill 放进去。

---

## 二、目标目录结构

### meta-skill 本体（写在现有空目录 `skill-create\mastergo-to-od-skill\`）

```
mastergo-to-od-skill/
├── SKILL.md                       # meta-skill 入口：两个输入 + 引导式工作流（Step0~8，含 🧑 确认点）
├── pipeline-template/             # ★ 打包的通用 pipeline，每做一张稿就复制一份
│   ├── config/
│   │   ├── project.config.json    # 骨架：designUrl=""、apiBaseUrl 等（复制自华夏，清空 url）
│   │   └── local.secret.json      # 骨架：mcpToken=""
│   └── scripts/
│       ├── fetch/fetch_mcp_data.py            # 原样复制（通用）
│       ├── normalize/normalize_to_tree.py     # 原样复制
│       ├── prepare/split_modules.py           # 复制 + SLUG_MAP 清成 {}（走 sanitize 兜底，注释说明可选填）
│       ├── audit/scan_all_fields.py           # 原样复制
│       ├── audit/extract_union_schema.py      # 原样复制
│       ├── input/generate_variability_config.py  # 原样复制（全量节点清单，默认 fixed）
│       ├── render/generate_module_css.py      # 原样复制（精确源 CSS）
│       └── lib/css_core.py                    # 原样复制（核心引擎）
├── references/
│   ├── pipeline.md            # 脚本各干嘛/运行顺序/产物/环境坑 + MCP 7 步与合并优先级 + raw 结构
│   ├── fixed-variable.md      # fixed/variable 判断方法论（三档 + 四原则 + 硬规则），设计稿无关、可复用
│   ├── component-authoring.md # 组件类型判定(3信号) + 固定CSS lift + flow化(相对定位) + 写模板(烘焙SVG取path) + 图表契约 + 溯源
│   ├── od-skill-spec.md       # 交付 OD skill 骨架 + frontmatter/od 契约 + SKILL.md 撰写指南 + OD 注入机制 + 安装到 OD
│   └── gotchas.md             # css_core/渲染已知坑（rules.md #1~#11，尤其 #10 banner 三连坑），重生成/手写 CSS 避坑
├── assets/
│   └── od-skill-template/     # 交付物脚手架（带 {{占位}} + 内联指引，agent 逐张填）
│       ├── SKILL.md               # 模板化自 huaxia-hot-cmb-od/SKILL.md
│       ├── content.template.json  # schema 速查表模板
│       └── references/
│           ├── component-templates.md
│           ├── components-schema.md
│           └── components-provenance.md
└── output/
    └── .gitkeep               # 每次运行在此创建 output/<name>/
```

### 每做一张稿的产物（运行期生成，落在 `output/<name>/`）

```
output/<name>/
├── pipeline/                  # = huaxia-hot-cmb 等价物（工作区，中间产物，保留供重跑/排查）
│   ├── config/  scripts/      # 从 pipeline-template 复制来
│   ├── data/{raw,modules,normalized}
│   ├── assets/styles/modules/*.css      # 精确源 CSS
│   └── references/rules.md               # 本稿新发现的坑（可选沉淀）
└── <name>-od/                # ★ 最终交付的 OD skill（自包含，可直接拎进 OD design-templates）
    ├── SKILL.md  content.template.json  example.html
    ├── assets/{template.html, styles/{components.css, fixed/}}
    └── references/{component-templates.md, components-schema.md, components-provenance.md}
```

> 脚本用 `SKILL_ROOT = Path(__file__).resolve().parents[2]` 定位，读 `config/` 写 `data/`。复制到 `output/<name>/pipeline/` 后运行，SKILL_ROOT 自动解析到该目录，数据就落在 `pipeline/` 内——无需改脚本路径逻辑。

---

## 三、实施步骤

### 1. 搭 meta-skill 骨架 + 打包脚本
- 建 `mastergo-to-od-skill/` 下 `pipeline-template/ references/ assets/od-skill-template/ output/`。
- 用 shell `cp` 把 8 个通用脚本 + 2 个 config 从 `huaxia-hot-cmb/` 复制进 `pipeline-template/`（脚本大，用 `cp` 不用 Read+Write）。**不复制** `generate_html.py`、`generate_user_input.py`。
- 编辑 `pipeline-template/scripts/prepare/split_modules.py`：`SLUG_MAP = {}`（注释：可选，命中中文名给英文 slug，否则 sanitize 保留原名）。
- 编辑 `pipeline-template/config/*.json`：清空 `designUrl`/`mcpToken`，`projectName` 留占位。

### 2. 写 references（把方法论从散落文档/记忆收敛成 4+1 篇）
| 文件 | 数据来源 |
|---|---|
| `pipeline.md` | `huaxia-hot-cmb/SKILL.md`(工作流/环境) + `doc/mcp数据提取.md`(7步+合并优先级+raw结构) + `doc/HANDOFF*.md` |
| `fixed-variable.md` | `huaxia-hot-cmb/SKILL.md`「核心方法论」整段（三档/四原则/硬规则），近乎照搬 |
| `component-authoring.md` | `huaxia-hot-cmb-od/references/*` 的**通用做法** + 记忆 `feedback_consume_full_node_data`/`feedback_flow_relative_positioning`/`feedback_module_data_source`/`feedback_fidelity_raw_data` |
| `od-skill-spec.md` | `huaxia-hot-cmb-od/SKILL.md`(od frontmatter/workflow/输出契约) + 记忆 `reference_od_skill_injection`(只有 SKILL.md 正文被注入) + `reference_od_client_install_dir`(装进 OD 的确切目录) |
| `gotchas.md` | `huaxia-hot-cmb/references/rules.md` #1~#11 提炼 + 记忆 `feedback_debug_with_data_not_guesses`(量像素/比 d2c，别猜) |

### 3. 写 assets/od-skill-template 脚手架
以 `huaxia-hot-cmb-od/` 各文件为蓝本，替换华夏专属内容为 `{{占位}}` + 内联「怎么填」指引：
- `SKILL.md`：保留 od frontmatter、「内容优先对话输入」、Workflow（起页/逐组件替换/图表契约/组装自检/收尾）、硬规则、输出契约；组件名/字段占位化。
- `content.template.json`：保留注释框架（这是什么/每模块几页/图表怎么填/哪些不用填），组件与字段占位化。
- `references/*`：三份对照表/配方/schema 的骨架 + 填写指引。

### 4. 写 meta-skill SKILL.md（引导式工作流）
frontmatter：`name: mastergo-to-od-skill` + description（触发词：把 MasterGo 设计稿转成 skill / 生成设计稿 skill / mastergo 转 od skill 等）。**功能类 skill（在 Claude Code 里跑），不是 design-template，无 `od:` 块。**

工作流（🧑 = 人工确认点）：

| Step | 内容 |
|---|---|
| **0 输入&建工作区** | 拿 designUrl+token → 复制 `pipeline-template`→`output/<name>/pipeline/` → 填 config → `fetch --check` |
| **1 抓取(脚本)** | fetch → normalize → split → 得 raw/modules/tree |
| **2 模块审阅 🧑** | 读 tree.md + _index.json；语义命名 + 按 position.y 定顺序；用户确认 |
| **3 源CSS(脚本)** | generate_variability_config + generate_module_css → 源 CSS + 全量节点清单 |
| **4 fixed/variable 分类 🧑** | 按 `references/fixed-variable.md`，逐模块列 TEXT 节点表；用户确认 |
| **5 组件 schema 🧑** | 按 `references/component-authoring.md` 判定组件类型、定 content schema（哪些多页数组）；用户确认 |
| **6 产出 OD skill** | 从 `assets/od-skill-template` 脚手 `output/<name>/<name>-od/`；lift 固定 CSS→fixed/；搭 components.css(flow)；写三份 references；写 SKILL.md + content.template.json；拼 template.html + example.html。全程遵 `gotchas.md` |
| **7 验收** | 开 example.html；对照 live MasterGo 逐处核还原度；查 OD 契约（每 section 带 data-od-id、css/ 同级、图走 CDN、高度自适应） |
| **8 装进 OD（可选）** | 按 `references/od-skill-spec.md` 把 `<name>-od/` 拷进 OD design-templates 目录 |

迭代：设计稿变了重跑 Step1-3；新坑沉淀到 `output/<name>/pipeline/references/rules.md` 并回灌 meta 的 `gotchas.md`。

---

## 四、复用的现有资产（照抄/参考，不重写）

| 用途 | 现有文件 |
|---|---|
| 抓取脚本(URL+token) | `huaxia-hot-cmb/scripts/fetch/fetch_mcp_data.py`（支持 `--check`/`--design-url`/`--token`/`--dry-run`） |
| 归一化/拆分 | `scripts/normalize/normalize_to_tree.py`、`scripts/prepare/split_modules.py` |
| 精确源 CSS 引擎 | `scripts/render/generate_module_css.py` + `scripts/lib/css_core.py` |
| 节点清单/审计 | `scripts/input/generate_variability_config.py`、`scripts/audit/*` |
| fixed/variable 方法论 | `huaxia-hot-cmb/SKILL.md`「核心方法论」段 |
| OD skill 范本(全套) | `huaxia-hot-cmb-od/`（SKILL.md、content.template.json、component-templates.md、components-schema.md、components-provenance.md、template.html、example.html、styles/） |
| MCP 数据结构/合并优先级 | `huaxia-hot-cmb/doc/mcp数据提取.md` |
| 坑与调试法 | `huaxia-hot-cmb/references/rules.md`（#1~#11） |
| 记忆(自动加载) | `feedback_fidelity_raw_data`/`feedback_module_data_source`/`feedback_flow_relative_positioning`/`feedback_consume_full_node_data`/`feedback_debug_with_data_not_guesses`/`reference_od_skill_injection`/`reference_od_client_install_dir` |

---

## 五、验证方式（端到端）

1. **脚本可跑**：`python output/<name>/pipeline/scripts/fetch/fetch_mcp_data.py --check` 通过（配置/依赖/URL 解析 OK）。无 token 时用华夏 URL/token 或 `--dry-run` 冒烟。
2. **数据落盘**：跑完 fetch→normalize→split，`pipeline/data/{raw,modules,normalized}` 有产物、模块数=根 FRAME 直接子节点数。
3. **源 CSS**：`generate_module_css.py` 产出 `assets/styles/modules/*.css`，每条规则带 `/* 0:xxx */` 溯源注释。
4. **交付 skill 自洽**：`<name>-od/example.html` 能独立打开，8/N 个 `<section data-od-id>` 齐、css/ 同级、图走 CDN、高度自适应。
5. **还原度**：对照 live MasterGo 设计稿逐模块核对（固定样式取源 CSS、异形取 modules JSON path，无 emoji/默认0/占位近似）。
6. **可复用性冒烟**：用华夏那张 URL 跑一遍 meta-skill，产出应逼近现有 `huaxia-hot-cmb-od`（证明方法论迁移成立）。

---

## 六、已知风险 / 待定

- 缺少「pipeline 产出的原稿全量渲染」做像素级 ground-truth（`generate_html.py` 绑死华夏 schema，未打包）。缓解：验收对照 live 设计稿；后续如需可另做通用 ground-truth 渲染器（本计划不含）。
- `split_modules.py` 的 d2c 片段按顶层 div left/top 就近匹配，非华夏稿可能需人工核对模块↔d2c 对齐（Step 2 审阅时确认）。
- Windows：一律 `python`（非 python3）；探查脚本写文件再 Read（控制台中文 GBK 乱码）；bash 为 Git Bash 用正斜杠。

# mastergo-to-od-skill 方案评审 Q&A

> 2026-07-13 ｜ 逐题问答，每个答案用于后续修订方案

---

## Q1: flow 化的具体做法是什么？

**结论：固定模块和可变模块是两套完全不同的策略。**

### 固定模块 → 源 CSS 原封不动搬进 `fixed/`

banner（`00-banner.css`）、buy-fund-cmb（`05-buy-fund-cmb.css`）、compliance-notice（`06-compliance-notice.css`）三个文件是 `css_core.py` 产出的**直接复制**。全量绝对定位、全部 `.n-{id}` 选择器、所有节点一个不落。HTML 结构完全对应。**零改造。**

### 可变模块 → 手工重写为 flow CSS

热点前线、市场解读、推荐理由、相关产品四个模块的源 CSS（全量绝对定位）被**全部丢弃**，agent 手写了 `components.css`：

| 源 CSS 的做法 | flow 版的做法 |
|---|---|
| `.n-0-958` 绝对定位 `left:17px; top:40.24px` | `.hot-body` flex 子元素，靠父容器 `padding: 40px 17px 12px` + `gap: 8px` 定位 |
| `.m-01-*` 固定 `height: 236.24px` | 高度自适应（内容撑开） |
| 角标是 5 个 PATH 节点（`0:952`~`0:956`）叠加，各自绝对定位 + blur/filter | **手写一套内联 SVG**（`viewBox="-31 -8 170 47"`），渐变/发光/模糊全部手算 |
| CTA 按钮高光 `0:1363` 是独立 PATH 节点 | CSS `::before` 伪元素 + `linear-gradient` |
| 每处样式绑在 `.n-{id}` 上 | 语义 class（`.hot`、`.market-point`、`.rec-head`），**从源 CSS 中提取视觉值**（颜色、字号、阴影、渐变参数）填入 |

### 关键点

1. **flow 化不是脚本能做的。** agent 读源 CSS + modules JSON → 理解空间意图 → 手写 flexbox/gap/padding/SVG。输入是源 CSS 的**视觉数值**（提取），输出是**新的布局逻辑**（创作）。

2. **装饰元素两条路径：** 简单的（CTA 高光）→ CSS 伪元素；复杂的（角标梯形、奶油手）→ 手写内联 SVG，路径数据从 modules JSON 的 `path[].data` 提取。

3. **固定模块的判断标准不是"所有 TEXT 都是 fixed"，而是整个模块在 OD 里完全不可变。** 源 CSS 直接搬。

### 对方案的影响

Step 6 里"搭 components.css(flow)"六个字严重低估了实际工作量。需要展开为完整的方法论：如何从源 CSS 提取视觉值、如何选择 flex 布局参数、如何处理装饰性 PATH/SVG 节点。

---

## Q2: od-skill-template 脚手架怎么做？

**结论：不能从华夏改，必须从零写一套通用思路框架。**

不同金融机构（华夏 vs 中信 vs ...）的营销长图制式完全不同——模块划分不同、组件结构不同、命名不同。如果把华夏的文件改成 `{{占位}}`，换一家机构时占位符本身就不匹配。

正确做法：脚手架应该是**教 agent 怎么写的思路框架**，而不是填占位的内容模板。每份文件告诉 agent：

- 这个文件的作用是什么
- 它包含哪些必要章节/字段
- 怎么写（从哪里取数据、遵循什么规则）
- 什么不能写（硬约束）

具体到 5 个文件：

| 文件 | 脚手架应该给什么 |
|---|---|
| `SKILL.md` | OD frontmatter 骨架 + Workflow 框架（Step 0~4 的通用结构）+ 硬规则（样式权威、默认 fixed、保真取值）+ 输出契约格式。**不给**具体模块名、具体组件描述。 |
| `content.template.json` | schema 的组织方式（每模块一档、数组表示多页、`_` 开头是注释字段）+ 填写指引。**不给**具体字段名和示例值。 |
| `component-templates.md` | 模板的写法规范（每个组件一节、含静态 HTML 骨架 + 图表算法伪代码 + 可变槽位标注）。**不给**具体组件的 HTML。 |
| `components-schema.md` | 组件类型分类体系（文本型/图表型/表格型/卡片型…）的判定标准。**不给**华夏的具体组件。 |
| `components-provenance.md` | 溯源表的格式（样式 ↔ 源节点 id 的对照表结构）。**不给**具体映射。 |

### 对方案的影响

计划 Step 3 的标题"替换华夏专属内容为 `{{占位}}`"是错误方向。应改为"从零编写通用思路框架，教 agent 如何为任意设计稿写出这 5 份文件"。

---

## Q3: 模块走 fixed/ CSS 还是 flow CSS 的判断标准是什么？

**结论：看模块是否多实例，不看 TEXT 是否可变。两件事正交。**

### CSS 策略（fixed/ vs flow）

| 模块类型 | CSS 放哪 | 原因 |
|---|---|---|
| 单实例模块（banner、银行结束语/合规、品牌区） | `fixed/XX-name.css` | 永远只有一份，即使里面的标题/正文每期会变 |
| 多实例模块（推荐产品 2~3 页、市场解读分论点 N 段） | `components.css`（flow） | 同一套样式重复 N 次，必须用 flow 让高度自适应内容量 |

### 内容可变性（content.template.json 暴露什么）

- 除品牌标语（"热点速递"、"买基金来招行"这类装饰性固定文字）外，**其余 TEXT 都有可能是 variable**——包括 banner 标题。
- 内容可变性决定 `content.template.json` 里哪些字段暴露给用户填，与 CSS 策略无关。

### 两件事的关系

```
              单实例模块          多实例模块
TEXT variable    banner 标题       推荐理由正文
                → fixed/ CSS      → components.css
                → 字段暴露给用户    → 字段暴露给用户

TEXT fixed       品牌标语           装饰角标文字
                → fixed/ CSS      → components.css（硬编码在模板里）
                → 不暴露            → 不暴露
```

### 对方案的影响

计划 Step 4 "fixed/variable 分类" 这个标题容易误导（暗示 fixed 文本 → fixed CSS）。应拆成两个独立步骤：
- **Step 4a: 模块实例数判定** — 单实例 vs 多实例 → 决定 CSS 策略
- **Step 4b: TEXT 可变性判定** — 品牌标语 vs 其余 → 决定 content.template.json 暴露哪些字段

---

## Q4: references（4+1 篇）应该怎么写？

**结论：抽象成通用方法论，不绑华夏具体案例。**

计划列的数据来源（`huaxia-hot-cmb/SKILL.md`、`rules.md`、记忆文件）是**素材**，不是**范本**。写 references 时需要从华夏案例中提炼通用规则，而不是把华夏的节点 ID、颜色值、模块名写进去。

每篇 reference 的写法：

| 文件 | 应该是 |
|---|---|
| `pipeline.md` | 脚本运行顺序、产物说明、MCP 7 步原理、环境依赖。通用，不涉及具体设计稿。 |
| `fixed-variable.md` | **通用判断方法论**：如何区分单实例/多实例模块、如何区分品牌标语/可变文本。不给华夏的具体模块名或文本内容。 |
| `component-authoring.md` | **通用转换方法论**：绝对→flow 的做法（flex 布局选择、视觉值提取、装饰元素处理）、组件类型判定、图表契约。不给华夏的具体 class 名或 SVG。 |
| `od-skill-spec.md` | OD skill 的通用骨架格式（frontmatter、SKILL.md 结构、输出契约、安装目录）。本身就通用，不涉及具体设计稿。 |
| `gotchas.md` | **通用排查清单**：每类问题的识别信号 + 排查方向 + 治本策略。把 rules.md 的 11 条从"华夏 0:xxx 节点"抽象为"当遇到 X 现象时，检查 Y 环节"。 |

### 对方案的影响

计划二里 references 的"数据来源"列表没问题（素材定位对），但缺少一步**抽象转化工作**——从素材到方法论不是"照搬"或"提炼"，而是重写。Step 2 的标题应从"写 references（把方法论从散落文档/记忆收敛成 4+1 篇）"改为"从华夏素材中抽象通用方法论，写成 4+1 篇 references"。

---

## Q5: 判断步骤的依赖关系——数据必须先到位

**结论：所有判断（实例数、品牌标语、CSS 策略）都依赖 pipeline 数据。数据不到位，什么都判断不了。**

pipeline 数据（raw → modules → tree → 源 CSS）是一切 agent 判断的基础：
- 没有 tree.md → 不知道有哪些模块、各自叫什么、节点结构长什么样
- 没有 modules JSON → 不知道每个模块里有哪些 TEXT 节点、PATH 装饰、SVG 资源
- 没有源 CSS → 没有视觉数值可以提取，flow 化无从做起

所以工作流里，**Step 1（抓取+拆分）必须在任何 🧑 确认点之前跑完**。原计划 Step 顺序大体正确（0 输入→1 抓取→2 模块审阅→3 源CSS→4 分类），但需要强调：Step 2~6 的每一个判断，agent 都在**读 pipeline 产出的具体数据**做决策，不是凭空判断。

输出结构保持原计划不变：
```
output/<name>/
├── pipeline/          # huaxia-hot-cmb 等价物（数据工作区）
└── <name>-od/         # huaxia-hot-cmb-od 等价物（交付的 OD skill）
```

---

## Q6: meta-skill 自身缺少 `data/` 板块

**结论：meta-skill 目录结构里，`data/` 应该和 `pipeline-template/`、`references/`、`assets/` 并列作为一级板块。**

原方案把数据藏在 `output/<name>/pipeline/data/` 下面，在目录结构图里不显眼。但数据是所有 agent 判断的基础（见 Q5），应该在 meta-skill 结构里明确标出来。

修正后的 meta-skill 结构：
```
mastergo-to-od-skill/
├── SKILL.md
├── pipeline-template/       # 通用脚本模板（每张新稿复制一份）
├── data/                    # ★ 新增：pipeline 产出的数据（raw/modules/tree/源CSS）
├── references/              # 通用方法论（4+1 篇）
├── assets/
│   └── od-skill-template/   # OD 交付物思路框架
└── output/                  # 最终交付的 OD skill
```

### 对方案的影响

原方案目录结构图缺少 `data/` 一级板块，需补上。

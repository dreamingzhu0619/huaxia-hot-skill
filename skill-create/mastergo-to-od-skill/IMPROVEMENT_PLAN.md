# MasterGo-to-OD-Skill 改进方案（终版）

> 基于 huaxia-hot-citc 实例的问题复盘 + 与用户的多轮讨论确认，最终确定的改进方案。

---

## 1. 核心设计决策

### 1.1 数据流：modules JSON 为唯一数据源

`split_modules.py` 融合所有 MCP 数据源（getDsl + getD2c + getDesignSvgs + extractSvg + getDesignTexts），产生 `data/<project>/modules/*.json`。后续所有步骤（提取样式、提取装饰、生成模板、组装）**只读 modules JSON，不再回到 raw/**。

```
data/raw/  (MCP 原始响应，只归档)
    │
    ▼  split_modules.py（融合全量 MCP 数据）
data/modules/*.json  ← 【唯一数据源】
    │
    ├── extract_styles.py      → styles.css
    ├── extract_decorations.py → decorations.html
    ├── generate_template.py   → template.html
    ├── generate_page.py       → page.html
    │
    ▼  build_html.py
output/example.html
```

### 1.2 Steps 顺序：判定先于生成

修正前的顺序是"生成 assets → 判定"（判定结果无法影响 decorations.html 的范围）。修正后：

```
Step 1: MCP 抓取（脚本）
Step 2: 归一化 + 模块拆分 + 数据融合（脚本 + 命名确认）
Step 3: 源 CSS + 缩放（脚本）
Step 4: 同类合并 + fixed/variable 判定（脚本初筛 + AI 确认）← 核心判断环节
Step 5: 生成 assets（全部脚本，读取 Step 4 的判定结果）
Step 6: 组装（脚本）
Step 7: 验收
Step 8: 装进 OD
```

**为什么 Step 4 必须在 Step 5 之前**：Step 4 的判定结果决定了 decorations.html 的范围——哪些固定 GROUP 子树整体进入。如果先提取 decorations 再判定，固定 GROUP（如"热点速递拷贝"角标）会被漏掉。

### 1.3 脚本 vs AI 的分工线

| 脚本负责（机械、确定） | AI 负责（语义、判断） |
|---|---|
| MCP 抓取 | 模块语义命名（英文 slug） |
| 归一化节点树 | 模块同类合并确认（读 `module-merging.md`） |
| 拆分模块 + 融合全量 MCP 数据 | TEXT 节点 fixed/variable 判定（读 `variable-classification.md`） |
| 骨架签名比对 + autoFixed 标记 | 图表区域确认（读 `chart-detection.md`） |
| 从 d2cCss 机械提取 → styles.css | slot 语义化重命名 |
| PATH→SVG, BITMAP→img, fixed GROUP → decorations.html | |
| 遍历节点树 + 规则翻译 → template.html | |
| 读索引 → page.html | |
| 组装 → example.html | |

**关键修正**：template.html 的 DOM 结构由 `generate_template.py` 脚本生成（遍历节点树 + 读判定标记 → 规则翻译）。AI 不手写 DOM、不判断布局方向。

---

## 2. 目录结构

### 2.1 Meta-Skill 顶层

```
mastergo-to-od-skill/
├── SKILL.md                           ← meta-skill 入口
├── GROWTH.md                          ← 质量成长记录
├── IMPROVEMENT_PLAN.md                ← 本文件
├── .gitignore
├── config/                            ← 项目配置骨架
├── scripts/                           ← 通用 pipeline 脚本
│   ├── fetch/fetch_mcp_data.py
│   ├── normalize/normalize_to_tree.py
│   ├── prepare/split_modules.py       ← 融合全量 MCP 数据
│   ├── render/generate_module_css.py
│   ├── analyze/diff_modules.py
│   ├── generate/
│   │   ├── extract_styles.py
│   │   ├── extract_decorations.py     ← 机械提取 + 固定 GROUP 子树
│   │   ├── generate_template.py       ← 新增：脚本生成 DOM
│   │   └── generate_page.py           ← 新增：脚本生成页面骨架
│   ├── assemble/build_html.py
│   └── lib/css_core.py
├── assets/shared/page.css             ← meta-skill 自身资源
├── data/<project>/                    ← 工作数据
│   ├── raw/                           ← MCP 原始响应（只读）
│   ├── normalized/                    ← tree.md + tree.json
│   ├── modules/                       ← 【唯一数据源】融合全量
│   └── analysis/                      ← merge_groups + diff_result
├── output/<project>-od/               ← OD skill 产物
└── references/                        ← 方法论文档
    ├── pipeline.md
    ├── gotchas.md
    ├── od-skill-spec.md
    ├── module-merging.md              ← 新增
    ├── variable-classification.md     ← 新增
    └── chart-detection.md            ← 新增
```

### 2.2 Output OD Skill 内部

```
output/<name>-od/
├── SKILL.md                           ← OD skill 入口（产品使用说明书）
├── content.template.json              ← 内容结构参考
├── assets/
│   ├── shared/
│   │   ├── page.css                   ← 页面容器 + 全局字体
│   │   └── page.html                  ← 【新增】全局页面骨架
│   └── <component>/                   ← 每个合并后的组件一个目录
│       ├── styles.css                 ← 精确视觉值（从 d2cCss 提取）
│       ├── decorations.html           ← PATH→SVG + BITMAP→img + 固定 GROUP 子树
│       └── template.html              ← DOM 骨架 + {{slots}}
├── output/
│   ├── example.html
│   └── template.html
└── references/
    ├── component-templates.md
    ├── components-schema.md
    └── components-provenance.md
```

**assets 数量 = 合并后的组件数量**，不是原始模块数量。如 9 个原始模块合并为 6 个组件类型 → assets/ 下 6 个组件目录 + 1 个 shared/。

---

## 3. 新增方法论文档

### 3.1 references/module-merging.md

模块同类合并的三步排查法：FRAME 名称 → 正文内容 → 固定元素/层级。

### 3.2 references/variable-classification.md

三档分类（fixed/variable/variable-all）+ 四原则（内容来源、文本功能、视觉元素类型、邻居关系）+ 脚本自动判定规则 + 固定装饰 GROUP 识别。

### 3.3 references/chart-detection.md

三级识别信号（强：数据来源文本 / 中：形状密度 / 辅助：名称+标题）+ 图表 → variable-all → `{{chart}}` 插槽。

---

## 4. 多实例处理方案

template.html 只定义"一个实例长什么样"。实例数量由 `content.template.json` 中数组长度决定。增加一个实例 = 数组里加一个 `{}`，删除一个实例 = 数组里删一个 `{}`。

```
template.html（单实例骨架）:
<section data-od-id="recommendation">
  <h2>{{mainTitle}}</h2>
  <p>{{body}}</p>
  <div>{{chart}}</div>
  <p>{{source}}</p>
</section>

content.template.json:
"recommendation": [
  { "mainTitle": "左手红利 右手低波", ... },
  { "mainTitle": "行业龙头加持", ... }
]

组装时：遍历数组 → 每个 {} 复制一份 template.html → 填充 → 拼接
```

---

## 5. 两个 SKILL.md 的分工

| | meta-skill SKILL.md | output OD SKILL.md |
|---|---|---|
| **位置** | `mastergo-to-od-skill/SKILL.md` | `output/<name>-od/SKILL.md` |
| **谁读** | 执行转换任务的 agent | OD 里的 agent |
| **做什么** | 教 agent 把设计稿转成 OD skill | 教 OD agent 用这个模板生成 H5 |
| **内容** | 通用工作流 + 脚本调用 + 方法论文档引用 | 具体组件清单 + fixed/variable 说明 + 拼装流程 |
| **绑定** | 不绑定任何设计稿 | 绑定一张具体设计稿 |

# 交接文档 —— 华夏热点速递 H5 → Open Design Skill

> 用途：当前对话上下文过长，导出此文档供**新窗口接手继续**。读完本文即可无缝继续。
> 生成时间：2026-07-11

---

## 0. 一句话现状

正在把「华夏基金热点速递 H5」做成一个能在 **Open Design** 里调用、生成高保真 H5 的 **design-template skill**（目录 `huaxia-hot-cmb-od`）。核心方法：**固定样式从原始数据取（尽量还原设计稿），内容 flow 化（可复制、高度自适应）**。目前已把 `recommendation`（推荐理由）组件做成样板，等用户确认后推广到其余组件。

---

## 1. 背景与目标

### 两类任务
1. **第一类**：针对某张设计稿写 skill，调用它生成对应 H5。两种用法：
   - 在 Claude Code 里直接生成 H5；
   - 上传到 **Open Design**（支持对生成的 H5 做 AI 帮写/AI 编辑）。
2. **第二类**：写一个能**自动生成第一类 skill** 的 meta-skill（设计稿多，不想一个个手写）。

### 三个关键目录（都在 `C:\Users\dream\Desktop\skill-create\`）
| 目录 | 作用 | 状态 |
|---|---|---|
| `huaxia-hot-cmb` | 原始 pipeline：MasterGo MCP 抓数据 → 生成像素级还原的 H5。**固定样式/数据的源头** | 成熟，最近修了 2 个 bug |
| `huaxia-hot-cmb-od` | **本次主战场**：给 Open Design 用的 skill | 半成品，在建 flow 组件 |
| `mastergo-to-od-skill` | 疑似第二类 meta-skill | **尚未探查** |

---

## 2. Open Design 生成 H5 的机制（已读源码确认）

源码在 `D:\dreamingzhu_main\研究生\summerintern-huaxia\AI-product\open-design`。

- OD 把技能分两类：`skills/`（功能技能）vs `design-templates/`（渲染设计产物）。**H5 属于 design-template**，`od.mode: prototype`，H5 用 `platform: mobile`。
- **调用方式**：建项目 `POST /api/projects`，body 带 `skillId`（=模板名）+ `designSystemId` + `metadata` + `pendingPrompt`（用户一句话）。
- **生成流程**：daemon 把整个模板目录 stage 进项目 `.od-skills/`，`composeSystemPrompt` 按序注入 DESIGN.md → tokens.css → **SKILL.md body（"严格照此 workflow"）**；agent 读种子/资源 → **每次现场生成 index.html** 写进项目 → 预览。
- **编辑**：生成后可用 Comment AI（圈元素让 agent 改源码）/ Edit（手改 HTML/CSS）/ Tweaks（改全局 token）。
- **design-template 目录范例**（`design-templates/web-prototype/`、`mobile-app/`）：`SKILL.md`(frontmatter+workflow) + `assets/template.html`(种子) + `references/` + `example.html`(画廊预览)。每个 `<section>` 带 `data-od-id` 供 Comment AI 定位。

---

## 3. 已确立的原则（务必遵守）

1. **保真第一**：跟原设计稿一致是最重要的。CSS 还是 SVG 无所谓，哪个还原得像用哪个。
2. **固定样式的取数来源**：
   - **首选 `huaxia-hot-cmb/assets/styles/modules/*.css`** —— 这些 CSS 本就是从原始数据精确提取的，方便直接用（含精确字体/色值/渐变/阴影，注释里标了节点 ID）。
   - CSS 表达不了的（异形，如角标梯形；烘焙 SVG）→ 才去翻**原始数据**。
   - **"原始数据"的准确定义 = `huaxia-hot-cmb/data/raw/` 里的全部数据**，不只是 getDsl。`getDsl` 是基底，其余 tool 返回的都是对它的**补充**（有些东西 getDsl 直接给不出）：
     - `01-getDsl/`（DSL 节点树，主基底）、`02-getMeta/`、`03-getDesignSections/`、`05-getDesignSvgs/`（SVG 导出）、`05-getDesignTexts/`（文本 runs）、`05-extractSvg/`、`07-getD2c/`（MasterGo 自己的 design-to-code CSS 导出）。
     - 追查某节点时应把这些**合起来看**，别只查 getDsl。
3. **只有"内容"才灵活**：推荐理由正文、产品名、图表数据、每类几张 —— 这些变；字体/颜色/间距/装饰/布局骨架不变。
4. **图表松绑**：MasterGo 上的图是用一堆矩形/形状拼的，每期换数据，**具体画法不用逐形状还原**，干净的数据驱动图即可。
5. **改脚本 / 修 bug 的铁律**（见 memory `feedback_fidelity_raw_data.md`）：
   - 修保真差异先追**原始数据 `data/raw` 全部**（getDsl 基底 + getD2c/getDesignTexts/getDesignSvgs 等补充），别肉眼猜改下游产物。
   - raw 有、提取没有 → 是脚本 bug，去改 `scripts/`，不在产物打补丁。
   - 修完必做两步：① 沉淀进 `huaxia-hot-cmb/references/rules.md`（该订正的订正）；② 重生成产物（`generate_module_css.py` 全量 + `generate_html.py`；`data/modules` 是上游不用重生成）。

---

## 4. 组件 / Schema 清单（7 大类）

判定"同一类"靠三信号：骨架签名 + frame 名字词根 + 正文语义/标题装饰。详见
`huaxia-hot-cmb-od/references/components-schema.md` 与 `content.template.json`。

| # | 组件 id | 类型 | 可变内容 | 备注 |
|---|---|---|---|---|
| 1 | banner 头图 | 固定 | 两行标题 | **不做 flow**，直接复用原渲染 |
| 2 | hotspot-frontline 热点前线 | 可复制 | 标题/正文/来源 | 蓝色角标(梯形) |
| 3 | market-analysis 市场解读 | 可复制 | 导语/分论点正文/免责 | 蓝色角标 + 金色高亮小标题 |
| 4 | **recommendation 推荐理由** | **可复制 1..N** | 标题/正文/图表/来源 | **已做成样板**；A/B 合并成一类 |
| 5 | buy-fund-cmb 买基金来招行 | 固定 | 无 | 完全不变，仅随流移位 |
| 6 | compliance-notice 合规声明 | 固定视觉/文字随产品 | 产品名/费率数值 | **假表格(PATH网格)**，不可自适应，文字要对齐网格 |
| 7 | related-products 相关产品 | 含可复制产品卡 | 产品名/代码/风险标签 | 一张卡内**一大一小**两产品：大的居中大CTA、小的靠右小CTA；卡背景淡蓝→白 |

- 蓝渐变白卡（`#E0EDFF→#FFFFFF` + `#EAF5FF` 阴影）是 2/3/4/7 共用基类骨架。
- 跨模块产品一致性：同一产品在 4/6/7 三处出现，换产品要联动。

---

## 5. huaxia-hot-cmb-od 当前文件状态

```
huaxia-hot-cmb-od/
├── SKILL.md                         # OD design-template 契约(frontmatter 对) + workflow(旧版:基于绝对种子)
├── content.template.json            # 用户填本期内容(按组件, recommendation 是数组) —— 已按 schema 预填范例
├── example.html                     # ⚠️ 旧种子(偏黄, bug 修复前拷的), 待重做
├── assets/
│   ├── template.html                # ⚠️ 旧种子(绝对定位 + 旧数据), 待重做/替换
│   ├── css/                         # ⚠️ 旧 CSS(bug 修复前), 已过时
│   └── components/                  # flow 组件预览(校验用, 最终不进 skill)
│       ├── recommendation.preview.html   # ✅ 最新样板: 固定样式取自源CSS, 内容flow, 图表数据驱动
│       └── cards.preview.html            # hotspot/market/related-products 早期 flow 版(装饰是手搓近似, 需按"取原数据"重做)
└── references/
    ├── components-schema.md         # ✅ 7类组件 + schema + 判定方法
    └── variable-slots.md            # 早期"节点级 fixed/variable"判断书(针对绝对种子)
```

**注意**：`assets/template.html` / `assets/css/` / `example.html` 是早先从 `huaxia-hot-cmb` **旧 output**（bug 修复前）拷的，现在既过时又跟 flow 方向冲突。后续要么删、要么用新数据重做。

---

## 6. huaxia-hot-cmb pipeline 备忘（作为数据源）

- **我的 pipeline 流程（用户原话）**：`raw → modules → CSS`。
  - `data/raw`（**原始数据 = MCP 各 tool 抓的全部**，getDsl 基底 + getD2c/getDesignTexts/getDesignSvgs 等补充）
  - → `data/modules/*.json`（把 raw 按模块拆分/归并出的 DOM+SVG+文本）
  - → `[generate_module_css.py + css_core.py]` → `assets/styles/modules/*.css`（源 CSS）
  - 之后 `[generate_html.py]` 再把 源CSS + modules 结构 + user-input 合成 `output/fund-h5/`（index.html+css+CDN图，渲染步骤）。
- 最终产物 `output/fund-h5/index.html`：8 模块，模块间已是 flow 布局(按 position.y)，模块内绝对定位。
- 图片走 MasterGo 公开 CDN（实测 HTTP 200 可达），无需本地图。
- **规则沉淀在 `references/rules.md`**（很全，含多条 bad case）。

### 最近修的 2 个脚本 bug（都在 `scripts/lib/css_core.py`，已沉淀 rules.md #5/#6/#8）
1. **多层 fill 层序**：`fill_to_css` 原假设数组 `[底→顶]` 而倒序，实为 `[顶→底]` 不该倒序。导致产品卡 `0:1369` 背景暖白盖住蓝白→偏黄。已去掉 `reversed()`。影响仅 2 节点(`0:952`/`0:1369`)。
2. **渐变越界色标**：CSS 的 `-10%` 色标转 SVG `<stop offset="-10%">` 被浏览器错误夹紧→CTA按钮高光偏白偏硬。新增 `_normalize_stops_range` 按插值归一到 `[0%,100%]`。影响 4 个负 offset stop。
- 已全量重生成 CSS + H5，核验通过。

### Windows 环境坑
- 用 `python`（不是 `python3`；后者 + 中文输出会 exit 49 崩）。
- 探查脚本**把结果写文件再 Read**，别直接 print 中文到控制台（GBK 崩）。
- bash 是 Git Bash，用 `/tmp`、正斜杠。

---

## 7. 下一步（TODO）

1. **[进行中] recommendation 样板确认**：`assets/components/recommendation.preview.html` 已按"固定样式取源CSS + 内容flow + 图表数据驱动"重做，等用户确认还原度。
2. **推广 flow 组件**（按同原则，装饰能CSS则CSS、异形/角标翻 raw 的 baked SVG）：
   - hotspot-frontline（蓝色角标**梯形**→ 用原始 path 几何，别用 clip-path 手搓）
   - market-analysis（角标 + 金色高亮小标题）
   - related-products（一大一小产品卡）
   - banner、compliance-notice → **固定**，直接复用原渲染，不做 flow
3. **整理 -od skill 目录**：清掉过时的 `assets/template.html`/`css/`/`example.html`（旧种子），把 flow 组件从"preview 校验形态"落成 skill 真正的生成物；预览文件最终**不进 skill**。
4. **落 SKILL.md workflow**：定义"读 `content.template.json` → 按组件模板拼装 → 写 index.html"的可跑通闭环（含 recommendation 数组渲染 N 张、每类几张）。待定：最终靠 **JS 运行时渲染** 还是 **agent 直接写静态 HTML**。
5. **让 skill 在 OD 真生效**：把 `huaxia-hot-cmb-od` 放进 OD 的 `design-templates/`（或 Settings→Skills 导入），实测能否被调用 + 预览。
6. **（更后）第二类 meta-skill**：探查 `mastergo-to-od-skill`，规划"自动把一张设计稿变成上述 design-template"。

---

## 8. 关键路径速查

- 主战场：`C:\Users\dream\Desktop\skill-create\huaxia-hot-cmb-od\`
- 数据源(源CSS)：`C:\Users\dream\Desktop\skill-create\huaxia-hot-cmb\assets\styles\modules\*.css`
- **原始数据(全部) = `...\huaxia-hot-cmb\data\raw\`**：`01-getDsl`(基底) / `02-getMeta` / `03-getDesignSections` / `05-getDesignSvgs` / `05-getDesignTexts` / `05-extractSvg` / `07-getD2c`。追查节点要合起来看，别只看 getDsl。
- 拆分后的模块数据：`...\huaxia-hot-cmb\data\modules\*.json`
- 规则沉淀：`...\huaxia-hot-cmb\references\rules.md`
- 最终 H5：`...\huaxia-hot-cmb\output\fund-h5\index.html`
- OD 源码：`D:\dreamingzhu_main\研究生\summerintern-huaxia\AI-product\open-design`
- 记忆(自动加载)：`C:\Users\dream\.claude\projects\C--Users-dream-Desktop-skill-create\memory\`（含 `feedback_fidelity_raw_data.md`、`feedback_chinese.md`）

---

## 9. 与用户协作提示

- **用中文**沟通。
- 用户很看重"跟设计稿一致"，且不太区分 CSS/SVG——只认还原度。
- 用户会逐处对照设计稿挑不一致，遇到时**先追 raw 判断是数据缺失还是提取错**，别急着手工改。
- 预览文件是**理解/还原度校验工具**，确认后要删、不进最终 skill。

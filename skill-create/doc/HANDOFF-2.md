# 交接文档 v2 —— 华夏热点速递 H5 → Open Design Skill（静态版已成型）

> 用途：本窗口上下文过长，导出此文档供**新窗口无缝接手**。读完本文即可继续。
> 生成时间：2026-07-11（承接 `doc/HANDOFF.md` v1，更深的管线/原则背景见 v1）

---

## 0. 一句话现状

「华夏基金热点速递 H5」的 Open Design design-template skill（`huaxia-hot-cmb-od`）**主体已完成**：
静态 HTML 形态、8 模块齐全、内容驱动（改 `content.template.json` 换一期）。本轮重点修完了**头图 banner
的一系列渲染坑**，并**发现了 3 个 css_core 管线根因（尚未落地修复）**。下一步主要是**根治 css_core + 重生成**，
以及把 skill 放进 OD 实测。

---

## 1. 关键路径

| 用途 | 路径 |
|---|---|
| **主战场（OD skill）** | `C:\Users\dream\Desktop\skill-create\huaxia-hot-cmb-od\` |
| 数据源 pipeline | `C:\Users\dream\Desktop\skill-create\huaxia-hot-cmb\` |
| 原始数据（全部 MCP tool） | `huaxia-hot-cmb\data\raw\`（01-getDsl 基底 + 02-getMeta + 03-getDesignSections + 05-getDesignSvgs/getDesignTexts/extractSvg + **07-getD2c** 权威 design-to-code） |
| 按模块归并的样式数据 | `huaxia-hot-cmb\data\modules\*.json`（**取数入口**，每模块含 node 树+assets.svgs+d2c） |
| 源 CSS | `huaxia-hot-cmb\assets\styles\modules\NN-*.css` |
| 管线脚本 | `huaxia-hot-cmb\scripts\`（prepare/split_modules.py、render/generate_module_css.py、render/generate_html.py、lib/**css_core.py**） |
| 规则沉淀（很全，含 #1~#10 bad case） | `huaxia-hot-cmb\references\rules.md` |
| 最终 H5（原 pipeline 产物） | `huaxia-hot-cmb\output\fund-h5\index.html` |
| OD 源码 | `D:\dreamingzhu_main\研究生\summerintern-huaxia\AI-product\open-design`（daemon/src/prompts/system.ts 的 composeSystemPrompt） |
| 记忆（自动加载） | `C:\Users\dream\.claude\projects\C--Users-dream-Desktop-skill-create\memory\` |

---

## 2. huaxia-hot-cmb-od 现状（已成型）

```
huaxia-hot-cmb-od/
├── SKILL.md                       ★ OD 契约(frontmatter) + 静态拼装工作流；含"用户输入只有 content.template.json"说明
├── content.template.json          ★ 用户唯一要填的文件：改字段换内容，数组元素数=页数(recommendation/points/products)
├── example.html                   画廊预览（就地可开，8 模块整页；css 指向 assets/styles/）
├── assets/
│   ├── template.html              静态种子：8 模块，每个 <section data-od-id>；外链 css/
│   └── styles/
│       ├── components.css         4 个 flow 组件样式权威 + .page 容器/模块 margin（还原设计稿间距）
│       └── fixed/                 3 个固定模块原 CSS（00-banner / 05-buy-fund-cmb / 06-compliance-notice）
├── references/
│   ├── component-templates.md     ★ agent 拼装配方：每组件静态 HTML 片段 + 角标/手 SVG + 图表算法
│   ├── components-provenance.md   节点级溯源对照表（每处固定样式 ↔ 源节点 id）
│   └── components-schema.md       7 类组件判定与 schema
└── _blend_test.html               ⚠️ 临时对照测试文件，待删
```

**工作原理**：OD 生成时，agent 读 `content.template.json` → 按 `component-templates.md` 把每组件拼成
**静态 HTML** → 组装 `index.html`（每模块 `<section data-od-id>` 供 Comment AI 定位）。图表按数据算成静态 SVG/div。
**样式权威 = components.css + fixed/**，agent 只写内容不改样式。图片走 MasterGo 公开 CDN（无本地图）。

**模块视觉顺序（按 position.y）**：banner → hotspot-frontline → market-analysis → related-products → recommendation(N) → buy-fund-cmb → compliance-notice。

**8 组件 schema 要点**：
- banner：固定，仅两行标题可变。
- hotspot-frontline：卡+梯形角标固定，正文/来源可变。
- market-analysis：角标"市场解读"固定，**无独立导语**，N 个分论点(金标 heading+正文 body)，免责。
- recommendation：**数组 N 页**，每页标题/正文/图表(bar 或 line，数据驱动)/来源；A/B 已合并成一个 `.rec`。
- related-products：标题(卡外) + 一大一小两产品(big 居中大 CTA 带手 / small 名左小 CTA)。
- buy-fund-cmb：完全固定。
- compliance-notice：假表格(PATH 网格)不可自适应，仅产品名/费率数字可变，费率要对齐网格；合规审核过勿动。

---

## 3. 本轮（本窗口）做完的事

1. **推广完 4 个 flow 组件**（hotspot / market / related / 已有的 recommendation），从"JS 预览"改成"静态 HTML + 共享 components.css"。
2. **组件真实几何还原**：角标梯形 path、related 大 CTA 的**奶油色手指点击图形**(0:1385-1388 真实 path 重建)、market 金标圆角、装饰菱形渐变线——全取自 data/modules。
3. **静态化 skill**：重写 SKILL.md 工作流、content.template.json 对齐真实 schema、组装 template.html/example.html、lift 3 个固定模块+CSS、删旧种子 `assets/css/`。
4. **根治过一个管线坑**：`split_modules.py` 透传 extractSvg 的非法渐变 SVG（fill=CSS串/NaN）→ 已在 split_modules 加 `_sanitize_inline_svg` 前移合法化，重生成 modules（见 rules.md #9）。
5. **头图 banner 大修**（本轮耗时最多，全靠"量像素+对照实验+比 d2c"定位）：
   - 位图丢失：lift 的 banner CSS 引用本地 `../images/*.png` → 改回 CDN。
   - 编组7 发黑：内部"光"层(深灰图)被编组7 的 `z-index:0` 层叠上下文隔离、mix-blend-mode:screen 混不到蓝底 → **去掉编组7 的 z-index** 解除隔离。
   - 位图四发暗：误把 `mix-blend-mode:soft-light` 改成 `background-blend-mode`（浏览器空转）→ 改回 mix。
   - 位图一光束不显示：css_core 定位错（裸用 relativeX/Y + 乱加 rotateX，没补偿旋转位移）→ 改用 **d2c 权威值** `rotate(90deg)+left:103.8%/top:-20.42%`。
6. **文档/记忆沉淀**：rules.md #10（三个 css_core 根因 + 调试方法论）；新增 memory `feedback_debug_with_data_not_guesses`；banner CSS 内联注释每处修复。

---

## 4. ★已发现但"未落地到管线"的 css_core 根因（最重要的 TODO）

以下坑目前**只在 -od 的手改 CSS 里修了**，**尚未改 css_core**。重生成会复现，必须在管线根治（详见 `rules.md #10`）：

- **坑 A —— 图层混合该用 `mix-blend-mode` 不是 `background-blend-mode`**：MasterGo 的图层混合(滤色/柔光)=与下层混合，浏览器等价是 `mix-blend-mode`；`background-blend-mode` 无基色时浏览器空转。css_core 落 CSS 时须用 mix-blend-mode。
- **坑 B —— 结构组的 z-index 造层叠上下文、隔离子层 mix-blend-mode**：css_core 给几乎每个节点发 z-index，定位元素带 z-index 会形成独立层叠上下文，隔断内部 blend 图层 → 发黑。根治：**纯结构组(无 fill/effect/opacity/mask)不发隔离性 z-index**（当心别打乱层序）。
- **坑 C —— 带 rotate 的节点定位错**：css_core 裸用 relativeX/Y 当 left/top 且乱加 rotateX(180)，没补偿旋转位移 → 元素被甩出可视区。根治：**带 rotate 的节点定位优先采用 d2c 值**（或正确补偿旋转），别盲加 rotateX。

---

## 5. 下一步 TODO（建议优先级）

1. **[高] 根治 css_core 的坑 A/B/C** + 全量重生成（`generate_module_css.py` + `generate_html.py`；坑 B/C 若动 split 层则还要重跑 split_modules）。重生成后**用 -od 的 example.html 复核 banner**（手改 CSS 会被覆盖，要确认管线产物同样正确）。改完沉淀/更新 rules.md。
2. **[中] 清理**：删 `huaxia-hot-cmb-od/_blend_test.html`（临时对照测试）。
3. **[中] 让 skill 在 OD 真生效**：把 `huaxia-hot-cmb-od` 放进 OD 的 `design-templates/`（或 Settings→Skills 导入），建项目实测能否被调用 + 预览 + Comment AI 编辑。
4. **[低] 逐处复核还原度**：对着设计稿过一遍 hotspot/market/rec/related/compliance 细节（间距、金标圆角、图表、假表格对齐）。
5. **[更后] 第二类 meta-skill**：探查 `mastergo-to-od-skill`，规划"自动把一张设计稿变成上述 design-template"。

---

## 6. 关键原则 & memory 索引（务必遵守）

**核心方法论（本轮血泪教训）**：修渲染问题**别猜 CSS**，用①量真实像素(下载图 PIL 统计颜色/透明/亮区) ②最小对照实验 ③比 `07-getD2c` 权威值。d2c 是 MasterGo 自己的 design-to-code=正确渲染标准答案，css_core 与它不符处就是 bug。

**判定 bug 归属**：字段在 raw/d2c 里存在、只是提取/生成错 = **脚本 bug**（改 css_core/split 重生成，别在产物打补丁）；raw 里根本没有该字段 = 真数据缺陷。改前先比 d2c。

**取数/还原**：固定样式取数入口是 `data/modules/NN-*.json` + 源 CSS；逐字段读节点(relativeX/Y/rotate/fill/effect/path)，禁 emoji/默认0/占位近似；flow 化后固定元素用相对父容器的相对值。

**OD 机制**：OD 只把 **SKILL.md 正文**注入 agent 提示词；组件 CSS/assets 是 agent 拷贝的死代码、注释不被语义理解 → 凡需 agent 执行的规则必须写进 SKILL.md。

**memory 文件**（`...\memory\`，自动加载 MEMORY.md 索引）：
`feedback_debug_with_data_not_guesses`、`feedback_fidelity_raw_data`、`feedback_module_data_source`、`feedback_consume_full_node_data`、`feedback_flow_relative_positioning`、`reference_od_skill_injection`、`feedback_chinese`。

---

## 7. 协作提示 & 环境坑

- **用中文**沟通。用户很看重跟设计稿一致，会逐处挑不一致；遇到时**先量数据/比 d2c 判断根因，别急着手工试错**（本轮因反复猜测挨批"治标不治本""你也没改好"）。
- Windows 环境：用 `python`（非 python3，后者+中文输出会崩）；探查脚本**把结果写文件再 Read**（控制台中文 GBK 会乱码，但不影响文件）；bash 是 Git Bash，用 `/c/...` 或正斜杠。
- 打开浏览器：`cmd.exe //c start "" "example.html"`；改 CSS 后让用户 **Ctrl+Shift+R 硬刷新**（否则缓存旧 CSS）。
- 分析图片颜色：`curl` 下载 + `PIL` 统计不透明像素均色/透明比例/亮区网格。

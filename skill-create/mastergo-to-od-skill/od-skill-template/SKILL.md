# OD Skill 入口文件 —— 框架（教 agent 怎么写）

> 这不是一个具体的 SKILL.md，而是告诉 agent **如何为一张具体设计稿写 SKILL.md**。
> 以下所有 `{{ }}` 部分需要 agent 根据具体设计稿填充。

---

## Frontmatter 骨架

```yaml
---
name: {{design-slug}}-od        # 设计稿的 kebab-case 标识 + "-od"
description: |
  {{一段话：这个 skill 对应什么设计稿，做什么，什么场景触发}}
triggers:
  - "{{触发词1}}"
  - "{{触发词2}}"
od:
  mode: prototype
  platform: mobile               # 或 desktop / web，根据设计稿定
  scenario: design
  preview:
    type: html
    entry: index.html
  design_system:
    requires: false              # 设计稿还原类永远设 false
---
```

### 填写指引

- `name`：与 output 目录名一致，如 `hotspot-cmb-od`
- `description`：说明这个 skill 的工作方式——"拿到本期内容 → 按固定模板拼静态 HTML"
- `triggers`：列出用户可能用来触发这个 skill 的关键词（设计稿主题、产品名、场景描述等）
- `platform`：根据设计稿宽度判断——375px 左右 = mobile；1024px+ = desktop
- `design_system.requires`：设计稿还原类 skill 一律 `false`（避免 token 覆盖精确样式）

---

## 正文结构框架

### 「这个 skill 做什么」

写清楚核心工作方式：**不从零画页面，不做 JS 渲染。拿到用户输入 → 按模板拼静态 HTML。**

强调保真原则：所有固定样式精确取自原设计稿数据（见 provenance 溯源表），不要自行发挥。

### 「本期内容从哪来」

写清楚内容输入方式：
- **优先对话输入**：用户在对话里口述本期内容
- `content.template.json` 是 schema 速查表（字段结构参考），不是逐期编辑的文件
- 仅当用户明确说「用 json 里的内容」时才 Read json 取值

### 「资源清单」

用目录树展示 skill 文件结构，每份文件一句话说明用途：
- `SKILL.md` — 你正在读
- `content.template.json` — 内容结构参考（schema 速查）
- `assets/<component>/template.html` — 每个组件的 DOM 骨架 + `data-od-id` + `{{slots}}`
- `assets/<component>/styles.css` — 组件精确视觉样式（从设计稿 JSON 机械提取）
- `assets/<component>/decorations.html` — 组件装饰元素（PATH→SVG、BITMAP→img、outlined text）
- `assets/shared/page.css` — 页面容器 + 背景 + 全局字体
- `references/component-templates.md` — 每组件 HTML 模板 + 图表算法（核心拼装配方）
- `references/components-schema.md` — 组件类型判定与 schema
- `references/components-provenance.md` — 样式 ↔ 源节点溯源
- `output/example.html` — 画廊预览
- `output/template.html` — 种子模板（{{slots}} 未填）

### 「Workflow」结构

```
### Step 0 —— 预读（动手前做一次）
1. 明确本期内容（以对话为准）
2. 读 references/component-templates.md —— 拼装配方
3. 读 output/template.html —— 上期种子模板基线

### Step 1 —— 起页
复制 output/template.html → output/index.html
复制 assets/ → css/（所有 styles.css 汇聚为一个 components.css）

### Step 2 —— 逐组件替换内容
按 component-templates.md 定位每个 <section data-od-id="...">，
用本期内容替换可变槽位 {{...}}

### Step 2.5 —— 图表（如有）
按图表样式契约，数据驱动生成静态 SVG/div。
输入以自然语言为准，图型不限。

### Step 3 —— 组装与自检
把所有 <section> 按顺序放进容器。自检清单：
① 只有可变内容变了，class/结构/样式未动
② 每模块 <section data-od-id> 保留
③ 页面能独立打开、css/ 在同级
④ 高度随内容自适应

### Step 4 —— 收尾
只发简短说明（改了哪几处），不贴整份 HTML 源码
```

### 「硬规则」

至少包含以下几条：
- **样式权威是 components.css + fixed/**，不引用外部设计系统
- **默认 fixed**：拿不准某处该不该改就不改
- **可变即全部可变来源**：仅 content.template.json schema 列出的字段（值以对话为准）
- **保真取值有依据**：任何固定样式如需核对，顺 components-provenance.md 回溯到源数据

### 「输出契约」

```
index.html
css/            ← 与 index.html 同级，随种子拷入，勿改
```

---

## 写作注意事项

1. **引用 references**：正文中要点名引用 references 下的文件（如 `references/component-templates.md`），OD 才能注入这些文件
2. **图表契约必须写在正文**：不要在 references 里藏图表规范——SKILL.md 正文中的「Step 2.5 图表样式契约」要包含配色/字号/画幅/布局规则
3. **固定模块特别说明**：如果设计稿有单实例模块（banner / compliance），必须在正文中说明它们是"固定模块，从 template.html 原样保留"
4. **图表输入以自然语言为准**：不要强制用户套固定 JSON schema。写清楚"用户怎么说你就怎么听"，同时给出可选的快捷写法（如 X/Y 类图的结构化对象）

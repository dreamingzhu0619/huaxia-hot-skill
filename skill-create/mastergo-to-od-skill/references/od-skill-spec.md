# OD Skill 规范：结构、frontmatter、输出契约、安装

> 适用：所有要装进 Open Design 的 design-template skill。

## 1. OD Skill 目录结构

```
<name>-od/
├── SKILL.md                       # 入口：frontmatter + Workflow + 硬规则 + 输出契约
├── content.template.json           # 内容结构参考（schema 速查表）
├── example.html                   # 画廊预览（完整的一期成品）
├── assets/
│   ├── shared/
│   │   └── page.css               # 页面容器 + 背景 + 全局字体
│   ├── <component>/
│   │   ├── styles.css             # 精确视觉值（从设计稿 JSON 机械提取）
│   │   ├── decorations.html       # 装饰元素（PATH→SVG、BITMAP→img、outlined text）
│   │   └── template.html          # DOM 骨架 + {{slot}} 插槽
│   └── ...                        # 每组件一个目录
├── output/
│   ├── example.html               # 填了示例数据的完整页面
│   └── template.html              # 未填数据的种子模板
└── references/
    ├── component-templates.md      # 每组件 HTML 模板 + 图表算法
    ├── components-schema.md        # 组件类型分类体系 + 判定记录
    └── components-provenance.md    # 样式 ↔ 源节点 id 溯源表
```

## 2. SKILL.md Frontmatter

```yaml
---
name: <skill-name>          # 英文标识，kebab-case
description: |
  <一段话描述这个 skill 做什么，什么场景触发>
triggers:                    # 触发词列表
  - "关键词1"
  - "关键词2"
od:                          # Open Design 元信息（必填）
  mode: prototype            # prototype | production
  platform: mobile           # mobile | desktop | web
  scenario: design           # design | development
  preview:
    type: html               # 预览类型
    entry: index.html        # 预览入口文件
  design_system:
    requires: false          # 是否需要设计系统 token 注入
---
```

### od 块字段说明

| 字段 | 说明 | 可选值 |
|---|---|---|
| `mode` | 使用模式 | `prototype`（设计稿还原）/ `production`（生产代码） |
| `platform` | 目标平台 | `mobile` / `desktop` / `web` |
| `scenario` | 场景 | `design` / `development` |
| `preview.type` | 预览类型 | `html` |
| `preview.entry` | 预览入口 | 生成的 HTML 文件名（通常是 `index.html`） |
| `design_system.requires` | 是否需要注入 DESIGN.md token | `true` / `false`。设计稿还原类 skill 设 `false`，避免 token 覆盖精确样式 |

## 3. SKILL.md 正文结构

```
# 标题（一句话描述这个 skill）

## 这个 skill 做什么
简述工作方式、核心原则

## 资源清单
目录结构 + 每份文件的用途

## Workflow
分 Step 0~4 的详细步骤：
- Step 0: 预读（读哪些文件）
- Step 1~3: 生成步骤
- Step 4: 收尾

## 硬规则
- 样式权威是 components.css + fixed/
- 默认 fixed（拿不准就不改）
- 保真取值有依据（溯源表）

## 输出契约
列出生成的文件清单
```

## 4. 输出契约格式

```
index.html
assets/            ← 与 index.html 同级（每组件 styles.css + decorations.html + template.html）
```

Open Design 从生成的 `index.html` 生成预览。同轮不要额外输出 `<artifact>` 源码块。

## 5. content.template.json 规范

- **作用**：内容结构参考示例（schema 速查表），**不是**逐期编辑的文件
- **本期内容来源**：用户在对话里口述为主；仅当用户明确说「用 json 里的内容」时才读 json 取值
- **结构规则**：
  - 每个模块一组 key
  - 带 `[ ]` 方括号的字段 = 可多页数组
  - `_` 开头字段 = 注释（给用户看的，skill 忽略）
  - 没出现在 json 里的一切 = 锁死的固定样式
  - 数组长度决定实例数量：加一个 `{}` = 多一页，删一个 = 少一页

## 6. 安装目录

OD design-template skill 的安装路径（Windows OD 桌面版）：
```
%APPDATA%/../Local/Programs/open-design/data/design-templates/<name>-od/
```

将最终的 `<name>-od/` 目录整个复制到上述路径即可。

## 7. OD 注入机制

- **SKILL.md 正文**会被注入 agent 上下文
- **references 目录下的文件**：只有 SKILL.md 正文中**点名引用**的才会被 agent 读取
- **content.template.json**：OD 不自动注入，agent 按需读取
- 因此：关键的拼装指令、硬规则、图表契约都必须写在 SKILL.md 正文中

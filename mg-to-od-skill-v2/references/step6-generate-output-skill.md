# Step 6: 生成 output SKILL.md

## 你要做什么

生成最终产物中的 `SKILL.md`——这是给下游 Open Design agent 使用的工作说明书。它描述 agent 如何用 `template.html` + `content.template.json` 拼出最终 `index.html`。

## 输入

1. Step 2 输出的 `slots-definition.json`
2. Step 4 生成的 `template.html`
3. Step 5 生成的 `content.template.json`

## 生成规则

### SKILL.md 结构

```markdown
# H5 Design Template Skill

## 1. 你是谁
## 2. 你怎么工作
## 3. 哪份文件是权威
## 4. 绝对不能做的事
## 5. 你从 content.template.json 读到什么、做什么
## 6. 模板语法速查
## 7. 最终输出
```

### 各部分内容要求

**1. 你是谁：**
- 说明这是一个移动端 H5 design-template skill
- 强调不从零设计，只拼装
- 拼装源：`template.html` + `content.template.json`

**2. 你怎么工作：**
按步骤描述 agent 工作流：

```
1. 读取 template.html，了解页面骨架和每个 section 的 blueprint
2. 读取 content.template.json，了解可变模块和字段
3. 如果用户提供了内容 → 映射到 json 字段 → 更新 json
4. 遍历 template.html 的每个 <section data-od-id="xxx">
   - 在 content.template.json 中找到同名 key → 取数组 → 遍历套 blueprint → 填 {{slot}}
   - 找不到同名 key → 固定模块，section 内 HTML 原样保留
   - 数组为空 [] → 跳过该模块不渲染
5. 输出 index.html
```

**3. 哪份文件是权威：**

| 问题 | 权威文件 |
|------|---------|
| 样式 | `assets/styles/components.css` |
| HTML 结构 | `assets/template.html` |
| 内容 | 用户对话或 `content.template.json` |

用户对话与 json 冲突时先询问用户。

**4. 绝对不能做的事：**
- 不从零设计视觉样式
- 不修改 `components.css` 中的规则
- 不使用整页绝对定位
- 不把模块实例数量写死
- 不手算根容器高度
- 不给每个元素单独写 inline style
- 不修改固定模块的内部结构

**5. 你从 content.template.json 读到什么、做什么：**

- 文字 → `{{fieldName}}` 替换
- 图表 / 图片 → 三种形态（字符串/数组/对象）的分支处理
- layout 自然语言 → 用 flex/grid 实现
- 图片路径 → `<img>` 引用
- 自然语言描述 → 生成内联 SVG

**6. 模板语法速查：**

- `{{fieldName}}` → 当前遍历 item 的同名字段
- 图表/图片的字符串/数组/对象三种形态处理规则
- 容器样式由 `components.css` 控制，不覆盖

**7. 最终输出：**
- 只输出一个 `index.html`
- 完整自包含，可直接浏览器/Open Design 预览
- CSS 引用路径从 template.html 保留，不修改

### 具体内容参考

参考 `doc/output-SKILL.md` 中已写好的模板，它是针对当前这个华夏×中信设计稿的输出 SKILL 示例。生成的 SKILL.md 应覆盖同样的规则点，但针对当前项目的实际模块和 slot 进行调整。

具体来说：
- 如果当前项目有新的可变字段类型（如 video），补充对应的处理规则
- 如果当前项目的模块命名不同于示例，使用实际的 `data-od-id`
- 规则和约束列表保持完整，不省略

## 输出文件

```
data/<project>/output/SKILL.md
```

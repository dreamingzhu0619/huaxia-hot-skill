# H5 Design Template Skill

## 1. 你是谁

你是一个移动端 H5 页面的 design-template skill。你不从零设计，不自由发挥任何视觉样式。你的工作是从已有资源中**拼装**出一个静态 `index.html`。

## 2. 你怎么工作

1. 读取 `template.html`，了解页面骨架、有哪些模块、每个 section 内的 blueprint 长什么样
2. 读取 `content.template.json`，了解有哪些可变模块、每个模块有哪些字段、字段名是什么
3. 如果用户通过对话提供了内容，先将用户的自然语言映射到 `content.template.json` 中对应的字段：
   - "第一个产品的名字改成XX" → `productCards[0].name = "XX"`
   - 映射完成后，相当于得到了一份更新后的 `content.template.json`
4. 按 `template.html` 中 `<section>` 的先后顺序，逐个处理每个 `data-od-id`：
   - 在 `content.template.json` 中查找同名 key
   - **找到了** → 取 `template.html` 中该 section 内的 blueprint → 取 json 数组 → 遍历套 blueprint 填 `{{slot}}`
   - **没找到** → 固定模块，section 内 HTML 原样保留
   - 数组为空 `[]` → 跳过该模块，不渲染
5. 将组装完成的页面输出为项目根目录下的 `index.html`

## 3. 哪份文件是权威

| 问题 | 权威文件 |
|------|---------|
| 样式长什么样 | `assets/styles/components.css` |
| HTML 结构长什么样 | `assets/template.html` |
| 内容填什么 | 用户对话，或 `content.template.json` |
如果用户对话和content.template.json冲突，应该先询问用户！优先用用户的回复作答

## 4. 绝对不能做的事

- 不从零设计视觉样式
- 不修改 `components.css` 中的任何规则
- 不使用整页绝对定位（`position: absolute` 写死顶层模块的 `top`）
- 不把模块实例数量写死——数组有多长就渲染多少个
- 不给每个元素单独写 inline style
- 不手算根容器高度
- 不修改固定模块（`content.template.json` 中不存在的模块）的内部结构，照搬模板即可

## 5. 你从 content.template.json 读到什么、做什么

你不需要自行判断"什么能改、什么不能改"。`content.template.json` 里出现的字段就是你要填的，没出现的就已在 `template.html` 和 `components.css` 中固化好了，照搬即可。

读到字段后，按类型处理：

### 文字

正常显示。`{{fieldName}}` 直接替换为字段值。字段不存在或为空 → 空字符串 `""`。

### 图表 / 图片（chart / image）

先判断值的形态，再判断每项怎么渲染。

**第一步 — 判断值形态：**

| 值类型 | 含义 |
|--------|------|
| 字符串 | 单个 |
| 数组 | 多个，默认同行等分排列 |
| 对象 `{ layout, items }` | 多个 + 自定义布局 |

`layout` 的值是自然语言，例如 `"上下堆叠，间距12px"`、`"2行2列等分网格"`、`"左大右小两栏"`。你理解后用 flex / grid 实现。

对象格式：

```json
// 图表
{ "layout": "上下堆叠，间距12px", "charts": ["近一年走势折线图...", "assets/images/a.png"] }

// 图片
{ "layout": "2行2列等分网格", "images": ["a.png", "b.png", "c.png", "d.png"] }
```

**第二步 — 判断每一项怎么渲染：**

| 该项是什么 | 处理方式 |
|-----------|---------|
| 图片路径（以 `.png` / `.jpg` / `.svg` / `.gif` / `.webp` 结尾） | `<img src="...">`，原样引用 |
| 自然语言描述 | 生成内联 `<svg>` |

同一个数组/对象里，自然语言项和图片路径项可以混用。

图表用内联 SVG 而非 ECharts / Chart.js 的理由：
- `index.html` 零依赖
- Open Design 预览一定可用
- 常用图表类型（折线、柱状、面积等）SVG 都能胜任，按自然语言描述生成对应类型即可

### 高度

不由你算，浏览器 flow 自动撑开。

## 6. 模板语法速查

### 文字

`{{fieldName}}` → 取当前遍历 item 的同名字段直接替换。当前上下文已是该数组的第 i 条数据，不需要写 `{{productCards[0].name}}` 这样的路径。

### 图表 / 图片

```
字符串？→ 单个渲染
数组？  → 同行等分，每项独立渲染
对象？  → 读 layout 自然语言布局，每项独立渲染

每项渲染：
  .png/.jpg/.svg → <img src="...">
  自然语言       → 内联 <svg>
```

容器样式和间距由 `components.css` 控制，你不要覆盖。

## 7. 最终输出

只输出一个文件：

```
index.html
```

`index.html` 必须是完整自包含的静态页面，可直接在浏览器或 Open Design 中预览。CSS 引用路径从 `template.html` 中保留，不修改。

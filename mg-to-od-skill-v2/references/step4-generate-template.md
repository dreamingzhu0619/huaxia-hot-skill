# Step 4: 生成 template.html

## 你要做什么

基于模块数据 + Step 2 的 slot 定义，生成 `template.html`。这是唯一的 HTML 权威文件，包含页面骨架、固定模块的完整 HTML、可变模块的 blueprint。

## 输入

1. `data/<project>/modules/*.json` —— 模块数据
2. Step 1 输出的 `modules-classification.json` —— 模块分类和页面顺序
3. Step 2 输出的 `slots-definition.json` —— 可变 slot 定义

## 生成规则

### HTML 基本结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>H5 Page</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { width: 100%; min-height: 100vh; -webkit-font-smoothing: antialiased; }
    body { font-family: "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif; line-height: 1.5; }
    img { max-width: 100%; display: block; }
    a { text-decoration: none; color: inherit; }
    ul, ol { list-style: none; }
  </style>
  <link rel="stylesheet" href="assets/styles/reset.css">
  <link rel="stylesheet" href="assets/styles/components.css">
</head>
<body>
<main class="h5-page">
  <!-- 模块按 y 坐标顺序排列 -->
</main>
</body>
</html>
```

### 模块渲染规则

模块按 Step 1 输出的 `moduleOrder` 顺序排列。每个模块一个 `<section data-od-id="groupId">`：

**固定模块（nature = "完全固定"）：**
- section 内直接写完整 HTML
- 不出现 `{{slot}}`
- 文字写死，图片路径写死
- 用设计稿的实际内容填充

**可变模块（nature = "实例可重复"或"内容随主题变"）：**
- section 内写**一份** blueprint
- 可变 text slot → `{{slotName}}`
- 可变 image slot → `{{slotName}}`
- 可变 chart slot → `{{slotName}}`
- 可变 list slot → 内层循环标记 `{{slotName}}`

```html
<!-- 可变模块示例 -->
<section data-od-id="productCards">
  <article class="product-card">
    <div class="product-card__info">
      <h3 class="product-card__name">{{name}}</h3>
      <span class="product-card__code">{{code}}</span>
    </div>
    <div class="product-card__risk">
      <span class="product-card__risk-tag">{{risk}}</span>
    </div>
    <div class="product-card__metric">
      <span class="product-card__metric-label">{{metricLabel}}</span>
      <span class="product-card__metric-value">{{metricValue}}</span>
    </div>
    <button class="product-card__cta">{{cta}}</button>
  </article>
</section>
```

### 固定内容处理

Step 2 标记为 `fixed` 的区域，写入 template.html：
- 固定装饰层 → 完整 HTML 标签
- 固定图片 → `<img src="assets/images/...">`
- 固定 SVG → 内联 `<svg>` 或引用
- 固定文字 → 直接写死文案

### 图片路径处理

- 设计稿中的图片 URL → 导出到 `assets/images/` → template.html 中使用相对路径
- 装饰性 SVG → 内联写入或导出为独立文件
- 图表区域 → 留 `{{slot}}`，不写死任何图表结构

## 输出文件

```
data/<project>/output/assets/template.html
```

## 注意

- 顶层模块不使用绝对定位（`position: absolute` + `top/left`），全部走文档流
- 模块之间间距由 CSS gap/margin 控制，不手算位置
- blueprint 中只写一份模板，不因为实例数量就复制多份
- 固定模块的文字内容是设计稿当前值，标注注释说明这些是固定的

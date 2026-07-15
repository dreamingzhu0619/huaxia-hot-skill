# Step 3: 生成 components.css

## 你要做什么

从模块 JSON 中提取所有**固定的**视觉属性，生成 `components.css`。

## 输入

1. `data/<project>/modules/*.json` —— 每个模块的完整数据
2. Step 2 输出的 `slots-definition.json` —— 知道哪些是可变 slot（不写进 CSS）

## 提取规则

### 哪些属性进 CSS

从模块 node 树中，提取以下**不会变**的视觉属性：

| 属性 | 来源字段 |
|------|---------|
| 宽度 | `layoutStyle.width`（固定值） |
| 内边距 | 文字节点与容器边缘的距离 |
| 间距 | 同级节点间的 gap |
| 字号 | font style 中的 `size` |
| 字重 | font style 中的 `weight` |
| 行高 | font style 中的 `lineHeight` |
| 颜色 | `fill` / `textColor` 引用的 paint（渐变或纯色） |
| 圆角 | `borderRadius` |
| 阴影 | `effect` 引用的 box-shadow |
| 边框 | `strokeColor`、`strokeWidth`、`strokeAlign` |
| 字间距 | font style 中的 `letterSpacing` |

### 哪些不进 CSS

- **可变 slot 中的文字内容** → 进 `content.template.json`
- **图片/图表 slot** → 进 `content.template.json`（图片路径或图表描述）
- **容器高度** → 不写死，浏览器 flow 自动撑开
- **绝对定位坐标（top/left）** → 顶层模块流动排列，不写死位置

### Scale 换算

设计稿宽度 1125px → 逻辑宽度 375px。

所有尺寸值 **÷ 3**：
```
设计稿字号 57px  →  CSS 19px
设计稿宽度 1075px → CSS 358px（或 100%）
设计稿间距 30px  →  CSS 10px
```

### 命名规范

BEM 命名：`模块名__元素名`，例如：

```css
.product-card { ... }
.product-card__name { ... }
.product-card__code { ... }
.product-card__risk-tag { ... }
.recommendation-card__title { ... }
.hotspot-express__list { ... }
```

### 合并同类样式

不同模块间**相同语义角色**的元素，复用同一套 class：
- 所有正文 → `.module-body`
- 所有数据来源 → `.module-source`
- 所有模块底框 → `.module-card`

模块特有样式才用专属 class。

## 输出文件

```
data/<project>/output/assets/styles/components.css
```

格式：标准 CSS，按模块分组，带简短注释标注数值来源。

## 注意

- 颜色保留设计稿原值（渐变、rgba 等），不自行调整为品牌色
- 字体 family 使用 `"PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif` 作为 fallback
- 如果设计稿用了特殊字体（如 MiSans、AlibabaPuHuiTi），作为首选字体，后面加 fallback

# 组件模板编写规范（教 agent 怎么写 component-templates.md）

> 这不是一份具体的 component-templates.md，而是告诉 agent **如何为一张具体设计稿写 component-templates.md**。

---

## 文件定位

`references/component-templates.md` 是 agent 的**拼装配方**——它告诉 agent：
- 每个组件的 HTML 骨架长什么样（从 `assets/<component>/template.html` 来）
- `{{ }}` 标记的可变槽位在哪里
- 图表怎么从数据算成静态 SVG/div
- 哪些装饰 SVG 片段需要复用（从 `assets/<component>/decorations.html` 来）

agent 读 content.template.json 后，**按本文件的模板把每个组件拼成静态 HTML**。

---

## 结构

```
# 组件静态 HTML 模板（agent 拼装配方）

> 用途说明

## 页面骨架
<!-- 整页 HTML 骨架：doctype → <head> → <body> → 容器 div -->

## 复用 SVG 片段
<!-- 跨组件复用的装饰 SVG：角标、手形、菱形装饰等 -->

## 组件 HTML 模板
<!-- 每个组件一节：名称 + data-od-id + HTML 骨架 + {{槽位}} -->

## 图表
<!-- 数据驱动的图表生成算法 -->
```

---

## 页面骨架写法

给出整页的 HTML 骨架代码块：
```html
<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{页面标题}}</title>
<link rel="stylesheet" href="css/components.css">
<!-- 固定模块的 CSS： -->
<link rel="stylesheet" href="css/fixed/XX-模块名.css">
</head><body>
<div class="{{页面容器class}}">
  <!-- 按顺序放 <section> -->
</div>
</body></html>
```

注：模块流式顺序按设计稿 position.y 排列。

---

## 复用 SVG 片段写法

对跨模块复用的装饰 SVG（如角标、手形、菱形装饰线），**完整写出 `<svg>` 代码**。agent 照抄，不改几何。

每个片段标注：
- 用途（哪些模块用）
- 源节点（来自哪个 modules JSON 的哪个节点 path）
- 特殊注意事项（如 gradient id 需要唯一后缀避免冲突）

示例格式：
```markdown
### 蓝色梯形角标（模块A / 模块B 共用）
<!-- 几何取自 data/modules/XX 的 0:xxx -->
<svg class="..." viewBox="..." xmlns="...">
  <defs>...</defs>
  <path d="..." fill="..."/>
</svg>
```

---

## 组件 HTML 模板写法

每个组件一节，格式：

```markdown
### {{组件名}}（content: `{{content.template.json 中的 key}}`）
```html
<section data-od-id="{{od-id}}">
  <div class="{{css class}}">
    <!-- 固定结构照抄，不变 -->
    <p class="{{class}}">{{可变字段}}</p>
  </div>
</section>
```
```

### 写作规则

1. **每组件一节**，用标题标注组件名和对应的 content key
2. **`{{ }}` 标记可变槽位**：agent 从 content.template.json 或对话内容取值填入
3. **固定结构照抄**：装饰 div、SVG 片段、分隔线等不变的 HTML 结构直接写出
4. **标注 data-od-id**：每个 section 必须有 `data-od-id="..."`，值用英文 slug
5. **多实例组件**：说明"对数组每项重复以下 HTML"
6. **固定模块**：说明"从 template.html 原样保留，只换 {{槽位}}"

---

## 固定模块（单实例）写法

```markdown
### {{模块名}}（固定模块，单实例）
从 `assets/template.html` 里对应 `<section>` **原样保留**。
- 可变：只有 {{具体哪些字段}} 可改
- 固定：其余（背景图/装饰/...）锁死
- 特殊注意事项（如有）：如假表格不可自适应、文字要对齐网格
```

如果模块完全固定（如品牌条），写：
```
### {{模块名}}（完全固定）
完全不改，从 template.html 原样复制。唯一变化是它的**相对位置**随上方内容高度自动下移。
```

---

## 图表写法

```markdown
## 图表（{{模块名}}的 chart，按数据算成静态 HTML）

图表**不逐形状还原**，用数据驱动的干净图。**图型不限于下面几种**：
agent 按数据自由选/设计合适的图型（柱/分组柱/堆叠柱/折线/面积/饼/环/散点…），
但必须遵守 SKILL.md 的图表样式契约。

### 常见图型的算法伪代码

#### 柱状图
- max = max(values)；每根柱宽百分比 pct = max(8, round(v/max*100, 1))
- HTML 骨架：...

#### 折线图
- 画布 W=321, H=130, pad=10
- 点坐标：x(i) = pad + i*(W-2*pad)/(n-1), y(v) = H-pad-(v-min)/((max-min)||1)*(H-2*pad)
- SVG 骨架：...
```

**图表写作注意事项**：
- 给出 1-2 个最常见图型的算法+HTML 骨架（柱+线通常足够）
- 不需要穷举所有图型——agent 按契约自行设计
- 算法用伪代码/Python-like，agent 能理解即可
- 说明坐标算完保留 1 位小数、数值直接显示原始数字

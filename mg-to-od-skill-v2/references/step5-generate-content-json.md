# Step 5: 生成 content.template.json

## 你要做什么

基于 Step 2 的 slot 定义，将每个可变 slot 的内容填入 `content.template.json`，用设计稿的实际值作为默认内容。

## 输入

1. `data/<project>/modules/*.json` —— 模块数据
2. Step 1 输出的 `modules-classification.json`
3. Step 2 输出的 `slots-definition.json`

## 生成规则

### 结构

每个 group 一个 key，值为数组。即使只有一个实例也用数组：

```json
{
  "productCards": [
    { "name": "华夏沪深300指数增强A", "code": "021483", ... }
  ],
  "recommendations": [
    { "title": "左手红利、右手低波...", "body": "红利策略...", ... },
    { "title": "政策红利持续释放...", "body": "科创板八条...", ... }
  ]
}
```

### Key 命名

使用驼峰命名（英文），与 template.html 中 `data-od-id` 一致。

### 字段赋值规则

**text 类型：**
```json
"name": "华夏中证红利低波动ETF发起式联接C"
```
直接取设计稿 TEXT 节点的文字。如果设计稿中该文本有分段/分色，合并为一段纯文本。

**image 类型：**
```json
"banner": "assets/images/hotspot-banner.png"
```
引用导出后的图片路径。如果设计稿中该图片是 MasterGo URL，导出到 `assets/images/` 后使用相对路径。

**chart 类型 — 分为三种形态：**

1. **单个图表（字符串）：** 直接用设计稿中图表区的自然语言描述
```json
"chart": "近一年净值走势对比折线图，红色为本策略，灰色为沪深300基准，横轴12个月"
```

2. **多个图表（数组）：** 同行等分排列
```json
"charts": [
  "assets/images/kcb-valuation-trend.png",
  "近一月科创板日均成交额柱状图，蓝色柱体，横轴为日期"
]
```

3. **自定义布局图表（对象）：** 包含 layout 描述 + 图表列表
```json
"charts": {
  "layout": "上下堆叠排列，间距12px",
  "charts": [
    "assets/images/chart-a.png",
    "近一月走势图..."
  ]
}
```

**chart 中每一项的判定：**
- 以 `.png` / `.jpg` / `.svg` / `.gif` / `.webp` 结尾 → 是图片路径
- 自然语言文字 → 是图表描述，下游用内联 SVG 渲染

如果设计稿中的图表区域不是自然语言描述（是一堆形状画出来的），Agent 需要根据形状的特征（柱状？折线？饼图？轴标签？）生成一句自然语言描述。

**image 类型同样支持三种形态：** 字符串 / 数组 / 对象 `{ layout, images }`，规则同上。

### 来自设计稿的默认值

json 中的值取自当前设计稿。这些作为默认内容，下游 Open Design agent 可以用用户对话中的新内容替换。

### 空数组处理

如果一个可变模块在当前设计稿中没有实例（空数组），保留 key 但值为 `[]`：
```json
"productCards": []
```

## 输出文件

```
data/<project>/output/content.template.json
```

## 注意

- 只输出可变 slot 字段，固定内容不在此文件出现
- 不在此文件中的 `data-od-id` = 固定模块（下游 agent 按此规则判断）
- 数组顺序 = 模块在设计稿中的出现顺序
- 不用 `_` 前缀字段（如下游 agent 不读它们），所有字段都是业务字段

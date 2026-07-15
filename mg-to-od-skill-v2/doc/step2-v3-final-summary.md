# Step 2 V3 重构总结 & 后续计划（2026-07-15）

## 核心转向

从"挖空预定义槽位"转向**"区分壳与内容区，标注可变文字的语义角色"**。

旧思路的问题：
- 把图表区挖出来锁死 → 换一个场景想多放一张图就没地方
- 对每个 TEXT 逐个分类 → 忽略了 GROUP 级别的固定性
- role 分得太细 → 图表数据记了也没用

## 新 Step 2 做了什么

`references/step2-identify-slots.md` 已更新为 V3 版本。

### 输出结构

```json
{
  "modules": [
    {
      "groupId": "productCard",
      "contentArea": { "paddingTop": 70, "paddingBottom": 152, "paddingLeft": 63, "paddingRight": 63 },
      "fixedGroups": [
        { "groupId": "0:50", "type": "decoration", "reason": "纯装饰层" },
        { "groupId": "0:53", "type": "fixedTexts", "childTexts": [{ "nodeId": "0:55", "text": "小试一笔" }] }
      ],
      "variableTexts": [
        { "nodeId": "0:57", "text": "华夏中证红利低波动ETF...", "role": "frameTitle" },
        { "nodeId": "0:84", "text": "中证红利低波动指数选取50只...", "role": "body" },
        { "nodeId": "0:177", "text": "资料来源：华泰研究。", "role": "sourceNote" }
      ]
    }
  ]
}
```

### 三个核心输出

| 输出 | 含义 | 谁用 |
|------|------|------|
| `contentArea` | 内容区到 frame 四边的距离 | Step 3 → CSS padding，Step 4 → 模板 |
| `fixedGroups` | 固定不变的壳（装饰容器 + 含固定文案的容器） | Step 3 → 提取壳样式，Step 4 → 写死 HTML |
| `variableTexts` | 可变文字，每个标注 role | Step 3 → 按 nodeId 提取文字样式，Step 5 → 默认内容 |

### 四个 role

| role | 判断 | 出现次数 |
|------|------|---------|
| `frameTitle` | 内容区最顶部的可变文字 | 0~1 |
| `sectionTitle` | 嵌入在 body 段落之间的可变文字 | 0~N |
| `body` | 长文（>20字），不在顶部 | 0~N |
| `sourceNote` | 含"数据来源""Wind""截至"等 | 0~N |

### 关键规则

1. **先判断容器（GROUP/FRAME）级别的固定性**，再判断剩余 TEXT
2. **同类模块只处理代表模块**（Step 1 归组的取第一个）
3. **不记录 chartData**（图表数字不提取样式，不记录）
4. **不预设内容区分组**（几个段落、几张图 → 留给下游 Agent）
5. 小标题外面的装饰框 → fixedGroups[type=decoration]，Step 3 提取壳样式，CSS 不写死宽度

---

## 待做

### Step 3（generate-css）需要重写

现有文件：`references/step3-generate-css.md`

需要调整为基于新 Step 2 的输出：

- **从 `contentArea`** → 生成 `.module-content { padding: ... }`
- **从 `fixedGroups[type=decoration]`** → 提取壳的视觉属性（背景色、圆角、阴影、边框），生成 `.module-card`、`.section-title-shell` 等
- **从 `variableTexts`** → 按 nodeId 去 JSON 里取 `textRuns[0].font.*`、`textColor`、`textAlign`，按 role 归类生成 class：
  - `frameTitle` → `.content-frame-title`
  - `sectionTitle` → `.content-section-title`
  - `body` → `.content-body`
  - `sourceNote` → `.content-source`
- **从 `fixedGroups[type=fixedTexts]`** → 壳样式 + 文字样式，生成固定组件的 CSS

规则：
- 宽度：容器不写死 width，用 `inline-block` / `fit-content`
- 尺度：÷3 换算
- 合并同类 role 的样式（同一 role 的多个 nodeId 取公共值）

### Step 4（generate-template）需要重写

现有文件：`references/step4-generate-template.md`

核心变化：模板里只有一个 `{{contentItems}}` 入口，不再有多个零散的 `{{slotName}}`。

模板结构：
```html
<section data-od-id="groupId">
  <!-- 壳：固定装饰 + 固定文案 -->
  <div class="module-card">
    <div class="module-content">
      {{contentItems}}
    </div>
  </div>
</section>
```

- `fixedGroups` → 壳的 HTML 写死
- `contentArea.padding` → CSS padding
- `variableTexts` 的 role → 模板不写死文字，留给 `{{contentItems}}`
- 固定文本（如"小试一笔"）→ 直接写进 HTML

### Step 5（generate-content-json）需要重写

现有文件：`references/step5-generate-content-json.md`

输出从旧的 slot 结构变为 `contentItems` 数组：

```json
{
  "recommendationC": {
    "contentItems": [
      { "type": "text", "role": "frameTitle", "value": ""哑铃型"策略  重构市场估值体系" },
      { "type": "text", "role": "body", "value": "从一季度持仓图谱看，险资坚定执行..." },
      { "type": "chart", "count": 2, "layout": "equal-row", "value": ["红利资产占比超60%", "科技资产占比超31%"] },
      { "type": "text", "role": "sourceNote", "value": "数据来源：Wind，截至2026.3.31" }
    ]
  }
}
```

图表通过 `type: "chart"` 以自然语言描述插入在 contentItems 数组中，和文字混排。

### Step 6（generate-output-skill）需要重写

现有文件：`references/step6-generate-output-skill.md`

适配新的 template.html 和 content.template.json 格式，README 说明新的 contentItems 结构。

---

## 流水线对比

| | 旧 | 新 |
|---|---|---|
| Step 1 | 模块分类 | **不变** |
| Step 2 | 识别可变 slot（分类图表区/文字区） | **区分壳与内容区 + role 标注** |
| Step 3 | 从所有节点提取 CSS | **从 contentArea + fixedGroups + variableTexts 提取 CSS** |
| Step 4 | 多个 `{{slot}}` 模板 | **单 `{{contentItems}}` 入口模板** |
| Step 5 | slot-by-slot 默认值 | **contentItems 数组默认值** |
| Step 6 | 生成 SKILL.md | **适配新格式** |

---

## 关键设计决策（已确认）

1. 一个 frame 一个大的内容区，不预设内部划分
2. 内容区里放几段文字、几张图 → 下游 Agent 通过对话决定
3. 壳的样式固定提取，宽度不写死（自适应文字/内容）
4. 图表不记录视觉样式，只以自然语言描述记录在 content.template.json
5. 图表数据（数字/百分比）不记，因为图表要重画

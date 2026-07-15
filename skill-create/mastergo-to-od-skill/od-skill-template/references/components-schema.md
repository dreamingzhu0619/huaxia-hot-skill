# 组件类型分类体系（教 agent 怎么写 components-schema.md）

> 这不是一份具体的 components-schema.md，而是告诉 agent **如何为一张具体设计稿做组件分类和 schema 设计**。

---

## 文件定位

`references/components-schema.md` 记录：
- 设计稿中有哪几种组件类型
- 每种组件的判定标准（三信号合一）
- 每种组件的 schema 格式（JSON）
- 哪些是 singleton（单实例）、哪些是 repeatable（可复制）

---

## 判断「是不是同一种组件」的方法

新流程使用 **脚本骨架签名比对 + diff** 作为主要方法：

1. **骨架签名（脚本）**：`diff_modules.py` 按节点 type 层级计算签名，只看 FRAME→GROUP→TEXT/PATH 的层级结构，忽略坐标和文本。签名相同的模块自动标记为候选合并组。
2. **逐属性 diff（脚本）**：对合并组内的节点，按树位置匹配后逐字段比对——text/font/fill/border/effect 每个字段独立判定 invariant/variable。
3. **AI 确认语义**：AI 读节点名和文本内容，确认脚本的合并建议在业务语义上是否合理。

三者一致 → 判为同一种组件，合并成一份 styles.css + decorations.html + template.html。

---

## 组件类型分类

常见的组件类型及判定标准：

### 1. 头图型（banner / hero）
- **特征**：全宽背景图/渐变、居中大标题、角标、装饰光点、分享按钮
- **实例**：singleton（每页一个）
- **schema**：`{ titleLine1, titleLine2 }`

### 2. 资讯正文型（文章卡片）
- **特征**：白卡/渐变卡片骨架、标题（带装饰）、富文本正文、来源/日期标注
- **实例**：singleton
- **schema**：`{ title, body, source }`

### 3. 分论点型（分析/解读）
- **特征**：卡片骨架 + 大标题 + 若干"小标题+正文"的分论点段落，小标题有独立装饰（金标/色条）
- **实例**：singleton 容器 + repeatable 分论点
- **schema**：`{ title, points: [{ heading, body }], disclaimer }`

### 4. 推荐卡片型（产品推荐 / 理由阐述）
- **特征**：卡片骨架 + 标题装饰（菱形线）+ 正文 + 图表 + 资料来源
- **实例**：repeatable（每期 N 张）
- **schema**：`{ title, body, chart, source }`
- **合并规则**：如果设计稿有"推荐理由A"和"推荐理由B"，骨架上只有图表类型不同 → 合并为一个组件，靠 `chart.type` 区分

### 5. 品牌条型（CTA / 品牌标语）
- **特征**：简短品牌标语 + Logo + 按钮/链接
- **实例**：singleton（完全固定）
- **schema**：`{}`（无可变字段）

### 6. 合规声明型（风险提示 / 费率表格）
- **特征**：风险提示长文 + 假表格（PATH 画的网格）+ 绝对定位叠文字
- **实例**：singleton（文字可变 / 视觉固定）
- **schema**：`{ riskWarning, products: [{ nameCode, fees }] }`
- **特殊处理**：假表格**不可**改成自适应——文字必须与固定网格对齐

### 7. 产品展示型（相关推荐 / 产品列表）
- **特征**：标题装饰 + 产品卡（名称/代码/风险标签/CTA 按钮）
- **实例**：singleton 容器 + repeatable 产品卡
- **schema**：`{ title, products: [{ name, code, riskTag, cta }] }`

---

## 小结写法

每份 components-schema.md 结尾宜有小结：

```
## 小结

- **CSS 种类从 N → M**（合并了哪些）。
- **N 种是可复制的**：列出哪些组件是 repeatable。
- **共用的骨架**：哪些组件共用同一套卡片骨架。
- **完全固定的组件**：哪些组件内部不改任何东西。
- **自适应高度的例外**：哪些组件不能改成 flow/自适应（如假表格）。
- **跨模块一致性**：同一数据在多个模块出现时需要联动。
```

---

## 写作指引

1. 先读 `data/modules/_index.json` + `tree.md`，了解有哪些模块
2. 用"三信号合一"判定哪些模块是同一种组件
3. 对每种组件给一个数字编号、命名、标记 singleton/repeatable
4. 写出每种组件的 JSON schema（可变字段）
5. 标注特殊处理（假表格/品牌固定用语/图表多类型等）

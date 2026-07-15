# 组件溯源表格式（教 agent 怎么写 components-provenance.md）

> 这不是一份具体的 components-provenance.md，而是告诉 agent **如何为一张具体设计稿建立样式溯源**。

---

## 文件定位

`references/components-provenance.md` 记录**每一处固定样式的取值依据**，确保能回溯到确定的源节点，便于逐处核对还原度。

可变内容（产品名/正文/图表数值/来源文字）不在此表——它们是每期填的，不需要溯源。

---

## 数据链路

先写清楚数据的完整链路：

```
MasterGo 设计稿
  └─(MCP 抓取)→ data/raw/            getDsl 基底 + getD2c/getDesignSvgs/getDesignTexts 补充
       └─(split_modules)→ data/modules/NN-*.json  每模块一份；每节点含完整字段 + sources[] + assets.svgs
            ├─(diff_modules)→ data/analysis/      invariant/variable 逐属性标记
            ├─(extract_styles)→ assets/<comp>/styles.css   每条规则注释源节点 id
            ├─(extract_decorations)→ assets/<comp>/decorations.html   PATH→SVG, BITMAP→img
            └─(agent)→ assets/<comp>/template.html   DOM骨架 + {{slots}}
```

核对任一值的方法：`styles.css` 中的 `/* 0:xxx */` 注释 → `data/modules/NN.json` 节点 `0:xxx` → `data/raw`。

---

## 固定样式的三大来源

```
固定样式（字体/色值/渐变/阴影/间距/圆角）
  → 抄源 CSS NN-*.css 的精确值，在 CSS 中用 /* 0:xxx */ 标注源节点

异形几何（角标/手势/金标/装饰 path/烘焙 SVG）
  → 抄 data/modules/NN-*.json 的 node[].path / assets.svgs[id]

相对定位
  → flow 化后固定元素的 left/top 用「相对当前 flow 容器」换算值
```

---

## 溯源表格式

### 每个组件一节

```markdown
## N. {{组件名}}  （源：`NN-slug.css` + `data/modules/NN-*.json`）

| 元素 | 源节点 | 取的什么 |
|---|---|---|
| `.css-class` 元素描述 | 0:xxx | 字体/字号/颜色/渐变/阴影/圆角等精确参数 |
| `.another-class` 另一元素 | 0:yyy / 0:zzz | 具体取了什么视觉属性 |
```

### 表格列说明

- **元素**：CSS class + 元素简要描述（如 `.hot` 卡骨架、`.rec-title` 标题）
- **源节点**：MasterGo 节点 ID（`0:xxx` 格式），多个源节点用 `/` 分隔
- **取的什么**：具体取了哪些视觉属性——字体名+字号/行高、颜色 hex、渐变参数（角度+色标+%）、阴影参数、圆角、path 几何来源等

---

## 写作步骤

1. **打开源 CSS**：读 `assets/styles/modules/NN-*.css`，每条规则的 `/* 0:xxx */` 注释标明了源节点
2. **打开 modules JSON**：读 `data/modules/NN-*.json`，找到对应节点，核实颜色/字体/渐变数据
3. **逐元素填写**：对 components.css + fixed/*.css 中每个非 `{{variable}}` 样式的元素，填写溯源
4. **装饰 SVG 特别标注**：对于从 `node[].path[].data` 提取的异形几何（角标/手/表格线），注明 path 来源节点 + fill 来源

---

## 待核实/占位项

文末列出暂不确定或待补数据的项：

```markdown
## 待核实/占位项（需用户确认或后续补数据）

- **某元素某属性**：原因（如 path 拐角估算、raw 缺失等）
- **某数值**：本期 modules 无对应数据，暂留默认值
```

---

## 写作注意事项

1. **可变内容不溯源**：产品名/正文/图表数据/来源文字等随期变化的内容不需要溯源
2. **精确度**：颜色用 hex、渐变用完整参数（角度+色标%+色值+透明度）、阴影用完整参数
3. **合并组件的溯源**：如果 A/B 两个模块合并为一个组件，要标注清楚哪些样式来自 A、哪些来自 B
4. **图表不逐形状溯源**：图表是数据驱动的，只溯源颜色/字体/字号等样式参数，不溯源每个柱的具体高度

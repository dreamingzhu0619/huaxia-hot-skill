# 常见问题排查清单（Gotchas）

> 适用：所有 MasterGo 设计稿的 pipeline → flow CSS → OD skill 全流程。
> 每类问题按 **识别信号 → 排查方向 → 治本策略** 组织。

---

## CSS 生成阶段

### G1. line-height 显示为 normal 而非精确值

- **信号**：生成的 CSS 中 `line-height: normal`，与设计稿有偏差
- **原因**：getDsl 的 `lineHeight="-1"` 表示 auto，css_core 无法拿到精确值
- **策略**：设计软件中单行文本的高度除以字号可手动估算行高比；确认后手写补入 flow CSS
- **治本**：这是数据源限制，非 bug。flow CSS 阶段用像素测量补偿

### G2. PATH 节点的 fill 丢失 → 背景色不输出

- **信号**：PATH 子节点的 CSS 缺少 `background-color`，渲染时透明
- **原因**：PATH 的 fill 写在 `path[0].fill` 而非 `node.fill`，split_modules.py 可能未提升
- **策略**：检查 `data/modules/NN-*.json` 中该节点的 `fill` 字段是否为空；若空，往上追 `data/raw/01-getDsl/` 中该节点的 paint 引用；在 flow CSS 中手写正确的背景色
- **治本**：split_modules.py 的 `resolve_node` 中，若 `node.fill` 为空，从 `path[0].fill` 提升

### G3. 多层 fill 的层序颠倒

- **信号**：某元素的渐变/颜色观感"不对"（如卡片偏黄而非偏蓝）
- **原因**：getDsl 的 fill 数组是 `[顶→底]`，若代码中做了 `reversed()` 会层序颠倒
- **策略**：检查 raw getDsl 的 paint 数组顺序 → modules JSON 的 fill 数组顺序 → CSS 的 background-image 顺序，三者必须一致（第一项=最上层）
- **治本**：fill_to_css 不要倒序，按数组原序拼接

### G4. 旋转 180° 的元素位置偏移

- **信号**：装饰元素（如标题两侧对称装饰）跑到了完全错误的位置
- **原因**：`transform: rotate(180deg)` + `transform-origin: 0 0` 绕左上角旋转 → 视觉偏移 (-width, -height)
- **策略**：180° 的奇数倍旋转必须用 `transform-origin: center`
- **治本**：css_core 中 abs(rot) % 180 == 0 且 abs(rot) % 360 != 0 时 → transform-origin: center

### G5. SVG_ELLIPSE 没有 border-radius → 变成正方形

- **信号**：设计稿里的圆形/椭圆在渲染时变成正方形
- **原因**：css_core 只检查 `node.borderRadius`，SVG_ELLIPSE 的 borderRadius 为 null
- **策略**：SVG_ELLIPSE 类型强制输出 `border-radius: 50%`
- **治本**：css_core 中加 `elif node.get("type") == "SVG_ELLIPSE": css["border-radius"] = "50%"`

---

## SVG 渲染阶段

### G6. 内联 SVG 渐变全部失效（透明/无色）

- **信号**：PATH 的渐变填充在浏览器中不显示，形状透明
- **原因**：extractSvg 导出的 SVG 用了非法写法 `fill="linear-gradient(...)"`。SVG 原生不认 CSS 渐变函数，只认 `fill="url(#id)"` + `<defs>` 中的 `<linearGradient>`
- **策略**：渲染前把 `fill="...gradient(...)"` 转成 `<defs>` 定义 + `fill="url(#id)"`
- **治本**：split_modules.py 写入 modules 的 `assets.svgs` 时提前做渐变合法化（幂等操作）

### G7. SVG viewBox 起点非 (0,0) → 整段 SVG 错位

- **信号**：某些模块的 SVG 内容整体平移/错位（如"看着变窄"、"没框住文字"）
- **原因**：viewBox 起点 minX/minY 非零（如 `-31, -8`），渲染时 `<svg>` 直接塞进 div 的 0,0 处
- **策略**：给 `<svg>` 注入 `position:absolute; left={minX}; top={minY}`，对齐节点本地坐标系
- **排查方法**：扫全站 SVG 的 viewBox 起点，绝对值大的模块优先排查

### G8. 细线 SVG（<1px）抗锯齿后不可见

- **信号**：表格竖线、分隔线"消失了"或极淡
- **原因**：浏览器对 0.5px 宽的 fill path 做抗锯齿，浅色被渲染成半透明
- **策略**：所有内联 `<svg>` 根标签注入 `shape-rendering="crispEdges"`
- **治本**：在 SVG 后处理链中加入此属性

### G9. 表格边框 SVG 双 subpath 同向 → 实心矩形遮内容

- **信号**：表格容器用 PATH 画边框，渲染时变成实心色块遮住文字
- **原因**：边框 SVG 用一条 path 的两个子路径（外框+内框）绘制，方向相同 → `nonzero` 填充规则不形成镂空
- **策略**：检测 2 子路径 + 实色 fill 的 path → 添加 `fill-rule="evenodd"`
- **治本**：SVG 后处理链中添加边框修复

### G10. baked SVG 中多值 fill 只保留最后一层

- **信号**：某元素的多层渐变叠加（如两张渐变叠出效果）在渲染时只剩一层
- **原因**：MasterGo baked SVG 对每个 `<path>` 只保留 fill 数组的最后一个值
- **策略**：对含多值 fill（`path[].fill` 是数组且 length≥2）的 PATH 节点，不跳过渲染 → CSS div 的多层 `background-image` 覆盖 baked SVG 的残缺层
- **排查三步法**：raw getDsl paint 数组 → modules JSON fill → CSS background-image → HTML 是否有对应 div

---

## 文本渲染阶段

### G11. 单行文本被字体回退挤成两行

- **信号**：设计里单行的文本（如产品全称），浏览器中末尾字符换到第二行
- **原因**：浏览器缺中文字体，回退到更宽字体后整行宽度超过设计框
- **策略**：用启发式判单行——设计框高 ≤ 行高×1.6 时输出 `white-space: nowrap`
- **权衡**：极少数"矮框但本意想换行"的文本会被误判（罕见）

### G12. 白色 text-shadow 反客为主

- **信号**：带白色下移阴影的彩色字（如渐变标题），白色比主体色还抢眼
- **原因**：缺字体。设计稿用的是重黑体（如 FZZDHJW），回退到细体后，固定 1px 的白色 text-shadow 与笔画差不多宽
- **排查方法**：比 07-getD2c 的 CSS 输出——若 font-family + text-shadow 与 D2C 一致，就是缺字体，非数据 bug
- **策略**：缺字体是渲染环境问题。目标环境装字体后自动解决。不改 css_core（改了反而偏离 D2C 权威值）

### G13. TEXT 的 `\n` 在 HTML 中被折叠

- **信号**：设计稿里多行文本（如表格单元格三行），渲染时变成一行
- **原因**：HTML 默认 white-space 把源码 `\n` 折叠成空格
- **策略**：渲染时把 TEXT 节点中的 `\n` 全局替换为 `<br>`

### G14. 多词合并文本未拆分

- **信号**：同一 TEXT 节点包含多个独立词（如"费率低  品类全  策略优  服务好"），渲染时挤在一起
- **识别**：`textMode="single-line"` + `\s{2,}` 可拆出 2-6 个词段 + 同级存在窄高 PATH 竖线分隔符
- **策略**：按同级竖线分隔符的真实位置算列中心，每个词渲染为独立的绝对定位 span
- **安全阀**：竖线数量 ≠ 词数-1 时，不拆，保持原文本不猜位置

---

## 通用调试方法论

### 三招定位 MasterGo 渲染问题

1. **量真实像素**：下载设计稿截图，统计颜色/透明度/亮区位置，知道每层本该什么效果
2. **做对照实验**：隔离单变量的最小 HTML，逐个验证生效条件
3. **比 getD2c 权威值**：D2C 是 MasterGo 自己的 design-to-code 输出 = "正确渲染"的标准答案

### 多项症状先找同源

同一模块多个看似无关的症状（如"四词不居中"+"竖线没在两词中间"），往往同因（文本没拆分+HTML 空格折叠）。先别分头修，找共同根因。

### 改判据前先全站扫描

修 css_core 的全局行为前，先扫描全站数据确认命中面——判据边界靠数据划，不靠直觉。避免"一刀切"误伤其他模块。

---

## HTML 生成阶段（extract_decorations.py 机械提取 + agent 写 template.html）

> **新流程（REDESIGN 后）：** PATH/SVG/BITMAP/装饰 GROUP 由 `extract_decorations.py` 机械提取到 `decorations.html`，agent 只写 `template.html` 的 DOM 骨架 + {{slot}}。
> 以下 G15-G17 记录旧流程中 agent 手写完整 HTML 时犯过的错误，保留作为 decorations.html 输出质量检查的参考。

### G15. PATH/SVG 节点在 decorations.html 中被跳过

- **信号**：设计稿里的装饰图形、角标、矢量图标在 decorations.html 中消失。模块 JSON 有 `assets.svgs[nodeId]` 但 decorations.html 无对应元素。
- **现在谁负责**：`extract_decorations.py` 遍历节点树，PATH→内联SVG、BITMAP→<img>、LAYER→<div>。**机械提取，不依赖 agent 判断。**
- **排查方法**：数模块 JSON 中 `assets.svgs` 的键数，对比 decorations.html 中 `<svg` 标签数。数量差 = 被跳过的 PATH 节点。
- **治本**：检查 `extract_decorations.py` 的 `walk_nodes()` 是否正确递归进入所有 GROUP/FRAME 子节点。

### G16. Gradient Overlay PATH 叠加层未渲染 → 文字颜色错误

- **信号**：文字的视觉效果与设计稿明显不同——设计稿里是渐变字，渲染出来是单一底色。
- **现在谁负责**：`extract_decorations.py` 检测 Gradient Overlay PATH（相邻 TEXT + PATH overlay），输出叠加 SVG 到 decorations.html。**机械提取。**
- **排查方法**：检查模块 JSON 中 TEXT 节点旁是否有名为 "Gradient Overlay" 的 PATH 兄弟节点。如有，确认 decorations.html 中包含对应 SVG。
- **治本**：`render_decoration_node()` 处理 Gradient Overlay 的逻辑是否覆盖了所有情况。

### G17. "固定"元素的子树不完整 → 漏掉子节点

- **信号**：某个装饰 GROUP（如"热点速递拷贝"角标）内部缺子元素。
- **现在谁负责**：`extract_decorations.py` 递归遍历装饰 GROUP 的所有子节点，完整输出到 decorations.html。**递归遍历，不挑节点。**
- **排查方法**：打开模块 JSON，找 GROUP 的 `children` 数组，数子节点数。对比 decorations.html 中该 GROUP 对应的 DOM 子树节点数。
- **治本**：确认 `walk_nodes()` 对 `is_decoration_group()` 返回 true 的 GROUP 做了完整递归。

---

## 分析 + 生成阶段（新流程）

### G18. extract_styles flow margin 计算错误

- **信号**：两个元素之间的间距与设计稿明显不符（过大或过小）
- **原因**：`extract_styles.py` 的 E2 步骤按 `relativeY` 排序兄弟节点后计算 gap，但背景 LAYER（y=0）排在第一个产生虚假间距
- **策略**：检查 FLOW-WARN 标记的条目。背景层（y=0, 全宽高）通常应该被排除出 flow margin 计算。AI 在 Step 5c 确认 layout 时应忽略背景层的间距
- **治本**：在 `calculate_flow_margins()` 中添加背景层检测：如果一个子节点的 width/height 接近父容器尺寸且 y=0，标记为"可能背景层"并跳过

### G19. decorations.html 漏掉 outlined text

- **信号**：设计稿中的大字标题（如"反脆弱红利低波"）在 decorations.html 中完全消失
- **原因**：`extract_decorations.py` 的 `is_decoration_node()` 没有检查 `outlinedText` 属性。outlined text 的 GROUP 名含中文但 type 非 PATH/TEXT，被跳过
- **策略**：检查模块 JSON 中是否有 `outlinedText: true` 的节点。如有，确认 decorations.html 中包含对应的 `<span>` 元素
- **治本**：`render_decoration_node()` 已处理 `outlinedText` 属性；确保 `walk_nodes()` 递归进入 GROUP 时也检查 `outlinedText`

### G20. build_html 组件排序错误

- **信号**：example.html 中组件排列顺序与设计稿不一致
- **原因**：组件按 `_index.json` 的 `position.y` 排序，但 D2C 匹配可能导致某些模块的 Y 坐标偏移
- **策略**：检查 `_index.json` 中各模块的 `position.y`，确认与设计稿截图中的视觉顺序一致。不一致时手动调整 merge_groups.json
- **治本**：`get_component_order()` 使用 position.y 排序；组件顺序在 Step 2 用户确认后写入 merge_groups.json 的 `order` 字段

### G21. diff_modules 签名的 false merge

- **信号**：两个结构不同的模块被合并为同一组件类型
- **原因**：骨架签名只看 type 层级，不区分"GROUP 内有 3 个 TEXT"和"GROUP 内有 2 个 TEXT + 1 个 PATH"。签名相同不代表真的是同一组件
- **策略**：Step 4b agent 展示合并建议时必须附带每个模块的节点名列表，让用户肉眼判断语义是否相同
- **治本**：骨架签名是候选建议，不是最终判定。用户确认是必经步骤

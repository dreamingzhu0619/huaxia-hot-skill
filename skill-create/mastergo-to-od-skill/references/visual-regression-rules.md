# 视觉还原问题规则沉淀

本文记录调试 `huaxia-hot-citc-od/example.html` 时发现的可复用规则。格式固定为：通用规则、具体例子、修改/应对。

## 1. PATH 外层容器不能绘制背景

**通用规则**：`PATH` 节点的可见形状必须由 inline SVG 渲染。外层定位 `div` 只负责 `left/top/width/height`，最多承载阴影或滤镜，不能再输出 `background`、`background-color`、`background-image`。否则文字转曲、银行 logo、角标形状会显示成黑块、红块或灰色矩形。

**具体例子**：`06-银行结束语.json` 里没有 `TEXT` 节点，结束语/logo 是由 `0:350` 到 `0:389` 等 PATH 组成。旧版 `extract_styles.py` 给这些 PATH class 输出背景色，浏览器就把字形显示成黑色、红色矩形。

**修改/应对**：`extract_styles.py` 对 `type == "PATH"` 跳过 fill/background/stroke，只把视觉填充交给 `extract_decorations.py` 的 inline SVG。若设计稿预期是可编辑文字，但 raw/modules 里只有 PATH、没有 TEXT，则标注为**源数据缺失**，需要人工补真实文案或重新导出未转曲文本。

## 2. SVG 渐变填充必须转成 defs

**通用规则**：浏览器 SVG 不支持 `<path fill="linear-gradient(...)">` 这种 CSS 渐变写法。写入 `decorations.html` 前，必须把 CSS gradient 转成 SVG `<defs>` 和 `fill="url(#...)"`。

**具体例子**：`08-热点速递.json` 里的角标路径 `0:38`、`0:42`、`0:43` 都有 gradient fill。旧版直接把 `linear-gradient(...)` 写进 SVG 的 `fill` 属性，导致形状丢失、透明或变黑。

**修改/应对**：`extract_decorations.py` 在输出 PATH SVG 前调用 `css_core.inline_svg_fix_gradients()`、`fix_svg_frame_fill()`、`fix_svg_thin_lines()`。生成后的 `decorations.html` 不应该再出现 `fill="linear-gradient` 或 `fill="radial-gradient`。

## 3. 跳过 Clip 里的灰色 fallback/mask 层

**通用规则**：父级链路中包含 `Clip`、且 fill 为 `#D8D8D8` 的层，通常是 MasterGo 的 fallback/mask 层，不是最终可见设计内容。直接渲染它会盖住真实图片或渐变。

**具体例子**：`08-热点速递.json` 中 `0:25 矩形 153 拷贝 3` 是 `Clip` 内的灰色层；真正可见的卡片颜色来自 `0:22` 的白金渐变和 `0:24` 图片层。旧版输出 `0:25` 后，热点速递卡片颜色变灰、不正确。

**修改/应对**：`extract_decorations.py` 在任一祖先节点名为 `Clip` 且当前节点 `fill == "#D8D8D8"` 时跳过该节点。若灰色层确实是设计可见层，通常不会位于 `Clip` 内，且不会有同层图片/SVG 替代。

## 4. 数组组件必须按实例生成模板

**通用规则**：合并为 array 的组件，如果各实例内部结构不同，不能只复制代表模块的 `template.html/decorations.html`。必须为每个原始 module 生成实例级模板和装饰，CSS 也要覆盖全部实例节点。

**具体例子**：`产品推荐理由A/B/C` 被合并为 `recommendation`，但 B、C 的图表/表格结构和 A 不同。旧版只复用 A 的 DOM，导致 B/C 的文本和数据错位。

**修改/应对**：`generate_template.py` 输出 `template.0.html`、`template.1.html`、`template.2.html`；`extract_decorations.py` 输出匹配的 `decorations.N.html`；`extract_styles.py` 把所有来源模块的 CSS 规则合并到同一 `styles.css`；`build_html.py` 按实例下标选择对应文件。如果 content 里缺少新实例 slot，组装 example 时从对应 module JSON 回填原始文本用于视觉验证。

## 5. fixed TEXT 仍然需要完整文本样式

**通用规则**：被归为 fixed 的 `TEXT` 不是可以丢弃的普通装饰。只要它仍然可见，就需要保留 width、height、font、line-height、letter-spacing、text-shadow、rotate 等样式。

**具体例子**：`08-热点速递.json` 的 `0:46 热点速递` 有 `rotate: -3.95`；`01-产品卡.json` 的 `0:55 小试一笔` 需要位于 `矩形 18` 正中间。旧版 fixed text 只输出 `left/top + text`，容易导致文字漂移、换行或看不见。

**修改/应对**：`extract_decorations.py` 输出 fixed TEXT 时写入 width/height/transform；`extract_styles.py` 从 getDsl 的 `textRuns` 补齐 font/color/line-height/letter-spacing/text-shadow，不再只依赖不完整的 D2C CSS。

## 6. 文本 letterSpacing 百分比必须转成 px

**通用规则**：MasterGo 可能把 `font.letterSpacing` 存成字号百分比，例如 `-2.25%`。CSS 的 `letter-spacing` 不接受百分比，原样输出会被浏览器忽略。

**具体例子**：`05-营销头图.json` 的 `0:10 市场开启震荡模式` 在 modules 里有完整样式数据：`MiSans-Bold`、字号 `84.965...`、颜色 `#DFD3B1`、`letterSpacing: -2.25%`。旧版 CSS 输出无效百分比字距，所以文字样式不对。

**修改/应对**：`extract_styles.py` 使用 `fontSize * percent / 100` 把百分比字距转成 px，再按设计缩放比例输出。若字体没有数值 `font-weight`，则从字体族名推断，例如 `Bold` -> `700`、`Semibold` -> `600`、`ExtraBold` -> `800`。


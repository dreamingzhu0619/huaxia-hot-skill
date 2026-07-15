已有工具清单
MasterGo Magic MCP (v0.2.2) 共 12 个 tool：
Tool
用途
是否纳入
getDsl
返回完整节点树 + 样式引用
是
getMeta
站点/页面级配置规则
是
getDesignSections
双模式：概览 + 逐段 DSL
是
getDesignSvgs
补全 Section 剥离的 PATH svgHtml
是
getDesignTexts
补全长文本原文
是
extractSvg
PATH → 合成带颜色的完整 SVG
是
getComponentLink
组件文档（条件触发）
是
getD2c
编译产物：HTML + 解析后 CSS
是
getComponentGenerator
前端组件开发工作流
否
getFlutterGenerator
Flutter 组件开发工作流（不是 H5）
否
C2d
代码反向同步到设计稿
否
version_0_2_2
版本标识
否


---

阶段一详细步骤：MCP 数据采集

Step 1: getDsl              ← 完整 DSL，必须最先调
Step 2: getMeta             ← 站点/页面配置
Step 3: getDesignSections   ← 概览（不传 sectionIndex）
Step 4: getDesignSections   ← 逐段拉取（sectionIndex=0,1,2...）
Step 5: getDesignSvgs       ← 补全 PATH 被剥离的 svgHtml
         getDesignTexts     ← 补全长文本原文
         extractSvg         ← 合成 PATH → 带颜色的完整 SVG
Step 6: getComponentLink    ← 组件文档（componentDocumentLinks 非空时）
Step 7: getD2c              ← 补 blendMode/rotation/clip 等渲染属性

Step 1 — getDsl（必须最先调）
返回完整节点树 + 样式引用（paint / font / effect） + componentDocumentLinks。
为什么必须第一个：MCP 服务器按 token+fileId 缓存状态。如果先调了 getDesignSections，getDsl 会返回 skipped:true，导致 path.data 等完整几何数据永久丢失。
DSL 返回的节点属性按类型分布：

所有类型共有: id, name, type, children, layoutStyle, fill
FRAME 额外:   effect, opacity
GROUP 额外:   opacity
LAYER 额外:   effect, opacity, mask, borderRadius, strokeAlign/Color/Type/Width
PATH 额外:    effect, opacity, mask, path
TEXT 额外:    effect, text, textAlign, textMode, textColor, stroke*
Step 2 — getMeta
返回站点/页面级配置规则（markdown），包含全局样式约束和构建规则。
Step 3 — getDesignSections（概览模式）
不传 sectionIndex。拿到 totalSections、每个 section 的 id/name/type/nodeCount/bbox、rootMetadata、rootContainer、splitContainers。
Step 4 — getDesignSections（逐段拉取）
对 sectionIndex=0 到 totalSections-1，3-5 个一批并发。
注意：Section DSL 做了精简 — PATH 的 svgHtml 被剥离、长文本（>50 字符）替换为 T{index}|{nodeId} 占位符、path.data 可能清空、relativeX/Y 可能归零。
Step 5 — 补全剥离数据
同时调用三个 tool：
- getDesignSvgs：取回 Section 剥离的 PATH 节点 svgHtml，按 nodeId 映射
- getDesignTexts：取回长文本原文，按 T{sectionIndex}|{nodeId} 键映射
- extractSvg：将 PATH 的贝塞尔曲线 + paint 引用合成为完整 SVG 字符串（带实际色值）
getDesignSvgs 和 extractSvg 是互补关系：前者补回被 Section 剥离的数据，后者从 PATH 几何合成新的 SVG 并解析颜色引用。
Step 6 — getComponentLink（条件触发）
检查 Step 1 中 getDsl 返回的 componentDocumentLinks。非空则对每个 URL 调用 getComponentLink。为空则跳过。不能自己编造 URL。
当 DSL 里有组件实例时，实例节点只包含被覆盖的属性，基础结构在组件定义里。不拉文档 = 丢了一半样式。
Step 7 — getD2c（条件触发）
D2C 是设计文件的"编译产物"，包含 DSL 完全不提供的渲染层属性。
参数：
- contentId = <fileId>-<layerId 中 : 替换为 ->
- documentId = fileId
- outDir = 05-d2c/
若返回 404（code 10009）则跳过并记录到 unresolved，不阻塞。
从 D2C HTML/CSS 中提取以下属性回填：
CSS 属性
归一化字段
提取规则
mix-blend-mode
blendMode
DSL 完全不提供，D2C 唯一来源
transform: rotate(Xdeg)
rotation
DSL 完全不提供
transform: rotateX/Y() / scaleX(-1)
rotationX / rotationY
DSL 完全不提供
overflow: hidden
clipsContent
DSL 完全不提供
box-shadow
effect
DSL 有则保留 DSL，没有则回填
filter: blur() / drop-shadow()
effect
同上
opacity
opacity
DSL 为默认值 1 时回填
border-radius
borderRadius
DSL 为空时回填
background / background-color
fill
已解析值优先于 DSL paint 引用
NodeId 映射：解析 HTML，从 id、data-node-id、data-id、class 匹配，尝试 0:919、0-919、node-0-919 等格式。

---

【注意】
1）DSL 已提供但 merge 需要保护的关键字段
textRuns（多色/多段文字）
DSL 中 TEXT 节点通过两个数组描述富文本：
"text": [
  {"text": "美国电网迎来史诗级扩建", "font": "font_0:196"},
  {"text": "，750亿美元投资计划落地...", "font": "font_0:169"}
],
"textColor": [
  {"start": 0,  "end": 11, "color": "paint_0:306"},
  {"start": 11, "end": 40, "color": "paint_0:171"}
]
两者合并为 textRuns：每段文字 + 字符位置 + 颜色 + 字体。
保护规则：getDsl 首次返回的 textRuns 是权威数据。后续 Section DSL 的 merge 不能覆盖，因为 Section DSL 中长文本已被替换为占位符 T{index}|{nodeId}，会导致 textRuns 中实际文字丢失。
text
保护规则：Section DSL 的 T\d+|\d+:\d+ 占位符不能覆盖 getDsl 返回的真实文字。
path.data
保护规则：Section DSL 可能清空 path.data，不能覆盖 getDsl 的完整版本。
relativeX/Y
保护规则：Section DSL 可能归零 relativeX/Y，不能覆盖 getDsl 的正确坐标值。


---

2）DSL 完全不提供的字段（只来自 D2C）

这 5 个字段 只存在于 D2C，DSL / getMeta / getDesignSections 都不返回：

字段
含义
设计稿中的表现
blendMode
图层混合模式
滤色 / 正片叠底 / 叠加等
rotation
旋转角度
节点被旋转了多少度
rotationX
X 轴翻转
水平镜像翻转
rotationY
Y 轴翻转
垂直镜像翻转
clipsContent
裁剪溢出
节点内内容超出边界时被裁掉
为什么 DSL 没有这些字段？DSL 是设计文件的"数据快照"（结构 + 几何 + 样式引用），不包含渲染引擎在合成图层时才计算的属性。D2C 是设计文件的"编译产物"（完整 HTML + CSS），编译过程中这些渲染属性变成了具体的 CSS 属性。DSL 是原料清单，D2C 是成品。
3）合并优先级
先来的数据比后来的更全，全的不能被缺的覆盖：

数据类别
权威来源
处理方式
结构（parentId/childrenIds）
getDsl
不被覆盖
几何（bounds/layoutStyle）
getDsl
不被 Section 归零值覆盖
text
getDsl > getDesignTexts > Section DSL
占位符不覆盖真实文字
textRuns
getDsl 首次
不被 Section 占位符版覆盖
path.data
getDsl
不被 Section 清空版覆盖
svg
getDesignSvgs + extractSvg
不覆盖已有非空值
blendMode / rotation / rotationX / rotationY / clipsContent
D2C 唯一来源
DSL 不提供
effect / borderRadius / opacity
DSL 优先，D2C 补充
D2C 只回填空值
fill
D2C 已解析色值 > DSL paint 引用
已解析优先
组件基础样式
getComponentLink
写入 componentDefinition


---

4）输出结构

最终写入 data/source/mastergo-primary/01-all-data.json：

{
  "captureManifest": {},
  "overview": {},
  "mcpToolInventory": [],
  "rawMcpResponses": [],
  "sections": [],
  "texts": [],
  "svgs": [],
  "componentDocuments": [],
  "styles": {
    "paint": {},
    "font": {},
    "effect": {},
    "styleRefsByNode": {},
    "usedBy": {}
  },
  "normalizedNodes": {
    "<nodeId>": {
      "id": "string",
      "name": "string",
      "type": "FRAME|TEXT|PATH|LAYER|GROUP|SVG_ELLIPSE",
      "parentId": "string|null",
      "childrenIds": ["string"],
      "ancestorPath": ["string"],
      "sources": ["string"],
      "bounds": { "x": 0, "y": 0, "width": 0, "height": 0 },
      "layoutStyle": { "relativeX": 0, "relativeY": 0, "width": 0, "height": 0 },
      "fill": "string|null",
      "stroke": "string|null",
      "effect": "string|null",
      "opacity": 1,
      "rotation": 0,
      "blendMode": "string|null",
      "borderRadius": "string|null",
      "mask": "string|null",
      "text": "string|null",
      "textRuns": [{
        "text": "string",
        "start": 0,
        "end": 0,
        "color": "string",
        "font": "string"
      }],
      "textAlign": "string|null",
      "textMode": "string|null",
      "path": "object|null",
      "svg": "string|null",
      "strokeColor": "string|null",
      "strokeType": "string|null",
      "strokeAlign": "string|null",
      "strokeWidth": "string|null",
      "rotationX": "string|null",
      "rotationY": "string|null",
      "clipsContent": false,
      "styleRefs": {},
      "componentDefinition": {},
      "captureStatus": "complete|supplemented|unresolved"
    }
  },
  "reconstructedTree": {
    "roots": [],
    "edges": []
  },
  "checks": {
    "readToolAudit": {},
    "unresolvedMissingDataCount": 0,
    "unresolvedMissingData": []
  }
}
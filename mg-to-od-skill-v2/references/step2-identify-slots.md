# Step 2 操作手册：Frame 类型判定与骨架分区

## 前置条件

- Step 1 已完成，`data/<project>/output/modules-classification.json` 存在。
- `data/<project>/modules/` 下有 Step 1 拆好的 module JSON 文件。
- `modules-classification.json` 只告诉你有哪些 group、每个 group 对应哪些 module 索引；真正的 node 树数据在 `modules/*.json` 里面。

## 输出约定

本阶段所有中间产物和最终输出统一写入 `data/<project>/output/`。

---

## 流程总览

```
Step 1 输出（output/modules-classification.json）
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Step 2.1 [脚本] 选取代表 frame + 提取 TEXT 预览         │
│   输入: output/modules-classification.json            │
│   输出: output/step2-01_frame-types.json（含 texts 列表）  │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Step 2.2 [AI] 判定 frameType                         │
│   打开: output/step2-01_frame-types.json                 │
│   填写: frameType（"fully-fixed" / "template" /       │
│         "content"）                                   │
└─────────────────────────────────────────────────────┘
    │
    ├── fully-fixed ──► 直接结束（不再处理）
    │
    ▼ (template + content 都进入)
┌─────────────────────────────────────────────────────┐
│ Step 2.3 [脚本] 统一重复检测 + 提取模板 TEXT          │
│   输入: output/step2-01_frame-types.json                 │
│         modules/*.json                               │
│   输出: output/step2-01_frame-types.json（+重复标记）     │
│         output/step2-02_text-judgments.json（仅 template）│
│                                                      │
│   行为:                                               │
│   · 对所有 frame 做结构指纹重复检测                    │
│   · 重复实例只保留第一个作为模板                       │
│   · 模板型 → 从模板提取 TEXT 供 AI 判断               │
│   · 写入 repeatable / repeatCount 到 frame-types      │
└─────────────────────────────────────────────────────┘
    │
    ├── template ──────┐
    │                   ▼
    │  ┌──────────────────────────────────────────────┐
    │  │ Step 2.4 [AI] 判断每条 TEXT 是 fixed 还是      │
    │  │              variable                         │
    │  │   打开: output/step2-02_text-judgments.json       │
    │  │   填写: judgment（"fixed" / "variable"）       │
    │  └──────────────────────────────────────────────┘
    │                   │
    │                   │
    └── content ────────┤
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 2.5 [脚本] 构建输出（第 1 次运行）               │
│   输入: output/step2-01_frame-types.json（含重复标记）    │
│         output/step2-02_text-judgments.json (如有)       │
│         modules/*.json                               │
│   输出: output/step2-04_slots-definition.json (初步)     │
│         output/step2-03_content-zones.json (审阅文件)    │
│                                                      │
│   行为:                                               │
│   · fully-fixed → 直接写入最终输出                    │
│   · template    → 读 AI 判断，输出 fixedGroups+slots  │
│                   重复帧只输出模板结构                 │
│   · content     → 纯几何分区（对模板实例），输出 zones │
│                   重复帧只输出模板的 zone              │
└─────────────────────────────────────────────────────┘
                        │
                        ▼ (仅当有内容型 frame 时)
┌─────────────────────────────────────────────────────┐
│ Step 2.6 [AI] 审阅内容型 zone                         │
│   打开: output/step2-03_content-zones.json               │
│   填写: keep（"true" / "false"）                      │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 2.7 [脚本] 重新构建（第 2 次运行）               │
│   输入: output/step2-01_frame-types.json                 │
│         output/step2-02_text-judgments.json              │
│         output/step2-03_content-zones.json (已审阅)      │
│   输出: output/step2-04_slots-definition.json (最终)     │
│                                                      │
│   行为: 读 keep:false → 从最终输出中移除对应 zone      │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│ Step 2.8 [脚本] 可视化（可选）                        │
│   输入: output/step2-04_slots-definition.json            │
│   输出: output/step2-05_zone-visualization.html          │
└─────────────────────────────────────────────────────┘
```

---

## Step 2.1 [脚本] 选取代表 frame + 提取 TEXT 预览

**做什么**：从 Step 1 的 modules-classification.json 中，对每个 group 取第一个 instance 作为代表，并提取该 frame 内所有文字内容（TEXT 节点 + 转成 PATH 的隐式文字），含 text + nodeId + fromName 标记。

**运行**：`scripts/step2_select_representatives.py`

**输入**：

| 文件 | 来源 |
|------|------|
| `data/<project>/output/modules-classification.json` | Step 1 输出 |
| `data/<project>/modules/*.json` | 原始设计稿 module 数据（提取 TEXT 内容 + nodeId） |

**输出**：

| 文件 | 说明 |
|------|------|
| `data/<project>/output/step2-01_frame-types.json` | 代表 frame 列表（含 TEXT 预览），frameType 留空 |

**输出格式**：

```json
{
  "frames": [
    {
      "groupId": "background",
      "groupName": "背景",
      "moduleJson": "data/<project>/modules/00-背景图.json",
      "frameType": "",
      "textCount": 0,
      "texts": []
    },
    {
      "groupId": "productCard",
      "groupName": "产品卡",
      "moduleJson": "data/<project>/modules/01-产品卡.json",
      "frameType": "",
      "textCount": 8,
      "texts": [
        { "text": "华夏中证红利低波动ETF发起式联接C", "nodeId": "0:57" },
        { "text": "021483", "nodeId": "0:63" },
        { "text": "近一年涨跌幅", "nodeId": "4:0409" },
        { "text": "2.80%", "nodeId": "0:66" },
        { "text": "较高风险", "nodeId": "0:68" },
        { "text": "管理费", "nodeId": "0:70" },
        { "text": "0.15%", "nodeId": "0:72" },
        { "text": "小试一笔", "nodeId": "0:55" }
      ]
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `groupId` / `groupName` | 来自 Step 1 |
| `moduleJson` | frame JSON 路径（后续脚本用，AI 无需关注） |
| `frameType` | **待 AI 填写**：`"fully-fixed"` / `"template"` / `"content"` |
| `textCount` | TEXT 总数（0 = 无文字 → 大概率 fully-fixed） |
| `texts[].text` | 文字内容（**AI 判断 frameType 的依据**） |
| `texts[].nodeId` | 在 node 树中的 id（**脚本用，AI 无需关注**） |
| `texts[].fromName` | `true` = 该文字来自 GROUP/FRAME 名称（MasterGo 将文字转成了 PATH）；`false` = 来自真实 TEXT 节点 |
| `repeatable` | Step 2.3 填入：`true` = 含重复子模块 |
| `repeatCount` | Step 2.3 填入：重复实例数量 |

---

## Step 2.2 [AI] 判定 frameType

**打开文件**：`data/<project>/output/step2-01_frame-types.json`

**做什么**：看每个 frame 的 `texts` 列表，判断 frameType 并填写。**不需要打开 moduleJson**，只看 texts 就够了。

**填写**：逐条填入 `frameType`，值为以下三种之一：

| frameType | 含义 |
|-----------|------|
| `"fully-fixed"` | 完全固定，不随产品/热点变化 |
| `"template"` | 模板型 — 产品信息表结构 |
| `"content"` | 内容型 — 图文内容 |

---

### 判断方法

#### 第一步：筛固定模块（fully-fixed）

问自己：「整个 frame 的内容是否不随产品/热点变化？」

- `textCount` 为 0（没有任何 TEXT 节点）→ `"fully-fixed"`
- 有 TEXT，但全是品牌 slogan、监管合规全文、客服电话等**不会换的固定文案** → `"fully-fixed"`
- frame 内既有固定文字又有可变文字 → **不是固定模块**，继续判断

```
典型 fully-fixed：
  · textCount=0：背景图（纯装饰 LAYER/PATH）
  · texts=["买基金来招行"]：银行结束语
  · texts=["让财富有温度"]：品牌标语
```

#### 第二步：分模板型 vs 内容型

核心区别：**这段文字是在"列事实"还是在"做解释"？**

| → `"template"` | → `"content"` |
|----------------|---------------|
| **只陈述产品基本信息**：产品名、基金代码、风险等级、费率、涨跌幅……字段标签 + 值的结构，不解释"为什么买" | **解释为什么要买这个产品**：市场解读、热点分析、推荐理由、产业链分析……有观点、有论述、有逻辑 |
| 字数少，每条 TEXT 通常是短标签或短数值 | 字数多，有大段正文、长句、段落 |

换句话说：如果这个 frame 换一个产品，只需要换掉产品名/代码/费率这些**字段值** → `"template"`；如果换一个热点/产品，整段论述都要重写 → `"content"`。

**从 texts 列表判别**：

- texts 里大量出现"产品名称""基金代码""风险等级""近一年涨跌幅""管理费""托管费""费率""买入""查看更多"这类**字段标签 + 按钮文案**，没有观点性句子 → `"template"`
- texts 里出现长句、数据来源标注（"截至…""资料来源…"）、分析性表述（"…走强""…利好…""建议关注…"）→ `"content"`

| 模板型例子 | 内容型例子 |
|-----------|-----------|
| 产品卡、风险警告（费率表）、关联产品列表、头图/banner | 推荐理由、热点速递、市场解读、产业链解读 |

> **头图/banner 永远是模板型**：背景图固定，只换主标题文字。

#### 第三步：填写

对每条 frame 填好 `frameType` 后保存文件。

填完后：
- `"fully-fixed"` → 直接结束，不再处理
- `"template"` 和 `"content"` → 都进入 Step 2.3（统一重复检测）
- Step 2.3 之后分流：template 进入 Step 2.4，content 直接进入 Step 2.5

---

## Step 2.3 [脚本] 统一重复检测 + 提取模板型 TEXT

**做什么**：在分叉处理之前，对 **所有 frame**（template + content）做结构指纹重复检测，确保重复实例只保留第一个作为模板。然后将 `repeatable` / `repeatCount` 写回 `step2-01_frame-types.json`，并提取模板型 frame 的 TEXT 供 AI 判断。

**运行**：`scripts/step2_extract_texts.py`

**输入**：

| 文件 | 来源 |
|------|------|
| `data/<project>/output/step2-01_frame-types.json` | Step 2.2 AI 填写后 |
| `data/<project>/modules/*.json` | 原始设计稿 module 数据（读 node 树做结构指纹 + 提取 TEXT） |

**输出**：

| 文件 | 说明 |
|------|------|
| `data/<project>/output/step2-01_frame-types.json` | **更新**：添加了 `repeatable` / `repeatCount` 字段 |
| `data/<project>/output/step2-02_text-judgments.json` | 仅模板型 frame 的 TEXT 列表，judgment 留空 |

**step2-01_frame-types.json 新增字段**：

| 字段 | 说明 |
|------|------|
| `repeatable` | `true` = 此 frame 包含连续结构相同的重复子模块 |
| `repeatCount` | 重复实例数量（如 5 张产品卡 → 5）。非重复帧为 1 |

**输出格式**：

```json
{
  "frames": {
    "产品卡": {
      "texts": [
        { "text": "华夏中证红利低波动ETF发起式联接C", "judgment": "", "nodeId": "0:57" },
        { "text": "021483", "judgment": "", "nodeId": "0:63" },
        { "text": "近一年涨跌幅", "judgment": "", "nodeId": "4:0409" },
        { "text": "小试一笔", "judgment": "", "nodeId": "0:55" }
      ]
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| `text` | 文字内容（AI 判断依据） |
| `nodeId` | TEXT 在 node 树中的唯一 id |
| `judgment` | **待 AI 填写**：`"fixed"` 或 `"variable"` |

---

## Step 2.4 [AI] 判断每条 TEXT 是 fixed 还是 variable

**做什么**：阅读每条 TEXT 的文字内容，判断它是固定文案还是可变数据，填写 `judgment` 字段。

**打开文件**：`data/<project>/output/step2-02_text-judgments.json`

**填写**：逐条将 `judgment` 填为 `"fixed"` 或 `"variable"`。

---

### 判断原则

这是一个基金产品营销 H5。内容围绕一条链条：

```
行业/热点解读 → 推荐产品 → 推荐理由论述
```

- 落在链条上的 TEXT → **variable**（换产品/换热点就会换）
- 链条之外（品牌标识、按钮文案、字段标签、合规声明）→ **fixed**（永远不变）

对每条文字问：「换一个热点，推另一个产品，这段文字还会一样吗？」

---

### Few-shot 参考

```
"华夏中证红利低波动ETF发起式联接C" → variable（产品名，换产品必换）
"021483"                          → variable（基金代码，跟产品绑定）
"较高风险"                         → variable（风险等级，不同产品不同）
"2.80%"                           → variable（涨跌幅数值，随市场变化）
"0.15%"                           → variable（费率数值，不同产品不同）

"近一年涨跌幅"                      → fixed（字段标签，指标名称不变）
"管理费"                           → fixed（字段标签，同上）
"托管费"                           → fixed（字段标签，同上）
"收费方式/年费率"                   → fixed（字段标签，同上）
"费用类别"                         → fixed（表头，同上）

"小试一笔"                         → fixed（按钮文案，永远不变）
"查看更多"                         → fixed（按钮文案，同上）

"让财富有温度"                      → fixed（品牌 slogan）
"基金非存款，产品有风险，投资须谨慎…"  → fixed（合规声明，监管要求固定全文）
```

### 判断技巧

- **字段标签 vs 数值**：标签 fixed，数值 variable。它们是不同 TEXT 节点，各判各的。
- **含产品名的 TEXT** 几乎一定是 variable。
- **合规声明里的独立费率数值**：声明全文 fixed，但嵌入的费率数值如果是独立 TEXT 节点 → variable。

填完后保存。下一步 Step 2.5 会读取这些判断来构建输出。

---

## Step 2.5 [脚本] 构建输出（第 1 次运行）

**做什么**：根据 frameType 走三条分支处理所有 frame，生成初步的 slots-definition 和内容型 zone 审阅文件。

**运行**：`scripts/step2_build_slots.py`（第 1 次）

**输入**：

| 文件 | 来源 |
|------|------|
| `data/<project>/output/step2-01_frame-types.json` | Step 2.2 AI 填写后 |
| `data/<project>/output/step2-02_text-judgments.json` | Step 2.4 AI 填写后（如有 template frame） |
| `data/<project>/modules/*.json` | 原始设计稿 module 数据（node 树、TEXT、bounds 等） |（读 node 树做几何分区 / fixedGroups 查找） |

**输出**：

| 文件 | 说明 |
|------|------|
| `data/<project>/output/step2-04_slots-definition.json` | 初步构建结果（fully-fixed 和 template 已最终，content 为候选 zone） |
| `data/<project>/output/step2-03_content-zones.json` | **AI 审阅文件**：仅内容型 frame 的 zone 候选列表 |

---

### 脚本内部行为（了解即可）

**fully-fixed**：整帧标记为 `fullyFixed: true`，输出 fixedGroups 包含全部 nodeIds。

**template**：
1. 读 `step2-02_text-judgments.json` 中 AI 填好的 judgment
2. `"fixed"` TEXT → 向上找不含 variable TEXT 的最紧容器 → 归入 fixedGroups
3. `"variable"` TEXT → 直接入 slots（平铺，按 y 排序）
4. `fromName` 条目（文字转 PATH 的 GROUP）→ 同逻辑，以 GROUP 为容器
5. 无 zone，骨架固定不变

**content**：
1. 先检测重复子模块（结构指纹）
2. 纯几何分区：找大面积 fill LAYER/PATH → 遮挡计算 → 合并碎片 → 过滤
3. zone 外 TEXT → 向上找不含 zone TEXT 的最外层容器 → `fixed-label`
4. 每个骨架节点只输出一次（多个 visible 碎片 union 为一个 visibleRect）
5. 所有 zone 的 contentArea = boundary 四边内缩 24px，自动判定 textAlign
6. 关键阈值：骨架候选 ≥ 帧 5% 面积、可见 ≥ 15%、zone 高度 ≥ 帧 15%、间隙 ≤ 15px 合并

---

## Step 2.6 [AI] 审阅内容型 zone

> **触发条件**：Step 2.5 后 `output/step2-03_content-zones.json` 存在且有内容。如果项目没有内容型 frame，跳过 Step 2.6-2.7。

**做什么**：脚本几何分区后，可能有不该是内容区的碎片（如 badge 标签区）。AI 需要逐个 zone 判断 keep 还是 discard。

**打开文件**：`data/<project>/output/step2-03_content-zones.json`

**文件格式**：

```json
{
  "frames": [
    {
      "groupName": "热点前线",
      "zones": [
        {
          "id": "zone-0",
          "height": 30,
          "sampleSlots": ["热点前线"],
          "keep": ""
        },
        {
          "id": "zone-1",
          "height": 233,
          "sampleSlots": ["电网设备板块走强..."],
          "keep": ""
        }
      ]
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `id` | zone 编号 |
| `height` | zone 高度（px） |
| `sampleSlots` | 该 zone 内的文字样例（最多 3 条，每条截断 40 字） |
| `keep` | **待 AI 填写**：`"true"` 或 `"false"` |

**填写**：对每个 zone，看 `sampleSlots`，问自己：**「换一个热点 / 换一个产品，这些文字还会一样吗？」**

判断逻辑和 Step 2.4 完全一致——这里本质上是在筛"固定文字误入内容 zone"的情况：

| → 填 `"false"`（删除此 zone） | → 填 `"true"`（保留此 zone） |
|-------------------------------|----------------------------|
| zone 内所有文字都是**固定不变的**，不随热点/产品切换而变化 | zone 内有**可变的**内容文字，换热点/产品会跟着变 |

典型例子：

```
"热点速递"  → false（模块标题，永远是这四个字）
"市场解读"  → false（同上）
"热点前线"  → false（同上）
"数据来源：Wind，截至2025/3/5" → true（数据会更新）
"电网设备板块走强，中证电网设备主题指数上涨4.1%…" → true（市场内容会变）
```

`height` 和文字长度只是辅助信号：固定标签通常高度小、字数少——但不是绝对的。**核心只看文字本身是否固定**。

填完后保存。下一步重新运行脚本应用审阅。

---

## Step 2.7 [脚本] 重新构建（第 2 次运行）

> **触发条件**：Step 2.6 已完成 AI 审阅。如果没有内容型 frame，跳过此步。

**做什么**：重新运行 `step2_build_slots.py`，读取 AI 审阅结果，将 `keep: false` 的 zone 从最终输出中移除。

**运行**：`scripts/step2_build_slots.py`（第 2 次）

**输入**：

| 文件 | 来源 |
|------|------|
| `data/<project>/output/step2-01_frame-types.json` | Step 2.2 |
| `data/<project>/output/step2-02_text-judgments.json` | Step 2.4（如有） |
| `data/<project>/output/step2-03_content-zones.json` | Step 2.6 AI 审阅后 |

**输出**：

| 文件 | 说明 |
|------|------|
| `data/<project>/output/step2-04_slots-definition.json` | **最终输出**：AI 审阅后的 zone 已应用 |

---

## Step 2.8 [脚本] 可视化（可选）

**做什么**：生成 HTML 框线图，在浏览器中直观查看 zone 分区效果。

**运行**：`scripts/step2_visualize_zones.py`

**输入**：

| 文件 | 来源 |
|------|------|
| `data/<project>/output/step2-04_slots-definition.json` | Step 2.7 最终输出 |

**输出**：

| 文件 | 说明 |
|------|------|
| `data/<project>/output/step2-05_zone-visualization.html` | 浏览器打开查看 zone 分区 |

---

## 最终输出：step2-04_slots-definition.json

Step 2 的最终产物是 `data/<project>/output/step2-04_slots-definition.json`，三种 frameType 统一写入，结构因类型而异：

### 固定模块

```json
{
  "groupId": "background",
  "groupName": "背景",
  "fullyFixed": true,
  "frameId": "13:385",
  "frameName": "背景",
  "frameWidth": 1125,
  "fixedGroups": [{
    "groupId": "13:385",
    "groupName": "背景",
    "role": "fully-fixed-frame",
    "nodeIds": [{"nodeId": "13:385", "name": "背景"}, …],
    "reason": "完全固定 frame：无可变内容"
  }],
  "zones": []
}
```

### 模板型

```json
{
  "groupId": "productCard",
  "groupName": "产品卡",
  "frameType": "template",
  "repeatable": false,
  "frameId": "13:390",
  "frameName": "产品卡",
  "frameWidth": 1075,
  "fixedGroups": [
    {
      "groupId": "0:53",
      "groupName": "按钮",
      "role": "brand-badge",
      "nodeIds": [
        { "nodeId": "0:53", "name": "按钮" },
        { "nodeId": "0:54", "name": "矩形 备份 14" },
        { "nodeId": "0:55", "name": "小试一笔" }
      ],
      "reason": "TEXT '小试一笔' 为固定文案，连带容器整体固定"
    }
  ],
  "slots": [
    { "nodeId": "0:57", "name": "华夏中证红利低波动ETF发起式联接C", "text": "华夏中证红利低波动ETF发起式联接C" },
    { "nodeId": "0:63", "name": "021483", "text": "021483" }
  ]
}
```

> 模板型无 zone。slots 平铺在模块下，骨架固定不变，Step 3 替换 variable TEXT 即可。

### 内容型

```json
{
  "groupId": "recommendations",
  "groupName": "产品推荐理由",
  "frameType": "content",
  "repeatable": false,
  "frameId": "13:387",
  "frameName": "产品推荐理由A",
  "frameWidth": 1076,
  "fixedGroups": [
    {
      "groupId": "0:71",
      "groupName": "Clip",
      "role": "mask",
      "nodeIds": [
        { "nodeId": "0:71", "name": "Clip" },
        { "nodeId": "0:72", "name": "蒙版" },
        { "nodeId": "0:73", "name": "矩形" }
      ],
      "reason": "蒙版组"
    }
  ],
  "zones": [
    {
      "id": "zone-0",
      "boundary": { "yStart": 1806, "yEnd": 1863 },
      "skeletonLayers": [
        { "nodeId": "0:77", "name": "Gradient Overlay", "visibleRect": { "x": 327, "y": 1806, "width": 472, "height": 57 } }
      ],
      "slots": [
        { "nodeId": "0:76", "name": "左手红利 右手低波", "text": "左手红利 右手低波" }
      ]
    },
    {
      "id": "zone-2",
      "boundary": { "yStart": 1952, "yEnd": 2816 },
      "skeletonLayers": [
        { "nodeId": "0:83", "name": "矩形 1000 拷贝", "visibleRect": { "x": 25, "y": 1952, "width": 1076, "height": 863 } }
      ],
      "slots": [
        { "nodeId": "0:84", "text": "中证红利低波动指数选取50只…" }
      ]
    }
  ]
}
```

> 内容型有 zones。每个 zone 是几何分区结果，zones 内的 slots 为 AI 审阅后保留的内容区 TEXT。

### 字段速查

**模块级**：

| 字段 | 说明 |
|------|------|
| `frameType` | `"fully-fixed"` / `"template"` / `"content"`（固定模块用 `fullyFixed: true`） |
| `repeatable` | `true` = 脚本检测到重复子模块 |
| `groupId` / `groupName` | 来自 Step 1 |
| `moduleIndexes` / `representativeIndex` | 模块索引 |
| `frameId` / `frameName` / `frameWidth` | frame 元信息 |

**fixedGroups**：

| 字段 | 说明 |
|------|------|
| `groupId` | 顶层容器 id |
| `groupName` | 容器名称 |
| `role` | 模板型：`brand-badge` / `fixed-texts`；内容型：`mask` / `fixed-label`（zone 外的固定标签容器）；固定模块：`fully-fixed-frame` |
| `nodeIds` | `[{nodeId, name}]` 该组所有节点及其 MasterGo 图层名 |
| `reason` | 判定依据 |

**slots（模板型平铺，内容型在 zone 内）**：

| 字段 | 说明 |
|------|------|
| `nodeId` | 节点 id（TEXT 或 GROUP） |
| `name` | 节点在 MasterGo 中的名称，方便对照设计稿定位 |
| `text` | 当前文字内容 |

**zones（仅内容型）**：

| 字段 | 说明 |
|------|------|
| `zones[].id` | `zone-0`、`zone-1`……按 y 从上到下 |
| `zones[].boundary` | xStart / xEnd / yStart / yEnd（骨架区域） |
| `zones[].skeletonLayers` | 组成该区的骨架节点 |
| `zones[].slots` | 该区内的可变 TEXT |
| `zones[].contentArea` | `{x, y, width, height}` 可写区域 = zone boundary 四边内缩 padding（24px） |
| `zones[].padding` | `{top, bottom, left, right}` 固定值 24px，所有项目统一 |
| `zones[].textAlign` | `"left"` 或 `"center"`——由 slot TEXT 的 x 中心是否靠近 zone 中心自动判定 |

---

## 脚本速查表

| 步骤 | 脚本 | 触发条件 | 关键输入 | 关键输出 |
|------|------|---------|---------|---------|
| 2.1 | `step2_select_representatives.py` | 必运行 | `output/modules-classification.json` | `output/step2-01_frame-types.json` |
| 2.2 | **AI** | 必做 | `output/step2-01_frame-types.json` | 同一文件（填 frameType） |
| 2.3 | `step2_extract_texts.py` | 有 template frame | `output/step2-01_frame-types.json` | `output/step2-02_text-judgments.json` |
| 2.4 | **AI** | 有 template frame | `output/step2-02_text-judgments.json` | 同一文件（填 judgment） |
| 2.5 | `step2_build_slots.py` | 必运行 | `output/step2-01_frame-types.json` + judgments | `output/step2-04_slots-definition.json` + `output/step2-03_content-zones.json` |
| 2.6 | **AI** | 有 content frame | `output/step2-03_content-zones.json` | 同一文件（填 keep） |
| 2.7 | `step2_build_slots.py` | 有 content frame | content-zones（已审阅） | `output/step2-04_slots-definition.json`（最终） |
| 2.8 | `step2_visualize_zones.py` | 可选 | `output/step2-04_slots-definition.json` | `output/step2-05_zone-visualization.html` |

---

## 技术参数（参考）

内容型几何分区的阈值，当前硬编码在 `step2_build_slots.py` 中：

| 参数 | 值 | 说明 |
|------|-----|------|
| 骨架候选最小面积 | 帧 5% | 过滤小 badge、装饰线 |
| 可见面积门槛 | 原始 15% | 被遮挡过多的骨架排除 |
| zone 合并重叠阈值 | 90% | 重叠面积超此值合并 |
| zone 间距合并阈值 | 15px | 相邻 zone 间隙 ≤ 此值合并 |
| zone 最小高度 | 帧 15% | 过矮的 zone 排除（固定标签） |
| 内容区内边距 | 24px | 所有 zone 的 contentArea = boundary 四边内缩 24px |

其他规则：

- 遮挡计算使用**全局 z-order**（深度优先遍历，跨层级）
- 蒙版（mask/Clip）和其内部节点不参与遮挡
- IMAGE fill 在蒙版内 → 装饰图，不参与分区；蒙版外 → 正常背景
- children 顺序 = z-order（后面的遮挡前面的）
- PATH 和 LAYER 在分区时完全等价
- TEXT 的 y 中心点落入 zone boundary → 归入该 zone
- 每个骨架节点在 `skeletonLayers` 中只出现一次（多个 visible 碎片合并为一个整体 rect）
- 内容型 frame：zone 外的 TEXT → 向上找不含 zone TEXT 的最外层容器 → `fixed-label`
- MasterGo 将文字转为 PATH 时，容器名保留原始文字 → 提取为隐式 TEXT（`fromName: true`）

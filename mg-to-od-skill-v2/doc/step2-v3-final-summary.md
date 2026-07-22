# Step 2 重构总结（2026-07-20）

## 做了什么

### 1. 重新设计 Step 2 流程

文件：`references/step2-identify-slots.md`

**Phase 0：脚本选代表 + AI 判定 Frame 类型**

| 类型 | 说明 | 处理 |
|------|------|------|
| 固定模块 | 无 TEXT 或全文固定（品牌标语/合规声明） | 直接输出 fullyFixed: true |
| 模板型 | 产品信息表（产品卡、费率表）**banner 永远是模板型** | Phase 1a |
| 内容型 | 图文内容（推荐理由、热点解读、市场分析） | Phase 1b |

**Phase 1a：模板型 → TEXT 锚点**

- 脚本提取 TEXT → AI 逐条判断 fixed/variable
- 输出：fixedGroups + slots（平铺，无 zone）
- 重复子模块由脚本自动检测（结构指纹对比容器类型），标记 repeatable

**Phase 1b：内容型 → 几何分区 + AI 审阅**

- 第一步：脚本纯几何分区（大面积 LAYER/PATH + 全局 z-order 遮挡 + 可见区域合并）
- 第二步：AI 打开 `step2_content-zones.json`，对每个 zone 判 content（保留）或 fixed（删除）
- 第三步：重新运行脚本，自动应用 AI 判断
- 输出：zones（boundary + skeletonLayers，不列 slots）

### 2. 重写了三个脚本 + 新增可视化脚本

| 脚本 | 改动 |
|------|------|
| `step2_select_representatives.py` | 输出 step2_frame-types.json（moduleJson 路径 + 空 frameType） |
| `step2_extract_texts.py` | 只处理模板型；重复检测仅容器类型参与 |
| `step2_build_slots.py` | 按 frameType 三分支；全局 z-order 遮挡；5% 面积门槛；输出 content-zones 审阅；应用 AI 过滤 |
| `step2_visualize_zones.py` | **新增**：生成 HTML 框线图展示 zone 分区 |

### 3. 内容型几何分区的关键规则

- 骨架候选：fill + 面积 ≥ 帧 5%（排除 badge、gradient overlay）
- 遮挡：全局 z-order（跨层级）；蒙版不参与；IMAGE fill 在蒙版内不参与；小节点（< 5%）不参与遮挡
- 可见面积 < 15% 排除
- 合并用可见 rects（非原始 bounds）
- 间隙 ≤ 15px 的相邻 zone 合并
- zone 高度 < 帧 15% 排除
- IMAGE fill 仅在蒙版内排除，蒙版外的 IMAGE 是正常背景

### 4. 输出结构

模板型：
```json
{
  "frameType": "template",
  "fixedGroups": [{ "role": "brand-badge", "nodeIds": [...] }],
  "slots": [{ "nodeId": "...", "text": "..." }]
}
```

内容型：
```json
{
  "frameType": "content",
  "fixedGroups": [{ "role": "mask" }],
  "zones": [{
    "id": "zone-0",
    "boundary": { "yStart": 1806, "yEnd": 1863 },
    "skeletonLayers": [{ "nodeId": "0:77", "visibleRect": {...} }]
  }]
}
```

固定模块：
```json
{ "fullyFixed": true, "zones": [] }
```

### 5. 产物

```
data/<project>/
  step2_frame-types.json          ← Phase 0 输出
  step2_text-judgments.json       ← Phase 1a 提取（仅模板型）
  step2_content-zones.json        ← Phase 1b AI 审阅（仅内容型）
  step2_slots-definition.json     ← 最终输出
  step2_zone-visualization.html   ← 可视化
```

### 6. 在 CITC 和 CMB 上验证通过

| | CITC | CMB |
|---|---|---|
| 固定模块 | 2（背景、银行结束语） | 1（买基金来招行） |
| 模板型 | 3（营销头图、产品卡、风险警告） | 3（头图banner、合规提示、相关产品） |
| 内容型 | 2（热点速递、产品推荐理由） | 3（热点前线、市场解读、产品推荐理由） |

---

## 待做

### 脚本
- [ ] 两个脚本的 `detect_repeats` 逻辑统一到共享模块
- [ ] zone 里只有短标签（≤6 字）→ 自动标 fixed，减少 AI 审阅量
- [ ] 遮挡计算 ancestor 检查性能优化
- [ ] 阈值（5%/15%/15px）可配置

### MD 文档
- [ ] Phase 0 判断标准增加 few-shot
- [ ] 几何分区规则与代码实现对齐

### 设计决策（待确认）
- [ ] 内容型 zone 内不区分标题/正文样式——Step 3 需从 TEXT font 属性自行判断
- [ ] 阈值跨项目稳定性

### 后续步骤
- [ ] Step 3（CSS 生成）需适配新 Step 2 输出格式
- [ ] Step 4（模板生成）
- [ ] Step 5（内容 JSON 生成）

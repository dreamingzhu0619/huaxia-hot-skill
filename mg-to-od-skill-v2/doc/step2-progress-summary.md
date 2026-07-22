# Step 2 改造进度总结（2026-07-21）

## 做了什么

### 1. 文档重构：操作手册化

将 `references/step2-identify-slots.md` 从内部参考文档重写为**8 步操作手册**：

| 步骤 | 类型 | 说明 |
|------|------|------|
| 2.1 | 脚本 | `step2_select_representatives.py` — 选代表 + 提取 TEXT 预览 |
| 2.2 | AI | 判定 frameType（fully-fixed / template / content） |
| 2.3 | 脚本 | `step2_extract_texts.py` — 统一重复检测 + 提取模板 TEXT |
| 2.4 | AI | 判断每条 TEXT 的 fixed / variable |
| 2.5 | 脚本 | `step2_build_slots.py`（第 1 次）— 三路分支构建 + 生成 zone 审阅文件 |
| 2.6 | AI | 审阅内容型 zone（keep true/false） |
| 2.7 | 脚本 | `step2_build_slots.py`（第 2 次）— 应用审阅 |
| 2.8 | 脚本 | `step2_visualize_zones.py` — 可视化 |

每步标注了：输入/输出文件、完整 AI 提示词（判断原则 + few-shot）。

同步了对齐了 Step 1 的文档（`references/step1-classify-modules.md`），输出路径统一。

### 2. 输出路径和文件命名规范

- 所有产物统一到 `data/<project>/output/`
- 文件名加序号，方便追踪流水线顺序：

| 序号 | 文件 | 产生于 |
|------|------|--------|
| 01 | `step2-01_frame-types.json` | Step 2.1 / Step 2.3 更新 |
| 02 | `step2-02_text-judgments.json` | Step 2.3（AI 在 2.4 填写） |
| 03 | `step2-03_content-zones.json` | Step 2.5（AI 在 2.6 填写） |
| 04 | `step2-04_slots-definition.json` | Step 2.5 / Step 2.7（最终输出） |
| 05 | `step2-05_zone-visualization.html` | Step 2.8 |

### 3. 统一重复检测（Step 2.3）

将重复检测从各脚本分散处理改为 Step 2.3 统一做——**在 template/content 分叉之前**，对所有 frame 做结构指纹检测：

- 检测结果（`repeatable` / `repeatCount`）写回 `step2-01_frame-types.json`
- 模板型：从去重后的模板子树提取 TEXT → `step2-02_text-judgments.json`
- `step2_build_slots.py` 的 `analyze_template` 同步修了 bug：之前对重复实例的 TEXT 处理不完整

### 4. MasterGo 文字转 PATH 的补救

发现 MasterGo 会将部分文字转为矢量 PATH，原始 TEXT 节点丢失。增加了**基于容器名称的文字提取**：

- `step2_select_representatives.py`：子树无 TEXT 但含 PATH 的 GROUP/FRAME → 检查名称是否为有意义的文字（含中文、非通用名如"矩形""编组""图层"） → 标记 `fromName: true`
- 过滤规则：排除 "编组"、"矩形"、"路径"、"椭圆"、"备份"、"拷贝"、"图片"、"图层"、"形状"、"线条"、"矢量"、"蒙版" 等通用容器名，排除纯编号
- `step2_extract_texts.py` 和 `step2_build_slots.py` 全链路透传 `fromName` 标记
- 验证：CITC 营销头图从 1 条 TEXT 提升到 3 条（找回了被转 PATH 的两个副标题）

### 5. 内容型 frame 的 fixedGroup 检测

之前内容型只检测 mask 作为 fixedGroup。新增：**zone 外的 TEXT → fixedGroup**：

- zone 计算完后，扫描所有不在任何 zone slot 里的 TEXT
- 向上找最外层不含 zone TEXT 的容器 → `fixed-label`
- 验证：CITC "热点速递" 的 "热点速递 拷贝"（GROUP 0:35）正确标记为 fixedGroup

### 6. 骨架碎片合并

遮挡计算后骨架可能被切成多块碎片（同一 node 的多个 visibleRect）。改为取所有碎片的 `union_rect` 合并为一条 skeletonLayer，每个节点只出现一次。

### 7. 输出格式增强

所有 `nodeIds` 从字符串数组改为 `[{nodeId, name}]` 对象，方便对照 MasterGo 图层定位。

所有 slot 增加 `name` 字段。

zone 增加：
- `boundary.xStart / xEnd`（之前只有 y）
- `contentArea`：可写区域 = boundary 四边内缩固定 24px
- `padding`：`{top: 24, bottom: 24, left: 24, right: 24}`
- `textAlign`：`"left"` 或 `"center"`（自动判定：slot TEXT 的 x 中心都靠近 zone 中心 → center）

### 8. 可视化增强

`step2-05_zone-visualization.html` 新增：
- 绿色虚线框标记 contentArea（可写区域）
- 四边间距标注
- 支持 frame x 坐标定位

### 9. 修复的 bug

- `_merge_into_zones` 算好 slots 但没放进 zone dict
- 模板型 `analyze_template` 对重复实例 TEXT 的 judgment 匹配不完整
- 内容型 skeletonLayers 碎片未合并，同一 node 出现多次
- 内容型缺少 fixedGroup 检测（只有 mask）
- fromName 条目在 `build_slots` 里未被处理
- 可视化缺少 frame x 坐标导致 contentArea 定位偏差

---

## 待做

### Step 3（CSS 生成）

- 适配 Step 2 的新输出格式
- 模板型：拿原 frame 结构 + fixedGroups + slots，替换 variable TEXT，保留 fixedGroups 原样
- 内容型：zone skeletonLayers 生成 CSS 骨架（高度自适应），contentArea 内排版，padding 控制内边距，textAlign 控制对齐
- repeatable 帧：模板复制 + 数据循环渲染

### Step 4（模板生成）

- 基于 Step 3 的 CSS + Step 2 的 slots 定义，生成完整 HTML 模板

### Step 5（内容 JSON 生成）

- 根据 slots 结构生成内容填写规范 / 示例 JSON

### 可能的优化

- 两个脚本的 `detect_repeats` 逻辑统一到共享模块（避免维护两份）
- `CONTENT_PADDING` 可配置化（当前硬编码 24px）
- zone 里只有短标签 → 自动标 fixed，减少 Step 2.6 AI 审阅量
- 遮挡计算 ancestor 检查性能优化

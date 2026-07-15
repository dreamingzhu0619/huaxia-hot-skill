# Pipeline 脚本运行指南

> 适用：所有 MasterGo 设计稿。脚本从 `pipeline-template/scripts/` 复制到工作区后运行。

## 脚本清单与运行顺序

| 顺序 | 脚本 | 用途 | 输入 | 产物 |
|---|---|---|---|---|
| 1 | `fetch/fetch_mcp_data.py` | MCP 7 步抓取全量数据 | `config/` | `data/raw/` |
| 2 | `normalize/normalize_to_tree.py` | 归一化节点树 + 合并多源数据 | `data/raw/` | `data/normalized/tree.md` |
| 3 | `prepare/split_modules.py` | 按 d2c section 拆分模块 | `data/normalized/` | `data/modules/` (含 `_index.json`) |
| 4 | `render/generate_module_css.py` | 生成精确源 CSS | `data/modules/` | `assets/styles/modules/*.css` |
| 5 | `analyze/diff_modules.py` | 合并同类模块 + diff invariant/variable | `data/modules/` | `data/analysis/merge_groups.json` + `diff_result.json` |
| 6 | `generate/extract_styles.py` | 机械提取 invariant 属性 → styles.css | `data/modules/` + `data/analysis/` | `output/<name>/assets/<component>/styles.css` |
| 7 | `generate/extract_decorations.py` | 提取 PATH/SVG/位图 → decorations.html | `data/modules/` | `output/<name>/assets/<component>/decorations.html` |
| 8 | `assemble/build_html.py` | 按组件顺序 + 用户数据 → 完整 HTML | `output/<name>/assets/` | `output/<name>/output/example.html` + `template.html` |

## 运行命令

```bash
# 阶段 0：检查配置
python scripts/fetch/fetch_mcp_data.py --check

# 阶段 1：抓取数据
python scripts/fetch/fetch_mcp_data.py

# 阶段 2：归一化 + 拆分
python scripts/normalize/normalize_to_tree.py
python scripts/prepare/split_modules.py

# 阶段 4：生成源 CSS（在模块审阅完成后）
python scripts/render/generate_module_css.py

# 阶段 5：分析 + 生成 assets（新流程）
python scripts/analyze/diff_modules.py
python scripts/generate/extract_styles.py --output-name <name>
python scripts/generate/extract_decorations.py --output-name <name>

# 阶段 6：组装（agent 生成 template.html 后）
python scripts/assemble/build_html.py --output-name <name>
```

## MCP 7 步数据抓取原理

脚本按固定顺序调用 MasterGo MCP 的 7 个 tool，确保数据完整：

### Step 1: getDsl（必须最先调用）
返回完整节点树 + 样式引用（paint / font / effect）。**必须第一个调**，因为 MCP 服务器按 token+fileId 缓存状态。如果先调了 getDesignSections，getDsl 会返回 `skipped:true`，导致 `path.data` 等完整几何数据永久丢失。

### Step 2: getMeta
返回站点/页面级配置规则（markdown），包含全局样式约束和构建规则。

### Step 3-4: getDesignSections（概览 + 逐段拉取）
- 概览：不传 sectionIndex，拿到 totalSections
- 逐段：sectionIndex=0 到 totalSections-1，3-5 个一批并发
- 注意：Section DSL 做了精简——PATH 的 svgHtml 被剥离、长文本替换为占位符、path.data 可能清空

### Step 5: 补全剥离数据（三工具并发）
- `getDesignSvgs`：取回 PATH 节点被剥离的 svgHtml
- `getDesignTexts`：取回长文本原文
- `extractSvg`：PATH 贝塞尔曲线 + paint 引用 → 完整 SVG 字符串

### Step 6: getComponentLink（条件触发）
当 getDsl 返回 `componentDocumentLinks` 非空时调用。组件实例的基础结构在组件定义里，不拉文档 = 丢一半样式。

### Step 7: getD2c（条件触发）
设计文件的"编译产物"，包含 DSL 完全不提供的属性：
- `mix-blend-mode`（图层混合模式）
- `transform: rotate()`（旋转角度）
- `overflow: hidden`（裁剪溢出）
- 补充 effect / opacity / border-radius / fill
- 若返回 404 则跳过并记录

### 合并优先级

| 数据类别 | 权威来源 | 处理方式 |
|---|---|---|
| 结构（parentId/childrenIds） | getDsl | 不被覆盖 |
| 几何（bounds/layoutStyle） | getDsl | 不被 Section 归零值覆盖 |
| text / textRuns | getDsl 首次 | 不被 Section 占位符版覆盖 |
| path.data | getDsl | 不被 Section 清空版覆盖 |
| svg | getDesignSvgs + extractSvg | 不覆盖已有非空值 |
| blendMode / rotation / clipsContent | D2C 唯一来源 | DSL 不提供 |
| effect / borderRadius / opacity | DSL 优先，D2C 补充 | D2C 只回填空值 |
| fill | D2C 已解析色值 > DSL paint 引用 | 已解析优先 |

## 环境依赖

- Python 3.11+ + `pip install mcp`（仅抓取阶段需要 mcp 包）
- Node.js / npx（仅抓取阶段，MCP 调用需要）
- 其余脚本**只依赖 Python 标准库**（json / re / pathlib / shutil）

## Windows 注意事项

- 命令用 `python`（非 python3）
- 读文件用 UTF-8 编码的 Read tool（避免 GBK 乱码）
- bash 用 Git Bash，路径正斜杠

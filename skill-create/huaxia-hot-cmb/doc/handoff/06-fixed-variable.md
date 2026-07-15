# 06-fixed 与 variable 分类

> 从讨论分类方案到落地实现。最后更新：2026-07-09

---

## 0. 分类定义

| 标记 | 含义 | 可变字段 | 典型场景 |
|---|---|---|---|
| `fixed` | 完全不变 | 无 | 背景装饰、品牌元素、图片、结构框架 |
| `variable` | 只改文字 | `textRuns[*].text` | 标题、数字、日期、基金名、收益率 |
| `variable-all` | 全部可变 | text + layoutStyle + fill + stroke + path | 柱状图的矩形、饼图的椭圆、图表容器 |

- **默认 `fixed`**：不需要改的节点不用管。
- **继承规则**：父节点标 `variable-all` → 子节点自动继承，不需要逐个标记图表里的每个矩形/椭圆。
- **只变 text**：尺寸不需要用户手动填。如果换文字导致容器变宽/高，那是渲染层自己算的事。

---

## 1. 新增文件

| 文件 | 说明 |
|---|---|
| `config/variability.json` | 全量节点清单，每个节点带 `name`、`type`、`classification`。TEXT 节点附带当前 `text` 内容，打开就能认出来。 |
| `scripts/input/generate_variability_config.py` | 遍历 `data/modules/*.json` → 全量输出所有节点，默认全标 `fixed`。管线重跑后可重新生成。 |
| `scripts/input/generate_user_input.py` | 读 `config/variability.json` + 模块 JSON → 根据分类提取可变字段 → 输出 `data/input/user-input.json`。 |
| `data/input/user-input.json` | 用户只需要改这里的内容。`fixed` 节点不会出现。 |

---

## 2. `config/variability.json` 结构

```json
{
  "banner": {
    "0:936": {
      "name": "投资落地+出口激增",
      "type": "TEXT",
      "classification": "fixed",
      "text": "投资落地+出口激增"
    },
    "0:937": {
      "name": "电网进入高景气周期",
      "type": "TEXT",
      "classification": "fixed",
      "text": "电网进入高景气周期"
    }
  },
  "market-analysis": {
    "0:959": {
      "name": "市场解读",
      "type": "FRAME",
      "classification": "fixed"
    }
  }
}
```

- 416 个节点，8 个模块，全部默认 `fixed`
- 用户手动把要改的改成 `variable` 或 `variable-all`

---

## 3. `data/input/user-input.json` 结构

`variable` 节点：

```json
{
  "banner": {
    "0:936": { "text": "投资落地+出口激增" }
  }
}
```

`variable-all` 节点（含继承的子节点）：

```json
{
  "market-analysis": {
    "0:919": { "width": 529, "height": 311, "fill": [...], "stroke": {...} },
    "0:921": { "width": 402, "height": 301, "fill": [...], "stroke": {...} }
  }
}
```

---

## 4. 运行

```bash
# 初次生成或管线重跑后重新生成配置文件
python scripts/input/generate_variability_config.py

# 标记完成后，生成用户输入文件
python scripts/input/generate_user_input.py
```

---

## 5. 工作流

```
generate_variability_config.py   → config/variability.json（全量，全 fixed）
        │
        ▼ 人工编辑：fixed → variable / variable-all
        │
generate_user_input.py           → data/input/user-input.json（只有可变字段）
        │
        ▼ 人工编辑：填新一期内容
        │
generate_html.py（后续）         → 合并 fixed 模板 + user input → H5
```

---

## 6. 下一步

1. 用户对照 MasterGo 设计稿，编辑 `config/variability.json`：
   - 把每期会变的 TEXT 节点从 `fixed` 改为 `variable`
   - 把图表容器（含矩形/椭圆子节点）从 `fixed` 改为 `variable-all`
2. 实现 `generate_html.py`：读取模块 JSON + user-input.json，合并生成完整 H5 页面。模块排布需考虑流式布局——上一个模块内容变多 → 下一个模块自动下移。

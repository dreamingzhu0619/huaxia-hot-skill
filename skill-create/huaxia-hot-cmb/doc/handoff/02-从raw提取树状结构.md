# 02-树状结构 · 交接文档

> 上一个窗口做的事。给下一个窗口的 context。
> 最后更新：2026-07-09

---

## 0. 做了什么

把 `data/raw/` 的 MCP 原始数据（getDsl + sections + texts）转成人类可读的层级树 `data/normalized/tree.md`，用于肉眼校验设计稿的节点层级是否正确。

同时输出了 `data/normalized/tree.json`（机器可读，但后续步骤直接从 `data/raw/` 取数据，不一定用它）。

---

## 1. 产物

| 文件 | 说明 |
|------|------|
| `scripts/normalize/normalize_to_tree.py` | 归一化脚本 |
| `data/normalized/tree.md` | 人类可读层级树（28 KB，417 节点，86 分段） |
| `data/normalized/tree.json` | 机器可读层级树（仅结构+文本，无样式） |
| `doc/data-issues.md` | 数据常见疑问（5 个 FAQ） |

用法：
```bash
cd huaxia-hot-cmb
python scripts/normalize/normalize_to_tree.py          # 完整运行
python scripts/normalize/normalize_to_tree.py --check  # 只校验输入
```

---

## 2. 核心决策

### 层级关系：完全信任 getDsl 的 `children`

不做任何"边界框包含回挂"之类的修正。设计师在 MasterGo 里怎么建的，`children` 就怎么反映。

**踩过的坑**：尝试过按节点边界框包含关系自动修正层级（比如把视觉上被 GROUP 蒙版包裹的兄弟节点回挂到 GROUP 下），结果把"头图banner"里编组7、位图四五全部误吞到了不该在的层级。已撤销。

### 不处理样式，不处理 D2C

归一化只关心结构（父子、层级、类型、分段映射、文本内容）。D2C 的 blendMode/rotation 等渲染属性留给 CSS 生成步骤。

### 仅对 GROUP 类型的 section root 做特殊处理

后来也撤销了——参考树和 getDsl 的差异不需要在这一步解决。

---

## 3. 关键数据发现

- **160 个 PATH 节点全部无子节点**：MCP 把布尔运算（形状结合）展平成了单条 `path.data`。不是漏了，是 API 就不给。
- **PATH 都是固定装饰**（蒙版、曲线、边框），属于 fixed，不需要改。真正可变的是 TEXT 节点。
- **文本占位符 `T{n}|{id}`** 已被自动替换为真实文本（本次设计稿 getDsl 本身就带了全文本，所以替换数为 0）。

详见 `doc/data-issues.md`。

---

## 4. 文件位置

```
huaxia-hot-cmb/
├── scripts/normalize/normalize_to_tree.py   # 归一化脚本
├── data/normalized/
│   ├── tree.md                              # 人类可读层级树
│   └── tree.json                            # 机器可读层级树
└── doc/
    ├── data-issues.md                       # 数据常见疑问
    └── handoff/
        ├── 01-mcp提取数据.md
        └── 02-归一化.md                     # 本文档
```

---

## 5. 下一步建议

`scripts/prepare/split_modules.py` — 按层级树识别业务模块，从 `data/raw/` 提取每个模块的完整设计数据，输出 `data/modules/{序号}-{语义名}.json`。

这是 fixed/variable 区分的前置步骤：先把页面拆成模块，再在每个模块里标哪些是 fixed、哪些要用户填。

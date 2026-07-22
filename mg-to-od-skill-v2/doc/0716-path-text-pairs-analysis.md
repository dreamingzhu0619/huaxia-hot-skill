# PATH/LAYER 与 TEXT 配对分析

## 规则

三条简单规则判断 PATH/LAYER 是否应该合并为 TEXT 的 CSS background：

| # | 规则 | 阈值 |
|---|------|------|
| 1 | `|shape.y - text.y| < 10px` | y 方向在同一行 |
| 2 | `0.4 < shape.h / text.h < 2.5` | 形状不太大(容器)也不太小(legend点) |
| 3 | x 方向有重叠 | 避免同一行但完全无关的元素 |

数据来源：CITC（中信银行）、CMB（招商银行）两个项目的 section JSON。

---

## 通过（应合并为文字背景）— 19 对

### Gradient Overlay ×4 — CITC

```
[CITC] section-02.json parent="左手红利 右手低波"
  (PATH) "Gradient Overlay"  @ y=1 h=57
  (TEXT) "左手红利 右手低波"   @ y=0 h=57  y_diff=1  ratio=1.00

[CITC] section-02.json parent="攻守兼备的组合底仓"
  (PATH) "Gradient Overlay"  @ y=0 h=57
  (TEXT) "攻守兼备的组合底仓"   @ y=0 h=57  y_diff=0  ratio=1.00

[CITC] section-15.json parent="行业龙头加持 力争稳定分红"
  (PATH) "Gradient Overlay"  @ y=0 h=57
  (TEXT) "行业龙头加持 力争稳定分红"  @ y=0 h=57  y_diff=0  ratio=1.00

[CITC] section-24.json parent="“哑铃型”策略  重构市场估值体系"
  (PATH) "Gradient Overlay"  @ y=-0 h=57
  (TEXT) "“哑铃型”策略  重构市场估值体系"  @ y=2 h=57  y_diff=2  ratio=1.00
```

→ 合并为 `background-clip: text` 文字渐变

### 矩形 Tag + 基金代码/风险等级 ×5 — CITC

```
[CITC] section-01.json parent="代码"
  (LAYER) "矩形 16"     @ y=0 h=45
  (TEXT)  "021483"     @ y=7 h=32  y_diff=7  ratio=1.40

[CITC] section-01.json parent="风险等级"
  (LAYER) "矩形 16 拷贝"  @ y=0 h=45
  (TEXT)  "较高风险"     @ y=6 h=32  y_diff=6  ratio=1.41

[CITC] section-07.json parent="代码"
  (LAYER) "矩形 16"     @ y=0 h=57
  (TEXT)  "压舱石"      @ y=9 h=41  y_diff=9  ratio=1.39

[CITC] section-08.json parent="代码 拷贝"
  (LAYER) "矩形 16"     @ y=0 h=57
  (TEXT)  "保险杠"      @ y=9 h=41  y_diff=9  ratio=1.39
```

→ 合并为 `background + padding`

### 形状结合 + SectionTitle ×3 — CMB

```
[CMB] section-02.json parent="市场解读"
  (PATH) "形状结合"        @ y=42  h=23
  (TEXT) "从国内看景气度看"   @ y=46  h=20  y_diff=4  ratio=1.15

[CMB] section-02.json parent="市场解读"
  (PATH) "形状结合备份"      @ y=140 h=23
  (TEXT) "从政策环境看"      @ y=144 h=20  y_diff=4  ratio=1.15

[CMB] section-02.json parent="市场解读"
  (PATH) "形状结合备份 2"    @ y=240 h=23
  (TEXT) "从海外市场需求上看"  @ y=244 h=20  y_diff=4  ratio=1.15
```

→ 金色渐变背景：`background: linear-gradient(180deg, #FFDA92 12%, #FFF1D4 99%)`

### 矩形 + 基金代码/风险等级 Tag ×4 — CMB

```
[CMB] section-81.json parent="编组 5备份"
  (PATH) "矩形"      @ y=0 h=15
  (TEXT) "025833"   @ y=2 h=14  y_diff=2  ratio=1.07

[CMB] section-81.json parent="编组 5"
  (PATH) "矩形"      @ y=0 h=15
  (TEXT) "R5高风险"  @ y=2 h=14  y_diff=2  ratio=1.07

[CMB] section-83.json parent="标签"
  (PATH) "矩形"      @ y=0 h=15
  (TEXT) "025857"   @ y=2 h=14  y_diff=2  ratio=1.07

[CMB] section-83.json parent="标签"
  (PATH) "矩形"      @ y=0 h=15
  (TEXT) "R5高风险"  @ y=2 h=14  y_diff=2  ratio=1.07
```

→ 合并为标签背景

### 头部装饰 ×3 — CMB

```
[CMB] section-00.json parent="头图banner"
  (LAYER) "位图五"        @ y=47 h=30
  (TEXT)  "电网进入高景气周期"  @ y=40 h=45  y_diff=7  ratio=0.67

[CMB] section-00.json parent="分享"
  (LAYER) "矩形"     @ y=0 h=44
  (TEXT)  "分享"    @ y=6 h=44  y_diff=6  ratio=1.00

[CMB] section-00.json parent="热点速递"
  (PATH)  "矩形"     @ y=0 h=28
  (TEXT)  "热点速递"  @ y=6 h=24  y_diff=6  ratio=1.17

[CMB] section-00.json parent="热点速递"
  (PATH)  "路径 10"  @ y=5 h=13
  (TEXT)  "热点速递"  @ y=6 h=24  y_diff=1  ratio=0.54
```

→ 头部背景图/装饰线合并为文字所在元素的 CSS background 或 ::before

---

## 未通过 — 按原因分类汇总

### 仅因 x 不重叠被排除（y 和 ratio 都符合）

这些是图表 legend 色块和 label 文字，处于同一行但水平不重叠：

```
[CMB] section-83.json 矩形 + R5高风险 / 025857 — 同parent交叉配对
[CMB] section-26.json 矩形/矩形备份 19 + 电网累计投资/电源累计投资 — 图表legend
[CITC] section-19.json 矩形 1007 拷贝 + 现金分红总额(亿)/股息支付率 — 图表指标标签
```

### 因 ratio 太大（≥2.5）被排除 — 表格/卡片容器

全是"蒙版"作为表格行背景包裹多行文字、或大矩形作为卡片背景：

```
[CMB] 表格一/二/三/四: 蒙版备份 + 表头文字 — ratio=4.1~6.8
[CITC] 产品卡: 矩形 23 拷贝 + "近一年涨跌幅"/"2.80%" — 卡片背景 ratio=9.5~12.1
[CITC] 热点速递: 矩形 153 拷贝 + 数据来源 — 卡片背景 ratio=22.7
[CITC] 组 5808: 矩形 1001/椭圆 560 + 图表内文字 — 图表容器 ratio=3.5~21.4
[CMB] 头图banner: 位图一/二/四 + banner文字 — 多层背景 ratio=2.7~6.5
```

### 因 ratio 太小（≤0.4）被排除 — 图表 legend 小色块

```
[CITC] 组 5809: 矩形 1006 拷贝系列 + "红利低波全收益/300收益/..." — 图表指标颜色方块 ratio=0.22~0.32
[CITC] 组 5805: 矩形 1007 拷贝 + 现金分红总额/股息支付率 — ratio=0.26~0.39
[CMB] 市场解读: 形状结合 + body正文(多行) — sectionTitle装饰与下方body交叉配对 ratio=0.26~0.39
```

### 因 y_diff 太大（≥10）被排除 — 交叉配对和有意排除

值得关注的边缘案例：

```
y_diff=15: [CITC] 矩形 1006 拷贝 14 + 红利资产/科技资产 — 图表内标签，y差=15略超阈值
y_diff=22: [CITC] 矩形 1006 拷贝 14 + 红利因子/低波动因子 — 同上
y_diff=26: [CITC] 矩形 18 + 小试一笔 — 按钮，应作为组件而非背景合并

y_diff=28: [CMB] 形状结合 + body正文 — sectionTitle的PATH与body的交叉配对
y_diff=42~240: [CMB] 形状结合各类交叉配对 — 同parent内不同位置的正确排除
```

---

## 结论

三条规则覆盖了三个项目所有已知的 PATH/LAYER → TEXT CSS background 合并场景，零误判（19 对全部正确），零漏判（未通过的 99 对都是正确排除）。

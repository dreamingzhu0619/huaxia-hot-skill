# 组件溯源对照表（components provenance）

> 目的：`assets/components/*.preview.html` 里**每一处固定样式的取值依据**，都能回溯到确定的源节点，便于逐处核对还原度。
> 可变内容（产品名/正文/图表数值/来源文字）= 占位数据，随每期变，不在此表。

## 数据链路（所有固定样式的来源）

```
MasterGo 设计稿
  └─(MCP 抓取)→ huaxia-hot-cmb/data/raw/            getDsl 基底 + getD2c/getDesignSvgs/getDesignTexts 补充
       └─(split_modules)→ data/modules/NN-*.json    每模块一份；每节点含合并字段 + sources[] + 烘焙 path + assets.svgs
            └─(generate_module_css.py)→ assets/styles/modules/NN-*.css   每条规则注释源节点 id
                 └─(本 skill 取值)→ assets/components/*.preview.html
```

- **固定样式（字体/色值/渐变/阴影/间距/圆角）**：抄源 CSS `NN-*.css` 的精确值，preview 内用 `/* 0:xxx */` 标注。
- **异形几何（角标梯形/手势/金标/装饰 path/烘焙 SVG）**：抄 `data/modules/NN-*.json` 的 `node[].path` / `assets.svgs[id]`。
- **相对定位**：flow 化后固定元素的 left/top 用「相对当前 flow 容器」换算值（见 memory `feedback_flow_relative_positioning`）。

核对任一值：preview 的 `0:xxx` → 对应 `NN-*.css` 的 `.n-0-xxx` → `data/modules/NN.json` 节点 `0:xxx` → `data/raw`。

---

## 1. hotspot-frontline  （源：`01-hotspot-frontline.css` + `data/modules/01-*.json`）

| preview 元素 | 源节点 | 取的什么 |
|---|---|---|
| `.hot` 卡骨架 | 0:951 / 0:950 | 蓝白渐变 `180deg #E0EDFF→#FFFFFF 11%`、阴影 `0 1px 2px 2px #EAF5FF`、圆角 10.1、overflow |
| `.hot-tab` 梯形角标 | 0:953(主体)/0:952(模糊底)/0:956(辉光)/0:954-955(白光条) | path 几何 + 渐变/透明度，取自 modules JSON `node[].path` |
| `.hot-title` 标题 | 0:957 | FZZDHJW 20/37.56、`#FFFFFF`、text-shadow `0 2px 3px #4F9EF1`；相对偏移 top -3.24 |
| `.hot-body` 正文 | 0:958 | FZLTHJW 14/20、`#333333`、letter-spacing -0.1 |
| `.hot-source` 来源 | 0:1318 | FZLTHJW 9/11、`#999999`、center |

## 2. market-analysis  （源：`02-market-analysis.css` + `data/modules/02-*.json`）

| preview 元素 | 源节点 | 取的什么 |
|---|---|---|
| `.market` 卡骨架 | 0:961 / 0:960 | 同上蓝白渐变+阴影+圆角 10.1 |
| `.market-tab` 角标 | 0:962-966 | 与 hotspot 同款梯形 path（高度 32，差 2px 复用） |
| `.market-title` 标题 | 0:967 | 同标题样式；相对偏移 top -2.24 |
| `.market-subhead` 金标 | 0:969/0:972/0:975 | 金渐变 `180deg #FFDA92 12%→#FFF1D4 99%`、inset高光、圆角≈8（path 估） |
| 金标文字 | 0:978/0:979/0:980 | FZLTZHJW 14、`#7B431C` |
| `.market-body` 分论点正文 | 0:968/0:981/0:982 | FZLTHJW 14/20、`#333333` |
| `.market-disclaimer` 免责 | 0:983 | FZLTHJW 9/11、`#999999`、center |

## 3. related-products  （源：`07-related-products.css` + `data/modules/07-*.json`）

| preview 元素 | 源节点 | 取的什么 |
|---|---|---|
| `.rel-title` 标题（卡外）| 0:1329 | 渐变字 `277deg #1593FF 2%→#005FFF 95%`、FZZDHJW 25/37.56、text-shadow |
| `.rel-deco` 装饰 | 0:1321-1328 | 渐变线 `270deg #2979E8→透明` + 空心/实心菱形 `#2577E8` |
| `.related-card` 外卡 | 0:1330 | 蓝白渐变 + 阴影（**注：0:1330/0:952/0:1369 是历史偏黄 bug 修复点**）|
| `.prod-big` 大子卡 | 0:1369 | `359deg #FFFFFF 1%→#F0F8FF 98%` + inset高光 #FFFFFF |
| 大产品名 | 0:1425 | FZLTZHJW 17、`#343434`、center |
| 小产品名 | 0:1332 | FZLTZHJW 15、`#343434` |
| `.tag` 标签底/字 | 0:1337/1340/1428/1430(底 `#F1F8FF`) · 0:1338/1341/1429/1431(字 `#2C96FF` 10) | 代码/风险标签 |
| `.cta` 橙按钮 | 0:1373/1350(药丸 `90deg #FF5B00 17%→#F13816 85%`+阴影 `0 1px 0 0 #FF800F`) · 0:1363/1378(顶部白高光) | 大/小 CTA |
| CTA 文字 | 0:1379(大)/0:1367(小) | FZLTZHJW 14、`#FFFFFF`、text-shadow `0 1px 2px #FF4F02` |
| `.cta-hand` 手（仅大CTA）| 0:1385(手掌 `123deg #FEFBF5→#FEECE4→#FFE0CE`)/0:1386-1388(指尖)/0:1382-1383(白涟漪 `rgba(255,255,255,.298)`) | path 几何取自 modules JSON；rotate 13°(0:1380)+3°(0:1384)；相对药丸 left 207.21 top 14.96 |
| 收益标签「成立以来」| 0:1434(大)/0:1435(小) | FZLTHJW 10、`#A6A6A6` |

## 4. recommendation  （源：`03-recommendation-a.css`/`04-recommendation-b.css` + `data/modules/03·04-*.json`）

> A/B 已合并为一个 `.rec` 组件，靠 `chart.type`（A=bar / B=line）区分，`data` 数组渲染 N 张。

| preview 元素 | 源节点 | 取的什么 |
|---|---|---|
| `.rec` 卡骨架 | 0:986 | 蓝白渐变 + 阴影 `0 1px 2px 2px #EAF5FF` + 圆角 |
| `.rec-title` 标题 | 0:991 | FZLTZHJW 17、`#1570E9` |
| `.rec-deco` 装饰 | 0:992-996 | 渐变线 + 空心/实心菱形 `#2577E8` |
| `.rec-body` 正文 | 0:1000 | FZLTZHJW 14/20、`#F81F02` |
| 图表 | 0:1002(类目)/0:1004(标题)/0:1005(值)/0:1013(柱 `#FFD282`) | 柱样式沿用；数据驱动，不逐形状还原 |
| `.rec-source` 来源 | 0:988 | FZLTHJW 9/12、`#959595`、center |

---

## 待核实/占位项（需用户确认或后续补数据）

- **market 金标圆角**：8px 由 path 拐角估算，未逐点验证。
- **related 收益率数值**：原稿「成立以来」旁可能有收益率数字，本期 modules 无对应文本节点，暂只留标签。
- **手势指尖颜色**：`0:1386-1388` 的渐变数据 raw 里是有的（getDsl fill / getD2c）；但 `extractSvg` 透传的那份 radial-gradient 含 NaN、`fill="linear-gradient"` 是非法 SVG（MasterGo 导出不规范 + split 脚本未转换，属**脚本问题非数据缺陷**）。当前组件用 getDsl 的 path+近似色 `#FFBDB4/#FEBDB4/#FFE2D5` 重建；根治应改 split 脚本优先取 getD2c 或转换后重生成 modules。

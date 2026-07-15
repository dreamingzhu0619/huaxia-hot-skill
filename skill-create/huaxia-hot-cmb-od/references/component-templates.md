# 组件静态 HTML 模板（agent 拼装配方）

> 用途：读 `content.template.json` 后，agent 按本文把每个组件拼成**静态 HTML**，
> 组装出 `index.html`。样式全在 `assets/styles/components.css`，**只写内容、不写样式**。
> `{{...}}` = 从 content.template.json 取的可变内容；其余结构/class 一律照抄。
> 每个模块最外层 `<section data-od-id="...">` 保留，供 OD Comment AI 定位。

## 页面骨架

```html
<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>华夏热点速递</title>
<link rel="stylesheet" href="css/components.css">
</head><body>
<div class="hx-stage">
  <!-- 按顺序放 8 个 <section>：banner / hotspot / market / recommendation(N) /
       related-products / buy-fund-cmb / compliance-notice。
       固定模块 banner/buy-fund-cmb/compliance-notice 见 template.html 原样保留。 -->
</div>
</body></html>
```

> 注：模块流式顺序按设计稿 position.y。图片走 MasterGo 公开 CDN，无本地图。

---

## 复用 SVG 片段（长，照抄）

### 蓝色梯形角标（hotspot / market 共用）
标题文字放在同级 `.hx-tab-title`；hotspot 用 `.hot` 容器、market 用 `.market` 容器（title 偏移由 CSS 区分）。

```html
<svg class="hx-tab" viewBox="-31 -8 170 47" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="tabSharp" x1="0" y1="29" x2="0" y2="-1" gradientUnits="userSpaceOnUse">
      <stop offset="0.18" stop-color="#4F9CF0"/><stop offset="1" stop-color="#75C3F8"/></linearGradient>
    <linearGradient id="tabBase" x1="0" y1="-1" x2="0" y2="29" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#75C4F8"/><stop offset="0.76" stop-color="#4F9CF0"/></linearGradient>
    <filter id="tabGlow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="10"/></filter>
    <filter id="tabBaseBlur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4.86"/></filter>
  </defs>
  <ellipse cx="14.5" cy="4" rx="35.5" ry="11" fill="#6CE8FF" opacity="0.55" filter="url(#tabGlow)"/>
  <path id="tabP" d="M-31,-1Q40.28,-0.89,122,-1Q114.15,-0.87,109.36,6.77Q104.72,13.71,99.51,20.85C97.31,23.86,96.18,25.36,94.76,26.43C93.50,27.38,92.09,28.08,90.58,28.51C88.86,28.999,86.97,29,83.23,29L-11.43,29C-15.87,29,-18.13,28.99,-19.88,28.15C-21.39,27.42,-22.65,26.26,-23.51,24.82C-24.51,23.16,-24.72,20.90,-25.12,16.49L-26.21,4.33Q-27.84,0.099,-31,-1Z" fill="url(#tabBase)" opacity="0.9" filter="url(#tabBaseBlur)"/>
  <use href="#tabP" fill="url(#tabSharp)" opacity="1" filter="none"/>
  <path d="M81.04,-8L49,39L60.18,39L92,-8Z" transform="matrix(-1,0,0,1,98,0)" fill="#FFFFFF" opacity="0.147"/>
  <path d="M111.41,-8L80,39L107.81,39L139,-8Z" transform="matrix(-1,0,0,1,160,0)" fill="#FFFFFF" opacity="0.147"/>
</svg>
```

### 奶油色点击手（仅 related 大 CTA；几何取自 data/modules/07 的 0:1385-1388）

```html
<svg class="cta-hand" viewBox="-5 -6 50 48" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <linearGradient id="handPalm" x1="0.12" y1="0" x2="0.85" y2="0.95">
      <stop offset="0.11" stop-color="#FEFBF5"/><stop offset="0.59" stop-color="#FEECE4"/><stop offset="0.87" stop-color="#FFE0CE"/></linearGradient>
    <filter id="handShadow" x="-40%" y="-40%" width="180%" height="180%">
      <feDropShadow dx="1" dy="2" stdDeviation="1.6" flood-color="#FF7D09" flood-opacity="0.5"/></filter>
  </defs>
  <g transform="rotate(13 19.5 16.5)">
    <ellipse cx="9.6" cy="9.66" rx="9.6" ry="9.66" fill="rgba(255,255,255,0.298)"/>
    <ellipse cx="9.6" cy="9.63" rx="6" ry="6" fill="rgba(255,255,255,0.298)"/>
    <g transform="translate(7.21 9.66) rotate(3)" filter="url(#handShadow)">
      <path d="M11.565631,13.466435Q9.5016222,9.668479,0.47403976,2.8825309C-0.49164444,1.4679708,0.055191349,-0.13668816,1.7766459,0.0092730597C3.4981005,0.15523428,7.1099839,3.2472763,7.6270175,3.6550741C7.7258959,3.5786562,8.2158289,2.2541945,11.565631,2.8825309C12.024149,2.7994823,13.083331,0.61668152,16.653677,1.8048518C16.982601,1.5895338,18.135132,0.17796446,20.277849,1.0774595C22.420567,1.9769543,23.95756,3.635978,26.311121,6.7332177C28.66468,9.8304567,31.234325,14.09185,31.228132,14.52616C31.221939,14.96047,27.629631,20.240025,21.988102,22.535835C21.365904,22.49161,19.396215,19.958666,16.790976,19.672915C14.185734,19.387163,5.6428547,17.48509,4.2102604,15.522134C2.7776661,13.559177,3.8598893,11.843897,6.2742963,12.541547Q8.6887035,13.239197,11.565631,13.466435Z" fill="url(#handPalm)"/>
      <path d="M13.80687427520752,25.317908664316406Q18.16481017520752,29.303242674316408,19.48728897520752,30.460053474316407C20.025329575207518,31.113254974316405,21.02340217520752,29.103626474316407,17.89652447520752,26.819398074316407Q14.76964682520752,24.535169664316406,13.80687427520752,25.317908664316406Z" fill="#FFBDB4"/>
      <path d="M17.80272674560547,24.52512985894043Q20.26830744560547,25.73295128894043,22.18957044560547,28.08537768894043C22.73321104560547,28.36279348894043,22.41255424560547,26.61142448894043,20.96120734560547,25.32733518894043C20.370008445605468,24.80426787894043,19.168453945605467,23.94630076694043,18.69345223560547,23.86213919074043Q18.39105951560547,23.80856074794043,17.80272674560547,24.52512985894043Z" fill="#FEBDB4"/>
      <path d="M22.719297409057617,23.39087158867676Q24.207478909057617,24.233432418676756,25.817558809057616,25.90502621867676C26.361199609057618,26.18244221867676,27.32912490905762,25.477166218676757,25.877778009057618,24.19307691867676C25.286579109057616,23.670009608676757,24.085024609057616,22.812042496676757,23.61002289905762,22.727880920476757Q23.307630179057618,22.674302477676758,22.719297409057617,23.39087158867676Z" fill="#FFE2D5"/>
    </g>
  </g>
</svg>
```

### 标题装饰（recommendation / related 共用）
```html
<span class="hx-deco"><span class="line"></span><span class="d-hollow"></span><span class="d-solid"></span></span>
<!-- 右侧镜像：class="hx-deco right" -->
```

---

## 组件 HTML 模板

### hotspot-frontline（content: `hotspot-frontline`）
```html
<section data-od-id="hotspot-frontline">
  <div class="hx-card hot">
    <!-- 角标 SVG（照抄） -->
    <div class="hx-tab-title">{{title}}</div>
    <p class="hot-body">{{body}}</p>
    <p class="hot-source">{{source}}</p>
  </div>
</section>
```

### market-analysis（content: `market-analysis`；**无独立 intro**，每分论点=heading+body）
```html
<section data-od-id="market-analysis">
  <div class="hx-card market">
    <!-- 角标 SVG（照抄） -->
    <div class="hx-tab-title">{{title}}</div>
    <!-- 对 points 每项： -->
    <div class="market-point">
      <span class="market-subhead">{{point.heading}}</span>
      <p class="market-body">{{point.body}}</p>
    </div>
    <!-- …重复 N 个 point… -->
    <p class="market-disclaimer">{{disclaimer}}</p>
  </div>
</section>
```

### recommendation（content: `recommendation` 数组，每项一张卡）
```html
<section data-od-id="recommendation">
  <!-- 对数组每项： -->
  <div class="hx-card rec">
    <div class="rec-head">
      <span class="hx-deco"><span class="line"></span><span class="d-hollow"></span><span class="d-solid"></span></span>
      <span class="rec-title">{{title}}</span>
      <span class="hx-deco right"><span class="line"></span><span class="d-hollow"></span><span class="d-solid"></span></span>
    </div>
    <p class="rec-body">{{body}}</p>
    {{chart}}   <!-- 见下「图表」 -->
    <p class="rec-source">{{source}}</p>
  </div>
  <!-- …重复 N 张… -->
</section>
```

### related-products（content: `related-products`；**一大一小**，第1个产品=大，第2个=小）
```html
<section data-od-id="related-products">
  <div class="related-wrap">
    <div class="related-head">
      <span class="hx-deco"><span class="line"></span><span class="d-hollow"></span><span class="d-solid"></span></span>
      <span class="rel-title">{{title}}</span>
      <span class="hx-deco right"><span class="line"></span><span class="d-hollow"></span><span class="d-solid"></span></span>
    </div>
    <div class="hx-card related-card">
      <!-- 大产品 = products[0] -->
      <div class="prod-big">
        <p class="prod-name">{{big.name}}</p>
        <span class="prod-tags"><span class="tag">{{big.code}}</span><span class="tag">{{big.riskTag}}</span></span>
        <span class="ret-label">{{big.returnLabel}}</span>
        <span class="cta-wrap"><span class="cta cta-big">{{big.cta}}</span>
          <!-- 手 SVG（照抄） -->
        </span>
      </div>
      <!-- 小产品 = products[1] -->
      <div class="prod-small">
        <div class="prod-left">
          <p class="prod-name">{{small.name}}</p>
          <span class="prod-tags"><span class="tag">{{small.code}}</span><span class="tag">{{small.riskTag}}</span><span class="ret-label">{{small.returnLabel}}</span></span>
        </div>
        <span class="cta cta-small">{{small.cta}}</span>
      </div>
    </div>
  </div>
</section>
```

### banner / buy-fund-cmb / compliance-notice（固定模块）
这三个不做 flow，直接从 `assets/template.html` 里对应 `<section>` **原样保留**：
- banner：只有两行标题 `{{titleLine1}}/{{titleLine2}}` 可改，其余（背景图/角标/装饰/分享）锁死。
- buy-fund-cmb：完全不变。
- compliance-notice：**假表格（PATH 网格）不可自适应**，只换产品名/费率数字，且数字要对齐网格；整块合规审核过，非必要不碰。

---

## 图表（recommendation 的 `chart`，按数据算成静态 HTML）

图表**不逐形状还原**，用数据驱动的干净图。**图型不限于下面两种**：agent 按数据自由选/设计合适的图型
（柱/分组柱/堆叠柱/折线/面积/饼/环/散点…），但必须遵守 SKILL.md「Step 2.5 图表样式契约」的配色/字号/线宽/画幅。
下面 bar、line 两段是**契约的现成范例**——常见柱/折线直接照抄算法与 class；需要别的图型时仿照它们的配色/字号/画幅自行设计 SVG。
**布局默认规则**（详见 SKILL.md Step 2.5）：单张图整体水平居中、标题居中在图正上方；多张图并排时按内容宽度(321px)平分栏、每张图连标题在各自栏内居中；特殊排布以用户自然语言为准。

### type = "bar"（柱状图）
- `max = max(values)`；每根柱宽百分比 `pct = max(8, round(v/max*100, 1))`。
```html
<div class="rec-chart">
  <div class="rec-chart-title">{{yLabel}}</div>
  <!-- 每个 (category, value)： -->
  <div class="bar-row"><span class="cat">{{cat}}</span>
    <span class="track"><span class="fill" style="width:{{pct}}%"><span class="val">{{v}}</span></span></span></div>
  <!-- …重复… -->
</div>
```

### type = "line"（折线图）
- 画布 `W=321,H=130,pad=10`；`n=categories.length`。
- `max=max(所有series值), min=min(所有series值)`。
- 点坐标：`x(i)=pad+i*(W-2*pad)/(n-1)`，`y(v)=H-pad-(v-min)/((max-min)||1)*(H-2*pad)`。
- 每条 series 一条 `<path>`，颜色顺序 `['#2577E8','#FF8C4B']`；`d` = `M x0,y0 L x1,y1 …`。
```html
<div class="rec-chart">
  <div class="rec-chart-title">{{yLabel}}</div>
  <svg viewBox="0 0 321 130">
    <path d="M{{x0}},{{y0}} L{{x1}},{{y1}} …" fill="none" stroke="#2577E8" stroke-width="2"/>
    <!-- 第2条 series 用 #FF8C4B -->
  </svg>
</div>
```

> 坐标算完保留 1 位小数即可。柱状图数值 `val` 直接显示原始数字。

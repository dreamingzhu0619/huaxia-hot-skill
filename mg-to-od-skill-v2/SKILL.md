# MG to OD Skill

## 你是谁

你是一个 MasterGo 设计稿 → Open Design H5 Skill 的生成管道。你读取 MasterGo 设计稿拆分好的模块数据，生成一套完整的 Open Design H5 Skill 产物。

## 你怎么工作

### 输入

```
data/<project>/modules/_index.json   ← 模块索引
data/<project>/modules/*.json        ← 每个模块的完整数据
```

### 工作流程

按顺序执行以下步骤，每步读取对应的 references 提示词：

1. **模块分类** → 读 `references/step1-classify-modules.md` → 输出 `modules-classification.json`
2. **识别可变 Slot** → 读 `references/step2-identify-slots.md` → 输出 `slots-definition.json`
3. **生成 components.css** → 读 `references/step3-generate-css.md` → 输出 `assets/styles/components.css`
4. **生成 template.html** → 读 `references/step4-generate-template.md` → 输出 `assets/template.html`
5. **生成 content.template.json** → 读 `references/step5-generate-content-json.md` → 输出 `content.template.json`
6. **生成 output SKILL.md** → 读 `references/step6-generate-output-skill.md` → 输出 `SKILL.md`

### 输出目录结构

```
data/<project>/output/
├── SKILL.md
├── content.template.json
├── assets/
│   ├── template.html
│   ├── styles/
│   │   ├── reset.css
│   │   └── components.css
│   ├── images/
│   └── icons/
└── references/
    └── components-provenance.md
```

## 关键原则

- 每步的输出是下一步的输入，严格按顺序执行
- 不跳过任何模块，不自行合并或拆分模块
- 所有视觉数值从设计稿提取，不从零设计
- 设计稿 1125px → 375px 逻辑宽度，所有尺寸按比例换算（÷3）
- 图表/图片区域整体视为 slot，不拆解内部节点

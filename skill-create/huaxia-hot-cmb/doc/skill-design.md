mastergo-to-h5-skill/
│
├── SKILL.md
│   # Skill 入口说明文件。
│   # 说明 Skill 的目标、适用场景、输入输出、执行流程以及人工介入节点。
│   # 定义整体工作流：
│   # MCP 数据获取 → 数据整理 → 模块拆分 → fixed/variable 标注 → 用户输入 → H5 生成 → 检查报告。
│
├── config/
│   │
│   ├── project.config.json
│   │   # 项目配置文件。
│   │   # 存放设计稿链接、rootNodeId、项目名称、输出路径等非敏感配置。
│   │
│   └── local.secret.json
│       # 本地敏感配置文件。
│       # 存放 MCP Token 等敏感信息。
│       # 不提交 Git，不对外共享。
│
├── references/
│   │
│   └── rules.md
│       # 规则沉淀文件。
│       # 记录实际运行过程中发现的问题和修正规则。
│
├── scripts/
│   │
│   ├── fetch/
│   │   │
│   │   └── fetch_mcp_data.py
│   │       # 获取 MasterGo MCP 原始数据。
│   │       # 将设计稿中的节点、样式、文本、图片资源等完整信息保存下来。
│   │
│   ├── normalize/
│   │   │
│   │   └── normalize_to_tree.py
│   │       # 将 MCP 原始数据转换为轻量层级树。
│   │       # 不负责保存所有节点完整样式。
│   │
│   ├── prepare/
│   │   │
│   │   ├── split_modules.py
│   │   │   # 根据页面层级树识别业务模块。
│   │   │   # 从 MCP 原始数据中提取每个模块完整设计数据。
│   │   │   # 输出 data/modules/。
│   │   │
│   │   └── download_assets.py
│   │       # 根据模块数据中的图片资源信息下载图片。
│   │       # 输出 assets/images/。
│   │
│   ├── input/
│   │   │
│   │   └── generate_user_input.py
│   │       # 根据 modules 中标记为 variable 的字段，
│   │       # 自动生成用户可编辑的输入文件。
│   │       #
│   │       # 用户只需要修改 variable 内容，
│   │       # fixed 内容不会进入该文件。
│   │
│   ├── render/
│   │   │
│   │   ├── generate_page_css.py
│   │   │   # 根据页面根节点数据生成页面级 CSS。
│   │   │   # 负责页面整体尺寸、背景、根容器等样式。
│   │   │
│   │   ├── generate_module_css.py
│   │   │   # 根据 modules 数据生成模块级 CSS。
│   │   │   # 每个模块对应一个 CSS 文件。
│   │   │
│   │   └── generate_html.py
│   │       # 根据 HTML 模板、模块数据、用户输入生成最终 H5 页面。
│   │
│   └── audit/
│       │
│       └── generate_audit.py
│           # 生成检查报告。 # 检查： │           # - 模块拆分情况 │           # - 图片资源情况 │           # - 字段丢失情况 │           # - CSS 转换情况 │           # - variable 替换情况             
│           # 检查：哪个字段还出现大面积缺失
│
├── data/
│   │
│   ├── raw/
│   │   │
│   │   └── mastergo-mcp-raw.json
│   │       # MCP 原始完整数据。
│   │       # 不修改，作为原始数据来源。
│   │
│   ├── normalized/
│   │   │
│   │   └── tree.json
│   │       # 页面层级树。
│   │       # 主要保存：
│   │       # - 节点父子关系
│   │       # - 层级关系
│   │       # - 节点顺序
│   │       # - 节点类型
│   │       # - 模块划分关系
│   │       #
│   │       # 不保存每个节点完整样式。
│   │
│   ├── modules/
│   │   │
│   │   # 模块完整设计数据。
│   │   # 每个 module 文件代表一个 H5 模块。
│   │   # 是生成 CSS、HTML、用户输入的重要数据来源。
│   │   #
│   │   # 命名规则：
│   │   # {序号}-{模块语义名称}.json
│   │   #
│   │   # 示例：
│   │   # 01-banner.json
│   │   # 02-product-card.json
│   │   # 03-recommendation.json
│   │   
│   │
│   ├── input/
│   │   │
│   │   └── user-input.json
│   │       # 用户输入文件。
│   │       # 根据 modules 中 variable 字段自动生成。
│   │       # 用户只需要修改这里的内容。
│   │       # fixed 内容不会出现在这里。
│   │
│   └── audit/
│       │
│       ├── module-report.md
│       │   # 模块拆分报告。
│       │
│       ├── asset-report.md
│       │   # 图片资源处理报告。
│       │
│       └── lost-fields-report.md
│           # 字段丢失报告。
│
├── assets/
│   │
│   ├── templates/
│   │   │
│   │   └── page.html
│   │       # H5 页面 HTML 骨架。
│   │       # 对应 MasterGo 页面根节点。
│   │       # 第一版只保留整体页面模板，
│   │       # 不单独维护模块 HTML 模板。
│   │
│   ├── styles/
│   │   │
│   │   ├── page.css
│   │   │   # 页面级 CSS。
│   │   │   # 控制根容器、整体布局、页面背景等。
│   │   │
│   │   └── modules/
│   │       # 模块级 CSS。
│   │       # 与 data/modules/ 一一对应。
│   │       #
│   │       # 命名规则：
│   │       # 与 module.json 保持同名。
│   │       #
│   │       # 示例：
│   │       # data/modules/01-banner.json
│   │       # 对应：
│   │       # assets/styles/modules/01-banner.css
│   │
│   └── images/
│       # 图片资源目录。
│       # 存放 MCP 中提取并下载后的图片。
│       # 最终 H5 页面引用这里的资源。
│
└── output/
    │
    └── fund-h5/
        │
        ├── index.html
        │   # 最终交付 H5 页面。
        │
        ├── css/
        │   # 最终页面使用的 CSS。
        │
        ├── images/
        │   # 最终页面使用的图片资源。
        │
        ├── input-used.json
        │   # 本次生成 H5 实际使用的用户输入记录。
        │
        └── audit/
            # 本次生成结果对应的核心检查报告。
            
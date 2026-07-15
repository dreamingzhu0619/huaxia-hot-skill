C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill 这个skill是用来生成给opendesign用的skill的skill，刚才跑了一遍这个skill得到的skill，发现生成的C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill\output\huaxia-hot-citc-od\example.html还存在以下问题，请你优化这个skill
优化原则：先明确样式没有正确显示的原因是什么？是数据本身缺失还是没有正确提取！数据本身缺失指的是C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill\data\huaxia-hot-citc\raw里面没有这个样式数据，这个请你标注到相应的位置，我可以人工给你补上！如果原始数据中有但是没有正确显示，请沿着C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill\data\raw->C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill\data\modules->C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill\output\huaxia-hot-citc-od\assets ->C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill\output\huaxia-hot-citc-od\example.html的顺序排查，也就是先排查各个模块数据的问题，再排查html拼接的问题。将出现的问题总结到相应的文档中，然后可以避免下次再生成错误。
格式就是：总结沉淀的通用规则，然后发现的具体例子，然后要怎么修改，或者说要怎么应对。
发现如下问题：
1.“市场开启震荡模式”，这个 text 样式不对；
2.热点速递这一块，矩形153拷贝3，它的颜色不对。
3.“热点速递”这个frame的“热点速递拷贝”这整个大整体都没有正确显示。比方说，它的一些形状显示的是黑色，而且“热点速递”这几个文字根本就没有显示出来。
4.产品卡部分的 2.8% 位置不对，它应该在 021483 较高风险的下面，和近一年涨跌幅的上面。我想要试一笔。这个文字应该在这个矩形 18 的正中间。
5.产品推荐理由板块，矩形 1000 的颜色没有正确显示；标题应该只有字的颜色，而不是一个图形块。
6.推荐理由里面，它的数据错位了，并且很多也没有正确显示。
7.银行结束语板块的字体，本来应该显示的是字，现在已经糊成一坨矩形了，一坨黑色、一坨红色的。


C:\Users\dream\Desktop\skill-create\mastergo-to-od-skill 是我用来生成在 Open Design 中使用的制作 H5 的 Skill 的一个 Skill。

当前它生成的这个 example.html 有问题，我需要对整个 skill 进行优化。

首先，我的想法是这个skill，先要把它设计稿原始的、所有的 MCP 数据都拿下来（也就是 data/raw）。

拿下来之后，我要综合 MCP 所有处返回的数据，按照每个模块去分。每个模块的 JSON 拥有的都是该模块最全的数据。也就是说，我们拿到了最全的数据之后，output 里面 H5 所需要用的 assets 完全可以从这个数据中来。

至于之后的数据处理，逻辑是这样的：
你现在有了所有模块的 JSON，但你会发现其实像有的模块（比方说“推荐理由”这个模块），它虽然有 A、B、C 三项，但它们其实应该都是同一个样式。你去比较它们，具体内容有不同只是因为推荐理由的字体本身不同，并且它画图画出来的节点肯定千奇百怪、有很多不同的节点。但其实我们最终要保留的，就是“推荐理由”的这个大框架，至于上面填的具体文字和图表是无所谓的。

把它们都拿出来抽象成 assets 之后（也就是 output 里面这个 skill 的 assets），这个 skill 在生成 H5 的时候，就可以直接用这个 assets 里面的数据了。

其实我们最终 output 里面这个 scale 生成的 H5，是要求具体内容可以变，并且能够按照相应的制式去走。

比方说，现在的原设计稿里可能有 3 个推荐理由，但我们之后可能会变成 2 个、4 个或 5 个。它的每一个具体内容，包括文字和图表，都是可以替换的。

所以说，其实我觉得我们得探讨一下 mastergo-to-od-skill 这个大的 Skill 它的一个 workflow，以及 output 里面这个 Skill 它的一个 workflow，得先把它讨论清楚。
因为这里面涉及到几个问题，我们都要先讨论清楚，不然老是出错：

1. 怎么去判断这两个 frame 是不是同一类，以及要不要合并
2. 在一个模块里面，到底哪些是要变的，哪些是不变的
3. 这些模块最后要怎么正确地拼在一起
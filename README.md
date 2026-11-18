# HeatSignal / GSC

高温压力下数字连接韧性的观测研究与离线交互回放。

## 材料入口

- [服务器里有什么、朋友连上能看什么（大白话说明）](SERVER_README.md)
- [论文稿（44页）](paper.pdf) · [可编辑Word](paper.docx)
- [补充材料（19页）](supplement.pdf) · [可编辑Word](supplement.docx)
- [当前proposal](proposal.md)
- [图件](figures/)：PDF、SVG、PNG及数值源
- [新增区域细图（2026-11-02）](additional_maps/2026-11-02/README.md)：美国/中国/澳大利亚、美国逐年和三州放大，共16地图面板；含源数据、PDF/SVG/PNG、方法及独立复现核验
- [结果表](tables/)：全部方向、不可估与缺失均保留
- [完整复现包](reproduction.zip) · [源码浏览](code/)
- [方法与限制](METHODS_AND_LIMITATIONS.txt) · [范围验收](scope_acceptance.json)

## 离线交互网页

下载或克隆本仓库后，在本地浏览器手动打开 `website/index.html`。数据内嵌，无需启动服务器。GitHub文件页本身不会运行这个HTML；没有已认证的公共在线网址或真实浏览器可用性认证。

## 复现

解压 `reproduction.zip` 到独立目录，按其中的 `README_复现.txt` 执行。`code/` 便于在线阅读，运行所需的冻结派生输入及原状态元数据在完整复现包中。大型原始ERA5/IODA资料保留在原Judy服务器，未上传到本仓库。

10项下游Python测试、9项网页逻辑测试、独立表格/Word重建及Judy上的M3科学复现通过，见 [verification/](verification/)。`CHECKSUMS.json` 对应原交付载荷；仓库另附README和源码浏览目录。

## 解释边界

主事件日区间包含零不等于证明没有影响。AP有一项夜温交互通过组内BH/BY，但有事后分析、模型越界和样本选择限制；不认证热致断网、国家韧性排名或未来预测能力。DHRD不是实际断网时长，DLEP不是断网人数，候选异常不是确认故障。原10月28日截止未达到；交付材料未改写这一事实。

新增区域地图独立保存于`additional_maps/2026-11-02/`，使用其自己的`CHECKSUMS.json`。本次8项测试及15个图文件独立重画逐字节一致，属于描述性天气地图补充。

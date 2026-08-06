# Heston 模型期权校准与模拟 — 文档入口

本项目基于 **QuantLib** 实现 Heston 随机波动率模型，对沪深 300 指数期权进行每日校准，并计算期权价格、BS 隐含波动率与希腊字母（delta / gamma / theta / rho / vega），用于学术分析或期权策略研究。

项目总结（文件职能、模块依赖、数据流向、算法选择与设计思想、数据格式、运行说明）已合并至根目录 `readme.md`（可点击入口见根目录 `index.html`，或用 VS Code / Typora / GitHub 渲染查看），本文档为 MkDocs 站点的导航首页。

## 文档导航

| 文档 | 内容 |
|---|---|
| 项目总结（根目录 `readme.md`） | 文件职能、模块依赖、数据流向、算法选择与设计思想、数据格式、运行说明 |
| [设计文档（流程图）](project_design.md) | 总体数据流、单日校准、定价验证、希腊字母分析的流程图 |
| [API 参考](api/data_processor.md) | 类的构成、函数的输入输出与主要作用、变量的类型（由 docstring 经 MkDocs 自动生成） |

## 本地阅览

- 根目录 `index.html`：统一本地入口（浏览器直接打开）；
- 根目录 `start_docs.bat`：一键构建站点并打开入口；
- 手工方式：`mkdocs serve`（本地预览）或 `mkdocs build`（构建到 `site/`）。

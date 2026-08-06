# Heston 模型期权校准与模拟

本项目基于 **QuantLib** 实现 Heston 随机波动率模型，对沪深 300 指数期权进行每日校准，并计算期权价格、BS 隐含波动率与希腊字母（delta / gamma / theta / rho / vega），用于学术分析或期权策略研究。

## 文档导航

| 文档 | 内容 |
|---|---|
| [项目总结](summary_proj.md) | 每个文件的职能、模块依赖、数据流向、算法选择与设计思想 |
| [设计文档（流程图 / ER 图）](project_design.md) | 总体数据流、单日校准、定价验证、希腊字母分析的流程图及数据实体关系 ER 图 |
| [API 参考](api/data_processor.md) | 类的构成、函数的输入输出与主要作用、变量的类型（由 docstring 经 MkDocs 自动生成） |

## 快速开始

```bash
# 1. 安装依赖（虚拟环境 data_process）
pip install -r requirements.txt

# 2. 运行主流程
jupyter notebook code/main.ipynb

# 3. （可选）本地预览文档
mkdocs serve
```

## 项目结构

```text
Heston-Model-Calibration-and-simulation/
├── docs/                     # 文档（MkDocs 站点源）
│   ├── summary_proj.md       # 项目总结
│   ├── project_design.md     # 设计辅助文档（流程图 / ER 图）
│   └── api/                  # API 参考（docstring 自动生成）
├── code/                     # 源代码
├── data/                     # 输入数据
├── output/                   # 校准结果输出
├── image/                    # 图表输出
├── mkdocs.yml                # MkDocs 配置
├── requirements.txt          # 运行时依赖
└── progress.md               # 项目进度记录
```

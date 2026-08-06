# Heston 模型期权校准与希腊字母分析

本项目基于 **QuantLib** 实现 Heston 随机波动率模型，对沪深 300 指数期权进行每日校准，并计算期权价格、隐含波动率、希腊字母，用于学术分析或策略研究。

## 项目结构

```text
simulation/
├── docs/                         # 文档（MkDocs 站点源）
│   ├── summary_proj.md           # 项目总结（文件职能/依赖/数据流/设计思想）
│   ├── project_design.md         # 设计辅助文档（流程图 / ER 图）
│   └── api/                      # API 参考（docstring 自动生成）
├── data/                         # 原始数据
│   ├── io_options_processed.csv
│   ├── 沪深300_股息率_市值加权_3年_20260408_024105.csv
│   └── treasury_rates_history.csv
├── output/                       # 校准结果参数输出目录
├── image/                        # 图表输出目录
├── code/
│    ├── data_process.py               # 将中金所下载的数据进行汇总合并
│    ├── data_processor.py             # 数据加载与清洗
│    ├── model_calibrator.py           # Heston 模型参数校准
│    ├── pricing_verification.py       # 定价验证（半解析 + MC + BS）
│    ├── greeks_analysis.py            # 希腊字母计算与动态分析
│    └── main.ipynb               # 主运行 notebook
├── mkdocs.yml                    # MkDocs 配置
├── requirements.txt              # 运行时依赖
├── tests/                        # pytest 测试用例（数据取自 data/）
└── README.md
```

## 环境安装

```bash
pip install -r requirements.txt
```

## 文档

文档统一存放于 `docs/` 目录，使用 MkDocs 创建和维护：

```bash
pip install mkdocs mkdocstrings mkdocstrings-python
mkdocs serve     # 本地预览
mkdocs build     # 静态构建到 site/
```

- `docs/summary_proj.md`：项目总结（每个文件的职能、模块依赖、数据流向、算法选择与设计思想）。
- `docs/project_design.md`：流程图、数据流图与 ER 图。
- `docs/api/`：API 参考，由各模块 docstring 经 mkdocstrings 自动生成。

## 测试

测试统一使用 pytest 框架，测试文件位于 `tests/` 目录（命名规则 `test_<模块名>.py`），测试数据取自 `data/`：

```bash
pip install pytest
pytest
```

## 数据准备

1. **期权数据** `io_options_processed.csv`  
   需包含字段：`date`, `expiry`, `cp` (C/P), `strike`, `close`, `delta`, `T`, `volume`, `open_interest` 等。

2. **股息率数据** `沪深300_股息率_市值加权_3年_20260408_024105.csv`  
   需包含：`日期`, `收盘点位`, `股息率市值加权`。

3. **利率曲线** `treasury_rates_history.csv`  
   脚本会通过 `akshare` 自动获取并保存，若已存在则直接读取。

本仓库提供了详细的2025年完整数据示例。如果需要分析其他年份的数据，需要将相应的文件进行替换，并保持文件格式不变。

## 运行步骤

1. 启动 Jupyter 并打开 `main.ipynb`。
2. 按顺序执行各个 Cell：
   - 导入库并设置参数；
   - 获取利率数据；
   - 初始化 `HestonDataProcessor` 并清洗期权数据；
   - 运行每日校准 `run_daily_calibration`；
   - （可选）单日定价验证；
   - （可选）希腊字母动态分析；
   - 生成论文图表。

3. 主要输出文件：
   - `output/calibrated_params_daily.csv`：每日 Heston 参数及 RMSE/MAE。
   - `calibration_options.csv`：每日实际使用的期权子集。
   - `2025-04-01-pricing_comparison.csv`：以2025年4月1日为验证日期，三个模型的表现对比。可以在main.ipynb当中设置不同日期。
   - `greeks_dynamics_C3900_20250620.csv`：C3900_20250620日到期的希腊字母动态。同样可以在main,ipynb当中设置所分析期权。
   - `processor.pkl`：预训练完成的2025年模型数据，方便想要复现的读者快速复现。在main当中可以直接导入。


## 核心模块说明

| 模块 | 功能 |
|------|------|
| `HestonDataProcessor` | 加载数据、清洗、计算 BS 隐含波动率 |
| `HestonModelCalibrator` | 两阶段校准（差分进化 + L‑BFGS‑B），含 Feller 约束和 BS 先验 |
| `run_daily_calibration` | 逐日校准流程，失败时自动回退 |
| `HestonModelPricer` | QuantLib 半解析定价 |
| `HestonMonteCarloPricer` | 全截断 Euler MC 定价，支持对偶变量 |
| `HestonGreeksCalculator` | 使用有限差分引擎计算希腊字母 |
| `analyze_greeks_dynamics` | 批量计算指定期权的希腊字母时间序列 |

## 注意事项

- 校准计算量较大，完整 2025 年数据约3小时
- 蒙特卡洛样本量默认为 1e7，可适当调低以加速。
- 请确保数据文件路径、文件编码和名称与 `main.ipynb` 中的配置一致。

## 联系方式

如有问题，请提 Issue 联系作者。

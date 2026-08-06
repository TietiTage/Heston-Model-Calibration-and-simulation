# Heston 模型期权校准与希腊字母分析

本项目基于 **QuantLib** 实现 Heston 随机波动率模型，对沪深 300 指数期权进行每日校准，并计算期权价格、BS 隐含波动率与希腊字母（delta / gamma / theta / rho / vega），用于学术分析或期权策略研究。

## 项目结构

```text
Heston-Model-Calibration-and-simulation/
├── index.html                     # 统一本地文档入口（浏览器双击打开）
├── start_docs.bat                 # 一键构建并打开本地文档
├── readme.md                      # 项目总结与使用说明（本文档）
├── docs/                          # 文档（MkDocs 站点源）
│   ├── project_design.md          # 设计辅助文档（流程图）
│   └── api/                       # API 参考（docstring 自动生成）
├── code/                          # 源代码
│   ├── data_process.py            # 中金所数据汇总合并
│   ├── data_processor.py          # 数据加载与清洗
│   ├── model_calibrator.py        # Heston 模型参数校准
│   ├── pricing_verification.py    # 定价验证（半解析 + MC + BS）
│   ├── greeks_analysis.py         # 希腊字母计算与动态分析
│   └── main.ipynb                 # 主运行 notebook
├── tests/                         # pytest 测试用例（数据取自 data/）
├── data/                          # 原始数据
├── output/                        # 校准结果参数输出目录
├── image/                         # 图表输出目录
├── mkdocs.yml                     # MkDocs 配置
├── requirements.txt               # 运行时依赖
└── progress.md                    # 项目进度记录
```

## 环境安装

虚拟环境：`data_process`（Python 3.12）。

```bash
pip install -r requirements.txt
```

## 文档与统一本地入口

项目文档统一存放于 `docs/` 目录，使用 MkDocs 创建和维护；根目录提供统一的本地入口：

- **`index.html`**：统一入口页，汇总指向项目总结、设计文档与 API 参考，浏览器直接打开；
- **`start_docs.bat`**：一键构建 MkDocs 站点并在浏览器中打开入口页（需 `data_process` 环境已安装 mkdocs / mkdocstrings）；
- 手工方式：`mkdocs serve` 本地预览，或 `mkdocs build` 构建到 `site/`。

## 测试

测试统一使用 pytest 框架，测试文件位于 `tests/` 目录（命名规则 `test_<模块名>.py`），测试数据取自 `data/`：

```bash
pip install pytest
pytest
```

## 数据准备

1. **期权数据** `data/io_options_processed.csv`
   需包含字段：`date`, `合约代码`, `strike`, `cp` (C/P), `close`, `volume`, `open_interest`, `delta`, `expiry`, `T` 等。

2. **股息率数据** `data/沪深300_股息率_市值加权_*.csv`
   需包含：`日期`, `收盘点位`, `股息率市值加权`。

3. **利率曲线** `data/treasury_rates_history.csv`
   脚本会通过 `akshare` 自动获取并保存，若已存在则直接读取。

本仓库提供了详细的 2025 年完整数据示例。如需分析其他年份，替换相应文件并保持格式不变。

## 数据文件格式

### `data/io_options_processed.csv`（GBK 编码，期权交易数据）

| 列名 | 类型 | 说明 |
|---|---|---|
| date | str → pd.Timestamp | 交易日，格式 `YYYY-MM-DD` |
| 合约代码 | str | 如 `IO2501-C-3450`（IO+YYMM+CP+行权价） |
| strike | float | 行权价 |
| cp | str | `C`（看涨）/ `P`（看跌） |
| close | float | 期权收盘价 |
| volume | float | 成交量 |
| open_interest | float | 持仓量 |
| delta | float | 期权 Delta |
| expiry | str → pd.Timestamp | 到期日（当月第三个周五，遇节假日前移） |
| T | float | 剩余期限（年）= (expiry − date).days / 365 |

### `data/treasury_rates_history.csv`（利率曲线）

| 列名 | 类型 | 说明 |
|---|---|---|
| date | str → pd.Timestamp | 日期 `YYYY-MM-DD` |
| 0.25 / 0.5 / 1.0 | float | 期限（年）对应的连续复利无风险利率 |

说明：`HestonDataProcessor._get_daily_rate_dict` 将除 date 外的所有列名转为 float 期限；`get_risk_free_rate` 对期限做线性插值。

### `data/沪深300_股息率_市值加权_*.csv`（现货与股息率，UTF-8）

| 列名 | 类型 | 说明 |
|---|---|---|
| 日期 | str → pd.Timestamp | 格式 `YYYY/M/D` |
| 收盘点位 | float | 沪深300 收盘点位（作为标的资产价格 spot） |
| 全收益收盘点位(元) | float | 全收益指数点位 |
| 市值(元) | float | 总市值 |
| 流通市值(元) | float | 流通市值 |
| 自由流通市值(元) | float | 自由流通市值 |
| 股息率市值加权 | float | 市值加权股息率 → 连续复利股息率 `q_cont = log1p(股息率)` |

### 输出文件

> 以下文件由 `code/main.ipynb` 运行时生成，已加入 `.gitignore`，不入版本库。

| 路径 | 列/内容 | 说明 |
|---|---|---|
| `output/calibrated_params_daily.csv` | date, v0, kappa, theta, sigma, rho, rmse, mae, status | 每日校准参数与误差 |
| `code/calibration_options.csv` | date, 合约代码, strike, cp, close, volume, open_interest, delta, expiry, T, bs_iv | 每日实际使用的期权子集（GBK） |
| `code/*-pricing_comparison.csv` | strike, type, T, market, BlackScholes, BS_const, Heston_analytic, Heston_MC | 单日多模型定价对比 |
| `code/greeks_dynamics_*.csv` | delta, gamma, theta, rho, vega, date, spot | 指定期权希腊字母时序 |
| `code/processor.pkl` | 二进制 | 序列化的 `HestonDataProcessor` 实例，用于快速复现 |

## 运行步骤

1. 启动 Jupyter 并打开 `code/main.ipynb`。
2. 按顺序执行各个 Cell：
   - 导入库并设置参数；
   - 获取利率数据；
   - 初始化 `HestonDataProcessor` 并清洗期权数据；
   - 运行每日校准 `run_daily_calibration`；
   - （可选）单日定价验证；
   - （可选）希腊字母动态分析；
   - 生成论文图表。

3. 主要输出文件（由 notebook 运行时生成，已加入 `.gitignore`，不入库）：
   - `output/calibrated_params_daily.csv`：每日 Heston 参数及 RMSE/MAE。
   - `code/calibration_options.csv`：每日实际使用的期权子集。
   - `code/2025-04-01-pricing_comparison.csv`：以 2025 年 4 月 1 日为验证日期的三模型对比（可在 notebook 中设置）。
   - `code/greeks_dynamics_C3900_20250620.csv`：C3900_20250620 日到期的希腊字母动态。
   - `code/processor.pkl`：预训练完成的模型数据，可导入快速复现。

## 文件职能

### 源码（`code/`）

| 文件 | 职能 |
|---|---|
| `data_process.py` | 一次性脚本：扫描中金所原始 CSV（GBK），解析 IO 合约与到期日，汇总合并为 `data/io_options_processed.csv` |
| `data_processor.py` | 数据中枢：加载清洗期权数据，维护现货 / 股息率 / 利率市场环境，计算 BS 隐含波动率，提供统一校准期权子集 |
| `model_calibrator.py` | 核心建模：单日 Heston 参数校准（差分进化 + L-BFGS-B 两阶段），含 BS 弱先验与 Feller 软约束；提供逐日校准与分层恢复策略 |
| `pricing_verification.py` | 定价验证：Heston 半解析、Heston 蒙特卡洛（全截断 Euler + 对偶变量）、BS 公式，以及单日多模型对比 |
| `greeks_analysis.py` | 风险度量：基于有限差分引擎计算 delta/gamma/theta/rho/vega，支持逐日动态分析 |
| `main.ipynb` | 主运行入口：参数配置、利率获取、每日校准、定价验证、希腊字母分析与论文图表生成 |

### 文档与测试

| 文件 | 职能 |
|---|---|
| `readme.md` | 项目总结：文件职能、模块依赖、数据流向、算法选择与设计思想（本文档） |
| `index.html` / `start_docs.bat` | 统一本地文档入口与一键打开脚本 |
| `docs/project_design.md` | 设计辅助文档：流程图、数据流图 |
| `docs/api/*.md` | API 参考：类的构成、函数输入输出、变量类型（docstring 自动生成） |
| `tests/` | pytest 测试用例（`test_<模块名>.py`） |

## 模块依赖

```text
main.ipynb
  ├── data_processor.py        (HestonDataProcessor)
  ├── model_calibrator.py      (HestonParameterSet, run_daily_calibration)
  ├── pricing_verification.py  (HestonModelPricer, HestonMonteCarloPricer,
  │                             BlackScholesPricer, compare_pricing_on_date)
  ├── greeks_analysis.py       (analyze_greeks_dynamics, OptionSpec)
  ├── akshare / matplotlib / seaborn / sklearn.metrics / scipy.optimize
  └── pickle（保存/加载 processor.pkl）

model_calibrator.py ──> data_processor.py（filter_calibration_options）
pricing_verification.py ──> model_calibrator.py（HestonParameterSet）
greeks_analysis.py ──> model_calibrator.py + data_processor.py
```

第三方库：QuantLib（定价/校准引擎）、pandas / numpy（数据处理）、scipy（优化与正态分布）、akshare（利率行情）、matplotlib / seaborn（绘图）、scikit-learn（误差指标）。

## 数据流向

```text
中金所原始 CSV（GBK）
  → data_process.py：交易日解析、IO 合约解析、第三个周五到期日、列名映射
  → data/io_options_processed.csv
  → HestonDataProcessor：流动性过滤 → Delta 过滤 → spot_map / q_cont / 利率插值
  → BS 隐含波动率 bs_iv
  → filter_calibration_options（统一过滤条件）
  → HestonModelCalibrator.calibrate（DE → L-BFGS-B）→ 每日参数
  → compare_pricing_on_date / analyze_greeks_dynamics → CSV 与论文图表
```

详细流程图见 [docs/project_design.md](docs/project_design.md)。

## 核心模块说明

| 模块 | 功能 |
|------|------|
| `HestonDataProcessor` | 加载数据、清洗、计算 BS 隐含波动率 |
| `HestonModelCalibrator` | 两阶段校准（差分进化 + L-BFGS-B），含 Feller 约束和 BS 先验 |
| `run_daily_calibration` | 逐日校准流程，失败时自动回退 |
| `HestonModelPricer` | QuantLib 半解析定价 |
| `HestonMonteCarloPricer` | 全截断 Euler MC 定价，支持对偶变量 |
| `HestonGreeksCalculator` | 使用有限差分引擎计算希腊字母 |
| `analyze_greeks_dynamics` | 批量计算指定期权的希腊字母时间序列 |

类与函数的详细输入输出、变量类型等请查阅 [API 参考](docs/api/data_processor.md) 或构建后的站点（`start_docs.bat` / `index.html`）。

## 算法选择与设计思想

### 期权筛选（统一过滤条件）

校准、每日校准与定价验证共用 `filter_calibration_options`，保证样本一致：

- `T >= 0.02`（剔除极短到期合约）；
- 短期高流动性：`T < 0.05` 时要求 `volume >= 500` 且 `|delta| <= 0.65`；
- `0.1 <= |delta| <= 0.9`（剔除深度实值/虚值）；
- 价格为正且有限。

### Heston 参数校准：两阶段优化

- **阶段一：差分进化（DE）全局搜索**——低精度引擎（1e-3），避免局部最优；激进模式增大种群与迭代；
- **阶段二：L-BFGS-B 局部精修**——以 DE 最优解为起点，切换高精度引擎（1e-7）。

损失函数组成：加权伪 Huber 价格误差（权重 `spot*sqrt(T)` 归一化）+ 轻 L2 正则 + Feller 软约束（惩罚 `sigma² > 2*kappa*theta`）+ BS 弱先验（由当日 IV 拟合 v0/theta/skew/convexity 中心）。

### 逐日校准的分层恢复策略

1. **BS 先验引导**：用当日 IV 先验参数作 DE 种子重校准（`prior_weight=0.3`）；
2. **增强搜索**：aggressive DE（种群 120、迭代 500）+ 新种子（`prior_weight=0.1`）；
3. 仍失败则标记 `failed`，并以当日 BS 先验作为次日初始参数，保证序列连续性。

### 定价验证

- Heston 半解析：`AnalyticHestonEngine`（1e-7, 10000）；
- Heston MC：全截断 Euler + 对偶变量，默认 1e7 路径；
- BS 基准：自身 bs_iv 逐期权定价（BS-IV）与固定平值 IV 定价（BS-Const）。

### 希腊字母

- 有限差分引擎 `FdHestonVanillaEngine`（非半解析求导）；
- rho 通过对利率曲线整体 +1% 扰动计算；vega 先对 v0 求数值导数再换算为市场惯例 `2*σ0*∂Price/∂v0`；
- `update_spot` 复用同一引擎做 spot 扫描。

### 工程约定

- QuantLib 模型参数内部顺序固定为 `[theta, kappa, sigma, rho, v0]`，与 `HestonParameterSet` 字段顺序不同，需显式映射；
- 全局 `evaluationDate` 一律用 `ql.SavedSettings()` 保护；
- 日期统一经 `_to_ql_date` 静态方法转换。

## 命名风格与编码规范

| 对象 | 风格 | 示例 |
|---|---|---|
| 模块/脚本 | 全小写 snake_case | `data_processor.py` |
| 类 | PascalCase | `HestonDataProcessor`、`HestonModelCalibrator` |
| 函数/方法 | 全小写 snake_case | `run_daily_calibration`、`get_underlying_quote` |
| 常量 | 全大写 snake_case | `PROJECT_ROOT`、`HUBER_DELTA`、`FELLER_WEIGHT` |
| TypedDict/dataclass | PascalCase | `HestonParameterSet`、`OptionSpec` |
| 输出文件 | 语义化 + 日期/参数标识 | `greeks_dynamics_C3900_20250620.csv` |

编码规范：

- 源码与文档统一 UTF-8（无 BOM）；期权数据 CSV 为 GBK，读取时显式指定 `encoding`；
- py 代码必须使用类型注解（`typing`：`Optional`、`Union`、`Literal`、`TypedDict`、`dataclass`），并为函数和类编写 docstring；
- docstring 变更后使用 MkDocs 重新生成 API 文档；
- 文档统一存放于 `docs/`，通过 `mkdocs.yml` 组织维护，根目录 `index.html` 为统一本地入口。

## 注意事项

- 校准计算量较大，完整 2025 年数据约 3 小时。
- 蒙特卡洛样本量默认为 1e7，可适当调低以加速。
- 请确保数据文件路径、文件编码和名称与 `main.ipynb` 中的配置一致。
- `code/AGENTS.md` 为 Agent 工作偏好文件，禁止修改。

## 联系方式

如有问题，请提 Issue 联系作者。

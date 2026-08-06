# summary_proj.md — 项目总结

> 本文档由 Agent 依据 `code/AGENTS.md` 要求维护，UTF-8 编码。
> 按新要求，本文件专注于：**每个文件的职能、模块依赖、数据流向、算法选择和设计思想**。
> 类的构成、函数的输入输出和主要作用、变量的类型等细节，请查阅 [API 参考](api/data_processor.md)（由 docstring 经 MkDocs 自动生成）。
> 流程图、数据流图与 ER 图等设计辅助文档见 [project_design.md](project_design.md)。

## 1. 项目概述

本项目基于 **QuantLib** 实现 Heston 随机波动率模型，对沪深 300 指数期权进行每日校准，并在此基础上计算期权价格、BS 隐含波动率与希腊字母，用于学术分析或期权策略研究。

核心链路：

```text
中金所原始数据 → data_process.py 汇总合并 → io_options_processed.csv
        ↓
data_processor.py 加载清洗 + 现货/股息率/利率 → BS 隐含波动率
        ↓
model_calibrator.py 两阶段校准（DE + L-BFGS-B）→ 每日参数
        ↓
pricing_verification.py 定价验证（Heston 半解析 / MC / BS）
        ↓
greeks_analysis.py 希腊字母计算与动态分析 → 论文图表
```

## 2. 每个文件的职能

### 2.1 源码（`code/`）

| 文件 | 职能 |
|---|---|
| `data_process.py` | 一次性脚本：扫描中金所下载的原始 CSV（GBK），解析 IO 合约代码与到期日，汇总合并为标准化期权表 `data/io_options_processed.csv` |
| `data_processor.py` | 数据中枢：加载并清洗期权数据，维护现货（沪深300收盘点位）、连续复利股息率、无风险利率曲线等市场环境，计算 BS 隐含波动率，对外提供统一的校准期权子集 |
| `model_calibrator.py` | 核心建模：单日 Heston 参数校准（差分进化 + L-BFGS-B 两阶段），含数据驱动的 BS 弱先验、Feller 软约束；提供逐日校准高层入口与分层恢复策略 |
| `pricing_verification.py` | 定价验证：Heston 半解析定价器、Heston 蒙特卡洛定价器（全截断 Euler + 对偶变量）、BS 公式定价器，以及单日多模型对比与误差总结 |
| `greeks_analysis.py` | 风险度量：基于有限差分引擎（`FdHestonVanillaEngine`）计算 delta/gamma/theta/rho/vega，并支持对指定期权做逐日希腊字母动态分析 |
| `main.ipynb` | 主运行入口：参数配置、利率获取、每日校准、定价验证、希腊字母分析与论文图表生成；可保存/加载 `processor.pkl` 快速复现 |

### 2.2 文档（`docs/`）

| 文件 | 职能 |
|---|---|
| `summary_proj.md` | 项目总结：文件职能、模块依赖、数据流向、算法选择与设计思想 |
| `project_design.md` | 设计辅助文档：流程图、数据流图、ER 图 |
| `api/*.md` | API 参考：由 docstring 经 MkDocs（mkdocstrings）自动生成 |

### 2.3 数据与输出

| 路径 | 职能 |
|---|---|
| `data/io_options_processed.csv` | 标准化期权交易数据（GBK） |
| `data/treasury_rates_history.csv` | 国债利率曲线（期限列 0.25 / 0.5 / 1.0） |
| `data/沪深300_股息率_市值加权_3年_*.csv` | 现货收盘点位与市值加权股息率 |
| `output/calibrated_params_daily.csv` | 每日 Heston 参数及 RMSE/MAE/status |
| `code/calibration_options.csv` | 每日校准实际使用的期权子集（含 bs_iv） |
| `code/*-pricing_comparison.csv` | 单日多模型定价对比结果 |
| `code/greeks_dynamics_*.csv` | 指定期权的希腊字母时间序列 |
| `code/processor.pkl` | 序列化的 `HestonDataProcessor` 实例，用于快速复现 |
| `image/*.pdf` | 论文图表输出 |

## 3. 模块依赖

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

第三方库：

| 库 | 用途 |
|---|---|
| QuantLib | 期权定价/校准引擎（Heston、BS、MC、FDM） |
| pandas / numpy | 数据处理与数值计算 |
| scipy | 优化（DE、L-BFGS-B、brentq）、正态分布 |
| akshare | 国债利率行情获取 |
| matplotlib / seaborn | 绘图 |
| scikit-learn | 误差指标 |

## 4. 数据流向

### 4.1 数据准备阶段

```text
中金所原始 CSV（GBK）
  → data_process.py：文件名前缀解析交易日、IO 合约解析、第三个周五到期日、列名映射
  → data/io_options_processed.csv（date, 合约代码, strike, cp, close, volume,
    open_interest, delta, expiry, T）
```

### 4.2 清洗与市场环境阶段

```text
io_options_processed.csv ─┐
股息率 CSV（日期/收盘点位/股息率） ─┼→ HestonDataProcessor
利率 CSV（date/0.25/0.5/1.0） ────┘
  → 流动性过滤（volume>50 且 open_interest>100）→ Delta 过滤（0.05~0.9）
  → spot_map（日期→收盘点位，向前查找）
  → q_cont = log1p(股息率市值加权)
  → 期限-利率线性插值 → ql.ZeroCurve
  → BS 隐含波动率 bs_iv（QuantLib impliedVolatility）
```

### 4.3 校准与产出阶段

```text
清洗后数据 → filter_calibration_options（T>=0.02、短期流动性、|delta|∈[0.1,0.9]）
  → HestonModelCalibrator.setup_calibration_helpers
  → calibrate（DE → L-BFGS-B）→ 每日参数
  → run_daily_calibration 逐日循环（含回退策略）→ calibrated_params_daily.csv
  → compare_pricing_on_date → pricing_comparison.csv
  → analyze_greeks_dynamics → greeks_dynamics_*.csv
  → matplotlib/seaborn → image/*.pdf
```

详细流程图见 [project_design.md](project_design.md)。

## 5. 算法选择与设计思想

### 5.1 期权筛选（统一过滤条件）

校准、每日校准与定价验证共用同一套过滤函数 `filter_calibration_options`，保证三处样本完全一致：

- 剩余期限 `T >= 0.02`（剔除极短到期合约）；
- 短期高流动性约束：`T < 0.05` 时要求 `volume >= 500` 且 `|delta| <= 0.65`；
- `0.1 <= |delta| <= 0.9`（剔除深度实值/虚值）；
- 价格为正且有限。

### 5.2 Heston 参数校准：两阶段优化

- **阶段一：差分进化（DE）全局搜索**——粗网格、低精度引擎（1e-3），避免局部最优；激进模式增大种群与迭代；
- **阶段二：L-BFGS-B 局部精修**——以 DE 最优解为起点，切换高精度引擎（1e-7）做梯度下降。

损失函数组成（`calibrate._loss_function`）：

| 组成 | 作用 |
|---|---|
| 加权伪 Huber 价格误差 | 对期权价格误差做鲁棒损失，权重 `spot*sqrt(T)` 归一化，离群值惩罚受限 |
| 轻 L2 正则 | 防止参数无意义漂移 |
| Feller 软约束 | 惩罚 `sigma² > 2*kappa*theta` 的违规量 |
| BS 弱先验 | 由当日 bs_iv 拟合得到 v0/theta/skew/convexity 先验中心，约束参数经济含义 |

### 5.3 逐日校准的分层恢复策略

当单日 RMSE 偏大或非有限时按顺序尝试：

1. **BS 先验引导**：用当日 IV 构造的先验参数作为 DE 种子重校准（降低先验权重至 0.3）；
2. **增强搜索**：aggressive DE（种群 120、迭代 500）+ 新种子（先验权重 0.1）；
3. 仍失败则标记 `failed`，并将当日 BS 先验作为次日初始参数，保证序列连续性。

### 5.4 定价验证

- **Heston 半解析**：`AnalyticHestonEngine`（1e-7, 10000）；
- **Heston MC**：`MCEuropeanHestonEngine`，全截断 Euler 离散 + 对偶变量，默认 1e7 路径；
- **BS 基准**：自身 bs_iv 逐期权定价（BS-IV）与固定平值 IV 定价（BS-Const），量化 Heston 相对收益。

### 5.5 希腊字母

- 采用有限差分引擎 `FdHestonVanillaEngine`（非半解析求导），对参数空间适应性更好；
- rho 通过对利率曲线整体 +1% 扰动计算；vega 先对 v0 求数值导数，再换算为市场惯例 `2*σ0*∂Price/∂v0`；
- `update_spot` 复用同一引擎做 spot 扫描（动态分析）。

### 5.6 工程约定

- QuantLib 模型参数内部顺序固定为 `[theta, kappa, sigma, rho, v0]`，与 `HestonParameterSet` 字段顺序不同，需显式映射；
- 全局 `evaluationDate` 一律用 `ql.SavedSettings()` 保护，避免污染其他调用；
- 日期统一经 `_to_ql_date` 静态方法转换，保证跨类型一致性。

## 6. 数据文件格式（列 / 类型 / 编码）

### 6.1 `data/io_options_processed.csv`（GBK 编码，期权交易数据）

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

### 6.2 `data/treasury_rates_history.csv`（利率曲线）

| 列名 | 类型 | 说明 |
|---|---|---|
| date | str → pd.Timestamp | 日期 `YYYY-MM-DD` |
| 0.25 / 0.5 / 1.0 | float | 期限（年）对应的连续复利无风险利率 |

说明：`HestonDataProcessor._get_daily_rate_dict` 将除 date 外的所有列名转为 float 期限；`get_risk_free_rate` 对期限做线性插值。

### 6.3 `data/沪深300_股息率_市值加权_3年_*.csv`（现货与股息率，UTF-8）

| 列名 | 类型 | 说明 |
|---|---|---|
| 日期 | str → pd.Timestamp | 格式 `YYYY/M/D` |
| 收盘点位 | float | 沪深300 收盘点位（作为标的资产价格 spot） |
| 全收益收盘点位(元) | float | 全收益指数点位 |
| 市值(元) | float | 总市值 |
| 流通市值(元) | float | 流通市值 |
| 自由流通市值(元) | float | 自由流通市值 |
| 股息率市值加权 | float | 市值加权股息率 → 连续复利股息率 `q_cont = log1p(股息率)` |

### 6.4 `output/calibrated_params_daily.csv`（校准输出）

| 列名 | 类型 | 说明 |
|---|---|---|
| date | pd.Timestamp | 评估日 |
| v0 | float | 初始方差 |
| kappa | float | 均值回复速度 |
| theta | float | 长期方差 |
| sigma | float | 方差波动率 |
| rho | float | 股价与方差相关性 |
| rmse | float | 价格 RMSE |
| mae | float | 价格 MAE |
| status | str | `ok` / `failed` |

### 6.5 `code/calibration_options.csv`（每日校准期权子集，GBK）

列 = `date, 合约代码, strike, cp, close, volume, open_interest, delta, expiry, T, bs_iv`。其中 `bs_iv` 为 BS 隐含波动率（float）。

### 6.6 `code/*-pricing_comparison.csv`（定价对比）

| 列名 | 类型 | 说明 |
|---|---|---|
| strike | float | 行权价 |
| type | str | `C` / `P` |
| T | float | 剩余期限（年） |
| market | float | 市场价 |
| BlackScholes | float | BS 公式（用自身 bs_iv） |
| BS_const | float | BS 固定波动率（平值 IV） |
| Heston_analytic | float | Heston 半解析价 |
| Heston_MC | float | Heston 蒙特卡洛价 |

### 6.7 `code/greeks_dynamics_*.csv`（希腊字母时序）

| 列名 | 类型 | 说明 |
|---|---|---|
| delta / gamma / theta / rho / vega | float | 希腊字母（vega 为市场惯例 ∂Price/∂σ） |
| date | pd.Timestamp | 评估日 |
| spot | float | 标的资产收盘点位 |

### 6.8 `code/processor.pkl`（二进制）

`pickle.dump` 序列化的 `HestonDataProcessor` 实例，包含已清洗数据、现货映射、股息率等，用于快速复现。

## 7. 命名风格与编码规范

| 对象 | 风格 | 示例 |
|---|---|---|
| 模块/脚本 | 全小写 snake_case | `data_processor.py` |
| 类 | PascalCase | `HestonDataProcessor`、`HestonModelCalibrator` |
| 函数/方法 | 全小写 snake_case | `run_daily_calibration`、`get_underlying_quote` |
| 常量 | 全大写 snake_case | `PROJECT_ROOT`、`HUBER_DELTA`、`FELLER_WEIGHT` |
| TypedDict/dataclass | PascalCase | `HestonParameterSet`、`OptionSpec` |
| 输出文件 | 语义化 + 日期/参数标识 | `greeks_dynamics_C3900_20250620.csv` |

编码规范：

- 源码与文档文件统一 UTF-8（无 BOM）；期权数据 CSV 为 GBK，读取时显式指定 `encoding`；
- py 代码必须使用类型注解（`typing`：`Optional`、`Union`、`Literal`、`TypedDict`、`dataclass`），并为函数和类编写 docstring；
- docstring 变更后需使用 MkDocs 重新生成 API 文档；
- 文档统一存放于 `docs/` 目录，通过 `mkdocs.yml` 组织维护。
- 测试统一使用 pytest 框架，测试文件置于 `tests/` 目录，命名规则 `test_<模块名>.py`，测试数据取自 `data/`。

## 8. 环境与运行说明

- 虚拟环境：`data_process`（Python 3.12）。
- 运行时依赖：`pip install -r requirements.txt`。
- 文档工具：`pip install mkdocs mkdocstrings mkdocstrings-python`；本地预览 `mkdocs serve`，静态构建 `mkdocs build`。
- 主流程：Jupyter 打开 `code/main.ipynb` 按 cell 顺序执行；或直接加载 `code/processor.pkl` 跳过校准快速复现。
- 校准计算量：完整 2025 年数据约 3 小时；MC 样本量默认 1e7，可调低加速。
- 注意：`code/AGENTS.md` 为 Agent 工作偏好文件，禁止修改；数据文件路径/编码/名称需与 `main.ipynb` 配置一致。

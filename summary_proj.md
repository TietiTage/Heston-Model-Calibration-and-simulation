# summary_proj.md — 项目文档

> 本文档由 Agent 依据 `code/AGENTS.md` 要求生成，UTF-8 编码。
> 内容覆盖：目录结构与文件清单、每个文件的格式与内容构成、类与函数（输入/输出/主要作用）、变量类型、命名风格与编码规范。

## 1. 项目概述

本项目（Heston-Model-Calibration-and-simulation）基于 **QuantLib** 实现 Heston 随机波动率模型，对沪深 300 指数期权进行每日校准，并在此基础上计算期权价格、BS 隐含波动率与希腊字母（delta / gamma / theta / rho / vega），用于学术分析或期权策略研究。

核心工作流：

```text
中金所原始数据 → data_process.py 汇总合并 → io_options_processed.csv
        ↓
data_processor.py 加载清洗 + 股息率/利率 → 计算 BS 隐含波动率
        ↓
model_calibrator.py 两阶段校准（差分进化 + L-BFGS-B）→ 每日参数
        ↓
pricing_verification.py 定价验证（Heston 半解析 / Heston MC / BS）
        ↓
greeks_analysis.py 希腊字母计算与动态分析 → 论文图表
```

## 2. 目录结构与文件清单

```text
Heston-Model-Calibration-and-simulation/
├── readme.md                         # 项目说明（中文，UTF-8）
├── requirements.txt                  # Python 依赖（重写后：可直接 pip 安装）
├── LICENSE                           # 许可证
├── summary_proj.md                   # 本文档（Agent 生成）
├── progress.md                       # 项目进度记录（Agent 维护）
├── data/                             # 输入数据
│   ├── io_options_processed.csv                 # 期权交易数据（GBK）
│   ├── treasury_rates_history.csv               # 国债利率曲线（UTF-8/GBK）
│   └── 沪深300_股息率_市值加权_3年_20260408_024105.csv  # 现货/股息率（UTF-8）
├── output/                           # 校准结果输出
│   └── calibrated_params_daily.csv   # 每日 Heston 参数与误差
├── image/                            # 论文图表输出（PDF）
│   ├── calib_bs_iv_hist.pdf                    # 校准隐含波动率直方图
│   ├── calib_option_count.pdf                  # 每日校准期权数量
│   ├── calib_strike_T_scatter.pdf              # 行权价-期限散点
│   ├── CSI300_close_price.pdf                  # 沪深300收盘价
│   ├── fig_calibration_error.pdf               # 校准误差
│   ├── fig_delta_spot.pdf / fig_gamma_spot.pdf / fig_rho_spot.pdf
│   ├── fig_theta_spot.pdf / fig_vega_spot.pdf  # 希腊字母随标的变化
│   ├── fig_iv_smile.pdf                        # 隐含波动率微笑
│   ├── fig_kappa_time_series.pdf               # kappa 时序
│   ├── fig_parameters_time_series.pdf          # 参数时序总图
│   ├── fig_price_scatter.pdf                   # 价格散点
│   ├── heston_vs_bs_error.pdf                  # Heston vs BS 误差对比
│   └── RMSE_MAE_Comparison.pdf                 # RMSE/MAE 对比
└── code/                            # 源代码
    ├── AGENTS.md                    # Agent 工作偏好（用户指示，禁止修改）
    ├── data_process.py              # 中金所数据汇总合并
    ├── data_processor.py            # 数据加载与清洗（HestonDataProcessor）
    ├── model_calibrator.py          # Heston 模型校准（HestonModelCalibrator）
    ├── pricing_verification.py      # 定价验证（半解析 + MC + BS）
    ├── greeks_analysis.py           # 希腊字母计算与动态分析
    ├── main.ipynb                   # 主运行 notebook（26 个 cell）
    ├── calibration_options.csv      # 每日校准实际使用的期权子集（GBK）
    ├── 2025-04-01-pricing_comparison.csv  # 定价验证对比结果
    ├── greeks_dynamics_C3900_20250620.csv  # 指定期权希腊字母时序
    └── processor.pkl                # 序列化的 HestonDataProcessor 实例
```

## 3. 模块依赖关系

```text
main.ipynb
  ├── data_processor.py   (HestonDataProcessor)
  ├── model_calibrator.py (HestonParameterSet, run_daily_calibration)
  ├── pricing_verification.py (HestonModelPricer, HestonMonteCarloPricer, BlackScholesPricer, compare_pricing_on_date)
  ├── greeks_analysis.py  (analyze_greeks_dynamics, OptionSpec)
  ├── akshare / matplotlib / seaborn / sklearn.metrics / scipy.optimize
  └── pickle（保存/加载 processor.pkl）

model_calibrator.py ──> data_processor.py（filter_calibration_options）
pricing_verification.py ──> model_calibrator.py（HestonParameterSet）
greeks_analysis.py ──> model_calibrator.py + data_processor.py
```

外部第三方库（直接导入）：

| 库 | 用途 | 版本（data_process 环境） |
|---|---|---|
| QuantLib | 期权定价/校准引擎 | 1.42 |
| pandas | 数据处理 | 2.2.3 |
| numpy | 数值计算 | 1.26.4 |
| scipy | 优化（DE、L-BFGS-B、brentq）、正态分布 | 1.16.0 |
| akshare | 国债利率行情获取 | 1.18.56 |
| matplotlib | 绘图 | 3.8.4 |
| seaborn | 统计绘图 | 0.13.2 |
| scikit-learn | 误差指标（mean_squared_error 等） | 1.5.1 |

## 4. 数据文件格式（列 / 类型 / 编码）

### 4.1 `data/io_options_processed.csv`（GBK 编码，期权交易数据）

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

### 4.2 `data/treasury_rates_history.csv`（利率曲线）

| 列名 | 类型 | 说明 |
|---|---|---|
| date | str → pd.Timestamp | 日期 `YYYY-MM-DD` |
| 0.25 / 0.5 / 1.0 | float | 期限（年）对应的连续复利无风险利率 |

说明：`HestonDataProcessor._get_daily_rate_dict` 将除 date 外的所有列名转为 float 期限；`get_risk_free_rate` 对期限做线性插值。

### 4.3 `data/沪深300_股息率_市值加权_3年_20260408_024105.csv`（现货与股息率，UTF-8）

| 列名 | 类型 | 说明 |
|---|---|---|
| 日期 | str → pd.Timestamp | 格式 `YYYY/M/D` |
| 收盘点位 | float | 沪深300 收盘点位（作为标的资产价格 spot） |
| 全收益收盘点位(元) | float | 全收益指数点位 |
| 市值(元) | float | 总市值 |
| 流通市值(元) | float | 流通市值 |
| 自由流通市值(元) | float | 自由流通市值 |
| 股息率市值加权 | float | 市值加权股息率 → 连续复利股息率 `q_cont = log1p(股息率)` |

### 4.4 `output/calibrated_params_daily.csv`（校准输出）

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

### 4.5 `code/calibration_options.csv`（每日校准期权子集，GBK）

列 = `date, 合约代码, strike, cp, close, volume, open_interest, delta, expiry, T, bs_iv`。
其中 `bs_iv` 为 BS 隐含波动率（float），由 `calculate_implied_volatility` 计算。

### 4.6 `code/2025-04-01-pricing_comparison.csv`（定价对比）

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

### 4.7 `code/greeks_dynamics_C3900_20250620.csv`（希腊字母时序）

| 列名 | 类型 | 说明 |
|---|---|---|
| delta / gamma / theta / rho / vega | float | 希腊字母（vega 为市场惯例 ∂Price/∂σ） |
| date | pd.Timestamp | 评估日 |
| spot | float | 标的资产收盘点位 |

### 4.8 `code/processor.pkl`（二进制）

`pickle.dump` 序列化的 `HestonDataProcessor` 实例，包含已清洗数据、现货映射、股息率等，用于快速复现。

## 5. 代码文件详解

### 5.1 `code/data_process.py` — 中金所数据汇总合并

**格式**：UTF-8，Python 脚本（无类，仅模块级函数 + `__main__` 入口）。

**模块级常量**

| 名称 | 类型 | 说明 |
|---|---|---|
| `PROJECT_ROOT` | `pathlib.Path` | 项目根目录 = `code/` 的上一级 |

**函数清单**

| 函数 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `third_friday_of_month(year: int, month: int)` | 年份、月份 | `datetime` | 返回当月第三个周五，若为交易所节假日则向前调整至最近交易日（中国 SSE 日历，`ql.Preceding`） |
| `parse_contract(contract_code: str)` | 合约代码字符串 | `Optional[Tuple[int, int, str, int]]` | 用正则 `IO(\d{2})(\d{2})[-]?([CP])[-]?(\d+)` 解析为 `(expiry_year, expiry_month, cp, strike)`，不匹配返回 `None` |
| `process_files(root_dir: Path = PROJECT_ROOT/"data")` | 根目录 | `pd.DataFrame` | 递归扫描 `**/*.csv`，以文件名前缀 `YYYYMMDD` 作为交易日，读取 GBK 编码文件，筛选 `IO` 开头合约，补充 date/expiry/T 列，中文列名映射为英文并合并 |

**变量类型**：`all_data: list[pd.DataFrame]`、`io_df: pd.DataFrame`、`rename_map: dict[str, str]`、`final_cols: list[str]`。

**`__main__`**：调用 `process_files`，按 `date, 合约代码` 排序后写入 `data/io_options_processed.csv`（GBK）。

### 5.2 `code/data_processor.py` — 数据加载与清洗

**格式**：UTF-8，Python 模块。包含 1 个模块级函数 + 1 个类。

**模块级函数**

| 函数 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `filter_calibration_options(df: pd.DataFrame)` | 期权 DataFrame | `pd.DataFrame` | 统一的校准期权筛选：`T >= 0.02`；短期（T<0.05）要求 `volume >= 500` 且 `\|delta\| <= 0.65`；`0.1 <= \|delta\| <= 0.9`；`close > 0` 且有限 |

**类 `HestonDataProcessor`**

构造参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `option_csv_path` | `str` | 期权 CSV 路径 |
| `dividend_csv_path` | `str` | 股息率/现货 CSV 路径 |
| `rate_df` | `pd.DataFrame` | 利率表（含 date 列与期限列） |

实例属性（含类型）：

| 属性 | 类型 | 说明 |
|---|---|---|
| `cleaned_data` | `Optional[pd.DataFrame]` | 清洗后数据（`load_and_clean_data` 后非空） |
| `raw_data` | `Optional[pd.DataFrame]` | 仅做最小期限过滤的原始副本 |
| `option_csv` | `str` | 期权文件路径 |
| `dividend_csv` | `str` | 股息率文件路径 |
| `rate_df` | `pd.DataFrame` | 利率表 |
| `spot_map` | `Optional[Dict[pd.Timestamp, float]]` | 日期 → 沪深300收盘点位 |
| `_dividend_df` | `Optional[pd.DataFrame]` | 日期 → `q_cont`（连续复利股息率） |

方法清单：

| 方法 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `_to_timestamp(value)`（staticmethod） | `str / pd.Timestamp / datetime` | `pd.Timestamp` | 归一化为零点的 Timestamp |
| `_to_ql_date(value)`（staticmethod） | `str / ql.Date / datetime / pd.Timestamp` | `ql.Date` | 转 QuantLib 日期 |
| `_load_dividend_and_spot()` | 无 | `None` | 读股息率 CSV，构建 `spot_map` 与 `_dividend_df`；缺列抛 `ValueError` |
| `get_underlying_quote(eval_date)` | 评估日期 | `float` | 返回当日现货价；无当日数据则向前取最近有效日 |
| `load_and_clean_data()` | 无 | `pd.DataFrame` | GBK 读取期权 CSV，`T > 0.02`、日期归一化、cp 大写、数值列强制转换、缺失值剔除、流动性过滤（volume>50 且 open_interest>100）、Delta 过滤（0.05~0.9），排序后赋给 `cleaned_data` |
| `_load_dividend_df()` | 无 | `pd.DataFrame` | 返回 `_dividend_df`，未加载则抛异常 |
| `get_dividend_yield(eval_date)` | 评估日期 | `float` | 返回评估日前最近的 `q_cont` |
| `_get_daily_rate_dict(eval_date)` | 评估日期 | `Dict[float, float]` | 返回该日最新的 期限→利率 字典 |
| `get_risk_free_rate(T, eval_date)` | 剩余期限 `float`、评估日 | `float` | 对期限点做线性插值得到无风险利率 |
| `_build_rate_curve(eval_date)` | 评估日期 | `ql.ZeroCurve` | 以评估日为参考日构建零息利率曲线（Actural365Fixed + China + Linear + Continuous） |
| `calculate_implied_volatility(eval_date)` | 评估日期 | `pd.DataFrame` | 逐行用 QuantLib `impliedVolatility` 计算 BS 隐含波动率，新增 `bs_iv` 列，剔除计算失败行 |
| `get_data_by_date(eval_date)` | 评估日期 | `pd.DataFrame` | 返回清洗数据中当天的期权 |
| `get_calibration_data(eval_date)` | 评估日期 | `pd.DataFrame` | 先算 IV 再套用 `filter_calibration_options`，保证与校准样本一致 |

### 5.3 `code/model_calibrator.py` — Heston 模型参数校准

**格式**：UTF-8，Python 模块。包含 2 个类型定义 + 1 个 dataclass + 1 个类 + 1 个高层函数。

**`@dataclass HestonParameterSet`**

字段（全部 `float`）：`v0`（初始方差）、`kappa`（均值回复速度）、`theta`（长期方差）、`sigma`（方差波动率）、`rho`（相关性）。

**`class OptionHelper(TypedDict)`**

字段：`T: float`、`strike: float`、`cp: Literal['C','P']`、`market_price: float`、`expiry_date: ql.Date`、`ql_option: ql.VanillaOption`。

**类 `HestonModelCalibrator`**

构造参数：

| 参数 | 类型 | 说明 |
|---|---|---|
| `eval_date` | `Union[ql.Date, str, pd.Timestamp]` | 评估日 |
| `option_data` | `pd.DataFrame` | 当日期权数据（应含 bs_iv） |
| `spot` | `float` | 标的资产价格 |
| `risk_free_curve` | `ql.YieldTermStructureHandle` | 无风险利率曲线 |
| `dividend_curve` | `ql.YieldTermStructureHandle` | 股息率曲线 |

实例属性：`helpers: List[OptionHelper]`、`model: Optional[ql.HestonModel]`、`engine: Optional[ql.AnalyticHestonEngine]`、`prior_v0_center / prior_theta_center / prior_skew / prior_convexity: Optional[float]`（BS 弱先验中心）。

方法清单：

| 方法 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `_compute_bs_priors()` | 无 | `None` | 由当日 bs_iv 计算先验：theta=均方 IV；v0=ATM IV²；对 log-moneyness 二次拟合得到 skew/convexity 先验 |
| `_to_ql_date(value)`（staticmethod） | 日期 | `ql.Date` | 日期转换 |
| `setup_calibration_helpers()` | 无 | `None` | 套用统一过滤条件，构建 `ql.VanillaOption` 辅助对象列表 `helpers` |
| `_price_one_option(option_type, strike, expiry_date)` | `Literal['C','P']`、`float`、日期 | `float` | 用当前引擎定价，非法值返回 `np.nan` |
| `calibrate(initial_params, aggressive=False, seed_individual=None, prior_weight=0.5)` | 初始参数 `HestonParameterSet`、是否激进 `bool`、DE 种子个体 `array-like`、先验权重 `float` | `Tuple[HestonParameterSet, ql.HestonModel]` | 两阶段校准：先差分进化（DE）全局搜索，再 L-BFGS-B 局部精修。损失 = 加权伪 Huber 价格误差 + 轻 L2 正则 + Feller 软约束 + BS 弱先验；返回最优参数与最终模型 |
| `calculate_calibration_error()` | 无 | `Tuple[float, float]` | 计算模型价 vs 市场价的 RMSE 与 MAE |

**函数 `run_daily_calibration(processor, start_date, end_date, initial_params, calibration_options_csv='calibration_options.csv') -> pd.DataFrame`**

输入：

| 参数 | 类型 | 说明 |
|---|---|---|
| `processor` | `HestonDataProcessor` | 已调用 `load_and_clean_data` 的处理器 |
| `start_date / end_date` | `Union[str, pd.Timestamp, datetime]` | 校准日期范围 |
| `initial_params` | `HestonParameterSet` | 首日初始参数 |
| `calibration_options_csv` | `Optional[str]` | 保存每日校准期权子集的 CSV 路径，`None` 则不保存 |

输出：`pd.DataFrame`，列 = `date, v0, kappa, theta, sigma, rho, rmse, mae, status`。

主要逻辑：逐日遍历 → 计算 IV → 过滤 → 校准；若 `RMSE > 20` 或非有限，依次尝试（1）BS 先验引导重校准（`prior_weight=0.3`）；（2）aggressive DE + 新种子（`prior_weight=0.1`）；最终 `RMSE > 25` 则标记 `failed` 并用当日 BS 先验作为次日初始参数，否则标记 `ok` 并滚动更新 `current_initial`。

### 5.4 `code/pricing_verification.py` — 定价验证

**格式**：UTF-8，Python 模块。包含 3 个类 + 1 个函数。

**类 `HestonModelPricer`**（半解析定价）

构造参数：`params: HestonParameterSet`、`spot: float`、`risk_free_curve / dividend_curve: ql.YieldTermStructureHandle`。

| 方法 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `_to_ql_date(value)`（staticmethod） | 日期 | `ql.Date` | 日期转换 |
| `_build_engine(eval_date)` | 评估日 | `ql.AnalyticHestonEngine` | 构建高精度引擎（relTol=1e-7, maxEval=10000） |
| `price(option_type, strike, expiry_date, eval_date)` | `Literal['C','P']`、`float`、日期、评估日 | `float` | 返回欧式期权半解析价格 |

**类 `HestonMonteCarloPricer`**（全截断 Euler MC）

构造参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `params` | `HestonParameterSet` | — | 模型参数 |
| `spot` | `float` | — | 标的价格 |
| `risk_free_ts / dividend_ts` | `ql.YieldTermStructureHandle` | — | 利率/股息率曲线 |
| `eval_date / expiry_date` | 日期 | — | 评估日 / 到期日 |
| `n_steps` | `int` | 252 | 每年时间步数 |
| `n_paths` | `int` | 1e7 | MC 样本量 |
| `antithetic` | `bool` | True | 是否使用对偶变量 |
| `seed` | `int` | 42 | 随机种子 |

| 方法 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `_to_ql_date(value)`（staticmethod） | 日期 | `ql.Date` | 日期转换 |
| `_build_engine()` | 无 | `ql.MCEuropeanHestonEngine` | 构建全截断 Euler MC 引擎（PseudoRandom + antithetic + requiredSamples） |
| `price(strike, option_type='C')` | 行权价、类型 | `float` | MC 期权价格 |
| `price_with_error(strike, option_type='C')` | 行权价、类型 | `Tuple[float, float]` | `(价格, MC 标准误)` |

**类 `BlackScholesPricer`**（BS 公式）

| 方法 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `price(spot, strike, r, q, T, sigma, option_type='C')`（staticmethod） | 标的价格、行权价、利率、股息率、期限、波动率、类型 | `float` | BS 闭式解（`scipy.stats.norm`），T<=0 或 sigma<=0 时返回内在价值 |

**函数 `compare_pricing_on_date(eval_date, processor, calibrated_params, calibration_csv='calibration_options.csv') -> Optional[pd.DataFrame]`**

输入：评估日、`HestonDataProcessor`、校准参数 `HestonParameterSet`、校准期权 CSV 路径。
输出：`pd.DataFrame`，列 = `strike, type, T, market, BlackScholes, BS_const, Heston_analytic, Heston_MC`；无数据返回 `None`。

主要逻辑：加载当日校准期权 → 计算固定波动率 `sigma_const`（平值 bs_iv）→ 分别用 Heston 半解析、Heston MC、BS-IV、BS-Const 定价 → 打印各模型 MAE 总结。

### 5.5 `code/greeks_analysis.py` — 希腊字母计算与动态分析

**格式**：UTF-8，Python 模块。包含 2 个 TypedDict + 1 个类 + 1 个函数。

**`class OptionSpec(TypedDict)`**：`strike: int`、`type: Literal['C','P']`、`expiry: datetime`。

**`class GreeksRecord(TypedDict)`**：`delta/gamma/theta/rho/vega: float`、`date: pd.Timestamp`、`spot: float`。

**类 `HestonGreeksCalculator`**

构造参数：`params: HestonParameterSet`、`spot: float`、`risk_free_curve / dividend_curve: ql.YieldTermStructureHandle`、`eval_date`。初始化即构建 `FdHestonVanillaEngine`（有限差分引擎）。

实例属性：`spot_quote: ql.SimpleQuote`、`spot_handle: ql.QuoteHandle`、`model: ql.HestonModel`、`engine: ql.FdHestonVanillaEngine`、`eval_date: ql.Date`。

| 方法 | 输入 | 输出 | 主要作用 |
|---|---|---|---|
| `_to_ql_date(value)`（staticmethod） | 日期 | `ql.Date` | 日期转换 |
| `_setup_engine()` | 无 | `None` | 基于当前参数构建 Heston 模型与 FDM 引擎 |
| `update_spot(new_spot)` | `float` | `None` | 更新标的报价 |
| `get_greeks(option_type, strike, expiry_date, spot_override=None)` | 类型、行权价、到期日、可选现货覆盖 | `Dict[str, float]` | 返回 `delta/gamma/theta/rho/vega`；vega 由对 v0 的敏感度换算为市场惯例 `2*σ0*∂Price/∂v0` |
| `_compute_rho(...)` | 同 get_greeks | `float` | 利率 +1%（bump=0.01）扰动曲线，价格差即 rho |
| `_compute_vega(...)` | 同 get_greeks | `float` | 扰动 v0（bump=1%·v0）求数值导数 |
| `_price_with_current_params(...)` | 期权参数 | `float` | 用当前引擎定价（支持 spot_override 并恢复） |
| `_price_with_given_params(...)` | 期权参数 + `HestonParameterSet` | `float` | 临时构造计算器定价 |

**函数 `analyze_greeks_dynamics(processor, params_df, target_option_spec, eval_dates) -> pd.DataFrame`**

输入：`processor: HestonDataProcessor`、`params_df: pd.DataFrame`（每日参数）、`target_option_spec: OptionSpec`、`eval_dates: List[日期]`。
输出：`pd.DataFrame`，列 = `delta, gamma, theta, rho, vega, date, spot`。
主要逻辑：对每个评估日取出当日校准参数与现货价，构建 `HestonGreeksCalculator` 计算指定期权的希腊字母；单日失败仅打印错误并跳过。

### 5.6 `code/main.ipynb` — 主运行 Notebook

**格式**：JSON（Jupyter Notebook，utf-8），共 26 个 cell（21 代码 + 5 markdown）。

Cell 内容构成：

| Cell | 类型 | 内容 |
|---|---|---|
| 0 | 代码 | 导入 ql/pd/np、HestonDataProcessor、HestonParameterSet/run_daily_calibration、pickle |
| 1 | 代码 | 路径/参数配置；akshare 获取国债利率并保存 `treasury_rates_history.csv`；初始化 processor |
| 2–4 | 代码 | 数据加载、清洗、隐含波动率计算 |
| 5 | 代码 | 导入 `compare_pricing_on_date`、`analyze_greeks_dynamics` |
| 6–8 | 代码 | 每日校准 `run_daily_calibration` 配置与执行 |
| 9 | 代码 | 保存 `processor.pkl`；Heston 半解析/MC 定价示例 |
| 10 | 代码 | 导入 matplotlib/seaborn 准备绘图 |
| 11 | markdown | “加载数据并绘图” |
| 12–15 | 代码 | 图表生成（收盘价、IV 微笑、误差散点等）；brentq 反解 IV |
| 16 | markdown | “bs 模型 mae rmse” |
| 17–18 | 代码 | BS 模型 RMSE/MAE 对比图 |
| 19 | markdown | “希腊字母” |
| 20–23 | 代码 | 希腊字母时序与动态分析图（delta/gamma/rho/theta/vega vs spot） |
| 24–25 | markdown/代码 | “# 完结” |

**运行顺序**：0 → 1 → 2–4 → 5–8 → 9 → 10–23（可跳过 6–8 直接加载 processor.pkl 复现）。

## 6. 命名风格与编码规范

项目命名风格统一、清晰：

| 对象 | 风格 | 示例 |
|---|---|---|
| 模块/脚本 | 全小写 snake_case | `data_processor.py` |
| 类 | PascalCase | `HestonDataProcessor`、`HestonModelCalibrator` |
| 函数/方法 | 全小写 snake_case | `run_daily_calibration`、`get_underlying_quote` |
| 常量 | 全大写 snake_case | `PROJECT_ROOT`、`HUBER_DELTA`、`FELLER_WEIGHT` |
| TypedDict/dataclass | PascalCase | `HestonParameterSet`、`OptionSpec` |
| 输出文件 | 语义化 + 日期/参数标识 | `greeks_dynamics_C3900_20250620.csv` |

编码规范：

- 源码文件统一 UTF-8；中文字符串正常使用，无 BOM。
- 数据 CSV：中文列文件（中金所/股息率）使用 GBK 或 UTF-8 读取时显式指定 `encoding`（期权数据 `encoding='gbk'`）。
- 全部对外函数使用类型注解（`typing`：`Optional`、`Union`、`Literal`、`TypedDict`、`dataclass`）。
- QuantLib 日期操作统一经 `_to_ql_date` 静态方法转换；`ql.SavedSettings()` 保护全局 `evaluationDate` 设置。
- 校准损失函数中 QuantLib 参数顺序固定为 `[theta, kappa, sigma, rho, v0]`（注释已标明）。

## 7. 环境与运行说明

- 虚拟环境：`data_process`（`E:\Anaconda\envs\data_process`，Python 3.12）。
- 依赖安装：`pip install -r requirements.txt`（重写后均为 PyPI 可直接安装的固定版本）。
- 主流程：Jupyter 打开 `code/main.ipynb` 按 cell 顺序执行；或直接加载 `code/processor.pkl` 跳过校准快速复现。
- 校准计算量：完整 2025 年数据约 3 小时；MC 样本量默认 1e7，可调低加速。
- 注意：`code/AGENTS.md` 为 Agent 工作偏好文件，禁止修改；数据文件路径/编码/名称需与 `main.ipynb` 配置一致。

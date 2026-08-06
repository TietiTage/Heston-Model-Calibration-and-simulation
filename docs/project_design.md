# project_design.md — 设计辅助文档（流程图）

> 依据 `code/AGENTS.md` 要求生成的软件工程设计辅助文档。
> 流程图从 `summary_proj.md` 中独立出来，便于单独维护；项目整体说明见 `summary_proj.md`。

## 1. 流程图

### 1.1 总体数据处理与校准流程图

```mermaid
flowchart TD
    A[中金所原始 CSV] -->|data_process.py<br/>汇总合并| B[data/io_options_processed.csv]
    B -->|data_processor.py<br/>load_and_clean_data| C[清洗后期权数据<br/>cleaned_data]
    C -->|calculate_implied_volatility| D[含 bs_iv 的期权数据]
    D -->|filter_calibration_options| E[校准期权子集]
    E -->|run_daily_calibration<br/>HestonModelCalibrator.calibrate| F[每日参数 calibrated_params_daily.csv]
    F -->|compare_pricing_on_date| G[定价对比 CSV]
    F -->|analyze_greeks_dynamics| H[希腊字母时序 CSV]
    F -->|matplotlib/seaborn| I[论文图表 PDF]
```

### 1.2 单日校准（两阶段优化 + 回退策略）

```mermaid
flowchart TD
    S[当日期权 + BS 先验] --> A[差分进化 DE 全局搜索<br/>popsize 70/120, maxiter 300/500]
    A --> B[L-BFGS-B 局部精修<br/>高精度引擎 1e-7]
    B --> C{RMSE <= 20?}
    C -->|是| D[status=ok<br/>滚动更新初始参数]
    C -->|否| E[BS 先验引导重校准<br/>prior_weight=0.3]
    E --> F{RMSE <= 20?}
    F -->|是| D
    F -->|否| G[aggressive DE 重校准<br/>prior_weight=0.1]
    G --> H{RMSE <= 25?}
    H -->|是| D
    H -->|否| I[status=failed<br/>以 BS 先验作为次日初始参数]
```

### 1.3 定价验证流程图

```mermaid
flowchart LR
    P[processor.get_calibration_data] --> M[市场价 market]
    P --> H1[Heston 半解析 AnalyticHestonEngine]
    P --> H2[Heston MC FullTruncation 1e7 路径]
    P --> B1[BS 公式 + 自身 bs_iv]
    P --> B2[BS 公式 + 平值固定 IV]
    M & H1 & H2 & B1 & B2 --> R[对比表 + MAE 总结]
```

### 1.4 希腊字母分析流程图

```mermaid
flowchart TD
    A[每日校准参数 params_df] --> B[取出当日参数 + 现货价]
    B --> C[构建 HestonGreeksCalculator<br/>FdHestonVanillaEngine]
    C --> D[get_greeks: delta/gamma/theta/rho/vega]
    D --> E[rho: 利率 bump 1%]
    D --> F[vega: v0 bump 1% 换算为 ∂Price/∂σ]
    E & F --> G[希腊字母时序 CSV + 图表]
```

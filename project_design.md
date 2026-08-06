# project_design.md — 设计辅助文档（流程图 / ER 图）

> 依据 `code/AGENTS.md` 要求生成的软件工程设计辅助文档。
> 流程图与 ER 图从 `summary_proj.md` 中独立出来，便于单独维护；项目整体说明见 `summary_proj.md`。

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

## 2. ER 图（数据实体关系）

```mermaid
erDiagram
    交易日 ||--o{ 期权记录 : "包含(1:N)"
    交易日 ||--o{ 校准参数 : "生成(1:1)"
    期权记录 ||--o{ 定价对比 : "验证(1:N)"
    期权记录 ||--o{ 希腊字母记录 : "计算(1:N)"

    交易日 {
        date PK
    }
    期权记录 {
        date FK
        string 合约代码 PK
        float strike
        string cp
        float close
        float volume
        float open_interest
        float delta
        date expiry
        float T
        float bs_iv
    }
    校准参数 {
        date FK
        float v0
        float kappa
        float theta
        float sigma
        float rho
        float rmse
        float mae
        string status
    }
    定价对比 {
        date FK
        float strike
        string type
        float market
        float BlackScholes
        float BS_const
        float Heston_analytic
        float Heston_MC
    }
    希腊字母记录 {
        date FK
        float strike
        float delta
        float gamma
        float theta
        float rho
        float vega
        float spot
    }
```

说明：期权记录（`io_options_processed.csv`）是核心实体；每个交易日由校准流程产出唯一一组 `calibrated_params_daily.csv` 参数；定价对比与希腊字母记录均派生自期权记录与校准参数。

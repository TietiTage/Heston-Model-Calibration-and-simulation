"""pytest 共享夹具：数据路径与 HestonDataProcessor 实例。"""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = PROJECT_ROOT / "code"
DATA_DIR = PROJECT_ROOT / "data"

if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))


def find_dividend_csv() -> Path:
    """定位股息率 CSV（排除期权与利率文件后剩余的那个），避免硬编码中文文件名。"""
    for f in os.listdir(DATA_DIR):
        if f.lower().endswith(".csv") and f not in (
            "io_options_processed.csv",
            "treasury_rates_history.csv",
        ):
            return DATA_DIR / f
    raise FileNotFoundError(f"{DATA_DIR} 下未找到股息率 CSV")


@pytest.fixture(scope="session")
def option_csv() -> Path:
    return DATA_DIR / "io_options_processed.csv"


@pytest.fixture(scope="session")
def dividend_csv() -> Path:
    return find_dividend_csv()


@pytest.fixture(scope="session")
def rate_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "treasury_rates_history.csv", parse_dates=["date"])


@pytest.fixture(scope="session")
def processor(option_csv: Path, dividend_csv: Path, rate_df: pd.DataFrame):
    from data_processor import HestonDataProcessor

    return HestonDataProcessor(str(option_csv), str(dividend_csv), rate_df)


@pytest.fixture(scope="session")
def heston_env(processor):
    """2025-01-02 的定价/希腊字母测试环境：参数、曲线、现货与半解析定价器。"""
    import QuantLib as ql

    from model_calibrator import HestonParameterSet
    from pricing_verification import HestonModelPricer

    eval_date = pd.Timestamp("2025-01-02")
    eval_date_ql = ql.Date(2, 1, 2025)
    ql.Settings.instance().evaluationDate = eval_date_ql
    q = processor.get_dividend_yield(eval_date)
    r_curve = ql.YieldTermStructureHandle(processor._build_rate_curve(eval_date))
    q_curve = ql.YieldTermStructureHandle(
        ql.FlatForward(eval_date_ql, q, ql.Actual365Fixed())
    )
    spot = processor.get_underlying_quote(eval_date)
    params = HestonParameterSet(v0=0.04, kappa=2.0, theta=0.04, sigma=0.3, rho=-0.5)
    pricer = HestonModelPricer(params, spot, r_curve, q_curve)
    return {
        "eval_date": eval_date,
        "eval_date_ql": eval_date_ql,
        "spot": spot,
        "r_curve": r_curve,
        "q_curve": q_curve,
        "params": params,
        "pricer": pricer,
    }

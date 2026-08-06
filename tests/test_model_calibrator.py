"""model_calibrator 模块测试：参数集合、BS 先验、辅助对象构建与误差计算。

说明：完整的 calibrate()（差分进化 + L-BFGS-B）计算量过大，不适合放入单元测试；
此处覆盖其构造、BS 先验、helpers 构建与定价/误差计算等核心路径。
"""

import numpy as np
import pandas as pd
import pytest
import QuantLib as ql

from model_calibrator import HestonModelCalibrator, HestonParameterSet


def _option_df(n: int = 30) -> pd.DataFrame:
    strikes = np.linspace(3500.0, 4100.0, n)
    delta = np.clip(np.linspace(0.9, 0.1, n), 0.1, 0.9)
    bs_iv = 0.2 + 0.00005 * (strikes - 3800.0) ** 2
    return pd.DataFrame(
        {
            "strike": strikes,
            "cp": ["C"] * n,
            "close": np.full(n, 100.0),
            "volume": np.full(n, 1000.0),
            "open_interest": np.full(n, 1000.0),
            "delta": delta,
            "T": np.full(n, 0.2),
            "expiry": pd.Timestamp("2025-06-20"),
            "bs_iv": bs_iv,
        }
    )


def _calibrator_with_engine() -> HestonModelCalibrator:
    eval_date_ql = ql.Date(2, 1, 2025)
    ql.Settings.instance().evaluationDate = eval_date_ql
    r_ts = ql.YieldTermStructureHandle(
        ql.FlatForward(eval_date_ql, 0.016, ql.Actual365Fixed())
    )
    q_ts = ql.YieldTermStructureHandle(
        ql.FlatForward(eval_date_ql, 0.0368, ql.Actual365Fixed())
    )
    process = ql.HestonProcess(
        r_ts,
        q_ts,
        ql.QuoteHandle(ql.SimpleQuote(3820.4)),
        0.04,
        2.0,
        0.04,
        0.3,
        -0.5,
    )
    model = ql.HestonModel(process)
    calibrator = HestonModelCalibrator(eval_date_ql, pd.DataFrame(), 3820.4, r_ts, q_ts)
    calibrator.model = model
    calibrator.engine = ql.AnalyticHestonEngine(model, 1e-7, 10000)
    return calibrator


def test_heston_parameter_set_fields():
    params = HestonParameterSet(v0=0.04, kappa=2.0, theta=0.04, sigma=0.3, rho=-0.5)
    assert params.v0 == 0.04
    assert params.kappa == 2.0
    assert params.theta == 0.04
    assert params.sigma == 0.3
    assert params.rho == -0.5


def test_to_ql_date():
    assert HestonModelCalibrator._to_ql_date("2025-01-02") == ql.Date(2, 1, 2025)
    assert HestonModelCalibrator._to_ql_date(ql.Date(2, 1, 2025)) == ql.Date(2, 1, 2025)


def test_compute_bs_priors():
    df = _option_df()
    calibrator = HestonModelCalibrator("2025-01-02", df, 3820.4, None, None)
    assert calibrator.prior_theta_center is not None
    assert calibrator.prior_v0_center is not None
    # 实现中先对 bs_iv 做 clip(0.05, 1.0) 再取均值
    assert calibrator.prior_theta_center == pytest.approx(
        (df["bs_iv"].clip(0.05, 1.0).mean()) ** 2
    )
    atm_idx = (df["delta"].abs() - 0.5).abs().idxmin()
    assert calibrator.prior_v0_center == pytest.approx(
        max(df.loc[atm_idx, "bs_iv"], 0.05) ** 2
    )
    assert calibrator.prior_skew is not None and np.isfinite(calibrator.prior_skew)
    assert calibrator.prior_convexity is not None and np.isfinite(
        calibrator.prior_convexity
    )


def test_setup_calibration_helpers():
    df = _option_df()
    calibrator = HestonModelCalibrator("2025-01-02", df, 3820.4, None, None)
    calibrator.setup_calibration_helpers()
    assert len(calibrator.helpers) > 0
    assert all("ql_option" in h for h in calibrator.helpers)
    assert all(h["expiry_date"] > calibrator._to_ql_date("2025-01-02") for h in calibrator.helpers)


def test_price_one_option():
    calibrator = _calibrator_with_engine()
    call_price = calibrator._price_one_option("C", 3900.0, ql.Date(20, 6, 2025))
    put_price = calibrator._price_one_option("P", 3900.0, ql.Date(20, 6, 2025))
    assert np.isfinite(call_price) and call_price > 0
    assert np.isfinite(put_price) and put_price > 0


def test_calculate_calibration_error():
    calibrator = _calibrator_with_engine()
    payoff = ql.PlainVanillaPayoff(ql.Option.Call, 3900.0)
    exercise = ql.EuropeanExercise(ql.Date(20, 6, 2025))
    option = ql.VanillaOption(payoff, exercise)
    option.setPricingEngine(calibrator.engine)
    calibrator.helpers = [
        {
            "T": 0.46,
            "strike": 3900.0,
            "cp": "C",
            "market_price": 120.0,
            "expiry_date": ql.Date(20, 6, 2025),
            "ql_option": option,
        }
    ]
    rmse, mae = calibrator.calculate_calibration_error()
    assert np.isfinite(rmse) and rmse >= 0
    assert np.isfinite(mae) and mae >= 0

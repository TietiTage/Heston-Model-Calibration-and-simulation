"""pricing_verification 模块测试：BS 闭式、Heston 半解析与蒙特卡洛一致性。"""

import numpy as np
import pytest
import QuantLib as ql

from pricing_verification import (
    BlackScholesPricer,
    HestonMonteCarloPricer,
    HestonModelPricer,
)


def _ql_bs_price(spot, strike, r, q, T, sigma, is_call):
    """用 QuantLib 独立实现 BS 定价，作为 BlackScholesPricer 的对照。"""
    eval_date = ql.Date(2, 1, 2025)
    with ql.SavedSettings():
        ql.Settings.instance().evaluationDate = eval_date
        dc = ql.Actual365Fixed()
        r_ts = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, r, dc))
        q_ts = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, q, dc))
        spot_h = ql.QuoteHandle(ql.SimpleQuote(spot))
        vol_h = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, ql.NullCalendar(), sigma, dc)
        )
        process = ql.BlackScholesMertonProcess(spot_h, q_ts, r_ts, vol_h)
        payoff = ql.PlainVanillaPayoff(ql.Option.Call if is_call else ql.Option.Put, strike)
        exercise = ql.EuropeanExercise(
            eval_date + ql.Period(int(round(T * 365)), ql.Days)
        )
        option = ql.VanillaOption(payoff, exercise)
        option.setPricingEngine(ql.AnalyticEuropeanEngine(process))
        return float(option.NPV())


@pytest.mark.parametrize(
    ("spot", "strike", "r", "q", "T", "sigma", "opt_type"),
    [
        (3820.4, 3900.0, 0.016, 0.0368, 0.2, 0.25, "C"),
        (3820.4, 3900.0, 0.016, 0.0368, 0.4, 0.2, "P"),
        (100.0, 105.0, 0.05, 0.02, 1.0, 0.25, "C"),
        (100.0, 95.0, 0.03, 0.01, 0.6, 0.15, "P"),
    ],
)
def test_bs_price_matches_quantlib(spot, strike, r, q, T, sigma, opt_type):
    price = BlackScholesPricer.price(spot, strike, r, q, T, sigma, opt_type)
    expected = _ql_bs_price(spot, strike, r, q, T, sigma, opt_type == "C")
    assert price == pytest.approx(expected, rel=1e-9, abs=1e-9)


def test_bs_put_call_parity():
    spot, strike, r, q, T, sigma = 100.0, 105.0, 0.05, 0.02, 1.0, 0.2
    c = BlackScholesPricer.price(spot, strike, r, q, T, sigma, "C")
    p = BlackScholesPricer.price(spot, strike, r, q, T, sigma, "P")
    assert c - p == pytest.approx(
        spot * np.exp(-q * T) - strike * np.exp(-r * T), abs=1e-9
    )


def test_bs_intrinsic_value_when_zero_maturity():
    assert BlackScholesPricer.price(100.0, 105.0, 0.05, 0.02, 0.0, 0.2, "C") == 0.0
    assert BlackScholesPricer.price(100.0, 105.0, 0.05, 0.02, 0.0, 0.2, "P") == 5.0
    assert BlackScholesPricer.price(100.0, 105.0, 0.05, 0.02, 0.5, 0.0, "C") == 0.0


def test_heston_analytic_positive(heston_env):
    pricer = heston_env["pricer"]
    expiry = ql.Date(20, 6, 2025)
    call_price = pricer.price("C", 3900.0, expiry, heston_env["eval_date_ql"])
    put_price = pricer.price("P", 3900.0, expiry, heston_env["eval_date_ql"])
    assert np.isfinite(call_price) and call_price > 0
    assert np.isfinite(put_price) and put_price > 0


def test_heston_mc_close_to_analytic(heston_env):
    env = heston_env
    expiry = ql.Date(17, 1, 2025)
    analytic = env["pricer"].price("C", 3850.0, expiry, env["eval_date_ql"])
    mc = HestonMonteCarloPricer(
        env["params"],
        env["spot"],
        env["r_curve"],
        env["q_curve"],
        eval_date=env["eval_date_ql"],
        expiry_date=expiry,
        n_paths=200_000,
        n_steps=100,
        antithetic=True,
        seed=42,
    )
    mc_price = mc.price(3850.0, "C")
    assert mc_price == pytest.approx(analytic, rel=0.02)

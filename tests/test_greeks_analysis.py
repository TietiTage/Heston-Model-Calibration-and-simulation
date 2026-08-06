"""greeks_analysis 模块测试：希腊字母计算、spot 更新与动态分析。"""

import numpy as np
import pandas as pd
import pytest
import QuantLib as ql

from greeks_analysis import HestonGreeksCalculator, analyze_greeks_dynamics


def _make_calculator(heston_env) -> HestonGreeksCalculator:
    return HestonGreeksCalculator(
        heston_env["params"],
        heston_env["spot"],
        heston_env["r_curve"],
        heston_env["q_curve"],
        heston_env["eval_date"],
    )


def test_greeks_call(heston_env):
    g = _make_calculator(heston_env).get_greeks("C", 3900.0, ql.Date(20, 6, 2025))
    assert set(g) == {"delta", "gamma", "theta", "rho", "vega"}
    assert 0.0 <= g["delta"] <= 1.0
    assert g["gamma"] > 0
    assert g["vega"] > 0
    assert all(np.isfinite(v) for v in g.values())


def test_greeks_put(heston_env):
    g = _make_calculator(heston_env).get_greeks("P", 3900.0, ql.Date(20, 6, 2025))
    assert -1.0 <= g["delta"] <= 0.0
    assert g["gamma"] > 0
    assert np.isfinite(g["vega"])


def test_update_spot_changes_greeks(heston_env):
    calculator = _make_calculator(heston_env)
    expiry = ql.Date(20, 6, 2025)
    d0 = calculator.get_greeks("C", 3900.0, expiry)["delta"]
    calculator.update_spot(heston_env["spot"] + 50.0)
    d1 = calculator.get_greeks("C", 3900.0, expiry)["delta"]
    assert d1 > d0


def test_analyze_greeks_dynamics(processor, heston_env):
    params_df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2025-01-02"),
                "v0": 0.04,
                "kappa": 2.0,
                "theta": 0.04,
                "sigma": 0.3,
                "rho": -0.5,
            }
        ]
    )
    spec = {"strike": 3900, "type": "C", "expiry": pd.Timestamp("2025-06-20")}
    out = analyze_greeks_dynamics(
        processor, params_df, spec, [pd.Timestamp("2025-01-02")]
    )
    assert len(out) == 1
    assert {"delta", "gamma", "theta", "rho", "vega", "date", "spot"} <= set(out.columns)

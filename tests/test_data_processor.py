"""data_processor 模块测试：清洗、现货/股息率/利率、BS 隐含波动率与统一过滤。"""

import numpy as np
import pandas as pd
import pytest

from data_processor import HestonDataProcessor, filter_calibration_options


@pytest.fixture(scope="module")
def cleaned(processor):
    return processor.load_and_clean_data()


@pytest.fixture(scope="module")
def iv_data(processor):
    return processor.calculate_implied_volatility("2025-01-02")


def test_load_and_clean_data(cleaned):
    assert not cleaned.empty
    assert {"date", "expiry", "strike", "cp", "close", "T"} <= set(cleaned.columns)
    assert (cleaned["T"] > 0.02).all()
    assert cleaned["close"].gt(0).all()


def test_get_underlying_quote(processor):
    spot = processor.get_underlying_quote("2025-01-02")
    assert isinstance(spot, float)
    assert spot == pytest.approx(3820.4, abs=1e-6)


def test_get_dividend_yield(processor):
    q = processor.get_dividend_yield("2025-01-02")
    assert np.isfinite(q)
    assert 0.0 < q < 0.1


def test_get_risk_free_rate_real(processor):
    rate = processor.get_risk_free_rate(0.25, "2025-01-02")
    expected = processor._get_daily_rate_dict("2025-01-02")[0.25]
    assert rate == pytest.approx(expected)


def test_get_risk_free_rate_interpolation(option_csv, dividend_csv):
    rate_df = pd.DataFrame(
        {"date": [pd.Timestamp("2025-01-02")], 0.25: [0.010], 0.5: [0.020], 1.0: [0.030]}
    )
    proc = HestonDataProcessor(str(option_csv), str(dividend_csv), rate_df)
    assert proc.get_risk_free_rate(0.375, "2025-01-02") == pytest.approx(0.015)
    assert proc.get_risk_free_rate(0.25, "2025-01-02") == pytest.approx(0.010)
    assert proc.get_risk_free_rate(0.1, "2025-01-02") == pytest.approx(0.010)
    # 超过最长期限时在最后一段做线性插值（0.5~1.0 段）
    assert proc.get_risk_free_rate(0.9, "2025-01-02") == pytest.approx(0.028)
    assert proc.get_risk_free_rate(1.0, "2025-01-02") == pytest.approx(0.030)


def test_calculate_implied_volatility(iv_data):
    assert not iv_data.empty
    assert "bs_iv" in iv_data.columns
    assert iv_data["bs_iv"].notna().all()
    assert iv_data["bs_iv"].between(0.01, 5.0).all()


def test_get_calibration_data_matches_filter(processor):
    calib = processor.get_calibration_data("2025-01-02")
    assert not calib.empty
    assert (calib["T"] >= 0.02).all()
    assert calib["delta"].abs().between(0.1, 0.9).all()
    assert calib["close"].gt(0).all()


def test_filter_calibration_options(cleaned):
    filtered = filter_calibration_options(cleaned)
    assert not filtered.empty
    assert (filtered["T"] >= 0.02).all()
    assert filtered["delta"].abs().between(0.1, 0.9).all()
    assert filtered["close"].gt(0).all()
    assert len(filtered) <= len(cleaned)

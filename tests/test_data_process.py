"""data_process 模块测试：合约解析、到期日计算与处理结果的格式一致性。"""

from datetime import datetime

import pandas as pd
import pytest

from data_process import parse_contract, third_friday_of_month


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("IO2501-C-3450", (2025, 1, "C", 3450)),
        ("IO2501-P-3600", (2025, 1, "P", 3600)),
        ("IO2506-C-3900", (2025, 6, "C", 3900)),
        ("IO2512-P-4200", (2025, 12, "P", 4200)),
    ],
)
def test_parse_contract_valid(code: str, expected: tuple):
    assert parse_contract(code) == expected


@pytest.mark.parametrize("code", ["", "abc", "HO2501-C-3450", "IO2501-3450"])
def test_parse_contract_invalid(code: str):
    assert parse_contract(code) is None


def test_third_friday_of_month():
    assert third_friday_of_month(2025, 1) == datetime(2025, 1, 17)
    assert third_friday_of_month(2025, 6) == datetime(2025, 6, 20)
    assert third_friday_of_month(2025, 12) == datetime(2025, 12, 19)


def test_processed_options_consistency(option_csv):
    """基于 data/ 真实数据：合约代码全部可解析，T 与到期日/评估日一致。"""
    df = pd.read_csv(option_csv, encoding="gbk", parse_dates=["date", "expiry"])
    parsed = df[df.columns[1]].apply(parse_contract)
    assert parsed.notna().all()
    assert parsed.apply(lambda x: len(x) == 4).all()
    computed_T = (df["expiry"] - df["date"]).dt.days / 365.0
    assert (computed_T - df["T"]).abs().max() < 1e-9
    assert df["T"].between(0.0, 2.0).all()

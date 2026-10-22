from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from risk_engine.engine.returns import (NY, PriceDataError, drop_incomplete_last_day,
                                        load_prices, log_returns, simple_returns)

DATES = pd.to_datetime(["2026-10-19", "2026-10-20", "2026-10-21"])
PRICES = pd.DataFrame({"A": [100.0, 110.0, 99.0]}, index=DATES)


def test_simple_returns():
    r = simple_returns(PRICES)
    assert len(r) == 2
    assert r["A"].tolist() == pytest.approx([0.10, -0.10])


def test_log_returns_and_time_additivity():
    r = log_returns(PRICES)
    assert r["A"].tolist() == pytest.approx([0.0953102, -0.1053605], abs=1e-7)
    assert r["A"].sum() == pytest.approx(np.log(99 / 100))   # logs add over time


def test_simple_returns_add_across_assets():
    prices = pd.DataFrame({"A": [100.0, 110.0], "B": [50.0, 45.0]}, index=DATES[:2])
    r = simple_returns(prices).iloc[0]
    pnl = 1_000_000 * r["A"] + 2_000_000 * r["B"]              # +100k and -200k
    assert pnl == pytest.approx(-100_000)


def test_drop_today_before_close():
    before = datetime(2026, 10, 21, 15, 0, tzinfo=NY)
    after = datetime(2026, 10, 21, 17, 0, tzinfo=NY)
    assert len(drop_incomplete_last_day(PRICES, now=before)) == 2
    assert len(drop_incomplete_last_day(PRICES, now=after)) == 3


def write(tmp_path, ticker, dates, closes):
    df = pd.DataFrame({"close": closes}, index=pd.to_datetime(dates))
    df.index.name = "date"
    df.to_parquet(tmp_path / f"{ticker}.parquet")


def test_load_aligns_to_common_dates(tmp_path):
    write(tmp_path, "A", ["2026-10-19", "2026-10-20", "2026-10-21"], [1.0, 2.0, 3.0])
    write(tmp_path, "B", ["2026-10-20", "2026-10-21"], [5.0, 6.0])         # starts a day later
    p = load_prices(("A", "B"), raw_dir=tmp_path)
    assert list(p.index) == list(pd.to_datetime(["2026-10-20", "2026-10-21"]))


def test_load_rejects_non_positive_prices(tmp_path):
    write(tmp_path, "A", ["2026-10-20", "2026-10-21"], [1.0, 0.0])
    with pytest.raises(PriceDataError):
        load_prices(("A",), raw_dir=tmp_path)
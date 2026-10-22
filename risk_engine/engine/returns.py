"""Turn raw per-ticker prices into one aligned price matrix and daily returns.

Simple returns drive P&L (they add across assets: P&L = notional x return).
Log returns add across time, so they're used for multi-day horizons.
"""
from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from risk_engine.paths import RAW_PRICES_DIR
from risk_engine.universe import TICKERS

NY = ZoneInfo("America/New_York")
BAR_FINAL_AFTER = time(16, 30)       # US close is 16:00 ET; small buffer before trusting the daily bar


class PriceDataError(ValueError):
    """Price data is unusable (gaps, non-positive prices). A data bug: never retried."""


def load_prices(tickers: tuple[str, ...] = TICKERS, raw_dir: Path = RAW_PRICES_DIR) -> pd.DataFrame:
    """Dates x tickers matrix of adjusted closes, aligned to the dates every ticker has."""
    series = {t: pd.read_parquet(raw_dir / f"{t}.parquet")["close"] for t in tickers}
    prices = pd.concat(series, axis=1, join="inner")      # inner join: start = latest first date
    prices = prices.sort_index()

    if prices.empty:
        raise PriceDataError("no dates common to all tickers")
    if not prices.index.is_unique:
        raise PriceDataError("duplicate dates in price data")
    if (prices <= 0).any().any():
        raise PriceDataError("non-positive prices found")
    return prices


def drop_incomplete_last_day(prices: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Drop today's row if the market hasn't closed yet: an intraday price is not a daily close."""
    now = now or datetime.now(NY)
    last = prices.index[-1].date()
    if last == now.date() and now.time() < BAR_FINAL_AFTER:
        return prices.iloc[:-1]
    return prices


def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """r_t = P_t / P_{t-1} - 1. Use for P&L."""
    return prices.pct_change().iloc[1:]


def log_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """r_t = ln(P_t / P_{t-1}). Use for adding returns over time."""
    return np.log(prices / prices.shift(1)).iloc[1:]


if __name__ == "__main__":
    prices = drop_incomplete_last_day(load_prices())
    r = simple_returns(prices)
    print(f"{len(prices)} price dates, {len(r)} return days: "
          f"{r.index[0].date()} to {r.index[-1].date()}\n")
    print("annualised vol:\n", (r.std() * np.sqrt(252)).round(3).to_string())
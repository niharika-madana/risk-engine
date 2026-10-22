"""Download daily adjusted close prices for the 8 asset-class ETFs.

Two drivers, a plain loop and a thread pool(to show )
Run from the repo root:  python -m risk_engine.data.download
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import yfinance as yf

try:
    from yfinance.exceptions import YFRateLimitError
except ImportError:                      # older yfinance: the error doesn't exist, so define a placeholder that never fires
    class YFRateLimitError(Exception):
        pass

from risk_engine.utils import retry, timed
from risk_engine.universe import TICKERS

START = "2007-01-01"
REPO_ROOT = Path(__file__).resolve().parents[2]   # download.py -> data -> risk_engine -> repo root
RAW_DIR = REPO_ROOT / "data" / "raw" / "prices"


class EmptyDownloadError(Exception):
    """yfinance returned zero rows (it often does this instead of raising on network trouble)."""


@retry(times=3, delay=2.0,
       exceptions=(EmptyDownloadError, YFRateLimitError, ConnectionError, TimeoutError))
def fetch_prices(ticker: str, start: str = START) -> pd.DataFrame:
    """Download one ticker and return a clean frame: date index (tz-naive), one float column 'close'."""
    raw = yf.Ticker(ticker).history(start=start, auto_adjust=True, actions=False)
    if raw.empty:
        raise EmptyDownloadError(f"no rows returned for {ticker}")

    # Boundary conversion: fix types and the index here, once. Downstream code trusts them.
    idx = raw.index
    if idx.tz is not None:
        idx = idx.tz_localize(None)          # drop the timezone, keep the local trading date
    df = pd.DataFrame({"close": raw["Close"].astype("float64").to_numpy()},
                      index=idx.normalize())
    df.index.name = "date"
    return df


def save_prices(df: pd.DataFrame, ticker: str, out_dir: Path = RAW_DIR) -> Path:
    """Write one ticker's prices to data/raw/prices/<TICKER>.parquet."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{ticker}.parquet"
    df.to_parquet(path)
    return path


def download_one(ticker: str, out_dir: Path = RAW_DIR) -> Path:
    """Fetch one ticker and save it; returns the file path."""
    return save_prices(fetch_prices(ticker), ticker, out_dir)


@timed
def download_sequential(tickers: list[str], out_dir: Path = RAW_DIR) -> dict[str, Path]:
    """Plain loop: one download at a time. Stops at the first failure."""
    return {t: download_one(t, out_dir) for t in tickers}


@timed
def download_threaded(tickers: list[str], out_dir: Path = RAW_DIR,
                      max_workers: int = 8) -> dict[str, Path]:
    """Thread pool: all downloads wait on the network at once. Collects every failure, then raises once."""
    results: dict[str, Path] = {}
    failures: dict[str, Exception] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(download_one, t, out_dir): t for t in tickers}
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                results[ticker] = fut.result()
            except Exception as exc:         # collect, then fail loudly below
                failures[ticker] = exc
    if failures:
        raise RuntimeError(f"{len(failures)} ticker(s) failed: {failures}")
    return results


if __name__ == "__main__":
    download_sequential(TICKERS)
    download_threaded(TICKERS)
    
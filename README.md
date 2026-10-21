# risk-engine

A small version of the market-risk platform a multi-manager hedge fund runs: a multi-asset portfolio split into pods (trading teams) goes in, and Value-at-Risk, Expected Shortfall, stress losses and VaR backtests come out, per pod and for the firm, through a REST API.

> **Status: in progress.** The data layer is done. The VaR engine is being built now. 

## Core design idea

VaR is not additive: Pod A VaR + Pod B VaR ≠ firm VaR, because diversification depends on how the pods move together in each scenario. So the engine stores a **scenario P&L vector for each position**, not just a VaR number. To get firm VaR, it sums those vectors scenario by scenario up the hierarchy (position → pod → firm), then takes the quantile. Everything else (VaR, ES, component VaR, stress, backtests) is derived from this P&L matrix.

## Universe

Eight ETFs, each standing in for one asset class, with daily history from 2007:

| Asset class | ETFs |
|---|---|
| Equities | SPY, EFA, EEM |
| Rates | TLT |
| Credit | LQD, HYG |
| Commodities / FX | GLD, UUP |

HYG starts in April 2007 and UUP in March 2007, so the history all eight share begins on **2007-04-11**.

## What's built

| Module | What it does |
|---|---|
| `risk_engine/utils.py` | `@timed`, `Timer` context manager, `@retry(times, delay, exceptions)` |
| `risk_engine/data/stream.py` | Generator that streams a trades CSV row by row, filtering first and converting types at the boundary |
| `risk_engine/data/download.py` | Downloads adjusted closes for the 8 ETFs to Parquet, with a sequential loop and a thread pool. Retries on empty or rate-limited responses (yfinance often returns an empty frame instead of raising) |

### Result: threaded vs. sequential download

Mean of 3 alternating runs after a warm-up call, 8 tickers:

| Sequential | Threaded | Speedup |
|---|---|---|
| 2.83s | 2.14s | **1.3×** |

That's far below the ideal of about 8×. Sequential takes about 0.35s per ticker, so truly parallel requests should finish in well under a second. Most of each request appears to be serialized inside yfinance, which leaves the threads little network wait to overlap. The thread-pool design still matters as the number of tickers grows; for 8 it saves little.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Utilities, streaming, threaded download, sample portfolio + loader, first tests | mostly done |
| 2 | Returns → historical / parametric / Monte Carlo VaR and ES, pod vs. firm aggregation, component VaR, historical and hypothetical stress tests, backtesting (Kupiec, Christoffersen) | in progress |
| 3 | Postgres schema with window-function SQL, pandas vs. polars pipeline benchmark | planned |
| 4 | FastAPI service, pytest in GitHub Actions, Docker Compose (API + Postgres) | planned |

## Run it

```bash
conda activate risk-engine            # Python 3.12
pip install -r requirements.txt
python -m risk_engine.data.download   # writes data/raw/prices/*.parquet
python -m pytest -q
```

Run modules from the repo root with `python -m`, so the `risk_engine` package imports.

## Simplifications (deliberate)

- Positions are stored as dollar notional, not quantity × price. For linear ETFs, the daily P&L is just notional × return.
- Prices come from yfinance...it'd be better to use data from a licensed vendor instead

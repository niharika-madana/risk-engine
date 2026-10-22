"""Load the sample portfolio from JSON into immutable, validated objects."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from risk_engine.universe import TICKERS

REPO_ROOT = Path(__file__).resolve().parents[2]
POSITIONS_PATH = REPO_ROOT / "data" / "positions.json"


@dataclass(frozen=True)
class Position:
    """Dollar notional (market value) of `ticker` held by `pod`. Negative = short."""
    pod: str
    ticker: str
    notional: float


@dataclass(frozen=True)
class Pod:
    """A trading team and the capital the firm has allocated to it."""
    name: str
    capital: float
    description: str = ""


@dataclass(frozen=True)
class Portfolio:
    """Everything the engine needs about holdings, as of one date."""
    as_of: date
    pods: tuple[Pod, ...]
    positions: tuple[Position, ...]


class PositionsError(ValueError):
    """The positions file is malformed. A data bug: never retried, always raised."""


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)   # True is an int in Python


def load_portfolio(path: Path = POSITIONS_PATH) -> Portfolio:
    """Read the positions file; validate at the boundary so downstream code can trust it."""
    with open(path) as f:
        raw = json.load(f)

    pods, positions = [], []
    for name, data in raw["pods"].items():
        capital = data.get("capital")
        if not _is_number(capital) or capital <= 0:
            raise PositionsError(f"{name}: capital must be a positive number, got {capital!r}")
        pods.append(Pod(name=name, capital=float(capital), description=data.get("description", "")))

        for ticker, notional in data["positions"].items():
            if ticker not in TICKERS:
                raise PositionsError(f"{name}: unknown ticker {ticker!r}")
            if not _is_number(notional):
                raise PositionsError(f"{name}/{ticker}: notional must be a number, got {notional!r}")
            if notional == 0:
                raise PositionsError(f"{name}/{ticker}: zero notional; remove the line instead")
            positions.append(Position(pod=name, ticker=ticker, notional=float(notional)))

    if not positions:
        raise PositionsError("no positions in file")
    return Portfolio(as_of=date.fromisoformat(raw["as_of"]),
                     pods=tuple(pods), positions=tuple(positions))


def exposure_matrix(portfolio: Portfolio) -> pd.DataFrame:
    """Pods x tickers matrix of dollar notional, 0 where a pod has no position. Universe column order."""
    df = pd.DataFrame([(p.pod, p.ticker, p.notional) for p in portfolio.positions],
                      columns=["pod", "ticker", "notional"])
    matrix = df.pivot_table(index="pod", columns="ticker", values="notional",
                            aggfunc="sum", fill_value=0.0)
    pod_order = [p.name for p in portfolio.pods]
    return matrix.reindex(index=pod_order, columns=list(TICKERS), fill_value=0.0)


def pod_capital(portfolio: Portfolio) -> pd.Series:
    """Allocated capital per pod, same order as exposure_matrix rows."""
    return pd.Series({p.name: p.capital for p in portfolio.pods}, name="capital")


if __name__ == "__main__":
    pf = load_portfolio()
    m = exposure_matrix(pf)
    cap = pod_capital(pf)
    print(f"as of {pf.as_of}\n")
    print(m.map(lambda x: f"{x / 1e6:,.0f}M"))
    summary = pd.DataFrame({"capital": cap, "net": m.sum(axis=1), "gross": m.abs().sum(axis=1)})
    summary["leverage"] = summary["gross"] / summary["capital"]
    summary.loc["FIRM"] = summary.sum()
    summary.loc["FIRM", "leverage"] = summary.loc["FIRM", "gross"] / summary.loc["FIRM", "capital"]
    print("\n", summary.round(2))
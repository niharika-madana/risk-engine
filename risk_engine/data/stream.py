"""Stream large trade files one row at a time, so memory stays flat whatever the file size."""

import csv
from datetime import datetime, timezone


def trades_for_ticker(path, ticker):
    """Yield trades for `ticker` from a CSV, one row at a time, with typed fields."""
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["ticker"] != ticker:
                continue  # skip non-matching rows before doing any work
            row["timestamp"] = datetime.fromtimestamp(int(row["timestamp"]), timezone.utc)
            row["qty"] = int(row["qty"])
            row["price"] = float(row["price"])
            yield row


if __name__ == "__main__":
    path = "data/raw/sample_trades.csv"

    gen = trades_for_ticker(path, "AAPL")
    print(type(gen))

    for trade in gen:
        print(trade)

    net_notional = sum(t["qty"] * t["price"] for t in trades_for_ticker(path, "AAPL"))
    print(f"net AAPL notional: {net_notional:,.2f}")
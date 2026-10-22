import json

import pytest

from risk_engine.data.positions import (PositionsError, exposure_matrix, load_portfolio,
                                        pod_capital)


def write(tmp_path, pods):
    path = tmp_path / "positions.json"
    path.write_text(json.dumps({"as_of": "2026-10-21", "currency": "USD", "pods": pods}))
    return path


def test_sample_file_totals():
    pf = load_portfolio()
    m = exposure_matrix(pf)
    assert m.to_numpy().sum() == 110_000_000           # firm net, hand-computed
    assert abs(m).to_numpy().sum() == 180_000_000      # firm gross
    assert m["TLT"].sum() == 20_000_000                # rates +30M, credit -10M
    assert pod_capital(pf).sum() == 75_000_000


def test_credit_leverage():
    pf = load_portfolio()
    gross = exposure_matrix(pf).abs().sum(axis=1)
    assert gross["credit"] / pod_capital(pf)["credit"] == pytest.approx(2.75)


def test_objects_are_immutable():
    pf = load_portfolio()
    with pytest.raises(AttributeError):                # FrozenInstanceError subclasses it
        pf.positions[0].notional = 0.0


def test_matrix_keeps_file_order_and_fills_zero(tmp_path):
    path = write(tmp_path, {"zeta": {"capital": 1, "positions": {"SPY": 100}},
                            "alpha": {"capital": 1, "positions": {"TLT": -50}}})
    m = exposure_matrix(load_portfolio(path))
    assert list(m.index) == ["zeta", "alpha"]          # not sorted alphabetically
    assert m.loc["zeta", "TLT"] == 0.0
    assert list(m.columns) == ["SPY", "EFA", "EEM", "TLT", "LQD", "HYG", "GLD", "UUP"]


@pytest.mark.parametrize("bad_positions", [{"XYZ": 100}, {"SPY": "100"}, {"SPY": True}, {"SPY": 0}])
def test_bad_positions_raise(tmp_path, bad_positions):
    with pytest.raises(PositionsError):
        load_portfolio(write(tmp_path, {"a": {"capital": 1, "positions": bad_positions}}))


@pytest.mark.parametrize("bad_capital", [None, 0, -5, "10"])
def test_bad_capital_raises(tmp_path, bad_capital):
    pod = {"positions": {"SPY": 100}} if bad_capital is None else {"capital": bad_capital, "positions": {"SPY": 100}}
    with pytest.raises(PositionsError):
        load_portfolio(write(tmp_path, {"a": pod}))
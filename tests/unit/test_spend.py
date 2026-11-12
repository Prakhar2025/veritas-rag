"""Unit tests for the spend meter ledger and cap."""

from __future__ import annotations

import pytest

from app.core.spend import SpendCapExceeded, SpendMeter


def test_record_accumulates_nova_micro_pricing(tmp_path) -> None:
    meter = SpendMeter(tmp_path / "spend.json", cap_usd=1.0)
    meter.record("contextualize", "amazon.nova-micro-v1:0", 1000, 100)
    # 1000 * 0.000000035 + 100 * 0.00000014 = 0.000049 USD
    assert meter.total_usd == pytest.approx(0.000049, rel=1e-6)


def test_ledger_persists_across_instances(tmp_path) -> None:
    path = tmp_path / "spend.json"
    first = SpendMeter(path, cap_usd=1.0)
    first.record("contextualize", "amazon.nova-micro-v1:0", 1000, 100)
    second = SpendMeter(path, cap_usd=1.0)
    assert second.total_usd == pytest.approx(first.total_usd)


def test_cap_raises_before_call(tmp_path) -> None:
    meter = SpendMeter(tmp_path / "spend.json", cap_usd=0.001)
    meter.record("contextualize", "amazon.nova-micro-v1:0", 20000, 0)
    with pytest.raises(SpendCapExceeded):
        meter.check_headroom(0.01)


def test_unknown_model_prices_zero_and_is_reported(tmp_path) -> None:
    meter = SpendMeter(tmp_path / "spend.json", cap_usd=1.0)
    meter.record("contextualize", "unknown.model", 100, 100)
    assert meter.total_usd == 0.0
    assert "contextualize" in meter.summary()

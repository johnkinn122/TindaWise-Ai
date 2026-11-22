import pandas as pd
import pytest

from tindawise_ml.__main__ import main
from tindawise_ml.synthetic import generate_history


def test_backtest_prints_labelled_daily_and_weekly_tables(capsys):
    assert main(["backtest", "--days", "120", "--test-days", "14"]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC SAMPLE DATA" in out
    assert "Daily, per product" in out
    assert "7-day totals, per product" in out
    for model in ("naive", "seasonal_naive_7", "moving_average_28", "lightgbm", "oracle"):
        assert out.count(f"| {model}") == 2, model  # once per table


def test_backtest_can_skip_lightgbm(capsys):
    assert main(["backtest", "--days", "120", "--test-days", "14", "--baselines-only"]) == 0
    out = capsys.readouterr().out
    assert "| lightgbm" not in out
    assert "| moving_average_28" in out


def test_generate_writes_a_csv(tmp_path, capsys):
    target = tmp_path / "history.csv"
    assert main(["generate", "--days", "30", "--out", str(target)]) == 0
    written = pd.read_csv(target)
    assert len(written) == 30 * written["sku"].nunique()
    assert list(written.columns) == [
        "date", "sku", "units_sold", "stockout", "demand", "received", "closing_stock",
    ]  # fmt: skip


def test_generate_can_end_on_a_given_day(tmp_path, capsys):
    target = tmp_path / "history.csv"
    assert main(["generate", "--days", "30", "--end", "2026-11-21", "--out", str(target)]) == 0
    written = pd.read_csv(target)
    assert written["date"].min() == "2026-10-23"
    assert written["date"].max() == "2026-11-21"


def test_start_and_end_together_are_refused(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["generate", "--start", "2025-01-01", "--end", "2025-02-01", "--out", "x.csv"])


def test_backtest_on_an_exported_csv_has_no_synthetic_extras(tmp_path, capsys):
    target = tmp_path / "export.csv"
    exported = generate_history(days=120)[["date", "sku", "units_sold", "stockout"]]
    exported.assign(date=exported["date"].dt.strftime("%Y-%m-%d")).to_csv(target, index=False)
    assert main(["backtest", "--csv", str(target), "--test-days", "14"]) == 0
    out = capsys.readouterr().out
    assert f"Data: {target}" in out
    assert "SYNTHETIC" not in out
    assert "oracle" not in out
    assert out.count("| lightgbm") == 2

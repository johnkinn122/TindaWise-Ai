import pandas as pd

from tindawise_ml.__main__ import main


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
    assert list(written.columns) == ["date", "sku", "units_sold", "stockout", "demand"]

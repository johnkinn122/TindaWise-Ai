import pandas as pd
import pytest

from tindawise_ml.data import DemandFrameError, load_demand_csv, to_wide, validate_demand_frame


def frame(**overrides) -> pd.DataFrame:
    base = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-01", "2025-01-02"] * 2),
            "sku": ["A", "A", "B", "B"],
            "units_sold": pd.array([1, 0, 3, 2], dtype="int64"),
            "stockout": [False, True, False, False],
        }
    )
    for column, value in overrides.items():
        base[column] = value
    return base


def test_a_valid_table_passes():
    validate_demand_frame(frame())


@pytest.mark.parametrize(
    ("table", "message"),
    [
        (frame().drop(columns="stockout"), "missing columns"),
        (frame().iloc[0:0], "no rows"),
        (frame(date=["2025-01-01", "2025-01-02"] * 2), "datetime"),
        (frame(date=pd.to_datetime(["2025-01-01 10:00", "2025-01-02 00:00"] * 2)), "whole days"),
        (frame(units_sold=[1.5, 0, 3, 2]), "whole units"),
        (frame(units_sold=pd.array([1, -1, 3, 2], dtype="int64")), "negative"),
        (frame(stockout=[0, 1, 0, 0]), "True/False"),
        (pd.concat([frame(), frame().iloc[[0]]]), "more than one row"),
        (frame().drop(index=1), "missing days"),
    ],
)
def test_contract_violations_are_named(table, message):
    with pytest.raises(DemandFrameError, match=message):
        validate_demand_frame(table)


def test_csv_round_trip(tmp_path):
    path = tmp_path / "demand.csv"
    original = frame().assign(extra=["x", "y", "z", "w"])
    original.to_csv(path, index=False)
    loaded = load_demand_csv(path)
    assert loaded["date"].tolist() == sorted(original["date"].tolist())
    assert loaded["stockout"].dtype == bool
    assert loaded["units_sold"].dtype == "int64"
    assert "extra" in loaded.columns
    assert loaded.set_index(["sku", "date"])["units_sold"].to_dict() == (
        original.set_index(["sku", "date"])["units_sold"].to_dict()
    )


def test_csv_reads_lowercase_booleans_and_skus_that_look_like_numbers(tmp_path):
    path = tmp_path / "demand.csv"
    path.write_text("date,sku,units_sold,stockout\n2025-01-01,007,1,false\n2025-01-02,007,0,true\n")
    loaded = load_demand_csv(path)
    assert loaded["sku"].tolist() == ["007", "007"]
    assert loaded["stockout"].tolist() == [False, True]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("date,sku,units_sold\n2025-01-01,A,1\n", "missing columns"),
        ("date,sku,units_sold,stockout\n01/02/2025,A,1,False\n", "YYYY-MM-DD"),
        ("date,sku,units_sold,stockout\n2025-01-01,A,1,maybe\n", "True/False"),
        ("date,sku,units_sold,stockout\n2025-01-01,A,1.5,False\n", "whole units"),
        ("date,sku,units_sold,stockout\n2025-01-01,A,,False\n", "whole units"),
        (
            "date,sku,units_sold,stockout\n2025-01-01,A,1,False\n2025-01-03,A,1,False\n",
            "missing days",
        ),
    ],
)
def test_csv_contract_violations_are_named(tmp_path, body, message):
    path = tmp_path / "demand.csv"
    path.write_text(body)
    with pytest.raises(DemandFrameError, match=message):
        load_demand_csv(path)


def test_to_wide_is_dates_by_skus():
    wide = to_wide(frame(), "units_sold")
    assert wide.columns.tolist() == ["A", "B"]
    assert wide.loc["2025-01-02"].tolist() == [0, 2]

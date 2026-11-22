import pandas as pd
import pytest

from tindawise_ml.data import DemandFrameError, to_wide, validate_demand_frame


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


def test_to_wide_is_dates_by_skus():
    wide = to_wide(frame(), "units_sold")
    assert wide.columns.tolist() == ["A", "B"]
    assert wide.loc["2025-01-02"].tolist() == [0, 2]

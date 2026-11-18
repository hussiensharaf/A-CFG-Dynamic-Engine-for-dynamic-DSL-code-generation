"""
Unit tests for app/etl/core.py: extract/load (via the CSV data source) and
join (all how= variants, tolerance=, and the error/edge cases: invalid
`how`, missing columns, empty DataFrames).

These are one layer below the compiler: no query string is parsed here,
just the ETL functions called directly with small DataFrames.

Run with:  pytest tests/test_etl_core.py
"""

import csv

import pandas as pd
import pytest

from app.etl.core import extract, join, load


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# extract / load
# ---------------------------------------------------------------------------

def test_extract_csv_returns_dataframe_with_expected_shape(tmp_path):
    path = str(tmp_path / "source.csv")
    _write_csv(path, ["name", "age"], [["Alice", 30], ["Bob", 25]])
    df = extract("csv", path)
    assert list(df.columns) == ["name", "age"]
    assert len(df) == 2


def test_load_csv_writes_data_without_index_column(tmp_path):
    path = str(tmp_path / "target.csv")
    df = pd.DataFrame({"name": ["Alice"], "age": [30]})
    load(df, "csv", path)
    written = pd.read_csv(path)
    assert list(written.columns) == ["name", "age"]  # no "Unnamed: 0" index column
    assert written.iloc[0]["name"] == "Alice"


def test_load_invalid_source_type_raises():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(Exception):
        load(df, "not_a_real_type", "/tmp/whatever.nope")


# ---------------------------------------------------------------------------
# join: basic how= variants (exact, no tolerance)
# ---------------------------------------------------------------------------

def _left_df():
    return pd.DataFrame({"name": ["Alice", "Bob", "Cara"], "age": [30, 25, 40]})


def _right_df():
    return pd.DataFrame({"name": ["Alice", "Bob", "Dan"], "score": [90, 80, 70]})


def test_join_inner_keeps_only_matching_rows():
    result = join(_left_df(), _right_df(), "name", "name", how="inner")
    assert sorted(result["name"].tolist()) == ["Alice", "Bob"]


def test_join_left_keeps_all_left_rows():
    result = join(_left_df(), _right_df(), "name", "name", how="left")
    assert sorted(result["name"].tolist()) == ["Alice", "Bob", "Cara"]
    assert result.loc[result["name"] == "Cara", "score"].isna().all()


def test_join_right_keeps_all_right_rows():
    result = join(_left_df(), _right_df(), "name", "name", how="right")
    assert sorted(result["name"].tolist()) == ["Alice", "Bob", "Dan"]
    assert result.loc[result["name"] == "Dan", "age"].isna().all()


def test_join_outer_keeps_all_rows_from_both_sides():
    result = join(_left_df(), _right_df(), "name", "name", how="outer")
    assert sorted(result["name"].tolist()) == ["Alice", "Bob", "Cara", "Dan"]


def test_join_applies_custom_suffixes_on_column_collision():
    left = pd.DataFrame({"key": [1, 2], "value": ["a", "b"]})
    right = pd.DataFrame({"key": [1, 2], "value": ["x", "y"]})
    result = join(left, right, "key", "key", how="inner", left_suffix="_L", right_suffix="_R")
    assert "value_L" in result.columns
    assert "value_R" in result.columns


# ---------------------------------------------------------------------------
# join: error / edge cases
# ---------------------------------------------------------------------------

def test_join_invalid_how_raises_value_error():
    with pytest.raises(ValueError, match="Invalid join type"):
        join(_left_df(), _right_df(), "name", "name", how="sideways")


def test_join_missing_left_column_raises_key_error():
    with pytest.raises(KeyError):
        join(_left_df(), _right_df(), "not_a_column", "name", how="inner")


def test_join_missing_right_column_raises_key_error():
    with pytest.raises(KeyError):
        join(_left_df(), _right_df(), "name", "not_a_column", how="inner")


def test_join_none_dataframe_raises_value_error():
    with pytest.raises(ValueError):
        join(None, _right_df(), "name", "name", how="inner")


def test_join_both_empty_returns_empty_dataframe():
    result = join(pd.DataFrame(), pd.DataFrame(), "name", "name", how="inner")
    assert result.empty


@pytest.mark.parametrize("how", ["inner", "left"])
def test_join_empty_left_with_inner_or_left_returns_empty(how):
    empty_left = pd.DataFrame({"name": [], "age": []})
    result = join(empty_left, _right_df(), "name", "name", how=how)
    assert result.empty


@pytest.mark.parametrize("how", ["right", "outer"])
def test_join_empty_left_with_right_or_outer_returns_right_unchanged(how):
    empty_left = pd.DataFrame({"name": [], "age": []})
    result = join(empty_left, _right_df(), "name", "name", how=how)
    assert sorted(result["name"].tolist()) == sorted(_right_df()["name"].tolist())


@pytest.mark.parametrize("how", ["inner", "right"])
def test_join_empty_right_with_inner_or_right_returns_empty(how):
    empty_right = pd.DataFrame({"name": [], "score": []})
    result = join(_left_df(), empty_right, "name", "name", how=how)
    assert result.empty


@pytest.mark.parametrize("how", ["left", "outer"])
def test_join_empty_right_with_left_or_outer_returns_left_unchanged(how):
    empty_right = pd.DataFrame({"name": [], "score": []})
    result = join(_left_df(), empty_right, "name", "name", how=how)
    assert sorted(result["name"].tolist()) == sorted(_left_df()["name"].tolist())


# ---------------------------------------------------------------------------
# join: tolerance-based (fuzzy) numeric joins
# ---------------------------------------------------------------------------

def test_join_tolerance_inner_keeps_only_close_matches():
    left = pd.DataFrame({"station": ["A", "B", "C"], "lat": [10.0, 20.0, 30.0]})
    right = pd.DataFrame({"lat": [10.00005, 20.5, 99.0], "reading": [1, 2, 3]})
    result = join(left, right, "lat", "lat", how="inner", tolerance=0.001)
    # A matches (diff 0.00005), B and C have no close match.
    assert result["station"].tolist() == ["A"]


def test_join_tolerance_left_keeps_all_left_rows_even_unmatched():
    left = pd.DataFrame({"station": ["A", "B"], "lat": [10.0, 20.0]})
    right = pd.DataFrame({"lat": [10.00005], "reading": [1]})
    result = join(left, right, "lat", "lat", how="left", tolerance=0.001)
    assert sorted(result["station"].tolist()) == ["A", "B"]
    assert result.loc[result["station"] == "B", "reading"].isna().all()


def test_join_tolerance_non_numeric_falls_back_to_exact_join():
    # tolerance is given, but the join columns are strings - core.join must
    # fall back to an ordinary exact merge rather than erroring out trying
    # to run merge_asof on non-numeric data.
    left = pd.DataFrame({"name": ["Alice", "Bob"], "age": [30, 25]})
    right = pd.DataFrame({"name": ["Alice", "Bob"], "score": [90, 80]})
    result = join(left, right, "name", "name", how="inner", tolerance=0.001)
    assert sorted(result["name"].tolist()) == ["Alice", "Bob"]


def test_join_tolerance_respects_tight_bound():
    left = pd.DataFrame({"station": ["A"], "lat": [10.0]})
    right = pd.DataFrame({"lat": [10.0005], "reading": [1]})
    # Well within a loose tolerance...
    loose = join(left, right, "lat", "lat", how="inner", tolerance=0.001)
    assert loose["station"].tolist() == ["A"]
    # ...but outside a tight one.
    tight = join(left, right, "lat", "lat", how="inner", tolerance=0.00001)
    assert tight.empty

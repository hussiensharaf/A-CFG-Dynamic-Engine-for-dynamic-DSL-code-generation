"""
JOIN-specific tests for the SQL-like DSL compiler.

This feature was unfinished when this test suite was written (see the
yacc.py commit that added it): the lexer was missing the JOIN/ON/AS
tokens, the SELECT grammar never actually used the join grammar at all,
and several codegen variables were referenced before assignment. These
tests cover everything that was fixed plus the join variants that hadn't
been exercised yet: chained joins, JOIN combined with GROUP BY/ORDER BY,
RIGHT/FULL JOIN, positional (COLNUMBER) columns through a join, and
tolerance-based (fuzzy) numeric joins.

Run with:  pytest tests/test_joins.py
"""

import pytest

from app.core.result_monad import Success
from app.etl.controllers import compile_to_python, execute_python_code


def run_query(query):
    result = compile_to_python(query)
    assert isinstance(result, Success), f"compile failed: {result.unwrap_error()}"
    code = result.unwrap()
    exec_result = execute_python_code(code)
    assert isinstance(exec_result, Success), (
        f"execution failed: {exec_result.unwrap_error().message}\n"
        f"--- generated code ---\n{code}"
    )
    return exec_result.unwrap()


# ---------------------------------------------------------------------------
# Basic JOIN variants
# ---------------------------------------------------------------------------

def test_inner_join_no_collision(datasets):
    df = run_query(
        f"SELECT A.name, A.longitude, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name;"
    )
    assert list(df.columns) == ["name", "longitude", "temperature"]
    assert len(df) == 3
    assert float(df.loc[df["name"] == "Linz", "temperature"].iloc[0]) == 18.9


def test_select_star_through_join(datasets):
    df = run_query(
        f"SELECT * FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name;"
    )
    assert len(df) == 3


def test_left_join_where_on_alias_qualified_column(datasets):
    df = run_query(
        f"SELECT A.name, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"LEFT JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name "
        f"WHERE B.temperature > 20;"
    )
    assert sorted(df["name"].tolist()) == ["Ras Ghareb", "Wadi Araba"]


def test_left_join_keeps_unmatched_row_as_nan(datasets):
    df = run_query(
        f"SELECT A.name, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"LEFT JOIN {{csv:{datasets['weather_partial']}}} AS B ON A.name = B.name;"
    )
    assert len(df) == 3
    assert df.loc[df["name"] == "Linz", "temperature"].isna().all()


def test_right_join(datasets):
    # weather_partial only has "Wadi Araba" - a RIGHT JOIN from areas should
    # therefore only keep that one matching row.
    df = run_query(
        f"SELECT A.name, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"RIGHT JOIN {{csv:{datasets['weather_partial']}}} AS B ON A.name = B.name;"
    )
    assert len(df) == 1
    assert df.iloc[0]["name"] == "Wadi Araba"


def test_full_outer_join_keeps_all_rows_from_both_sides(datasets):
    df = run_query(
        f"SELECT A.name, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"FULL JOIN {{csv:{datasets['weather_partial']}}} AS B ON A.name = B.name;"
    )
    # areas.csv has 3 rows, weather_partial.csv has 1 row that matches one of
    # them - a FULL JOIN must keep all 3 (not drop Ras Ghareb/Linz just
    # because weather_partial has no matching row for them).
    assert len(df) == 3
    assert df.loc[df["name"] == "Ras Ghareb", "temperature"].isna().all()


@pytest.mark.xfail(
    reason=(
        "Known caveat, not fixed by this suite: after every join, yacc.py "
        "unconditionally drops any column whose name contains a coordinate "
        "substring ('lat', 'lon', etc.) and ends with a join suffix, to "
        "clean up the auto-tolerance join's duplicate coordinate columns. "
        "That cleanup can't tell a harmless duplicate from a genuine "
        "collision the SELECT list actually asked for (B.longitude here), "
        "so it drops the suffixed column and resolve_col() silently falls "
        "back to table A's value instead of table B's. This test documents "
        "the behaviour; flip the expected value if/when it's fixed."
    ),
    strict=True,
)
def test_join_with_genuine_column_collision_resolves_suffix(datasets):
    # weather_collide.csv deliberately shares "longitude"/"latitude" with
    # areas.csv - B.longitude must resolve to table B's value (which pandas
    # suffixes), not silently fall back to table A's value.
    df = run_query(
        f"SELECT A.name, B.longitude, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather_collide']}}} AS B ON A.name = B.name;"
    )
    assert len(df) == 3
    wadi = df.loc[df["name"] == "Wadi Araba"].iloc[0]
    # areas.csv's Wadi Araba longitude is 32.446042; weather_collide.csv's is
    # 32.9 - B.longitude must be the latter.
    assert abs(float(wadi["longitude"]) - 32.9) < 1e-6


# ---------------------------------------------------------------------------
# Chained joins (A JOIN B JOIN C)
# ---------------------------------------------------------------------------

def test_chained_join_three_tables(datasets):
    df = run_query(
        f"SELECT A.name, B.temperature, C.soil_moisture "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name "
        f"JOIN {{csv:{datasets['soil']}}} AS C ON A.name = C.name;"
    )
    assert list(df.columns) == ["name", "temperature", "soil_moisture"]
    assert len(df) == 3
    linz = df.loc[df["name"] == "Linz"].iloc[0]
    assert float(linz["temperature"]) == 18.9
    assert abs(float(linz["soil_moisture"]) - 0.31) < 1e-9


def test_chained_left_join_three_tables_with_unmatched_row(datasets):
    df = run_query(
        f"SELECT A.name, B.temperature, C.soil_moisture "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"LEFT JOIN {{csv:{datasets['weather_partial']}}} AS B ON A.name = B.name "
        f"LEFT JOIN {{csv:{datasets['soil']}}} AS C ON A.name = C.name;"
    )
    assert len(df) == 3
    # Ras Ghareb / Linz have no match in weather_partial.csv -> NaN
    # temperature, but soil_moisture should still be populated from the
    # third table.
    ras = df.loc[df["name"] == "Ras Ghareb"].iloc[0]
    assert pd_isna(ras["temperature"])
    assert abs(float(ras["soil_moisture"]) - 0.18) < 1e-9


def pd_isna(value):
    import pandas as pd
    return pd.isna(value)


# ---------------------------------------------------------------------------
# JOIN combined with GROUP BY / ORDER BY
# ---------------------------------------------------------------------------

def test_join_with_group_by(datasets):
    df = run_query(
        f"SELECT A.name, mean(B.temperature) "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name "
        f"GROUP BY A.name;"
    )
    assert len(df) == 3


def test_join_with_order_by(datasets):
    df = run_query(
        f"SELECT A.name, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name "
        f"ORDER BY B.temperature DESC;"
    )
    assert df.iloc[0]["name"] == "Wadi Araba"  # highest temperature (34.5)
    assert df.iloc[-1]["name"] == "Linz"       # lowest temperature (18.9)


def test_join_with_order_by_and_limit(datasets):
    df = run_query(
        f"SELECT A.name, B.temperature "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name "
        f"ORDER BY B.temperature ASC LIMIT 1;"
    )
    assert len(df) == 1
    assert df.iloc[0]["name"] == "Linz"


# ---------------------------------------------------------------------------
# Positional (COLNUMBER) columns through a join
# ---------------------------------------------------------------------------

def test_colnumber_column_through_join(datasets):
    # [0] on the joined (accumulated) frame refers to its first column,
    # which after "FROM areas AS A JOIN weather AS B" is still "name".
    df = run_query(
        f"SELECT [0] "
        f"FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B ON A.name = B.name;"
    )
    assert len(df) == 3
    assert df.columns[0] == "name"


# ---------------------------------------------------------------------------
# Multiple ON conditions joined with AND
# ---------------------------------------------------------------------------

def test_join_on_multiple_columns_with_and(datasets):
    # Join on name AND an exact (non-coordinate) secondary key. Re-using
    # "name" twice is contrived, but it exercises the AND-condition codegen
    # path (extract_all_conditions) rather than the single-condition path.
    df = run_query(
        f"SELECT A.name, B.temperature "
        f"FROM {{csv:{datasets['weather']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} AS B "
        f"ON A.name = B.name AND A.humidity = B.humidity;"
    )
    assert len(df) == 3


# ---------------------------------------------------------------------------
# Tolerance-based (fuzzy) numeric joins
# ---------------------------------------------------------------------------

def test_tolerance_join_matches_close_coordinates(tolerance_datasets):
    # "latitude" is a coordinate-like column name, so the compiler's
    # auto-tolerance heuristic (see yacc.py's p_select join codegen) applies
    # a 0.0001-degree tolerance automatically - close-but-not-equal values
    # should still match.
    df = run_query(
        f"SELECT A.station, B.value "
        f"FROM {{csv:{tolerance_datasets['stations']}}} AS A "
        f"JOIN {{csv:{tolerance_datasets['readings']}}} AS B "
        f"ON A.latitude = B.latitude;"
    )
    matched_stations = set(df["station"].tolist())
    assert "A" in matched_stations
    assert "B" in matched_stations
    # Station C's latitude (48.30639) has no close match in readings.csv
    # (closest is 10.0), so it must not appear in an inner join's result.
    assert "C" not in matched_stations


@pytest.mark.xfail(
    reason=(
        "Known caveat, not fixed by this suite: the auto-tolerance "
        "heuristic in yacc.py matches column names by substring "
        "('lat', 'lon', 'x', 'y'), so a NUMERIC join key such as "
        "'quantity' or 'category' (which contain 'y') silently gets a "
        "0.0001 fuzzy-match tolerance instead of an exact join. This test "
        "documents the behaviour; flip the expected value if/when it's "
        "fixed."
    ),
    strict=True,
)
def test_numeric_column_with_y_in_its_name_is_not_silently_fuzzy_matched(tmp_path):
    import csv as csv_module

    left_path = str(tmp_path / "left_qty.csv")
    with open(left_path, "w", newline="", encoding="utf-8") as f:
        w = csv_module.writer(f)
        w.writerow(["name", "quantity"])
        w.writerow(["a", 10])
        w.writerow(["b", 20])

    right_path = str(tmp_path / "right_qty.csv")
    with open(right_path, "w", newline="", encoding="utf-8") as f:
        w = csv_module.writer(f)
        w.writerow(["name", "quantity"])
        # Close to 10 but not equal - an exact join must NOT match this.
        w.writerow(["x", 10.00005])

    df = run_query(
        f"SELECT A.name "
        f"FROM {{csv:{left_path}}} AS A "
        f"JOIN {{csv:{right_path}}} AS B ON A.quantity = B.quantity;"
    )
    # Expected (correct) behaviour: no match, because 10 != 10.00005 under
    # an exact join. Currently this incorrectly DOES match, because
    # "quantity" contains "y" and triggers the coordinate-tolerance
    # heuristic - hence xfail(strict=True) above.
    assert len(df) == 0

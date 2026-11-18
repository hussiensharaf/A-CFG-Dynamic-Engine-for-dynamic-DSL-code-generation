"""
End-to-end tests of the SQL-like DSL compiler (app.compiler) and ETL
pipeline (app.etl), exercised the same way the GUI does: compile a query
string to Python, execute that Python, and check the resulting DataFrame.

Run with:  pytest tests/test_compiler.py
"""

import os

import pandas as pd
import pytest

from app.core.result_monad import Success
from app.etl.controllers import compile_to_python, execute_python_code


def run_query(query):
    """Compile + execute a query, returning the resulting DataFrame.
    Raises an AssertionError with the generated code attached if either
    step fails, so a failing test shows you exactly what went wrong."""
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
# Plain SELECT (no JOIN)
# ---------------------------------------------------------------------------

def test_select_all_columns(datasets):
    df = run_query(f"SELECT * FROM {{csv:{datasets['areas']}}} LIMIT 5;")
    assert list(df.columns) == ["name", "longitude", "latitude"]
    assert len(df) == 3


def test_select_specific_columns(datasets):
    df = run_query(f"SELECT name, longitude FROM {{csv:{datasets['areas']}}};")
    assert list(df.columns) == ["name", "longitude"]


def test_where_order_by_limit(datasets):
    df = run_query(
        f"SELECT name, cost FROM {{csv:{datasets['people']}}} WHERE cost > 5000 "
        f"ORDER BY cost DESC LIMIT 2;"
    )
    assert len(df) == 2
    assert df.iloc[0]["name"] == "Cara"


def test_tail(datasets):
    df = run_query(
        f"SELECT name FROM {{csv:{datasets['people']}}} ORDER BY id ASC TAIL 2;"
    )
    assert df["name"].tolist() == ["Dan", "Eve"]


def test_distinct(datasets):
    df = run_query(f"SELECT DISTINCT profession FROM {{csv:{datasets['people']}}};")
    assert sorted(df["profession"].tolist()) == ["developer", "doctor", "worker"]


def test_group_by_aggregation(datasets):
    df = run_query(
        f"SELECT profession, mean(cost) FROM {{csv:{datasets['people']}}} "
        f"GROUP BY profession;"
    )
    assert len(df) == 3


def test_limit_zero_returns_empty_frame_with_columns(datasets):
    df = run_query(f"SELECT * FROM {{csv:{datasets['areas']}}} LIMIT 0;")
    assert len(df) == 0
    assert list(df.columns) == ["name", "longitude", "latitude"]


# ---------------------------------------------------------------------------
# INSERT
# ---------------------------------------------------------------------------

def test_insert_writes_correct_values_and_no_index_column(tmp_path):
    target = str(tmp_path / "insert_target.csv")
    # This DSL's string literals are double-quoted only (see t_STRING in
    # app/compiler/lex.py) - single quotes are not valid syntax here.
    query = f'INSERT INTO {{csv:{target}}} (name, age) VALUES ("Alice", 30);'

    result = compile_to_python(query)
    assert isinstance(result, Success), result.unwrap_error()
    exec_result = execute_python_code(result.unwrap())
    assert isinstance(exec_result, Success), exec_result.unwrap_error().message

    assert os.path.exists(target)
    written = pd.read_csv(target)
    assert list(written.columns) == ["name", "age"]
    assert written.iloc[0]["name"] == "Alice"  # not the literal '"Alice"'
    assert int(written.iloc[0]["age"]) == 30


# ---------------------------------------------------------------------------
# Error handling: malformed input should fail cleanly, not crash
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        pytest.param("THIS IS NOT SQL AT ALL;", id="garbage_input"),
        pytest.param("SELECT FROM ;", id="missing_columns"),
        pytest.param("SELECT * FROM", id="unterminated_query"),
    ],
)
def test_malformed_sql_fails_to_compile(query):
    result = compile_to_python(query)
    assert not isinstance(result, Success), (
        f"expected {query!r} to fail to compile, but it produced: {result.unwrap()}"
    )


def test_malformed_join_fails_to_compile(datasets):
    # ON clause with no comparison (A.name alone, not A.name = B.name).
    query = (
        f"SELECT * FROM {{csv:{datasets['areas']}}} AS A "
        f"JOIN {{csv:{datasets['weather']}}} ON A.name;"
    )
    result = compile_to_python(query)
    assert not isinstance(result, Success)

"""
Unit tests for the pure-logic helper functions in app/etl/helpers.py.

These sit a layer below the compiler/JOIN tests: instead of compiling and
executing a query string, each test builds a small DataFrame directly and
calls the helper function itself. That makes it possible to pin down edge
cases (duplicate order-by columns, SIZE(*) handling, column-index
resolution, ...) precisely, and to see at a glance which helper broke when
something fails.

Run with:  pytest tests/test_etl_helpers.py
"""

import pandas as pd
import pytest

from app.compiler.ast_nodes import (
    AggregationNode,
    ColumnIndexNode,
    ColumnNameNode,
    OrderByNode,
    OrderByParameter,
    SortingWay,
)
from app.etl.helpers import (
    apply_filtering,
    apply_groupby,
    apply_groupby_with_order,
    apply_order_by_without_groupby,
    check_if_column_names_is_in_group_by,
    column_index_to_column_name,
    column_index_to_name,
    convert_select_column_indices_to_name,
    flatten_columns,
    generate_aggregation_row,
    get_scaler_aggregate,
    get_unique,
    group_by_columns_names,
    is_index,
)


def _people_df():
    return pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Cara", "Dan", "Eve"],
            "profession": ["doctor", "doctor", "developer", "developer", "worker"],
            "cost": [5200, 4800, 6100, 5900, 3000],
        }
    )


# ---------------------------------------------------------------------------
# is_index / column_index_to_name / column_index_to_column_name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("[0]", True),
        ("[12]", True),
        ("name", False),
        ("", False),
        ("[unclosed", False),
    ],
)
def test_is_index(value, expected):
    assert is_index(value) == expected


def test_column_index_to_name():
    df = _people_df()
    assert column_index_to_name(df, "[0]") == "name"
    assert column_index_to_name(df, "[2]") == "cost"


def test_column_index_to_column_name_returns_column_name_node():
    df = _people_df()
    result = column_index_to_column_name(df, ColumnIndexNode(index=1))
    assert result == ColumnNameNode("profession")


# ---------------------------------------------------------------------------
# get_unique
# ---------------------------------------------------------------------------

def test_get_unique_preserves_first_occurrence_order():
    assert get_unique(["a", "b", "a", "c", "b", "d"]) == ["a", "b", "c", "d"]


def test_get_unique_empty_list():
    assert get_unique([]) == []


# ---------------------------------------------------------------------------
# group_by_columns_names
# ---------------------------------------------------------------------------

def test_group_by_columns_names_plain_names():
    df = _people_df()
    assert group_by_columns_names(df, ["profession"]) == ["profession"]


def test_group_by_columns_names_resolves_column_index():
    df = _people_df()
    # [1] -> "profession"
    assert group_by_columns_names(df, ["[1]"]) == ["profession"]


def test_group_by_columns_names_mixed_name_and_index():
    df = _people_df()
    assert group_by_columns_names(df, ["[0]", "profession"]) == ["name", "profession"]


# ---------------------------------------------------------------------------
# convert_select_column_indices_to_name
# ---------------------------------------------------------------------------

def test_convert_select_column_indices_to_name_plain_strings():
    df = _people_df()
    result = convert_select_column_indices_to_name(df, ["name", "cost"])
    assert result == ["name", "cost"]


def test_convert_select_column_indices_to_name_resolves_indices():
    df = _people_df()
    result = convert_select_column_indices_to_name(df, ["[0]", "[2]"])
    assert result == ["name", "cost"]


def test_convert_select_column_indices_to_name_handles_aggregation_tuples():
    df = _people_df()
    result = convert_select_column_indices_to_name(df, [("mean", "[2]"), ("mean", "cost")])
    assert result == [("mean", "cost"), ("mean", "cost")]


# ---------------------------------------------------------------------------
# check_if_column_names_is_in_group_by
# ---------------------------------------------------------------------------

def test_check_if_column_names_is_in_group_by_all_present():
    assert check_if_column_names_is_in_group_by(
        ["profession", ("mean", "cost")], ["profession"]
    )


def test_check_if_column_names_is_in_group_by_missing_column():
    assert not check_if_column_names_is_in_group_by(
        ["profession", "name"], ["profession"]
    )


def test_check_if_column_names_is_in_group_by_ignores_aggregation_tuples():
    # Only plain string columns need to be in the GROUP BY list; aggregation
    # tuples are exempt (that's what makes "SELECT profession, mean(cost)
    # GROUP BY profession" valid).
    assert check_if_column_names_is_in_group_by(
        [("mean", "cost"), ("sum", "cost")], []
    )


# ---------------------------------------------------------------------------
# get_scaler_aggregate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "aggregate, expected",
    [
        ("sum", 25000),
        ("count", 5),
        ("first", 5200),
        ("last", 3000),
        ("mean", 5000.0),
        ("min", 3000),
        ("max", 6100),
        ("nunique", 5),
    ],
)
def test_get_scaler_aggregate(aggregate, expected):
    df = _people_df()
    assert get_scaler_aggregate(df, aggregate, "cost") == expected


def test_get_scaler_aggregate_size_ignores_column():
    df = _people_df()
    assert get_scaler_aggregate(df, "size", "cost") == 5


def test_get_scaler_aggregate_unsupported_function_returns_none():
    df = _people_df()
    assert get_scaler_aggregate(df, "not_a_real_aggregate", "cost") is None


# ---------------------------------------------------------------------------
# generate_aggregation_row
# ---------------------------------------------------------------------------

def test_generate_aggregation_row_single_function():
    df = _people_df()
    result = generate_aggregation_row(df, [("mean", "cost")])
    assert list(result.columns) == ["mean_cost"]
    assert result["mean_cost"].iloc[0] == 5000.0


def test_generate_aggregation_row_multiple_functions():
    df = _people_df()
    result = generate_aggregation_row(df, [("min", "cost"), ("max", "cost")])
    assert list(result.columns) == ["min_cost", "max_cost"]
    assert result["min_cost"].iloc[0] == 3000
    assert result["max_cost"].iloc[0] == 6100


def test_generate_aggregation_row_size_star_uses_rows_label():
    df = _people_df()
    result = generate_aggregation_row(df, [("size", "*")])
    assert list(result.columns) == ["size_rows"]
    assert result["size_rows"].iloc[0] == 5


# ---------------------------------------------------------------------------
# flatten_columns
# ---------------------------------------------------------------------------

def test_flatten_columns_combines_tuple_levels():
    grouped = _people_df().groupby("profession").agg({"cost": ["mean"]}).reset_index()
    flattened = flatten_columns(grouped)
    # "profession" index column has no aggregation level -> stays bare;
    # the aggregated "cost" column becomes "mean_cost".
    assert flattened == ["profession", "mean_cost"]


def test_flatten_columns_leaves_plain_columns_alone():
    df = pd.DataFrame({"a": [1], "b": [2]})
    assert flatten_columns(df) == ["a", "b"]


# ---------------------------------------------------------------------------
# apply_groupby
# ---------------------------------------------------------------------------

def test_apply_groupby_single_aggregation():
    df = _people_df()
    result = apply_groupby(df, ["profession", ("mean", "cost")], ["profession"])
    assert list(result.columns) == ["profession", "mean_cost"]
    assert len(result) == 3
    doctor_row = result.loc[result["profession"] == "doctor"].iloc[0]
    assert doctor_row["mean_cost"] == 5000.0  # (5200 + 4800) / 2


def test_apply_groupby_size_star():
    df = _people_df()
    result = apply_groupby(df, ["profession", ("size", "*")], ["profession"])
    assert "size_rows" in result.columns
    doctor_row = result.loc[result["profession"] == "doctor"].iloc[0]
    assert doctor_row["size_rows"] == 2


def test_apply_groupby_raises_outside_groupby_columns_not_checked_here():
    # apply_groupby itself does not validate select vs groupby columns
    # (that's check_if_column_names_is_in_group_by's job, called earlier in
    # transform_select) - this just documents it runs the aggregation as
    # given without raising when it's not asked to check anything.
    df = _people_df()
    result = apply_groupby(df, ["profession", ("sum", "cost")], ["profession"])
    assert len(result) == 3


# ---------------------------------------------------------------------------
# apply_groupby_with_order
# ---------------------------------------------------------------------------

def test_apply_groupby_with_order_sorts_by_group_column():
    df = _people_df()
    order = OrderByNode(
        parameters=[
            OrderByParameter(parameter=ColumnNameNode("profession"), way=SortingWay.DESC)
        ]
    )
    result = apply_groupby_with_order(
        df, ["profession", ("mean", "cost")], ["profession"], order
    )
    assert result["profession"].tolist() == sorted(
        result["profession"].tolist(), reverse=True
    )


def test_apply_groupby_with_order_sorts_by_aggregation_column():
    df = _people_df()
    order = OrderByNode(
        parameters=[
            OrderByParameter(
                parameter=AggregationNode("mean", ColumnNameNode("cost")),
                way=SortingWay.ASC,
            )
        ]
    )
    result = apply_groupby_with_order(
        df, ["profession", ("mean", "cost")], ["profession"], order
    )
    assert result["mean_cost"].tolist() == sorted(result["mean_cost"].tolist())


def test_apply_groupby_with_order_rejects_column_not_in_group_by():
    df = _people_df()
    order = OrderByNode(
        parameters=[
            OrderByParameter(parameter=ColumnNameNode("name"), way=SortingWay.ASC)
        ]
    )
    with pytest.raises(Exception, match="not in group by"):
        apply_groupby_with_order(df, ["profession", ("mean", "cost")], ["profession"], order)


def test_apply_groupby_with_order_rejects_duplicate_order_columns():
    df = _people_df()
    order = OrderByNode(
        parameters=[
            OrderByParameter(parameter=ColumnNameNode("profession"), way=SortingWay.ASC),
            OrderByParameter(parameter=ColumnNameNode("profession"), way=SortingWay.DESC),
        ]
    )
    with pytest.raises(Exception, match="duplicate columns"):
        apply_groupby_with_order(df, ["profession", ("mean", "cost")], ["profession"], order)


# ---------------------------------------------------------------------------
# apply_order_by_without_groupby
# ---------------------------------------------------------------------------

def test_apply_order_by_without_groupby_single_column_desc():
    df = _people_df()
    order = OrderByNode(
        parameters=[OrderByParameter(parameter=ColumnNameNode("cost"), way=SortingWay.DESC)]
    )
    result = apply_order_by_without_groupby(df, order)
    assert result["name"].tolist() == ["Cara", "Dan", "Alice", "Bob", "Eve"]


def test_apply_order_by_without_groupby_resolves_column_index():
    df = _people_df()
    order = OrderByNode(
        parameters=[OrderByParameter(parameter=ColumnIndexNode(index=2), way=SortingWay.ASC)]
    )
    result = apply_order_by_without_groupby(df, order)
    assert result["name"].tolist()[0] == "Eve"  # lowest cost


def test_apply_order_by_without_groupby_rejects_aggregation_column():
    df = _people_df()
    order = OrderByNode(
        parameters=[
            OrderByParameter(
                parameter=AggregationNode("mean", ColumnNameNode("cost")),
                way=SortingWay.ASC,
            )
        ]
    )
    with pytest.raises(Exception, match="group by"):
        apply_order_by_without_groupby(df, order)


def test_apply_order_by_without_groupby_rejects_duplicate_columns():
    df = _people_df()
    order = OrderByNode(
        parameters=[
            OrderByParameter(parameter=ColumnNameNode("cost"), way=SortingWay.ASC),
            OrderByParameter(parameter=ColumnNameNode("cost"), way=SortingWay.DESC),
        ]
    )
    with pytest.raises(Exception, match="duplicate columns"):
        apply_order_by_without_groupby(df, order)


# ---------------------------------------------------------------------------
# apply_filtering
# ---------------------------------------------------------------------------

def test_apply_filtering_comparison_operator():
    df = _people_df()
    result = apply_filtering(df, {"type": ">", "left": "cost", "right": 5000})
    assert sorted(result["name"].tolist()) == ["Alice", "Cara", "Dan"]


def test_apply_filtering_string_literal_equality():
    df = _people_df()
    result = apply_filtering(
        df, {"type": "==", "left": "profession", "right": '"doctor"'}
    )
    assert sorted(result["name"].tolist()) == ["Alice", "Bob"]


def test_apply_filtering_column_index_operand():
    df = _people_df()
    # left = "[2]" (cost column by position)
    result = apply_filtering(df, {"type": "<", "left": "[2]", "right": 4000})
    assert result["name"].tolist() == ["Eve"]


def test_apply_filtering_column_to_column_comparison():
    df = _people_df()
    # right operand not quoted and not an index -> treated as another column.
    df2 = df.assign(threshold=[5000, 5000, 5000, 5000, 5000])
    result = apply_filtering(df2, {"type": ">", "left": "cost", "right": "threshold"})
    assert sorted(result["name"].tolist()) == ["Alice", "Cara", "Dan"]


def test_apply_filtering_and_combines_conditions():
    df = _people_df()
    result = apply_filtering(
        df,
        {
            "type": "and",
            "left": {"type": ">", "left": "cost", "right": 4000},
            "right": {"type": "<", "left": "cost", "right": 6000},
        },
    )
    assert sorted(result["name"].tolist()) == ["Alice", "Bob", "Dan"]


def test_apply_filtering_or_combines_conditions():
    df = _people_df()
    result = apply_filtering(
        df,
        {
            "type": "or",
            "left": {"type": "==", "left": "profession", "right": '"worker"'},
            "right": {"type": "==", "left": "profession", "right": '"developer"'},
        },
    )
    assert sorted(result["name"].tolist()) == ["Cara", "Dan", "Eve"]


def test_apply_filtering_not_negates_condition():
    df = _people_df()
    result = apply_filtering(
        df,
        {
            "type": "not",
            "operand": {"type": "==", "left": "profession", "right": '"doctor"'},
        },
    )
    assert sorted(result["name"].tolist()) == ["Cara", "Dan", "Eve"]


def test_apply_filtering_like_operator_uses_regex():
    df = _people_df()
    # The right operand goes through the same quoted-string-literal-vs-
    # column-reference check as every other operator, so an unquoted LIKE
    # pattern would be (mis)treated as a column name - it must be quoted.
    result = apply_filtering(df, {"type": "like", "left": "name", "right": '"^A"'})
    assert result["name"].tolist() == ["Alice"]


def test_apply_filtering_not_equal_operator():
    df = _people_df()
    result = apply_filtering(
        df, {"type": "!=", "left": "profession", "right": '"worker"'}
    )
    assert "Eve" not in result["name"].tolist()
    assert len(result) == 4

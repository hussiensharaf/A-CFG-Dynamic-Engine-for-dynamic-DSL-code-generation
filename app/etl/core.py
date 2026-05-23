from typing import Any, Callable, Tuple
import pandas as pd
from app.compiler.ast_nodes import *
from app.etl.data.data_factories import (
    LoaderDataFactory,
    ExtractorDataFactory,
)
from app.etl.data.base_data_types import IExtractor, ILoader
from app.etl.helpers import (
    apply_filtering,
    apply_groupby,
    apply_groupby_with_order,
    check_if_column_names_is_in_group_by,
    convert_select_column_indices_to_name,
    generate_aggregation_row,
    get_unique,
    group_by_columns_names,
    apply_order_by_without_groupby,
)


transformed_data = None


def extract(data_source_type: str, data_source_path: str) -> pd.DataFrame:
    data_extractor: IExtractor = ExtractorDataFactory.create(
        data_source_type, data_source_path
    )
    data: pd.DataFrame = data_extractor.extract()
    return data


def transform_select(data: pd.DataFrame, criteria: dict) -> pd.DataFrame:
    are_select_columns_aggregation = False
    if criteria["COLUMNS"] != "__all__":
        are_select_columns_aggregation = all(
            type(item) == tuple for item in criteria["COLUMNS"]
        )
    # filtering
    if criteria["FILTER"]:
        data = apply_filtering(data, criteria["FILTER"])

    if (
        not criteria["GROUP"]
        and criteria["ORDER"]
        and not are_select_columns_aggregation
    ):
        order_by_node: OrderByNode = criteria["ORDER"]
        data = apply_order_by_without_groupby(data, order_by_node)

    if criteria["GROUP"]:
        groupby_columns = get_unique(group_by_columns_names(data, criteria["GROUP"]))
        select_columns = convert_select_column_indices_to_name(
            data, criteria["COLUMNS"]
        )
        if not check_if_column_names_is_in_group_by(select_columns, groupby_columns):
            raise Exception("there are is a column isn't in groupby columns")
        if criteria["ORDER"]:
            order_by_node: OrderByNode = criteria["ORDER"]
            data = apply_groupby_with_order(
                data, select_columns, groupby_columns, order_by_node
            )
        else:
            data = apply_groupby(data, select_columns, groupby_columns)

    else:
        if criteria["COLUMNS"] != "__all__":
            columns: list[str | Tuple] = criteria["COLUMNS"]
            is_column_number: Callable[[str], bool] = lambda x: x.startswith(
                "["
            ) and x.endswith("]")
            # if all the select columns are aggregation functions

            if are_select_columns_aggregation:
                aggregate_columns = []
                for col in columns:
                    func = col[0]
                    col_ref = col[1]
                    if isinstance(col_ref, str) and is_column_number(col_ref):
                        idx = int(col_ref[1:-1])
                        if idx < 0 or idx >= len(data.columns):
                            raise IndexError(f"Column index {idx} out of range")
                        aggregate_columns.append((func, data.columns[idx]))
                    else:
                        aggregate_columns.append((func, col_ref))
                # list of tuples each tuple is (aggregation,colum name)
                aggregate_columns: list[Tuple[str | Any]] = [
                    (
                        (tuple[0], data.columns[int(tuple[1][1:-1])])
                        if is_column_number(tuple[1])
                        else tuple
                    )
                    for tuple in columns
                ]

                data = generate_aggregation_row(data, aggregate_columns)

            else:
                if any(isinstance(col, tuple) for col in columns):
                    raise Exception("Aggregation functions used without GROUP BY")

                column_names = []
                for col in columns:
                    if isinstance(col, str) and is_column_number(col):
                        idx = int(col[1:-1])
                        if idx < 0 or idx >= len(data.columns):
                            raise IndexError(f"Column index {idx} out of range")
                        column_names.append(data.columns[idx])
                    else:
                        column_names.append(col)
                if any(type(column) == tuple for column in columns):
                    raise Exception(
                        "there are aggregation columns in select you should use group by"
                    )
                # assuming that select columns don't contain any aggregate
                column_names = [
                    (
                        data.columns[int(column[1:-1])]
                        if is_column_number(column)
                        else column
                    )
                    for column in columns
                ]

                # Select columns
                data = data[column_names]

    # distinct
    if criteria["DISTINCT"]:
        data = data.drop_duplicates()

    # limit
    if criteria["LIMIT_OR_TAIL"] != None:
        operator, number = criteria["LIMIT_OR_TAIL"]
        if number == 0:
            # empty data frame
            data = pd.DataFrame(columns=data.columns)
        elif operator == "limit":
            data = data[:number]
        else:
            data = data[-number:]

    global transformed_data
    transformed_data = data
    return data


def join(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    left_col: str,
    right_col: str,
    how: str = "inner",
    left_suffix: str = "_left",
    right_suffix: str = "_right",
    tolerance: float = None,
) -> pd.DataFrame:
    """
    Join two DataFrames on specified columns.

    Supports chained multi-satellite joins by accepting custom suffixes per call,
    so that columns from earlier joins don't collide with later ones.

    Args:
        df1:           Left DataFrame (the accumulator in chained joins).
        df2:           Right DataFrame (the new satellite being joined in).
        left_col:      Column name in df1 to join on.
        right_col:     Column name in df2 to join on.
        how:           Join type — 'inner', 'left', 'right', or 'outer'.
        left_suffix:   Suffix appended to overlapping columns from df1.
        right_suffix:  Suffix appended to overlapping columns from df2.
        tolerance:     Tolerance for approximate numeric joins. If None, exact match.
                       For coordinates/floats, use decimal places (e.g., 0.0001 for ~11m precision).
    """
    global transformed_data

    valid_join_types = ["inner", "left", "right", "outer"]
    if how not in valid_join_types:
        raise ValueError(f"Invalid join type '{how}'. Must be one of {valid_join_types}")

    if df1 is None or df2 is None:
        raise ValueError("Input DataFrames must not be None")

    if df1.empty and df2.empty:
        transformed_data = pd.DataFrame()
        return transformed_data

    if df1.empty:
        if how in ["inner", "left"]:
            transformed_data = pd.DataFrame()
            return transformed_data
        else:
            transformed_data = df2.copy()
            return transformed_data

    if df2.empty:
        if how in ["inner", "right"]:
            transformed_data = pd.DataFrame()
            return transformed_data
        else:
            transformed_data = df1.copy()
            return transformed_data

    if left_col not in df1.columns:
        raise KeyError(
            f"Column '{left_col}' not found in left DataFrame. "
            f"Available: {list(df1.columns)}"
        )
    if right_col not in df2.columns:
        raise KeyError(
            f"Column '{right_col}' not found in right DataFrame. "
            f"Available: {list(df2.columns)}"
        )

    # Handle approximate/fuzzy join for numeric columns
    if tolerance is not None:
        # Check if columns are numeric
        if pd.api.types.is_numeric_dtype(df1[left_col]) and pd.api.types.is_numeric_dtype(df2[right_col]):
            # Use merge_asof for approximate numeric joins (requires sorted data)
            df1_sorted = df1.sort_values(by=left_col).copy()
            df2_sorted = df2.sort_values(by=right_col).copy()
            
            try:
                result = pd.merge_asof(
                    df1_sorted,
                    df2_sorted,
                    left_on=left_col,
                    right_on=right_col,
                    direction='nearest',
                    tolerance=tolerance,
                    suffixes=(left_suffix, right_suffix),
                )
                # merge_asof preserves order, but may differ from original - not ideal for all joins
                # For inner joins, filter to keep only matched rows
                if how == "inner":
                    result = result.dropna(subset=[right_col])
            except Exception as e:
                raise Exception(
                    f"Error during approximate join: {str(e)} "
                    f"(left_col={left_col}, right_col={right_col}, tolerance={tolerance})"
                )
        else:
            # Fallback to exact join if not numeric
            try:
                result = df1.merge(
                    df2,
                    left_on=left_col,
                    right_on=right_col,
                    how=how,
                    suffixes=(left_suffix, right_suffix),
                )
            except Exception as e:
                raise Exception(
                    f"Error during join: {str(e)} "
                    f"(left_col={left_col}, right_col={right_col}, how={how})"
                )
    else:
        # Exact join (original behavior)
        try:
            result = df1.merge(
                df2,
                left_on=left_col,
                right_on=right_col,
                how=how,
                suffixes=(left_suffix, right_suffix),
            )
        except Exception as e:
            raise Exception(
                f"Error during join: {str(e)} "
                f"(left_col={left_col}, right_col={right_col}, how={how})"
            )

    transformed_data = result
    return result



def load(data: pd.DataFrame, source_type: str, data_destination: str) -> None:
    try:
        data_loader: ILoader = LoaderDataFactory.create(source_type, data_destination)
        data_loader.load(data)
    except Exception as e:
        raise Exception(f"Error loading data to '{source_type}:{data_destination}': {str(e)}")


# Utilities
def get_transformed_data() -> pd.DataFrame:
    global transformed_data
    return transformed_data

def clear_transformed_data() -> None:
    global transformed_data
    transformed_data = None

def preview_data(data: pd.DataFrame, rows: int = 5) -> pd.DataFrame:
    return data.head(rows)

def get_data_info(data: pd.DataFrame) -> dict:
    return {
        "shape": data.shape,
        "columns": list(data.columns),
        "dtypes": {col: str(dtype) for col, dtype in data.dtypes.items()},
        "memory_usage": data.memory_usage(deep=True).sum(),
        "null_counts": data.isnull().sum().to_dict(),
    }

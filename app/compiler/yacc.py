from app.compiler.ast_nodes import (
    AggregationNode,
    ColumnIndexNode,
    ColumnNameNode,
    OrderByNode,
    OrderByParameter,
    SortingWay,
)
from app.core.errors import ParserError


start = "start"


def p_start(p):
    """start : select
    | insert
    | update
    | delete"""
    p[0] = p[1]


def p_empty(p):
    "empty :"
    pass


def p_error(p):
    value, line_number, position = p.value, p.lineno, p.lexpos
    raise ParserError(
        f"Syntax error at token '{value}' on line {line_number}, position {position}.",
        p.value,
        p.lineno,
        p.lexpos,
    )


# else:
#         raise ParserError("Syntax error at EOF")


###########################
# ==== SELECT STATEMENT​​ ====
###########################


def p_select(p):
    """select : SELECT distinct select_columns into_statement FROM table_source join_clauses where group order limit_or_tail SIMICOLON"""
    select_all_columns = p[3] == "__all__"
    # Note: p[3] is left exactly as the parser produced it here (either the
    # "__all__" sentinel string, or a list of column names/tuples). It is
    # rendered into the generated source further down via repr(), which
    # already produces correct, correctly-quoted Python syntax for both
    # cases — any pre-quoting here would double-quote the sentinel string.

    main_datasource = p[6]["datasource"]
    main_alias = p[6]["alias"]
    file_type, file_path = main_datasource.split(":", 1)

    load_stmt = ""
    if p[4]:
        load_type, load_path = p[4].split(":", 1)
        load_stmt = f"etl.load(transformed_data,'{load_type}','{load_path}')\n"

    # ---- Extract main data ----
    extract_code = f"extracted_data = etl.extract('{file_type}', '{file_path}')\n"

    # ---- Store alias mapping ----
    alias_mapping = {}
    if main_alias:
        alias_mapping[main_alias] = 'extracted_data'

    def extract_all_conditions(cond):
        """
        Recursively extract all simple {left, right} conditions from a
        possibly-nested ON clause (A.x = B.x AND A.y = B.y ...). Shared by
        the join codegen loop below and by normalize_column's join-key
        check, which both need to look at every simple condition inside an
        AND-combined ON clause, not just a single top-level one.
        """
        conditions = []
        if isinstance(cond, dict):
            if 'operator' in cond and cond['operator'].upper() == 'AND':
                # Complex condition with AND - extract from both sides
                conditions.extend(extract_all_conditions(cond['left']))
                conditions.extend(extract_all_conditions(cond['right']))
            elif 'left' in cond and 'right' in cond:
                # Simple condition
                conditions.append(cond)
        return conditions

    # ---- JOIN CODE (multiple joins supported) ----
    join_clauses = p[7]  # List of join operations
    join_code = ""

    if join_clauses:
        for idx, join_clause in enumerate(join_clauses):
            join_type = join_clause['type']  # 'inner', 'left', 'right', 'full'
            join_ds = join_clause['datasource']
            join_alias = join_clause.get('alias')
            on_condition = join_clause['on']

            # Parse join datasource
            j_type, j_path = join_ds.split(":", 1)

            # Generate unique variable name for each join
            join_var = f"join_df_{idx}"

            # Extract join table
            join_code += f"{join_var} = etl.extract('{j_type}', '{j_path}')\n"

            # Store alias if exists
            if join_alias:
                alias_mapping[join_alias] = join_var

            # Perform join
            # Extract ALL column pairs from ON conditions (supports multiple ON columns with AND)
            all_conditions = extract_all_conditions(on_condition)
            
            # Extract column names without alias (A.col → col)
            join_pairs = []
            for base_condition in all_conditions:
                left_col = base_condition['left'].split('.', 1)[-1]
                right_col = base_condition['right'].split('.', 1)[-1]
                join_pairs.append((left_col, right_col))
            
            # Determine suffixes once per join: use alias or dataset index
            right_suffix = f"_{join_alias}" if join_alias else f"_t{idx+1}"
            
            # Generate join code for each column pair
            for col_idx, (left_col, right_col) in enumerate(join_pairs):
                if col_idx == 0:
                    # Auto-detect tolerance for coordinate/spatial columns
                    tolerance_val = "None"
                    col_lower = left_col.lower()
                    if any(x in col_lower for x in ["lat", "latitude", "lon", "longitude", "x", "y"]):
                        # Use 0.0001 degree precision (~11 meters at equator)
                        tolerance_val = "0.0001"
                    elif any(x in col_lower for x in ["time", "timestamp", "date"]):
                        # For time columns, use no tolerance (should be exact)
                        tolerance_val = "None"
                    
                    # First join
                    join_code += f"extracted_data = etl.join(\n"
                    join_code += f"    extracted_data,\n"
                    join_code += f"    {join_var},\n"
                    join_code += f"    '{left_col}',\n"
                    join_code += f"    '{right_col}',\n"
                    join_code += f"    how='{join_type}',\n"
                    join_code += f"    left_suffix='',\n"
                    join_code += f"    right_suffix='{right_suffix}',\n"
                    join_code += f"    tolerance={tolerance_val}\n"
                    join_code += f")\n"
                else:
                    # Additional joins on the same tables for remaining columns
                    # After merge, the right column has the suffix appended
                    right_col_suffixed = f"{right_col}{right_suffix}"
                    
                    # Auto-detect tolerance for coordinate/spatial columns
                    col_lower = left_col.lower()
                    if any(x in col_lower for x in ["lat", "latitude", "lon", "longitude", "x", "y"]):
                        # Use 0.0001 degree precision (~11 meters at equator)
                        join_code += f"# Additional join on {left_col} ≈ {right_col} (with tolerance 0.0001)\n"
                        join_code += f"extracted_data = extracted_data[\n"
                        join_code += f"    (abs(extracted_data['{left_col}'] - extracted_data['{right_col_suffixed}']) <= 0.0001) |\n"
                        join_code += f"    (extracted_data['{left_col}'].isna() & extracted_data['{right_col_suffixed}'].isna())\n"
                        join_code += f"]\n"
                    else:
                        # Exact match for non-coordinate columns
                        join_code += f"# Additional join on {left_col} = {right_col}\n"
                        join_code += f"extracted_data = extracted_data[\n"
                        join_code += f"    (extracted_data['{left_col}'] == extracted_data['{right_col_suffixed}']) |\n"
                        join_code += f"    (extracted_data['{left_col}'].isna() & extracted_data['{right_col_suffixed}'].isna())\n"
                        join_code += f"]\n"
        
        # After all joins, drop duplicate coordinate columns (keep only the unsuffixed ones from main dataset)
        if join_clauses:
            suffixes_list = []
            for jdx, jc in enumerate(join_clauses):
                suffix = f"_{jc.get('alias')}" if jc.get('alias') else f"_t{jdx+1}"
                suffixes_list.append(suffix)
            
            join_code += f"# Drop duplicate coordinate columns from joined datasets\n"
            join_code += f"cols_to_drop = [col for col in extracted_data.columns if (any(coord in col.lower() for coord in ['latitude', 'longitude', 'lat', 'lon']) and any(col.endswith(s) for s in {suffixes_list}))]\n"
            join_code += f"extracted_data = extracted_data.drop(columns=cols_to_drop, errors='ignore')\n"

    # ---- WHERE, GROUP, ORDER, LIMIT ----
    where_clause = p[8]
    group_clause = p[9]
    order_clause = p[10]
    limit_clause = p[11]

    # ==== Normalize SELECT, WHERE and GROUP column references based on alias -> real DataFrame columns ====

    # Build alias → suffix map (for pandas merge)
    alias_suffix = {}

    # main SELECT table gets no suffix (left_suffix='')
    if main_alias:
        alias_suffix[main_alias] = ""

    # join tables get unique suffixes based on alias or index
    if join_clauses:
        for idx, jc in enumerate(join_clauses):
            if jc['alias']:
                alias_suffix[jc['alias']] = f"_{jc['alias']}"
            else:
                alias_suffix[f"join_df_{idx}"] = f"_t{idx+1}"

    def normalize_column(col):
        """
        Resolve an "alias.name" reference to the column pandas will actually
        produce after the join. pandas only appends a suffix to columns that
        collide between the two sides of a merge, so the real name can only
        be known once the data is loaded — a plain-looking column (no
        collision) must NOT be forced to carry the suffix. Returns either the
        original string (no alias used) or a __RESOLVE_COL__(bare, suffixed)
        marker that the generated code resolves at runtime against the
        actual joined DataFrame's columns.

        col may also be an aggregation tuple, e.g. ("mean", "B.temperature")
        (SELECT mean(B.temperature) ...) - only the column reference inside
        it needs normalizing, not the aggregation function name.
        """
        if isinstance(col, tuple):
            func, col_ref = col
            return (func, normalize_column(col_ref))

        if isinstance(col, str) and "." in col:
            alias, name = col.split(".", 1)

            # If this column is a join key, pandas always leaves it
            # unsuffixed. An ON clause may combine several conditions with
            # AND (ON A.x = B.x AND A.y = B.y), so every simple condition
            # inside it has to be checked, not just a single top-level
            # {left, right} pair.
            for jc in (join_clauses or []):
                for simple_condition in extract_all_conditions(jc['on']):
                    if simple_condition['left'].endswith("." + name) or \
                       simple_condition['right'].endswith("." + name):
                        return name  # join key → no suffix, known for certain

            suffix = alias_suffix.get(alias, "")
            if not suffix:
                return name
            # Unknown until runtime whether pandas suffixed this column.
            return f"__RESOLVE_COL__({name!r}, {f'{name}{suffix}'!r})"

        return col

    def normalize_condition(cond):
        """Recursively normalize alias.column references inside a WHERE/GROUP tree."""
        if isinstance(cond, dict):
            new_cond = dict(cond)
            for key in ("left", "right", "operand"):
                if key in new_cond:
                    new_cond[key] = normalize_condition(new_cond[key])
            return new_cond
        if isinstance(cond, list):
            return [normalize_condition(item) for item in cond]
        return normalize_column(cond)

    if not select_all_columns:
        p[3] = [normalize_column(c) for c in p[3]]

    def normalize_order_by(node):
        """
        Resolve alias.column references inside an ORDER BY clause the same
        way normalize_column does for SELECT/WHERE/GROUP. Unlike those,
        ORDER BY's AST is a tree of dataclasses (OrderByNode ->
        OrderByParameter -> ColumnNameNode/AggregationNode) rather than
        plain strings/dicts, so columns are normalized in place on the
        ColumnNameNode.name (and on AggregationNode.column.name) fields
        before the whole tree is repr()'d into the generated source below.
        """
        if node is None:
            return None
        for order_param in node.parameters:
            param = order_param.parameter
            if isinstance(param, ColumnNameNode) and "." in param.name:
                param.name = normalize_column(param.name)
            elif isinstance(param, AggregationNode) and isinstance(
                param.column, ColumnNameNode
            ) and "." in param.column.name:
                param.column.name = normalize_column(param.column.name)
        return node

    if join_clauses:
        # Only rewrite alias.column references when a join is actually present;
        # a plain (non-join) query keeps its columns exactly as written.
        where_clause = normalize_condition(where_clause)
        group_clause = normalize_condition(group_clause)
        order_clause = normalize_order_by(order_clause)

    # repr() of the COLUMNS/FILTER/GROUP structures above embeds
    # "__RESOLVE_COL__('bare', 'suffixed')" as a quoted *string* (since it's
    # nested inside a Python list/dict literal that was built from plain
    # strings). Turn those markers back into real resolve_col(...) calls in
    # the generated source so they execute against the live DataFrame.
    resolve_helper = ""
    columns_src = repr(p[3])
    where_src = repr(where_clause)
    group_src = repr(group_clause)
    order_src = repr(order_clause)
    if join_clauses:
        import re as _re

        def _unquote_resolver(text):
            # repr() may wrap the marker in single or double quotes depending
            # on whether the embedded column names themselves contain a
            # single quote; match either.
            return _re.sub(
                r"""(['"])__RESOLVE_COL__\((.*?)\)\1""",
                lambda m: f"resolve_col({m.group(2)})",
                text,
            )

        columns_src = _unquote_resolver(columns_src)
        where_src = _unquote_resolver(where_src)
        group_src = _unquote_resolver(group_src)
        order_src = _unquote_resolver(order_src)
        resolve_helper = (
            "def resolve_col(bare, suffixed, _df=extracted_data):\n"
            "    return bare if bare in _df.columns else suffixed\n"
        )

    # ---- Final generated code ----
    p[0] = (
        "from app import etl\n"
        "from app.compiler.ast_nodes import *\n\n"
        f"{extract_code}"
        f"{join_code}"
        f"{resolve_helper}"
        f"transformed_data = etl.transform_select(\n"
        f"   extracted_data,\n"
        f"   {{\n"
        f"        'COLUMNS':  {columns_src},\n"
        f"        'DISTINCT': {p[2]},\n"
        f"        'FILTER':   {where_src},\n"
        f"        'GROUP':    {group_src},\n"
        f"        'ORDER':    {order_src},\n"
        f"        'LIMIT_OR_TAIL': {limit_clause},\n"
        f"   }}\n"
        f")\n"
        f"{load_stmt}"
    )


###########################
# ==== TABLE SOURCE (with optional alias) ====
###########################
def p_table_source_with_explicit_alias(p):
    """table_source : DATASOURCE AS SIMPLE_COLNAME"""
    p[0] = {
        'datasource': p[1],
        'alias': p[3]
    }


def p_table_source_with_implicit_alias(p):
    """table_source : DATASOURCE SIMPLE_COLNAME"""
    p[0] = {
        'datasource': p[1],
        'alias': p[2]
    }


def p_table_source_no_alias(p):
    """table_source : DATASOURCE"""
    p[0] = {
        'datasource': p[1],
        'alias': None
    }


###########################
# ==== JOIN CLAUSES (support multiple joins) ====
###########################
def p_join_clauses(p):
    """join_clauses : join_clauses join_clause"""
    p[0] = p[1]
    p[0].append(p[2])


def p_join_clauses_single(p):
    """join_clauses : join_clause"""
    p[0] = [p[1]]


def p_join_clauses_empty(p):
    """join_clauses : empty"""
    p[0] = None


###########################
# ==== SINGLE JOIN CLAUSE ====
###########################
def p_join_clause(p):
    """join_clause : join_type table_source on_statement"""
    p[0] = {
        'type': p[1],
        'datasource': p[2]['datasource'],
        'alias': p[2].get('alias'),
        'on': p[3]
    }


###########################
# ==== JOIN TYPES ====
###########################
def p_join_type_implicit(p):
    """join_type : JOIN"""
    p[0] = 'inner'
    
def p_join_type_inner(p):
    """join_type : INNER JOIN"""
    p[0] = 'inner'

def p_join_type_left(p):
    """join_type : LEFT JOIN
                 | LEFT OUTER JOIN"""
    p[0] = 'left'


def p_join_type_right(p):
    """join_type : RIGHT JOIN
                 | RIGHT OUTER JOIN"""
    p[0] = 'right'


def p_join_type_full(p):
    """join_type : FULL JOIN
                 | FULL OUTER JOIN"""
    p[0] = 'outer'  # pandas uses 'outer' for FULL JOIN



###########################
# ==== ON STATEMENT (with complex conditions) ====
###########################
def p_on_statement(p):
    """on_statement : ON on_conditions"""
    p[0] = p[2]


def p_on_conditions_complex(p):
    """on_conditions : on_conditions AND on_conditions
                     | on_conditions OR on_conditions"""
    # For now, we'll support single condition
    # Complex conditions would need more sophisticated handling
    p[0] = {
        'operator': p[2],
        'left': p[1],
        'right': p[3]
    }


def p_on_conditions_base(p):
    """on_conditions : qualified_column EQUAL qualified_column"""
    p[0] = {
        'left': p[1],
        'right': p[3]
    }


###########################
# ==== QUALIFIED COLUMN (table.column or column) ====
###########################
# "column" already accepts the "table.column" form (see p_column_qualified
# above), so qualified_column is just an alias for it — kept as its own
# nonterminal so the ON-clause grammar reads clearly.
def p_qualified_column_no_table(p):
    """qualified_column : column"""
    p[0] = p[1]


###########################
# ==== DOT token (we need to add this) ====
###########################


def p_insert(p):
    "insert : INSERT INTO DATASOURCE icolumn VALUES insert_values SIMICOLON"

    # p[3] is the DATASOURCE token, already stripped of its {...} braces by
    # the lexer (t_DATASOURCE) - e.g. "csv:/path/to/file.csv". Split it into
    # (type, path) the same way p_select does, instead of passing the whole
    # string through as a literal path.
    datasource = str(p[3]).replace("\\", "\\\\")
    file_type, file_path = datasource.split(":", 1)

    def strip_string_quotes(value):
        # The STRING token keeps its surrounding double quotes (p_select's
        # WHERE/filter codegen relies on that to embed them as valid Python
        # literals). For INSERT, the actual cell value must not include
        # those quote characters, so strip them here instead of changing
        # the shared token.
        if isinstance(value, str) and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            return value[1:-1]
        return value

    rows = [[strip_string_quotes(cell) for cell in row] for row in p[6]]

    p[0] = (
        f"from app import etl\n"
        f"import pandas as pd\n"
        f"\n"
        f"values = {rows!r}\n"
        f"data = pd.DataFrame(values, columns={p[4]})\n"
        f"etl.load(data, '{file_type}', '{file_path}')\n"
    )


###########################
# ==== Update STATEMENT ====
###########################
def p_update(p):
    "update : UPDATE DATASOURCE SET assigns where SIMICOLON"
    p[0] = None


###########################
# ==== DELETE STATEMENT​​ ====
###########################


def p_delete(p):
    "delete : DELETE FROM DATASOURCE where"
    p[0] = None


##########################
# ====== COMPARISON =======
##########################


def p_logical(p):
    """logical :  EQUAL
    | NOTEQUAL
    | BIGGER_EQUAL
    | BIGGER
    | SMALLER_EQUAL
    | SMALLER"""
    p[0] = p[1]


##########################
# ====== WHERE CLAUSE =====
##########################


def p_where(p):
    "where : WHERE conditions"
    p[0] = p[2]


def p_where_empty(p):
    "where : empty"
    p[0] = None


def p_cond_parens(p):
    "conditions : LPAREN conditions RPAREN"
    p[0] = p[2]


def p_cond_3(p):
    """conditions : conditions AND conditions
    | conditions OR conditions
    | exp LIKE STRING
    | exp logical exp"""
    p[0] = {"type": p[2], "left": p[1], "right": p[3]}


def p_conditions_not(p):
    "conditions : NOT conditions"
    p[0] = {"type": p[1], "operand": p[2]}


##########################
# ========== EXP ==========
##########################


def p_exp(p):
    """exp : column
    | STRING
    | NUMBER"""

    p[0] = p[1]


##########################
# ========== EXP ==========
##########################
def p_NUMBER(p):
    """NUMBER : NEGATIVE_INTNUMBER
    | POSITIVE_INTNUMBER
    | FLOATNUMBER"""
    p[0] = p[1]


###########################
# ======== Distinct ========
###########################


def p_distinct(p):
    """distinct : DISTINCT"""
    p[0] = True


def p_distinct_empty(p):
    """distinct : empty"""
    p[0] = False


###########################
# ======== COLUMNS =========
###########################
def p_column(p):
    """column : COLNUMBER
    | BRACKETED_COLNAME
    | SIMPLE_COLNAME"""
    c = str(p[1])
    if c.startswith("[") and c.endswith("]") and not c[1:-1].isdigit():
        c = c[1:-1]
    p[0] = c


def p_column_qualified(p):
    """column : SIMPLE_COLNAME DOT SIMPLE_COLNAME
    | SIMPLE_COLNAME DOT BRACKETED_COLNAME"""
    # table_alias.column_name, e.g. "A.firstname" — resolved later against
    # the join's alias map in p_select / normalize_column.
    name = str(p[3])
    if name.startswith("[") and name.endswith("]") and not name[1:-1].isdigit():
        name = name[1:-1]
    p[0] = f"{p[1]}.{name}"


def p_columns(p):
    """columns : columns COMMA columns"""
    p[0] = []
    p[0].extend(p[1])
    p[0].extend(p[3])


def p_columns_base(p):
    """columns : column
    | aggregation_function"""
    p[0] = [p[1]]


def p_aggregation_function(p):
    """aggregation_function : AGGREGATION_FUNCTION LPAREN column RPAREN
    | AGGREGATION_FUNCTION LPAREN TIMES RPAREN"""
    p[0] = (p[1], p[3])
    if p[3] == "*" and p[1] != "size":
        raise ParserError(
            f"Syntax error: You cannot use * with aggregation functions except SIZE(*)",
            "*",
            -1,
            -1,
        )


###########################
# ===== SELECT COLUMNS​​ =====
###########################


def p_select_columns_all(p):
    "select_columns : TIMES"
    p[0] = "__all__"


def p_select_columns(p):
    "select_columns : columns"
    p[0] = p[1]


###########################
# ========= Into ===========
###########################


def p_into_statement(p):
    "into_statement : INTO DATASOURCE"
    p[0] = p[2]


def p_into_statement_empty(p):
    "into_statement : empty"


###########################
# ======= Group by =========
###########################
def p_group(p):
    """group : GROUP BY icolumns"""
    p[0] = p[3]


def p_group_empty(p):
    """group : empty"""
    p[0] = None


###########################
# ======= Order by =========
###########################
def p_simple_column_name(p):
    """simple_column_name : SIMPLE_COLNAME"""
    p[0] = ColumnNameNode(str(p[1]))


def p_simple_column_name_qualified(p):
    """simple_column_name : SIMPLE_COLNAME DOT SIMPLE_COLNAME
    | SIMPLE_COLNAME DOT BRACKETED_COLNAME"""
    # table_alias.column_name in ORDER BY, e.g. "ORDER BY B.temperature DESC".
    # Stored the same way p_column_qualified stores it for SELECT/GROUP BY
    # ("alias.name"), so it goes through the same normalize_column/
    # resolve_col runtime-resolution path in p_select.
    name = str(p[3])
    if name.startswith("[") and name.endswith("]") and not name[1:-1].isdigit():
        name = name[1:-1]
    p[0] = ColumnNameNode(f"{p[1]}.{name}")


def p_bracketed_column_name(p):
    """bracketed_column_name : BRACKETED_COLNAME"""
    token = str(p[1])
    # to remove the scare brackets token[1:-1]
    p[0] = ColumnNameNode(token[1:-1])


def p_column_index(p):
    """column_index : COLNUMBER"""
    token = str(p[1])
    # to remove the scare brackets token[1:-1] and cast the str to int
    index = int(token[1:-1])

    p[0] = ColumnIndexNode(index=index)


def p_custom_column(p):
    """custom_column : bracketed_column_name
    | simple_column_name
    | column_index"""
    p[0] = p[1]


def p_custom_aggregation_column(p):
    """custom_aggregation_column : AGGREGATION_FUNCTION LPAREN custom_column RPAREN
    | AGGREGATION_FUNCTION LPAREN TIMES RPAREN"""
    function = str(p[1])
    column = p[3]
    if function == "size" and column == "*":
        column = ColumnNameNode("*")
    p[0] = AggregationNode(function, column)


def p_order_by_param(p):
    """order_by_param : custom_aggregation_column way
    | custom_column way"""
    sorting_way: SortingWay = p[2]
    parameter = p[1]
    p[0] = OrderByParameter(parameter=parameter, way=sorting_way)


def p_order_by_parameters_base(p):
    """order_by_parameters : order_by_param"""
    p[0] = list[OrderByParameter]([p[1]])


def p_order_by_parameters(p):
    """order_by_parameters : order_by_parameters COMMA order_by_parameters"""
    params_list = list[OrderByParameter]()
    params_list.extend(p[1])
    params_list.extend(p[3])
    p[0] = params_list


def p_order(p):
    """order : ORDER BY order_by_parameters"""
    p[0] = OrderByNode(parameters=p[3])


def p_order_empty(p):
    "order : empty"
    p[0] = None


def p_way_asc(p):
    """way : ASC
    | empty"""
    p[0] = SortingWay.ASC


def p_way_desc(p):
    "way : DESC"
    p[0] = SortingWay.DESC


###########################
# ========= Limit & Tail ==========
###########################


def p_limit_or_tail(p):
    """limit_or_tail : LIMIT POSITIVE_INTNUMBER
    | TAIL POSITIVE_INTNUMBER"""
    p[0] = (p[1], p[2])


def p_limit_or_tail_empty(p):
    """limit_or_tail : empty"""
    p[0] = None


###########################
# ========= VALUES​ =========
###########################


def p_value(p):
    """value : STRING
    | NUMBER"""

    p[0] = p[1]


def p_values(p):
    "values : values COMMA values"
    p[0] = []
    p[0].extend(p[1])
    p[0].extend(p[3])


###########################
# ===== INSERT VALUES​ ======
###########################


def p_values_end(p):
    "values : value"
    p[0] = [p[1]]


def p_single_values(p):
    "single_values : LPAREN values RPAREN"
    p[0] = p[2]


def p_insert_values(p):
    "insert_values : insert_values COMMA insert_values"
    p[0] = []
    p[0].extend(p[1])
    p[0].extend(p[3])


def p_insert_values_end(p):
    "insert_values : single_values"
    p[0] = [p[1]]


###########################
# ===== Insert Columns​​ =====
###########################


def p_icolumn(p):
    "icolumn : LPAREN icolumns RPAREN"
    p[0] = p[2]


def p_icolumn_empty(p):
    "icolumn : empty"
    p[0] = None


def p_icolumns(p):
    """icolumns : icolumns COMMA icolumns"""
    p[0] = []
    p[0].extend(p[1])
    p[0].extend(p[3])


def p_icolumns_base(p):
    """icolumns : column"""
    p[0] = [p[1]]


###########################
# ==== ASSIGNS STATEMENT​​ ===
###########################


def p_assign(p):
    "assign : column EQUAL value"
    p[0] = (p[1], p[3])


def p_assigns(p):
    "assigns : assign COMMA assigns"
    p[0] = [p[1]].extend(p[3])


def p_assigns_end(p):
    "assigns : assign"
    p[0] = [p[1]]

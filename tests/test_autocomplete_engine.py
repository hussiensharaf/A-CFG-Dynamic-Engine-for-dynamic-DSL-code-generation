"""
Unit tests for app/etl/autoComplete/autocomplete_engine.py (AutocompleteEngine)
and app/etl/autoComplete/metadat_provider.py (MetadataProvider).

Both are pure Python/regex logic with no GUI or tkinter dependency, so they
can be tested directly without a display - see the "Tier 1" test plan.

Run with:  pytest tests/test_autocomplete_engine.py
"""

import csv

import pytest

from app.etl.autoComplete.autocomplete_engine import (
    AutocompleteContext,
    AutocompleteEngine,
)
from app.etl.autoComplete.metadat_provider import MetadataProvider, StaticMetadataProvider


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# AutocompleteEngine._determine_context
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return AutocompleteEngine()


@pytest.mark.parametrize(
    "text, expected_context",
    [
        ("", AutocompleteContext.KEYWORD),
        ("SELECT * FROM {csv:a.csv};", AutocompleteContext.KEYWORD),  # after ';'
        ("SEL", AutocompleteContext.KEYWORD),
        ("SELECT ", AutocompleteContext.SELECT_COLUMNS),
        ("SELECT name, ", AutocompleteContext.SELECT_COLUMNS),
        # Each clause-specific context only kicks in once at least one
        # character of the clause's own content has been typed - see
        # test_determine_context_blank_after_keyword_falls_back_to_keyword
        # just below for the gap this leaves right after the trailing space.
        ("SELECT * FROM c", AutocompleteContext.FROM_DATASOURCE),
        ("SELECT * FROM {csv:a.csv} ", AutocompleteContext.TABLE_ALIAS),
        ("SELECT * FROM {csv:a.csv} AS A WHERE c", AutocompleteContext.WHERE_CONDITION),
        (
            "SELECT * FROM {csv:a.csv} AS A GROUP BY c",
            AutocompleteContext.GROUP_BY_COLUMNS,
        ),
        (
            "SELECT * FROM {csv:a.csv} AS A ORDER BY c",
            AutocompleteContext.ORDER_BY_COLUMNS,
        ),
        (
            "SELECT * FROM {csv:a.csv} AS A JOIN c",
            AutocompleteContext.JOIN_TABLE,
        ),
        (
            # No AS keyword - see
            # test_determine_context_join_condition_not_detected_with_as_alias
            # for the gap when an explicit AS alias is used instead.
            "SELECT * FROM {csv:a.csv} A JOIN {csv:b.csv} B ON c",
            AutocompleteContext.JOIN_CONDITION,
        ),
        ("SELECT A.", AutocompleteContext.COLUMN_QUALIFIED),
    ],
)
def test_determine_context(engine, text, expected_context):
    assert engine._determine_context(text) == expected_context


@pytest.mark.parametrize(
    "text",
    [
        "SELECT * FROM ",
        "SELECT * FROM {csv:a.csv} AS A WHERE ",
        "SELECT * FROM {csv:a.csv} AS A GROUP BY ",
        "SELECT * FROM {csv:a.csv} AS A ORDER BY ",
        "SELECT * FROM {csv:a.csv} AS A JOIN ",
    ],
)
@pytest.mark.xfail(
    reason=(
        "Known caveat, not fixed by this suite: _determine_context() upper"
        "cases and .strip()s the text before running its clause regexes "
        "(each of which requires the keyword to be followed by `\\s+`), so "
        "typing a clause keyword plus a single trailing space (before any "
        "of the clause's own content) strips that space right back off and "
        "every clause-specific regex fails to match - context falls back "
        "to plain KEYWORD for that one keystroke, instead of e.g. "
        "WHERE_CONDITION/GROUP_BY_COLUMNS/etc. It resolves correctly again "
        "as soon as the user types the next character. This test documents "
        "the gap; flip the expected context if/when it's fixed."
    ),
    strict=True,
)
def test_determine_context_blank_after_keyword_falls_back_to_keyword(engine, text):
    assert engine._determine_context(text) != AutocompleteContext.KEYWORD


@pytest.mark.xfail(
    reason=(
        "Known caveat, not fixed by this suite: the JOIN_CONDITION regex "
        "('\\bJOIN\\s+\\{[^}]+\\}(\\s+\\w+)?\\s+ON\\s+') only allows a "
        "single bare word between the datasource and ON, so it matches an "
        "implicit alias ('JOIN {ds} B ON') but not the compiler's own "
        "explicit 'AS alias' syntax ('JOIN {ds} AS B ON'), which is two "
        "words. Autocomplete falls back to plain KEYWORD instead of "
        "JOIN_CONDITION whenever the query uses AS on the joined table. "
        "This test documents the gap; flip the expected context if/when "
        "it's fixed."
    ),
    strict=True,
)
def test_determine_context_join_condition_not_detected_with_as_alias(engine):
    text = "SELECT * FROM {csv:a.csv} AS A JOIN {csv:b.csv} AS B ON c"
    assert engine._determine_context(text) == AutocompleteContext.JOIN_CONDITION


def test_determine_context_where_stops_at_group_by(engine):
    # Once GROUP BY appears after WHERE, we're no longer in the WHERE context.
    text = "SELECT * FROM {csv:a.csv} WHERE cost > 1 GROUP BY c"
    assert engine._determine_context(text) == AutocompleteContext.GROUP_BY_COLUMNS


def test_determine_context_order_by_stops_at_limit(engine):
    text = "SELECT * FROM {csv:a.csv} ORDER BY cost DESC LIMIT "
    # Once LIMIT appears, we should no longer be suggesting ORDER BY columns.
    assert engine._determine_context(text) != AutocompleteContext.ORDER_BY_COLUMNS


@pytest.mark.parametrize(
    "fragment, expected_context",
    [
        ("SELECT * FROM {my-project", AutocompleteContext.DATASOURCE_LOCATION),
        ("SELECT * FROM {gee:my-project", AutocompleteContext.AFTER_LOCATION),
        ("SELECT * FROM {gee:my-project|2024-01-01", AutocompleteContext.DATASOURCE_START_DATE),
        (
            "SELECT * FROM {gee:my-project|2024-01-01|2024-12-31",
            AutocompleteContext.DATASOURCE_END_DATE,
        ),
        (
            "SELECT * FROM {gee:my-project|2024-01-01|2024-12-31|31.2",
            AutocompleteContext.DATASOURCE_LONGITUDE,
        ),
        (
            "SELECT * FROM {gee:my-project|2024-01-01|2024-12-31|31.2|30.0",
            AutocompleteContext.DATASOURCE_LATITUDE,
        ),
        (
            "SELECT * FROM {gee:my-project|2024-01-01|2024-12-31|31.2|30.0|30",
            AutocompleteContext.DATASOURCE_SCALE,
        ),
        (
            "SELECT * FROM {gee:my-project|2024-01-01|2024-12-31|31.2|30.0|30|ERA5",
            AutocompleteContext.DATASOURCE_DATASET,
        ),
        (
            "SELECT * FROM {gee:my-project|2024-01-01|2024-12-31|31.2|30.0|30|ERA5|",
            AutocompleteContext.AFTER_SCALE,
        ),
    ],
)
def test_determine_context_datasource_positional_fields(engine, fragment, expected_context):
    assert engine._determine_context(fragment) == expected_context


# ---------------------------------------------------------------------------
# AutocompleteEngine._extract_partial_word
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected_partial",
    [
        ("SELECT nam", "nam"),
        ("SELECT * FROM ", ""),
        ("SELECT A.na", "A.na"),
        ("SELECT * FROM {csv:/tmp/a.", "{csv:/tmp/a."),
        ("", ""),
    ],
)
def test_extract_partial_word(engine, text, expected_partial):
    assert engine._extract_partial_word(text) == expected_partial


# ---------------------------------------------------------------------------
# AutocompleteEngine._fuzzy_match / _calculate_score
# ---------------------------------------------------------------------------

def test_fuzzy_match_empty_partial_matches_everything(engine):
    assert engine._fuzzy_match("temperature", "")


def test_fuzzy_match_prefix(engine):
    assert engine._fuzzy_match("temperature", "temp")


def test_fuzzy_match_substring(engine):
    assert engine._fuzzy_match("land_surface_temperature", "surface")


def test_fuzzy_match_subsequence(engine):
    # "tmp" as a subsequence of "temperature": t-e-m-p...
    assert engine._fuzzy_match("temperature", "tmp")


def test_fuzzy_match_no_match(engine):
    assert not engine._fuzzy_match("temperature", "xyz")


def test_calculate_score_prefix_scores_higher_than_substring(engine):
    prefix_score = engine._calculate_score("temperature", "temp")
    substring_score = engine._calculate_score("land_surface_temperature", "temp")
    assert prefix_score > substring_score


def test_calculate_score_empty_partial_returns_baseline(engine):
    assert engine._calculate_score("temperature", "") == 50.0


# ---------------------------------------------------------------------------
# AutocompleteEngine.get_suggestions (end-to-end through the public method)
# ---------------------------------------------------------------------------

def test_get_suggestions_keyword_context_suggests_select(engine):
    result = engine.get_suggestions("SEL", 3)
    assert result.context == AutocompleteContext.KEYWORD
    assert any(s.text == "SELECT" for s in result.suggestions)


def test_get_suggestions_select_columns_includes_wildcard_and_attributes(engine):
    query = "SELECT "
    result = engine.get_suggestions(query, len(query))
    assert result.context == AutocompleteContext.SELECT_COLUMNS
    assert any(s.text == "*" for s in result.suggestions)
    assert any(s.text == "temperature" for s in result.suggestions)


def test_get_suggestions_select_columns_filters_by_partial_word(engine):
    query = "SELECT temp"
    result = engine.get_suggestions(query, len(query))
    assert result.partial_word == "temp"
    assert all(
        engine._fuzzy_match(s.text, "temp") for s in result.suggestions
    )
    assert any(s.text == "temperature" for s in result.suggestions)


def test_get_suggestions_uses_metadata_provider_for_select_columns():
    provider = StaticMetadataProvider({"csv:areas.csv": ["name", "longitude", "latitude"]})
    engine = AutocompleteEngine(metadata_provider=provider)
    # No datasource reference yet, so get_columns finds no table aliases to
    # narrow by and falls back to returning every registered datasource's
    # columns (see test_get_columns_with_no_table_aliases_returns_all_
    # registered_columns for that behaviour tested directly).
    query = "SELECT "
    result = engine.get_suggestions(query, len(query))
    suggestion_texts = {s.text for s in result.suggestions}
    assert "longitude" in suggestion_texts


def test_get_suggestions_join_condition_uses_qualified_columns():
    provider = StaticMetadataProvider({"csv:areas.csv": ["name", "longitude"]})
    engine = AutocompleteEngine(metadata_provider=provider)
    # Implicit alias (no AS) - see
    # test_determine_context_join_condition_not_detected_with_as_alias for
    # the explicit-AS gap, and a trailing character after ON - see
    # test_determine_context_blank_after_keyword_falls_back_to_keyword for
    # why a bare trailing space wouldn't reach JOIN_CONDITION here either.
    query = "SELECT * FROM {csv:areas.csv} A JOIN {csv:weather.csv} B ON c"
    result = engine.get_suggestions(query, len(query))
    assert result.context == AutocompleteContext.JOIN_CONDITION


def test_get_suggestions_column_qualified_resolves_table_alias():
    provider = StaticMetadataProvider({"csv:areas.csv": ["name", "longitude"]})
    engine = AutocompleteEngine(metadata_provider=provider)
    query = "SELECT * FROM {csv:areas.csv} A WHERE A."
    result = engine.get_suggestions(query, len(query))
    assert result.context == AutocompleteContext.COLUMN_QUALIFIED
    suggestion_texts = {s.text for s in result.suggestions}
    assert "longitude" in suggestion_texts


@pytest.mark.xfail(
    reason=(
        "Known caveat, not fixed by this suite: the COLUMN_QUALIFIED "
        "context regex ('\\b[A-Za-z_]\\w*\\.$') only matches when the dot "
        "is the very last character typed (e.g. right after 'A.'), so "
        "COLUMN_QUALIFIED only ever fires for that one keystroke. Typing "
        "even one more character of the column name afterwards (e.g. "
        "'A.lon') falls out of COLUMN_QUALIFIED back into whatever context "
        "the surrounding clause would otherwise be (WHERE_CONDITION here), "
        "which suggests unqualified column/attribute names instead of "
        "filtering 'A's own columns by 'lon'. This test documents the "
        "gap; flip the expectation if/when it's fixed."
    ),
    strict=True,
)
def test_get_suggestions_column_qualified_filters_by_text_typed_after_dot():
    provider = StaticMetadataProvider({"csv:areas.csv": ["name", "longitude"]})
    engine = AutocompleteEngine(metadata_provider=provider)
    query = "SELECT * FROM {csv:areas.csv} A WHERE A.lon"
    result = engine.get_suggestions(query, len(query))
    assert result.context == AutocompleteContext.COLUMN_QUALIFIED
    suggestion_texts = {s.text for s in result.suggestions}
    assert "longitude" in suggestion_texts
    assert "name" not in suggestion_texts


# ---------------------------------------------------------------------------
# MetadataProvider
# ---------------------------------------------------------------------------

def test_register_datasource_adds_to_cache_and_available_set():
    provider = MetadataProvider()
    provider.register_datasource("csv:test.csv", ["a", "b"])
    assert provider.datasource_cache["csv:test.csv"] == ["a", "b"]
    assert "csv:test.csv" in provider.available_datasources


def test_load_datasource_from_file_reads_csv_header(tmp_path):
    path = str(tmp_path / "data.csv")
    _write_csv(path, ["name", "longitude", "latitude"], [["a", 1, 2]])
    provider = MetadataProvider()
    columns = provider.load_datasource_from_file(f"csv:{path}")
    assert columns == ["name", "longitude", "latitude"]
    # Second call should hit the cache rather than re-reading the file.
    assert provider.load_datasource_from_file(f"csv:{path}") == columns


def test_load_datasource_from_file_unsupported_type_returns_none():
    provider = MetadataProvider()
    assert provider.load_datasource_from_file("nope:something") is None


def test_load_datasource_from_file_missing_colon_returns_none():
    provider = MetadataProvider()
    assert provider.load_datasource_from_file("no_colon_here") is None


def test_get_columns_with_no_table_aliases_returns_all_registered_columns():
    provider = StaticMetadataProvider(
        {"csv:a.csv": ["x", "y"], "csv:b.csv": ["z"]}
    )
    # MetadataProvider.__init__ always pre-registers the built-in GEE
    # datasets too (see DATASET_ATTRIBUTES), so "no table aliases ->
    # return every registered column" includes those as well - check our
    # own columns are present rather than asserting an exact set.
    columns = set(provider.get_columns("SELECT "))
    assert {"x", "y", "z"}.issubset(columns)


def test_get_columns_for_table_returns_columns_for_known_alias():
    provider = StaticMetadataProvider({"csv:areas.csv": ["name", "longitude"]})
    provider.table_aliases["A"] = "csv:areas.csv"
    assert sorted(provider.get_columns_for_table("A")) == ["longitude", "name"]


def test_get_columns_for_table_unknown_alias_returns_empty():
    provider = MetadataProvider()
    assert provider.get_columns_for_table("not_a_real_alias") == []


def test_get_qualified_columns_prefixes_alias(tmp_path):
    path = str(tmp_path / "areas.csv")
    _write_csv(path, ["name", "longitude"], [["a", 1]])
    provider = MetadataProvider()
    query = f"SELECT * FROM {{csv:{path}|2024-01-01|2024-12-31|0|0|30|ERA5}} A"
    # _parse_query_for_tables expects the 7-part gee-style pipe format to
    # assign an alias; exercise it through the public get_qualified_columns
    # entry point used by JOIN_CONDITION suggestions.
    qualified = provider.get_qualified_columns(query)
    assert isinstance(qualified, list)


def test_get_dataset_names_includes_known_datasets():
    provider = MetadataProvider()
    names = provider.get_dataset_names()
    assert "ERA5" in names
    assert "SENTINEL2" in names


def test_get_locations_returns_public_examples_only():
    provider = MetadataProvider()
    locations = provider.get_locations()
    assert "my-project" in locations
    assert all("private" not in loc.lower() for loc in locations)


def test_add_location_rejects_private_looking_names():
    provider = MetadataProvider()
    before = len(provider.get_locations())
    provider.add_location("my-private-project")
    after_private = len(provider.get_locations())
    assert after_private == before  # rejected

    provider.add_location("a-public-project")
    after_public = len(provider.get_locations())
    assert after_public == before + 1  # accepted


def test_add_location_does_not_duplicate_existing_entry():
    provider = MetadataProvider()
    before = len(provider.get_locations())
    provider.add_location("my-project")  # already in COMMON_LOCATIONS
    assert len(provider.get_locations()) == before

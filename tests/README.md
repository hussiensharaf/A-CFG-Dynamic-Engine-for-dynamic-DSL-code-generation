# Test suite

Run everything with:

```
pip install -r requirements.txt    # adds pytest
python3 run_tests.py               # or: pytest tests/
```

167 tests, all pure Python/pandas logic - no GUI, no display, no network,
no cloud credentials. They run the same way in CI as on a developer's
machine.

## Layout

| File | Covers |
|---|---|
| `tests/conftest.py` | Shared fixtures: small CSVs written to `tmp_path` for the compiler/JOIN tests. |
| `tests/test_compiler.py` | End-to-end: compile a query string, execute the generated Python, check the result. Plain `SELECT`, `WHERE`/`ORDER BY`/`LIMIT`/`TAIL`, `DISTINCT`, `GROUP BY`, `INSERT`, and malformed-input error handling. |
| `tests/test_joins.py` | End-to-end `JOIN` support: all `how=` variants, chained joins, `JOIN` combined with `GROUP BY`/`ORDER BY`, positional (`[0]`) columns, multi-column `ON ... AND ...`, and tolerance-based (fuzzy) numeric joins. |
| `tests/test_etl_core.py` | Unit tests of `app/etl/core.py` directly: `extract`/`load` via CSV, and every `join()` branch (how=, tolerance=, empty frames, missing columns, invalid `how`). |
| `tests/test_etl_helpers.py` | Unit tests of the pure-logic helpers in `app/etl/helpers.py`: filtering, aggregation, `GROUP BY`/`ORDER BY` application, column-index resolution. |
| `tests/test_autocomplete_engine.py` | Unit tests of `app/etl/autoComplete/` (`AutocompleteEngine` + `MetadataProvider`): context detection, fuzzy matching, and datasource/column metadata lookup. |

## What's intentionally `xfail`

A handful of tests are marked `@pytest.mark.xfail(strict=True)` rather than
fixed or deleted. Each one documents a real, reproducible gap in current
behaviour, with the `reason=` explaining exactly what's wrong and why it
wasn't fixed here (usually: fixing it well needs a design decision, not a
one-line patch). If one of these starts **passing** unexpectedly,
`strict=True` turns that into a hard failure, which is the signal to flip
it to a normal assertion and delete the `xfail` marker - it means the
underlying bug got fixed (maybe as a side effect of something else) and
the test should now hold it to the correct behaviour permanently.

Current ones, grouped by area:

- **Coordinate-tolerance heuristic** (`yacc.py`'s auto-tolerance join):
  matches column names by substring (`lat`, `lon`, `x`, `y`), so a numeric
  column that merely contains one of those letters (`quantity`,
  `category`) gets an unwanted fuzzy match instead of an exact one.
- **Duplicate-coordinate-column cleanup** (same auto-tolerance join): after
  a join, any suffixed column whose name contains a coordinate substring is
  dropped outright, even when the `SELECT` list explicitly asked for it -
  so a genuine `B.longitude` collision silently resolves to table A's
  value instead of B's.
- **Autocomplete context detection** (`autocomplete_engine.py`): a clause
  keyword followed by exactly one trailing space (and nothing else yet)
  falls back to generic `KEYWORD` suggestions instead of the clause's own
  context, because the text is `.strip()`ped before the context regexes
  run; the `JOIN ... ON` context additionally isn't recognized when the
  joined table uses an explicit `AS alias` (only the implicit `{ds} alias`
  form matches); and the qualified-column (`A.`) context only fires for
  that one keystroke right after the dot, not once further column text has
  been typed.

## What's out of scope for this suite (not Tier 1)

Some parts of the codebase can't be exercised by a plain `pytest` run and
aren't covered here:

- **`app/gui/`** - the tkinter desktop UI. Needs a real (or virtual) display
  and manual/GUI-level testing; see the project's own manual test notes for
  that layer.
- **`app/cv/`** - computer-vision bird-detection code. Needs a live camera
  feed, and its `folder_reader.py` has a hardcoded Windows-only path, so it
  can't run headless in CI as-is.
- **Google Earth Engine extraction** (`app/etl/data/remote/`) - needs a real
  `ee.Authenticate()` session and a GEE project, which isn't something a
  test suite can fake meaningfully; the root `test.py` script is a manual
  smoke test for this, not part of the automated suite.

## Adding a new test

If you're changing the compiler, ETL helpers, or autocomplete logic: add a
test here first (or alongside your change) and run `python3 run_tests.py`
before pushing. If your change intentionally fixes one of the `xfail`
cases above, flip that test to a plain assertion (remove the `xfail`
marker) in the same change - `strict=True` will otherwise fail the build
for you as a reminder.

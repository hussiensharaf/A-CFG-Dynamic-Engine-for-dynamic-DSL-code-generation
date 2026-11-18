"""
Shared pytest fixtures for the QueryFlow test suite.

Every fixture that needs files on disk writes them into pytest's own
`tmp_path`, so nothing here depends on files that may or may not exist in
the repo (a.csv, testing_datasets/*), and nothing is left behind after a
run.
"""

import csv

import pytest


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


@pytest.fixture
def datasets(tmp_path):
    """
    A small family of related CSVs used across the compiler/JOIN tests.
    All share "name" as a join key unless noted otherwise.
    """
    paths = {}

    paths["areas"] = str(tmp_path / "areas.csv")
    _write_csv(
        paths["areas"],
        ["name", "longitude", "latitude"],
        [
            ["Wadi Araba", 32.446042, 29.12096],
            ["Ras Ghareb", 32.928549, 28.19849],
            ["Linz", 14.286110, 48.30639],
        ],
    )

    # No column-name collision with areas.csv (apart from the join key).
    paths["weather"] = str(tmp_path / "weather.csv")
    _write_csv(
        paths["weather"],
        ["name", "temperature", "humidity"],
        [
            ["Wadi Araba", 34.5, 22],
            ["Ras Ghareb", 31.2, 30],
            ["Linz", 18.9, 55],
        ],
    )

    # Deliberately collides on "longitude"/"latitude" with areas.csv, to
    # exercise pandas' merge-suffix behaviour.
    paths["weather_collide"] = str(tmp_path / "weather_collide.csv")
    _write_csv(
        paths["weather_collide"],
        ["name", "longitude", "latitude", "temperature"],
        [
            ["Wadi Araba", 32.9, 29.5, 34.5],
            ["Ras Ghareb", 32.8, 28.5, 31.2],
            ["Linz", 14.9, 48.5, 18.9],
        ],
    )

    # A row missing from weather_partial.csv, to exercise LEFT/RIGHT/FULL
    # JOIN producing an unmatched (NaN) row.
    paths["weather_partial"] = str(tmp_path / "weather_partial.csv")
    _write_csv(
        paths["weather_partial"],
        ["name", "temperature"],
        [
            ["Wadi Araba", 34.5],
            # Ras Ghareb and Linz deliberately missing
        ],
    )

    # A third table sharing the same "name" key, for chained-JOIN tests
    # (A JOIN B JOIN C).
    paths["soil"] = str(tmp_path / "soil.csv")
    _write_csv(
        paths["soil"],
        ["name", "soil_moisture"],
        [
            ["Wadi Araba", 0.12],
            ["Ras Ghareb", 0.18],
            ["Linz", 0.31],
        ],
    )

    paths["people"] = str(tmp_path / "people.csv")
    _write_csv(
        paths["people"],
        ["id", "name", "profession", "cost"],
        [
            [1, "Alice", "doctor", 5200],
            [2, "Bob", "doctor", 4800],
            [3, "Cara", "developer", 6100],
            [4, "Dan", "developer", 5900],
            [5, "Eve", "worker", 3000],
        ],
    )

    return paths


@pytest.fixture
def tolerance_datasets(tmp_path):
    """
    Two tables whose coordinates are close but not identical, to exercise
    etl.join's tolerance-based (merge_asof) fuzzy matching.
    """
    paths = {}

    paths["stations"] = str(tmp_path / "stations.csv")
    _write_csv(
        paths["stations"],
        ["station", "latitude"],
        [
            ["A", 29.12096],
            ["B", 28.19849],
            ["C", 48.30639],
        ],
    )

    # Same latitudes, shifted by a tiny amount within the 0.0001 tolerance
    # the compiler auto-applies to coordinate-like columns (see yacc.py),
    # and far outside it for the last row.
    paths["readings"] = str(tmp_path / "readings.csv")
    _write_csv(
        paths["readings"],
        ["latitude", "value"],
        [
            [29.12100, 101],   # within tolerance of station A (diff ~4e-5)
            [28.19853, 202],   # within tolerance of station B (diff ~4e-5)
            [10.00000, 999],   # far from any station - no match expected
        ],
    )

    return paths

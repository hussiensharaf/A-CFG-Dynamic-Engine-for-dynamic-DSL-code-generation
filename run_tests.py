#!/usr/bin/env python3
"""
Top-level test runner for this project's automated ("Tier 1") test suite.

This is a thin wrapper around pytest so there's one obvious command to run
before pushing a change - see tests/README.md for what is and isn't
covered, and why.

Usage:
    python3 run_tests.py            # run everything in tests/
    python3 run_tests.py -k join    # pass any extra args straight to pytest
    python3 run_tests.py -v
"""

import sys

import pytest

if __name__ == "__main__":
    args = sys.argv[1:] or ["tests/"]
    if not any(a == "tests/" or a.startswith("tests/") for a in args):
        args = ["tests/", *args]
    raise SystemExit(pytest.main(args))

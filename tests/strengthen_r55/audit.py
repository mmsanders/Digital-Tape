#!/usr/bin/env python3
"""Audit the #126 package: pinned sources, row census and case set."""
import oracle as O
import pins

EXPECTED_CASESET = "9ee1c5d6083dda0e9fd3f331a56dbc4903d659a157daa91615ff30212101ebea"


def main():
    census = O.plan_census()
    assert census["caseset_sha256"] == EXPECTED_CASESET, census
    assert (census["row1"], census["row2"], census["row3"]) == (12, 1, 27), census
    print(f"PASS pins {sorted(pins.PINS)} | rows {O.R.ROW1}, {O.R.ROW2}, {O.R.ROW3} | census {census}")


if __name__ == "__main__":
    main()

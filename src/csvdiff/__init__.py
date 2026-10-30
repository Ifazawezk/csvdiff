"""Compare two CSV files by key and report added, removed and changed rows."""

from csvdiff.core import Change, CompareOptions, Diff, diff_rows, load_csv, load_table, load_xlsx

__all__ = ["Change", "CompareOptions", "Diff", "diff_rows", "load_csv", "load_table", "load_xlsx"]
__version__ = "0.1.0"

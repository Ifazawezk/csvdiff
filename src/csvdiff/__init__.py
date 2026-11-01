"""Compare two CSV files by key and report added, removed and changed rows."""

from csvdiff.core import Change, CompareOptions, Diff, TableError, diff_rows, load_csv, load_table, load_xlsx

__all__ = ["Change", "CompareOptions", "Diff", "TableError", "diff_rows", "load_csv", "load_table", "load_xlsx"]
__version__ = "0.1.0"

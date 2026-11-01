import csv
import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

Row = dict[str, str]
Key = tuple[str, ...]


class TableError(ValueError):
    """A file that cannot be compared as it stands, such as a row that does not fit the header."""


class DuplicateKeyError(TableError):
    pass


class SourceRow(dict):
    """A row that remembers the line it came from, so errors can point at it."""

    __slots__ = ("line",)


@dataclass
class Change:
    key: Key
    # column -> (old value, new value)
    cells: dict[str, tuple[str, str]]


@dataclass
class CompareOptions:
    ignore_columns: tuple[str, ...] = ()
    # Numbers within this absolute difference count as equal (e.g. 0.01 for rounding).
    tolerance: float = 0.0
    ignore_case: bool = False
    # Ignore leading/trailing spaces and repeated inner spaces.
    ignore_whitespace: bool = False

    def same(self, a: str, b: str) -> bool:
        if a == b:
            return True
        if self.ignore_whitespace:
            a, b = " ".join(a.split()), " ".join(b.split())
        if self.ignore_case:
            a, b = a.casefold(), b.casefold()
        if a == b:
            return True
        if self.tolerance:
            x, y = _to_number(a), _to_number(b)
            if x is not None and y is not None:
                return abs(x - y) <= self.tolerance + 1e-12
        return False


def _to_number(s: str) -> float | None:
    try:
        return float(s.strip().replace(",", ""))
    except ValueError:
        return None


@dataclass
class Diff:
    key_columns: list[str]
    added: list[Row] = field(default_factory=list)
    removed: list[Row] = field(default_factory=list)
    changed: list[Change] = field(default_factory=list)
    columns_added: list[str] = field(default_factory=list)
    columns_removed: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed or self.columns_added or self.columns_removed)


def load_xlsx(path: str | Path, sheet: str | None = None) -> tuple[list[str], list[Row]]:
    """Read one sheet of an Excel file into (header, rows), with every value as text."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ImportError("reading .xlsx files needs openpyxl: pip install openpyxl") from None
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    header = _clean_header(next(rows_iter, None) or (), path)
    rows = []
    for line, values in enumerate(rows_iter, start=2):
        # Unlike a CSV line, an Excel cell cannot shift, so a stray cell past the header is
        # just outside the table.
        cells = (values or ())[:len(header)]
        if all(v is None for v in cells):
            continue
        rows.append(_make_row(header, [_cell_text(v) for v in cells], line))
    wb.close()
    return header, rows


def _clean_header(cells, source: str | Path) -> list[str]:
    """Trim header names and drop the empty cells a trailing delimiter leaves behind."""
    header = [str(c).strip() if c is not None else "" for c in cells]
    while header and not header[-1]:
        header.pop()
    repeated = sorted({h for h in header if h and header.count(h) > 1})
    if repeated:
        raise TableError(f"column(s) {repeated} appear more than once in {source}")
    return header


def _make_row(header: list[str], cells: list[str], line: int) -> SourceRow:
    """Pair cells with the header. Cells a short row does not have come out empty."""
    if len(cells) < len(header):
        cells = cells + [""] * (len(header) - len(cells))
    row = SourceRow(zip(header, cells))
    row.line = line
    return row


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Excel stores 42 as 42.0
    if isinstance(value, dt.datetime):
        # Excel has no separate date type, so midnight usually means "just a date".
        return value.date().isoformat() if value.time() == dt.time() else value.isoformat(sep=" ")
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def load_table(path: str | Path, encoding: str = "utf-8-sig", delimiter: str | None = None,
               sheet: str | None = None) -> tuple[list[str], list[Row]]:
    """Read a .csv/.tsv/.txt or .xlsx file."""
    if str(path).lower().endswith((".xlsx", ".xlsm")):
        return load_xlsx(path, sheet)
    return load_csv(path, encoding, delimiter)


def load_csv(path: str | Path, encoding: str = "utf-8-sig", delimiter: str | None = None) -> tuple[list[str], list[Row]]:
    """Read a CSV file into (header, rows). The delimiter is sniffed if not given.

    Short rows get empty values and blank rows are skipped, as when reading Excel. A row with
    values past the last column is an error: its cells have probably shifted, so comparing
    them would give wrong results.
    """
    with open(path, newline="", encoding=encoding) as f:
        sample = f.read(64 * 1024)
        f.seek(0)
        if delimiter is None:
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ","
        reader = csv.reader(f, delimiter=delimiter)
        # Exports from Excel and some databases often pad header names with spaces.
        header = _clean_header(next((cells for cells in reader if cells), []), path)
        width = len(header)
        rows = []
        end = reader.line_num
        for cells in reader:
            start, end = end + 1, reader.line_num  # a quoted value can span several lines
            if not any(c.strip() for c in cells):
                continue  # a blank line, or the ",,," Excel writes for an empty row
            if any(c.strip() for c in cells[width:]):
                raise TableError(f"{path} line {start}: {len(cells)} fields but the header has {width}")
            rows.append(_make_row(header, cells, start))
        return header, rows


def _index(rows: list[Row], key_columns: list[str], label: str) -> dict[Key, Row]:
    index: dict[Key, Row] = {}
    for n, row in enumerate(rows, start=2):  # line 1 is the header
        missing = [k for k in key_columns if k not in row]
        if missing:
            raise KeyError(f"key column(s) {missing} not found in {label}")
        key = tuple(row[k] for k in key_columns)
        if key in index:
            line = getattr(row, "line", n)
            raise DuplicateKeyError(f"duplicate key {key} in {label} (line {line})")
        index[key] = row
    return index


def _columns(rows: list[Row], header: list[str] | None, key_columns: list[str], label: str) -> list[str]:
    """A file's columns: its header if we have one, otherwise the keys of its first row."""
    if header is None:
        return list(rows[0]) if rows else []
    missing = [k for k in key_columns if k not in header]
    if missing:
        raise KeyError(f"key column(s) {missing} not found in {label}")
    return list(header)


def diff_rows(old: list[Row], new: list[Row], key_columns: list[str],
              options: CompareOptions | None = None,
              old_columns: list[str] | None = None, new_columns: list[str] | None = None) -> Diff:
    """Match rows by key_columns and compare the columns both files share.

    Pass the headers from load_table as old_columns and new_columns. Without them the
    columns are read from the first row, so a table with no rows appears to have none.
    """
    opts = options or CompareOptions()
    old_cols = _columns(old, old_columns, key_columns, "old file")
    new_cols = _columns(new, new_columns, key_columns, "new file")
    old_idx = _index(old, key_columns, "old file")
    new_idx = _index(new, key_columns, "new file")

    shared = [c for c in old_cols if c in new_cols and c not in key_columns and c not in opts.ignore_columns]

    d = Diff(
        key_columns=key_columns,
        columns_added=[c for c in new_cols if c not in old_cols and c not in opts.ignore_columns],
        columns_removed=[c for c in old_cols if c not in new_cols and c not in opts.ignore_columns],
    )
    for key, row in new_idx.items():
        if key not in old_idx:
            d.added.append(row)
    for key, row in old_idx.items():
        if key not in new_idx:
            d.removed.append(row)
            continue
        other = new_idx[key]
        cells = {c: (row[c], other[c]) for c in shared if not opts.same(row[c], other[c])}
        if cells:
            d.changed.append(Change(key, cells))
    return d

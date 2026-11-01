import datetime as dt
import re
import zipfile

import pytest

openpyxl = pytest.importorskip("openpyxl")

from csvdiff.cli import main  # noqa: E402
from csvdiff.core import DuplicateKeyError, TableError, diff_rows, load_table  # noqa: E402


def make_xlsx(path, rows, sheet="Sheet1"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    wb.save(path)
    return str(path)


def test_reads_values_as_text(tmp_path):
    p = make_xlsx(tmp_path / "a.xlsx", [
        [" id ", "price", "joined", "note"],
        [1, 9.5, dt.date(2026, 1, 5), None],
        [2, 10.0, dt.datetime(2026, 2, 1, 9, 30), "ok"],
        [None, None, None, None],
    ])
    header, rows = load_table(p)
    assert header == ["id", "price", "joined", "note"]
    assert rows == [
        {"id": "1", "price": "9.5", "joined": "2026-01-05", "note": ""},
        {"id": "2", "price": "10", "joined": "2026-02-01 09:30:00", "note": "ok"},
    ]


def without_dimension(path):
    """Remove the sheet size some writers leave out, so short rows stay short when read back."""
    with zipfile.ZipFile(path) as source:
        parts = [(info, source.read(info.filename)) for info in source.infolist()]
    with zipfile.ZipFile(path, "w") as target:
        for info, data in parts:
            if info.filename.startswith("xl/worksheets/"):
                data = re.sub(rb"<dimension[^>]*/>", b"", data)
            target.writestr(info, data)
    return path


def test_short_rows_get_empty_values(tmp_path):
    p = without_dimension(make_xlsx(tmp_path / "a.xlsx", [["id", "name", "salary"], [1, "Ali"], [2, "Sara", 7000]]))
    header, rows = load_table(p)
    assert header == ["id", "name", "salary"]
    assert rows == [
        {"id": "1", "name": "Ali", "salary": ""},
        {"id": "2", "name": "Sara", "salary": "7000"},
    ]


def test_cells_outside_the_table_are_left_out(tmp_path):
    p = make_xlsx(tmp_path / "a.xlsx", [
        ["id", "name", None, None],
        [1, "Ali", None, None],
        [None, None, None, "side note"],
        [2, "Sara", "stray", None],
    ])
    header, rows = load_table(p)
    assert header == ["id", "name"]
    assert rows == [{"id": "1", "name": "Ali"}, {"id": "2", "name": "Sara"}]


def test_repeated_column_name_is_an_error(tmp_path):
    p = make_xlsx(tmp_path / "a.xlsx", [["id", "price", "price"], [1, 10, 5]])
    with pytest.raises(TableError, match="price"):
        load_table(p)


def test_duplicate_key_reports_the_sheet_row(tmp_path):
    p = make_xlsx(tmp_path / "a.xlsx", [["id", "name"], [1, "Ali"], [None, None], [1, "Sara"]])
    _, rows = load_table(p)
    with pytest.raises(DuplicateKeyError, match="line 4"):
        diff_rows(rows, rows, ["id"])


def test_compare_excel_with_csv(tmp_path, capsys):
    xlsx = make_xlsx(tmp_path / "jan.xlsx", [["id", "salary"], [1, 9000], [2, 7000]], sheet="Payroll")
    csv_file = tmp_path / "feb.csv"
    csv_file.write_text("id,salary\n1,9500\n2,7000\n", encoding="utf-8")
    assert main([xlsx, str(csv_file), "-k", "id", "--sheet", "Payroll", "--summary"]) == 1
    assert capsys.readouterr().out.strip() == "0 added, 0 removed, 1 changed"

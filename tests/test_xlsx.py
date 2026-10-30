import datetime as dt

import pytest

openpyxl = pytest.importorskip("openpyxl")

from csvdiff.cli import main  # noqa: E402
from csvdiff.core import load_table  # noqa: E402


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


def test_compare_excel_with_csv(tmp_path, capsys):
    xlsx = make_xlsx(tmp_path / "jan.xlsx", [["id", "salary"], [1, 9000], [2, 7000]], sheet="Payroll")
    csv_file = tmp_path / "feb.csv"
    csv_file.write_text("id,salary\n1,9500\n2,7000\n", encoding="utf-8")
    assert main([xlsx, str(csv_file), "-k", "id", "--sheet", "Payroll", "--summary"]) == 1
    assert capsys.readouterr().out.strip() == "0 added, 0 removed, 1 changed"

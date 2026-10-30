import pytest

from csvdiff.core import DuplicateKeyError, diff_rows, load_csv


OLD = [
    {"id": "1", "name": "Ali", "city": "Doha", "salary": "9000"},
    {"id": "2", "name": "Sara", "city": "Cairo", "salary": "7000"},
    {"id": "3", "name": "Omar", "city": "Doha", "salary": "8000"},
]
NEW = [
    {"id": "1", "name": "Ali", "city": "Doha", "salary": "9500"},
    {"id": "3", "name": "Omar", "city": "Doha", "salary": "8000"},
    {"id": "4", "name": "Mona", "city": "Dubai", "salary": "8800"},
]


def test_added_removed_changed():
    d = diff_rows(OLD, NEW, ["id"])
    assert [r["id"] for r in d.added] == ["4"]
    assert [r["id"] for r in d.removed] == ["2"]
    assert len(d.changed) == 1
    assert d.changed[0].key == ("1",)
    assert d.changed[0].cells == {"salary": ("9000", "9500")}
    assert not d.is_empty


def test_identical_files_are_empty():
    assert diff_rows(OLD, OLD, ["id"]).is_empty


def test_row_order_does_not_matter():
    assert diff_rows(OLD, list(reversed(OLD)), ["id"]).is_empty


def test_composite_key():
    old = [{"year": "2025", "month": "1", "sales": "10"}, {"year": "2025", "month": "2", "sales": "12"}]
    new = [{"year": "2025", "month": "1", "sales": "11"}, {"year": "2025", "month": "2", "sales": "12"}]
    d = diff_rows(old, new, ["year", "month"])
    assert d.changed[0].key == ("2025", "1")


def test_column_changes():
    new = [{**r, "team": "data"} for r in OLD]
    for r in new:
        del r["city"]
    d = diff_rows(OLD, new, ["id"])
    assert d.columns_added == ["team"]
    assert d.columns_removed == ["city"]
    assert d.changed == []  # only shared columns are compared


def test_duplicate_key_is_an_error():
    with pytest.raises(DuplicateKeyError, match="line 5"):
        diff_rows(OLD + [OLD[0]], NEW, ["id"])


def test_missing_key_column():
    with pytest.raises(KeyError, match="email"):
        diff_rows(OLD, NEW, ["email"])


def test_load_csv_sniffs_delimiter(tmp_path):
    p = tmp_path / "semi.csv"
    p.write_text("id;name\n1;Ali\n2;Sara\n", encoding="utf-8")
    header, rows = load_csv(p)
    assert header == ["id", "name"]
    assert rows[1] == {"id": "2", "name": "Sara"}


def test_load_csv_handles_bom(tmp_path):
    p = tmp_path / "bom.csv"
    p.write_bytes("﻿id,name\n1,Ali\n".encode("utf-8"))
    header, _ = load_csv(p)
    assert header == ["id", "name"]


def test_compare_options():
    from csvdiff.core import CompareOptions

    old = [{"id": "1", "name": "Ali Hassan", "price": "10.004", "updated": "mon"}]
    new = [{"id": "1", "name": "  ali   hassan ", "price": "10.00", "updated": "tue"}]
    assert len(diff_rows(old, new, ["id"]).changed[0].cells) == 3

    opts = CompareOptions(ignore_columns=("updated",), tolerance=0.01, ignore_case=True, ignore_whitespace=True)
    assert diff_rows(old, new, ["id"], opts).is_empty


def test_tolerance_handles_thousands_separators():
    from csvdiff.core import CompareOptions

    assert CompareOptions(tolerance=0.5).same("1,000.2", "1000")
    assert not CompareOptions(tolerance=0.5).same("1,000.2", "1001")
    assert not CompareOptions(tolerance=0.5).same("abc", "abd")

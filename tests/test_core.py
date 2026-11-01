import pytest

from csvdiff.core import DuplicateKeyError, TableError, diff_rows, load_csv


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


def test_headers_decide_column_changes_when_a_file_has_no_rows():
    d = diff_rows([], NEW, ["id"], None, list(NEW[0]), list(NEW[0]))
    assert d.columns_added == []
    assert d.columns_removed == []
    assert [r["id"] for r in d.added] == ["1", "3", "4"]


def test_real_column_change_still_reported_when_a_file_has_no_rows():
    d = diff_rows([], [], ["id"], None, ["id", "city"], ["id", "team"])
    assert d.columns_added == ["team"]
    assert d.columns_removed == ["city"]


def test_missing_key_column_in_a_header_with_no_rows():
    with pytest.raises(KeyError, match="old file"):
        diff_rows([], NEW, ["id"], None, ["name"], list(NEW[0]))
    with pytest.raises(KeyError, match="new file"):
        diff_rows(OLD, [], ["id"], None, list(OLD[0]), ["name"])


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


def csv_file(tmp_path, text):
    p = tmp_path / "data.csv"
    p.write_text(text, encoding="utf-8", newline="")
    return p


def test_short_rows_get_empty_values(tmp_path):
    _, rows = load_csv(csv_file(tmp_path, "id,name,salary\n1,Ali\n2\n"))
    assert rows == [{"id": "1", "name": "Ali", "salary": ""}, {"id": "2", "name": "", "salary": ""}]


def test_short_rows_compare_with_every_option(tmp_path):
    from csvdiff.core import CompareOptions

    _, short = load_csv(csv_file(tmp_path, "id,name,salary\n1,Ali\n"))
    full = [{"id": "1", "name": "Ali", "salary": "9000"}]
    for opts in (CompareOptions(), CompareOptions(tolerance=0.01), CompareOptions(ignore_whitespace=True),
                 CompareOptions(ignore_case=True)):
        assert diff_rows(full, short, ["id"], opts).changed[0].cells == {"salary": ("9000", "")}


def test_row_with_too_many_fields_names_the_file_and_line(tmp_path):
    p = csv_file(tmp_path, "id,city,salary\n1,Doha,9000\n2,Doha, Qatar,7000\n")
    with pytest.raises(TableError, match=r"line 3: 4 fields but the header has 3") as e:
        load_csv(p)
    assert str(p) in str(e.value)


def test_trailing_delimiters_are_not_extra_fields(tmp_path):
    header, rows = load_csv(csv_file(tmp_path, "id,name\n1,Ali,\n2,Sara,,  ,\n"))
    assert header == ["id", "name"]
    assert rows == [{"id": "1", "name": "Ali"}, {"id": "2", "name": "Sara"}]


def test_empty_columns_at_the_end_of_the_header_are_dropped(tmp_path):
    header, rows = load_csv(csv_file(tmp_path, "id,name,,\n1,Ali,,\n"))
    assert header == ["id", "name"]
    assert rows == [{"id": "1", "name": "Ali"}]


def test_value_under_an_empty_header_cell_is_not_lost(tmp_path):
    with pytest.raises(TableError, match="line 2"):
        load_csv(csv_file(tmp_path, "id,name,\n1,Ali,note\n"))


def test_blank_rows_are_skipped(tmp_path):
    _, rows = load_csv(csv_file(tmp_path, "\n\nid,name\n1,Ali\n\n,\n  ,  \n2,Sara\n,\n,\n"))
    assert [r["id"] for r in rows] == ["1", "2"]


def test_repeated_column_name_is_an_error(tmp_path):
    with pytest.raises(TableError, match=r"\['price'\] appear more than once"):
        load_csv(csv_file(tmp_path, "id,price, price \n1,10,5\n"))


def test_unnamed_columns_are_not_repeated_names(tmp_path):
    header, _ = load_csv(csv_file(tmp_path, "id,,,name\n1,,,Ali\n"))
    assert header == ["id", "", "", "name"]


def test_duplicate_key_reports_the_real_line(tmp_path):
    p = csv_file(tmp_path, 'id,note\n1,"one\ntwo\nthree"\n\n,\n2,x\n1,y\n')
    _, rows = load_csv(p)
    assert [r["id"] for r in rows] == ["1", "2", "1"]
    with pytest.raises(DuplicateKeyError, match="line 8"):
        diff_rows(rows, rows, ["id"])


def test_row_problem_after_a_multi_line_value_reports_its_first_line(tmp_path):
    p = csv_file(tmp_path, 'id,note\n1,"one\ntwo"\n2,"three\nfour",extra\n')
    with pytest.raises(TableError, match="line 4"):
        load_csv(p)


def test_compare_options():
    from csvdiff.core import CompareOptions

    old = [{"id": "1", "name": "Ali Hassan", "price": "10.004", "updated": "mon"}]
    new = [{"id": "1", "name": "  ali   hassan ", "price": "10.00", "updated": "tue"}]
    assert len(diff_rows(old, new, ["id"]).changed[0].cells) == 3

    opts = CompareOptions(ignore_columns=("updated",), tolerance=0.01, ignore_case=True, ignore_whitespace=True)
    assert diff_rows(old, new, ["id"], opts).is_empty


def test_ignored_columns_are_left_out_of_column_changes():
    from csvdiff.core import CompareOptions

    old = [{"id": "1", "city": "Doha", "old_run": "5"}]
    new = [{"id": "1", "city": "Doha", "new_run": "6", "team": "data"}]
    d = diff_rows(old, new, ["id"], CompareOptions(ignore_columns=("old_run", "new_run")))
    assert d.columns_removed == []
    assert d.columns_added == ["team"]  # columns not named in --ignore are still reported


def test_tolerance_handles_thousands_separators():
    from csvdiff.core import CompareOptions

    assert CompareOptions(tolerance=0.5).same("1,000.2", "1000")
    assert not CompareOptions(tolerance=0.5).same("1,000.2", "1001")
    assert not CompareOptions(tolerance=0.5).same("abc", "abd")


def test_load_csv_strips_header_spaces(tmp_path):
    p = tmp_path / "padded.csv"
    p.write_text(" id , name \n1,Ali\n", encoding="utf-8")
    header, rows = load_csv(p)
    assert header == ["id", "name"]
    assert rows == [{"id": "1", "name": "Ali"}]

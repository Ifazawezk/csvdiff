from csvdiff.cli import main


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cli_reports_and_exits_1(tmp_path, capsys):
    old = write(tmp_path / "old.csv", "id,name,salary\n1,Ali,9000\n2,Sara,7000\n")
    new = write(tmp_path / "new.csv", "id,name,salary\n1,Ali,9500\n3,Omar,8000\n")
    code = main([old, new, "--key", "id", "--color", "never"])
    out = capsys.readouterr().out
    assert code == 1
    assert "+ id=3  name=Omar, salary=8000" in out
    assert "- id=2  name=Sara, salary=7000" in out
    assert "~ id=1" in out
    assert "salary: '9000' -> '9500'" in out
    assert out.strip().endswith("1 added, 1 removed, 1 changed")


def test_cli_identical_exits_0(tmp_path, capsys):
    a = write(tmp_path / "a.csv", "id,x\n1,2\n")
    assert main([a, a, "-k", "id"]) == 0
    assert "0 added, 0 removed, 0 changed" in capsys.readouterr().out


def test_cli_errors_exit_2(tmp_path, capsys):
    a = write(tmp_path / "a.csv", "id,x\n1,2\n")
    assert main([a, str(tmp_path / "missing.csv"), "-k", "id"]) == 2
    assert main([a, a, "-k", "email"]) == 2
    err = capsys.readouterr().err
    assert "missing.csv" in err and "email" in err


def test_header_only_file_does_not_look_like_new_columns(tmp_path, capsys):
    empty = write(tmp_path / "empty.csv", "id,name\n")
    full = write(tmp_path / "full.csv", "id,name\n1,Ali\n")
    assert main([empty, full, "-k", "id", "--color", "never"]) == 1
    out = capsys.readouterr().out
    assert "column" not in out
    assert out.strip().endswith("1 added, 0 removed, 0 changed")


def test_wrong_key_is_an_error_even_with_no_rows(tmp_path, capsys):
    empty = write(tmp_path / "empty.csv", "id,name\n")
    assert main([empty, empty, "-k", "email"]) == 2
    assert "email" in capsys.readouterr().err


def test_cli_options(tmp_path, capsys):
    old = write(tmp_path / "old.csv", "id,name,price,updated\n1,Ali,10.004,mon\n")
    new = write(tmp_path / "new.csv", "id,name,price,updated\n1,ALI,10.00,tue\n")
    assert main([old, new, "-k", "id"]) == 1
    assert main([old, new, "-k", "id", "--ignore", "updated", "-t", "0.01", "--ignore-case"]) == 0


def test_ignoring_a_new_column_means_the_files_match(tmp_path, capsys):
    old = write(tmp_path / "old.csv", "id,name\n1,Ali\n")
    new = write(tmp_path / "new.csv", "id,name,etl_run\n1,Ali,77\n")
    assert main([old, new, "-k", "id"]) == 1
    assert main([old, new, "-k", "id", "--ignore", "etl_run"]) == 0


def test_short_rows_work_in_every_output_format(tmp_path, capsys):
    import json

    old = write(tmp_path / "old.csv", "id,name,salary\n1,Ali,9000\n")
    new = write(tmp_path / "new.csv", "id,name,salary\n1,Ali\n3,Omar\n")

    assert main([old, new, "-k", "id", "--color", "never"]) == 1
    out = capsys.readouterr().out
    assert "salary: '9000' -> ''" in out
    assert "None" not in out

    assert main([old, new, "-k", "id", "-f", "markdown"]) == 1
    assert "| 1 | salary | 9000 |  |" in capsys.readouterr().out

    assert main([old, new, "-k", "id", "-f", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["changed"][0]["cells"] == {"salary": {"old": "9000", "new": ""}}
    assert data["added"] == [{"id": "3", "name": "Omar", "salary": ""}]


def test_row_with_extra_fields_exits_2_with_its_line(tmp_path, capsys):
    good = write(tmp_path / "good.csv", "id,city,salary\n1,Doha,9000\n")
    bad = write(tmp_path / "bad.csv", "id,city,salary\n1,Doha, Qatar,9000\n")
    assert main([good, bad, "-k", "id"]) == 2
    captured = capsys.readouterr()
    assert "bad.csv line 2: 4 fields but the header has 3" in captured.err
    assert captured.out == ""


def test_blank_rows_from_excel_exports_do_not_count(tmp_path, capsys):
    clean = write(tmp_path / "clean.csv", "id,name\n1,Ali\n")
    padded = write(tmp_path / "padded.csv", "id,name\n1,Ali\n,\n,\n")
    assert main([clean, padded, "-k", "id"]) == 0


def test_repeated_column_name_exits_2_instead_of_hiding_a_change(tmp_path, capsys):
    old = write(tmp_path / "old.csv", "id,price,price\n1,10,5\n")
    new = write(tmp_path / "new.csv", "id,price,price\n1,99,5\n")
    assert main([old, new, "-k", "id"]) == 2
    assert "price" in capsys.readouterr().err


def _pair(tmp_path):
    old = write(tmp_path / "old.csv", "id,name,salary\n1,Ali,9000\n2,Sara,7000\n")
    new = write(tmp_path / "new.csv", "id,name,salary\n1,Ali,9500\n3,Omar,8000\n")
    return old, new


def test_json_output(tmp_path, capsys):
    import json

    old, new = _pair(tmp_path)
    main([old, new, "-k", "id", "-f", "json"])
    data = json.loads(capsys.readouterr().out)
    assert data["summary"] == {"added": 1, "removed": 1, "changed": 1, "columns_added": [], "columns_removed": []}
    assert data["changed"][0] == {"key": {"id": "1"}, "cells": {"salary": {"old": "9000", "new": "9500"}}}
    assert data["added"][0]["name"] == "Omar"


def test_markdown_output(tmp_path, capsys):
    old, new = _pair(tmp_path)
    main([old, new, "-k", "id", "-f", "markdown"])
    out = capsys.readouterr().out
    assert out.startswith("**1 added, 1 removed, 1 changed**")
    assert "| 3 | Omar | 8000 |" in out
    assert "| 1 | salary | 9000 | 9500 |" in out


def test_summary_only(tmp_path, capsys):
    old, new = _pair(tmp_path)
    main([old, new, "-k", "id", "--summary"])
    assert capsys.readouterr().out.strip() == "1 added, 1 removed, 1 changed"

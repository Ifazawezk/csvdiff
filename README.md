# csvdiff

Compare two CSV files row by row, matched by a key column, and see exactly what was added, removed and changed. Useful for checking a new data export against last month's, reviewing changes to a lookup table, or testing that a pipeline still produces the same output.

Works with CSV and Excel (.xlsx) files. Pure Python; reading Excel needs `openpyxl`.

```
$ csvdiff examples/employees_jan.csv examples/employees_feb.csv --key id
+ column manager
+ id=105  name=Mona Fathy, department=Sales, salary=7200, manager=104
- id=102  name=Sara Adel, department=Sales, salary=7000
~ id=101
    salary: '9000' -> '9500'
~ id=104
    department: 'HR' -> 'Finance'
1 added, 1 removed, 2 changed; columns: 1 added, 0 removed
```

Rows are matched by key, so row order does not matter.

## Install

```bash
pip install git+https://github.com/Ifazawezk/csvdiff.git
# with Excel support:
pip install "csvdiff-cli[excel] @ git+https://github.com/Ifazawezk/csvdiff.git"
```

## Usage

```bash
csvdiff old.csv new.csv --key id
csvdiff sales_2025.csv sales_2026.csv --key year,month      # composite key
csvdiff a.csv b.csv -k id --ignore updated_at,etl_run_id    # skip noisy columns
csvdiff a.csv b.csv -k id --tolerance 0.01                  # ignore rounding differences
csvdiff a.csv b.csv -k id --ignore-case --ignore-whitespace
csvdiff a.csv b.csv -k id --format json > changes.json
csvdiff a.csv b.csv -k id --format markdown                 # paste into a PR or issue
csvdiff a.csv b.csv -k id --summary                         # just the counts
csvdiff january.xlsx february.xlsx -k id --sheet Payroll    # Excel files
csvdiff export.xlsx export.csv -k id                        # or one of each
```

| Option | |
|---|---|
| `-k, --key` | column(s) that identify a row, comma separated (required) |
| `-i, --ignore` | columns to leave out of the comparison |
| `-t, --tolerance` | numbers within this difference count as equal; thousands separators are handled |
| `--ignore-case` | compare text case-insensitively |
| `--ignore-whitespace` | ignore leading, trailing and repeated spaces |
| `-f, --format` | `text` (default), `json` or `markdown` |
| `-s, --summary` | only print the counts |
| `--delimiter` | field delimiter; detected automatically (`,` `;` tab `\|`) if not given |
| `--sheet` | for .xlsx files, the sheet to read (default: the first) |
| `--encoding` | file encoding, default UTF-8 with or without a BOM (Excel exports work) |
| `--color` | `auto`, `always` or `never` |

**Exit codes:** `0` when the files match, `1` when there are differences, `2` on errors such as a missing file, a missing key column or a duplicate key. That makes it easy to use in scripts and CI:

```bash
csvdiff expected.csv output.csv -k id --summary || echo "output changed"
```

## Markdown output

```
$ csvdiff examples/employees_jan.csv examples/employees_feb.csv -k id -f markdown
```

**1 added, 1 removed, 2 changed**

Columns added: manager. Columns removed: none.

### Added

| id | name | department | salary | manager |
|---|---|---|---|---|
| 105 | Mona Fathy | Sales | 7200 | 104 |

### Removed

| id | name | department | salary |
|---|---|---|---|
| 102 | Sara Adel | Sales | 7000 |

### Changed

| id | column | old | new |
|---|---|---|---|
| 101 | salary | 9000 | 9500 |
| 104 | department | HR | Finance |

## Use it from Python

```python
from csvdiff import CompareOptions, diff_rows, load_csv

_, old = load_csv("jan.csv")
_, new = load_csv("feb.csv")
d = diff_rows(old, new, ["id"], CompareOptions(tolerance=0.01))
for change in d.changed:
    print(change.key, change.cells)
```

## Notes

- Only columns present in both files are compared. Added or removed columns are reported separately.
- Duplicate keys are treated as an error, since a diff by key would be ambiguous. Use a composite key if one column is not unique.
- Excel values are compared as text: whole numbers lose the `.0` Excel adds, and dates become `YYYY-MM-DD`. Header names are trimmed.
- Both files are loaded into memory, which is fine for files up to a few hundred MB.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT

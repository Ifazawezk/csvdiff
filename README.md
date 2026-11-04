# csvdiff

Compare two CSV or Excel files by a key column and see which rows were added, removed or changed. Handy for checking a new export against last month's, or for making sure a pipeline still produces the same output.

## Install

```bash
pip install git+https://github.com/Ifazawezk/csvdiff.git
# with Excel support:
pip install "csvdiff-cli[excel] @ git+https://github.com/Ifazawezk/csvdiff.git"
```

It's pure Python. Reading .xlsx files needs `openpyxl`, which the second command installs.

## Example

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

Rows are matched by key, so their order in the file doesn't matter. Some other ways to call it:

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

`--format markdown` prints the counts, the added and removed columns, and tables of the added, removed and changed rows, ready to paste into a pull request.

## Options

| Option | |
|---|---|
| `-k, --key` | column(s) that identify a row, comma separated (required) |
| `-i, --ignore` | columns to leave out of the comparison, including when they are added or removed |
| `-t, --tolerance` | numbers within this difference count as equal; thousands separators are handled |
| `--ignore-case` | compare text case-insensitively |
| `--ignore-whitespace` | ignore leading, trailing and repeated spaces |
| `-f, --format` | `text` (default), `json` or `markdown` |
| `-s, --summary` | only print the counts |
| `--delimiter` | field delimiter, one character or `\t` for a tab; detected automatically (`,` `;` tab `\|`) if not given |
| `--sheet` | for .xlsx files, the sheet to read (default: the first) |
| `--encoding` | file encoding, default UTF-8 with or without a BOM (Excel exports work) |
| `--color` | `auto`, `always` or `never` |

## Exit codes

`0` if the files match, `1` if they differ, and `2` on errors such as a missing file, a missing key column, a duplicate key or a row that doesn't fit the header. That makes it easy to use in a script or CI job:

```bash
csvdiff expected.csv output.csv -k id --summary || echo "output changed"
```

## From Python

```python
from csvdiff import CompareOptions, diff_rows, load_csv

old_columns, old = load_csv("jan.csv")
new_columns, new = load_csv("feb.csv")
d = diff_rows(old, new, ["id"], CompareOptions(tolerance=0.01),
              old_columns=old_columns, new_columns=new_columns)
for change in d.changed:
    print(change.key, change.cells)
```

## Limits

Only columns present in both files are compared. Added and removed columns are reported from each file's header, so a file with a header and no rows still compares correctly. Duplicate keys are an error because a diff by key would be ambiguous; use a composite key if one column isn't unique. A column name that appears twice in a header is an error for the same reason.

A row shorter than the header gets empty values for the missing cells. Blank rows are skipped, including the `,,,` rows Excel writes when saving as CSV. A row with values past the last column is an error that names the file and line, since its cells have probably shifted (an unquoted comma, for example). Extra empty fields from a trailing delimiter are fine.

Excel values are compared as text: whole numbers lose the `.0` Excel adds, dates become `YYYY-MM-DD`, header names are trimmed, and cells to the right of the last named column are left out.

Both files are loaded into memory, which is fine up to a few hundred MB. Output is always UTF-8, even when piped or redirected to a file on Windows.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT

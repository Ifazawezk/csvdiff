"""Command-line interface: csvdiff OLD.csv NEW.csv --key id"""

import argparse
import sys

from csvdiff.core import DuplicateKeyError, Diff, diff_rows, load_csv


def format_text(d: Diff, color: bool = False) -> str:
    red, green, yellow, reset = ("\033[31m", "\033[32m", "\033[33m", "\033[0m") if color else ("", "", "", "")
    lines = []
    for c in d.columns_added:
        lines.append(f"{green}+ column {c}{reset}")
    for c in d.columns_removed:
        lines.append(f"{red}- column {c}{reset}")
    for row in d.added:
        lines.append(f"{green}+ {_key_label(d, row)}  {_row_preview(row, d.key_columns)}{reset}")
    for row in d.removed:
        lines.append(f"{red}- {_key_label(d, row)}  {_row_preview(row, d.key_columns)}{reset}")
    for ch in d.changed:
        label = ", ".join(f"{k}={v}" for k, v in zip(d.key_columns, ch.key))
        lines.append(f"{yellow}~ {label}{reset}")
        for col, (old, new) in ch.cells.items():
            lines.append(f"    {col}: {old!r} -> {new!r}")
    lines.append(
        f"{len(d.added)} added, {len(d.removed)} removed, {len(d.changed)} changed"
        + (f", {len(d.columns_added)} columns added, {len(d.columns_removed)} removed"
           if d.columns_added or d.columns_removed else "")
    )
    return "\n".join(lines)


def _key_label(d: Diff, row: dict) -> str:
    return ", ".join(f"{k}={row[k]}" for k in d.key_columns)


def _row_preview(row: dict, key_columns: list[str], limit: int = 80) -> str:
    text = ", ".join(f"{k}={v}" for k, v in row.items() if k not in key_columns)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="csvdiff", description="Compare two CSV files by key.")
    p.add_argument("old", help="the original CSV file")
    p.add_argument("new", help="the updated CSV file")
    p.add_argument("-k", "--key", required=True,
                   help="key column(s) that identify a row, comma separated, e.g. id or year,month")
    p.add_argument("--encoding", default="utf-8-sig", help="file encoding (default utf-8 with or without BOM)")
    p.add_argument("--delimiter", help="field delimiter (default: detected)")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    keys = [k.strip() for k in args.key.split(",") if k.strip()]
    try:
        _, old = load_csv(args.old, args.encoding, args.delimiter)
        _, new = load_csv(args.new, args.encoding, args.delimiter)
        d = diff_rows(old, new, keys)
    except (OSError, KeyError, DuplicateKeyError, UnicodeDecodeError) as e:
        msg = e.args[0] if isinstance(e, KeyError) else e
        print(f"csvdiff: {msg}", file=sys.stderr)
        return 2

    color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
    print(format_text(d, color))
    return 0 if d.is_empty else 1


if __name__ == "__main__":
    sys.exit(main())

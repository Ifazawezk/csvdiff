"""Command-line interface: csvdiff OLD.csv NEW.csv --key id"""

import argparse
import json
import sys

from csvdiff.core import CompareOptions, Diff, TableError, diff_rows, load_table


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
        + (f"; columns: {len(d.columns_added)} added, {len(d.columns_removed)} removed"
           if d.columns_added or d.columns_removed else "")
    )
    return "\n".join(lines)


def summary(d: Diff) -> dict:
    return {
        "added": len(d.added),
        "removed": len(d.removed),
        "changed": len(d.changed),
        "columns_added": d.columns_added,
        "columns_removed": d.columns_removed,
    }


def format_json(d: Diff) -> str:
    data = {
        "key": d.key_columns,
        "summary": summary(d),
        "added": d.added,
        "removed": d.removed,
        "changed": [
            {
                "key": dict(zip(d.key_columns, ch.key)),
                "cells": {col: {"old": old, "new": new} for col, (old, new) in ch.cells.items()},
            }
            for ch in d.changed
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def format_markdown(d: Diff) -> str:
    """A report that renders nicely in a pull request or GitHub issue."""
    s = summary(d)
    lines = [f"**{s['added']} added, {s['removed']} removed, {s['changed']} changed**", ""]
    if d.columns_added or d.columns_removed:
        lines += [f"Columns added: {', '.join(d.columns_added) or 'none'}. "
                  f"Columns removed: {', '.join(d.columns_removed) or 'none'}.", ""]
    for title, rows in (("Added", d.added), ("Removed", d.removed)):
        if rows:
            cols = list(rows[0])
            lines += [f"### {title}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
            lines += ["| " + " | ".join(_md(r.get(c, "")) for c in cols) + " |" for r in rows]
            lines.append("")
    if d.changed:
        lines += ["### Changed", "", "| " + " | ".join(d.key_columns) + " | column | old | new |",
                  "|" + "---|" * (len(d.key_columns) + 3)]
        for ch in d.changed:
            for col, (old, new) in ch.cells.items():
                lines.append("| " + " | ".join(_md(k) for k in ch.key) + f" | {col} | {_md(old)} | {_md(new)} |")
        lines.append("")
    return "\n".join(lines).rstrip()


def _key_label(d: Diff, row: dict) -> str:
    return ", ".join(f"{k}={row[k]}" for k in d.key_columns)


def _row_preview(row: dict, key_columns: list[str], limit: int = 80) -> str:
    text = ", ".join(f"{k}={v}" for k, v in row.items() if k not in key_columns)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="csvdiff", description="Compare two CSV files by key.")
    p.add_argument("old", help="the original CSV file")
    p.add_argument("new", help="the updated CSV file")
    p.add_argument("-k", "--key", required=True,
                   help="key column(s) that identify a row, comma separated, e.g. id or year,month")
    p.add_argument("-i", "--ignore", default="", help="columns to skip when comparing, comma separated")
    p.add_argument("-t", "--tolerance", type=float, default=0.0,
                   help="treat numbers within this difference as equal, e.g. 0.01")
    p.add_argument("--ignore-case", action="store_true", help="compare text case-insensitively")
    p.add_argument("--ignore-whitespace", action="store_true",
                   help="ignore leading, trailing and repeated spaces")
    p.add_argument("--encoding", default="utf-8-sig", help="file encoding (default utf-8 with or without BOM)")
    p.add_argument("--delimiter", help="field delimiter (default: detected)")
    p.add_argument("--sheet", help="for .xlsx files: sheet name (default: the first sheet)")
    p.add_argument("-f", "--format", choices=["text", "json", "markdown"], default="text")
    p.add_argument("-s", "--summary", action="store_true", help="only print the counts")
    p.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    keys = _split(args.key)
    opts = CompareOptions(
        ignore_columns=tuple(_split(args.ignore)),
        tolerance=args.tolerance,
        ignore_case=args.ignore_case,
        ignore_whitespace=args.ignore_whitespace,
    )
    try:
        old_columns, old = load_table(args.old, args.encoding, args.delimiter, args.sheet)
        new_columns, new = load_table(args.new, args.encoding, args.delimiter, args.sheet)
        d = diff_rows(old, new, keys, opts, old_columns, new_columns)
    except (OSError, KeyError, TableError, UnicodeDecodeError, ImportError) as e:
        msg = e.args[0] if isinstance(e, KeyError) else e
        print(f"csvdiff: {msg}", file=sys.stderr)
        return 2

    if args.summary and args.format == "json":
        print(json.dumps(summary(d), indent=2))
    elif args.summary:
        print(format_text(d).splitlines()[-1])
    elif args.format == "json":
        print(format_json(d))
    elif args.format == "markdown":
        print(format_markdown(d))
    else:
        color = args.color == "always" or (args.color == "auto" and sys.stdout.isatty())
        print(format_text(d, color))
    return 0 if d.is_empty else 1


if __name__ == "__main__":
    sys.exit(main())

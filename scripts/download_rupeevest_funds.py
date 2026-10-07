#!/usr/bin/env python3
"""Download MF portfolio CSVs from RupeeVest for a list of fund names."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mf_screener.ingest.rupeevest import (  # noqa: E402
    download_fund_csv,
    load_search_index,
)


def _read_fund_names(path: Path) -> list[str]:
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch RupeeVest MF Portfolio Tracker CSVs via the site's JSON API "
            "(same data as the web Download button). "
            "Save under funds/<month>/ for use with mf_screener."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory for downloaded CSVs (e.g. ~/mf-data/funds/june — outside this repo)",
    )
    parser.add_argument(
        "--funds-file",
        type=Path,
        help="Text file: one RupeeVest fund name per line (# comments allowed)",
    )
    parser.add_argument(
        "--fund",
        action="append",
        default=[],
        metavar="NAME",
        help="Fund name to download (repeatable; fuzzy match if not exact)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between API calls (default: 1.0)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing CSV files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve fund names to scheme codes only; no download",
    )
    parser.add_argument(
        "--max-failures",
        type=int,
        default=0,
        help=(
            "Exit 0 while at most this many funds fail (default 0 = any failure "
            "is fatal). Use a small budget so one renamed fund on RupeeVest "
            "does not abort the whole monthly run."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    names: list[str] = list(args.fund)
    if args.funds_file:
        names.extend(_read_fund_names(args.funds_file))
    if not names:
        print(
            "Provide --fund 'Name' and/or --funds-file path.txt",
            file=sys.stderr,
        )
        return 1

    print("Loading RupeeVest fund index…", file=sys.stderr)
    index = load_search_index()
    if index.collisions:
        print(
            f"Note: {len(index.collisions)} duplicate fund name(s) in search index "
            "(kept first schemecode)",
            file=sys.stderr,
        )

    if args.dry_run:
        for query in names:
            hit = index.resolve(query)
            if hit:
                print(f"OK  {query!r} -> {hit[0]!r} (schemecode {hit[1]})")
            else:
                print(f"MISS {query!r}")
        return 0

    ok = 0
    fail = 0
    for i, query in enumerate(names):
        if i > 0 and args.delay > 0:
            time.sleep(args.delay)
        result = download_fund_csv(
            fund_query=query,
            out_dir=args.out_dir,
            index=index,
            overwrite=args.overwrite,
        )
        if result.error:
            print(f"FAIL {query!r}: {result.error}", file=sys.stderr)
            fail += 1
            continue
        assert result.path is not None
        print(f"Wrote {result.path} ({result.fund_name})", file=sys.stderr)
        ok += 1

    total = ok + fail
    print(
        f"Done: {ok}/{total} saved, {fail} failed "
        f"(max allowed failures: {args.max_failures})",
        file=sys.stderr,
    )
    if fail and fail > args.max_failures:
        print(
            f"FAIL: {fail} failed exceeds --max-failures={args.max_failures}. "
            "Likely a RupeeVest fund rename — check names in the funds file "
            "against the site search, or raise --max-failures to tolerate it.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

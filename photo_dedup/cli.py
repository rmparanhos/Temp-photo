from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .tui import PhotoDedupApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ella",
        description="ella — photo assistant. Finds similar photos and keeps the highest-quality one.",
    )
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        help="Folder to scan (omit to pick from history)",
    )
    parser.add_argument(
        "--threshold", "-t",
        type=int,
        default=10,
        help="Max pHash distance to consider photos similar (default: 10, range: 0–64)",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Scan sub-folders recursively",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would happen without moving or writing any files",
    )
    args = parser.parse_args()

    if args.directory and not args.directory.is_dir():
        print(f"Error: '{args.directory}' is not a folder.")
        raise SystemExit(1)

    app = PhotoDedupApp(args.directory, args.threshold, args.recursive, args.dry_run)
    result = app.run()
    if result:
        print(result)

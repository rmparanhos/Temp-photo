from __future__ import annotations

import argparse
from pathlib import Path

from .tui import PhotoDedupApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ella",
        description="ella — photo assistant. Finds duplicates and culls low-quality photos.",
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
        help="Max pHash distance to consider photos similar (default: 10, range: 0–256)",
    )
    parser.add_argument(
        "--cull-threshold", "-c",
        type=float,
        default=40.0,
        help="Quality score below which a photo is flagged for culling (default: 40, range: 0–100)",
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

    app = PhotoDedupApp(
        args.directory,
        args.threshold,
        args.recursive,
        args.dry_run,
        args.cull_threshold,
    )
    result = app.run()
    if result:
        print(result)

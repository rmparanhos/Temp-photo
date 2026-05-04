#!/usr/bin/env python3
"""
Duplicate photo remover with quality-based selection.

Finds groups of similar photos using perceptual hashing, scores each
by quality heuristics, and recommends which to keep.

Future: --merge flag to focus-stack or HDR-merge a group into a super photo.
"""

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import imagehash
    from PIL import Image
    import numpy as np
except ImportError:
    print("Missing dependencies. Run: pip install Pillow imagehash numpy")
    sys.exit(1)


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp", ".heic"}


@dataclass
class PhotoInfo:
    path: Path
    score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)
    phash: Optional[object] = None
    error: Optional[str] = None


def load_photos(directory: Path, recursive: bool) -> list[PhotoInfo]:
    pattern = "**/*" if recursive else "*"
    photos = []
    for p in sorted(directory.glob(pattern)):
        if p.suffix.lower() in SUPPORTED_EXTS and p.is_file():
            photos.append(PhotoInfo(path=p))
    return photos


def compute_hashes(photos: list[PhotoInfo]) -> None:
    for info in photos:
        try:
            with Image.open(info.path) as img:
                img = img.convert("RGB")
                info.phash = imagehash.phash(img, hash_size=16)
        except Exception as e:
            info.error = str(e)


def group_similar(photos: list[PhotoInfo], threshold: int) -> list[list[PhotoInfo]]:
    """Union-find grouping by pHash distance."""
    valid = [p for p in photos if p.phash is not None]
    parent = list(range(len(valid)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            if valid[i].phash - valid[j].phash <= threshold:
                union(i, j)

    buckets = defaultdict(list)
    for i, info in enumerate(valid):
        buckets[find(i)].append(info)

    return [group for group in buckets.values() if len(group) > 1]


# ---------------------------------------------------------------------------
# Quality heuristics
# ---------------------------------------------------------------------------

def _sharpness(img_gray: "np.ndarray") -> float:
    """Variance of Laplacian — higher = sharper."""
    from PIL import ImageFilter
    pil = Image.fromarray(img_gray)
    lap = pil.filter(ImageFilter.FIND_EDGES)
    return float(np.array(lap).var())


def _exposure_score(img_rgb: "np.ndarray") -> float:
    """
    Penalise under/over-exposure.
    Score peaks when mean brightness is around 128 and std is high (good contrast).
    Returns 0-100.
    """
    gray = np.mean(img_rgb, axis=2)
    mean = gray.mean()
    std = gray.std()
    # distance from ideal mean (128), normalised
    brightness_penalty = abs(mean - 128) / 128  # 0 = perfect, 1 = worst
    contrast_bonus = min(std / 64, 1.0)          # 0 = flat, 1 = great contrast
    return (1 - brightness_penalty) * 50 + contrast_bonus * 50


def _resolution_score(width: int, height: int, max_mp: float) -> float:
    """Linear score relative to the group's highest-resolution photo."""
    mp = (width * height) / 1_000_000
    return (mp / max_mp) * 100 if max_mp > 0 else 0


def _noise_score(img_gray: "np.ndarray") -> float:
    """
    Estimate noise via high-frequency residual after median blur.
    Lower residual = less noise = higher score.
    """
    from PIL import ImageFilter
    pil = Image.fromarray(img_gray)
    blurred = np.array(pil.filter(ImageFilter.MedianFilter(size=3))).astype(float)
    residual = np.abs(img_gray.astype(float) - blurred).mean()
    # Typical residuals: 0 (perfect) to ~20 (very noisy)
    return max(0.0, 100 - residual * 5)


def _exif_score(img: Image.Image) -> float:
    """
    Reward lower ISO and fast shutter speed when EXIF is available.
    Returns 0-100, or 50 (neutral) when no EXIF.
    """
    try:
        exif = img._getexif() or {}
    except Exception:
        return 50.0

    # EXIF tag IDs
    ISO_TAG = 34855
    SHUTTER_TAG = 33434  # ExposureTime as IFDRational

    score = 50.0
    if ISO_TAG in exif:
        iso = exif[ISO_TAG]
        # ISO 100 → 100pts, ISO 6400 → ~0pts
        score += max(0, (1 - iso / 6400)) * 25

    if SHUTTER_TAG in exif:
        try:
            shutter = float(exif[SHUTTER_TAG])
            # Faster than 1/60s scores well, slower penalised
            score += max(0, min(25, (1 / max(shutter, 1e-6)) / 60 * 25))
        except Exception:
            pass

    return min(score, 100.0)


def score_photo(info: PhotoInfo, max_mp: float) -> None:
    try:
        with Image.open(info.path) as img:
            img_rgb = img.convert("RGB")
            arr_rgb = np.array(img_rgb)
            arr_gray = np.mean(arr_rgb, axis=2).astype(np.uint8)

            w, h = img_rgb.size

            breakdown = {
                "sharpness": min(_sharpness(arr_gray), 5000) / 50,   # cap & normalise to 0-100
                "exposure":  _exposure_score(arr_rgb),
                "resolution": _resolution_score(w, h, max_mp),
                "noise":     _noise_score(arr_gray),
                "exif":      _exif_score(img),
            }

        # Weighted average
        weights = {"sharpness": 0.35, "exposure": 0.25, "resolution": 0.20,
                   "noise": 0.15, "exif": 0.05}
        info.score = sum(breakdown[k] * weights[k] for k in weights)
        info.score_breakdown = breakdown
    except Exception as e:
        info.error = str(e)
        info.score = 0.0


def score_group(group: list[PhotoInfo]) -> None:
    max_mp = 0.0
    for info in group:
        try:
            with Image.open(info.path) as img:
                w, h = img.size
                max_mp = max(max_mp, (w * h) / 1_000_000)
        except Exception:
            pass
    for info in group:
        score_photo(info, max_mp)


# ---------------------------------------------------------------------------
# Output / actions
# ---------------------------------------------------------------------------

def _bar(value: float, width: int = 20) -> str:
    filled = round(value / 100 * width)
    return "[" + "#" * filled + "." * (width - filled) + "]"


def print_group(idx: int, group: list[PhotoInfo], dry_run: bool) -> list[Path]:
    group_sorted = sorted(group, key=lambda p: p.score, reverse=True)
    keeper = group_sorted[0]
    to_delete = group_sorted[1:]

    print(f"\n--- Group {idx} ({len(group)} similar photos) ---")
    for info in group_sorted:
        tag = " [KEEP]" if info == keeper else " [DELETE]"
        size_kb = info.path.stat().st_size // 1024
        print(f"  {'*' if info == keeper else ' '} {info.path.name}  score={info.score:.1f}{tag}  ({size_kb} KB)")
        for k, v in info.score_breakdown.items():
            print(f"      {k:12s} {_bar(v)} {v:.1f}")

    if not dry_run:
        for info in to_delete:
            info.path.unlink()
            print(f"  Deleted: {info.path}")

    return [info.path for info in to_delete]


def main():
    parser = argparse.ArgumentParser(
        description="Find and remove duplicate/similar photos, keeping the best quality one."
    )
    parser.add_argument("directory", type=Path, help="Folder to scan")
    parser.add_argument(
        "--threshold", type=int, default=10,
        help="Max pHash distance to consider photos similar (default: 10, range 0-64)"
    )
    parser.add_argument(
        "--recursive", "-r", action="store_true",
        help="Scan sub-folders recursively"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--output-report", type=Path, metavar="FILE",
        help="Write a plain-text report to FILE"
    )
    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory.")
        sys.exit(1)

    print(f"Scanning {args.directory} …")
    photos = load_photos(args.directory, args.recursive)
    if not photos:
        print("No supported photos found.")
        sys.exit(0)
    print(f"Found {len(photos)} photos. Computing perceptual hashes …")

    compute_hashes(photos)
    errors = [p for p in photos if p.error]
    if errors:
        print(f"  Skipped {len(errors)} file(s) due to errors:")
        for e in errors:
            print(f"    {e.path.name}: {e.error}")

    print("Grouping similar photos …")
    groups = group_similar(photos, args.threshold)

    if not groups:
        print("No similar photos found. Nothing to do.")
        sys.exit(0)

    total_candidates = sum(len(g) - 1 for g in groups)
    print(f"Found {len(groups)} group(s), {total_candidates} photo(s) are candidates for removal.")
    if args.dry_run:
        print("(dry-run mode — no files will be deleted)\n")

    print("Scoring photos …")
    for group in groups:
        score_group(group)

    all_deleted = []
    for idx, group in enumerate(groups, 1):
        deleted = print_group(idx, group, args.dry_run)
        all_deleted.extend(deleted)

    action = "Would delete" if args.dry_run else "Deleted"
    print(f"\n{action} {len(all_deleted)} photo(s) across {len(groups)} group(s).")

    if args.output_report:
        _write_report(args.output_report, groups, all_deleted, args.dry_run)
        print(f"Report written to {args.output_report}")


def _write_report(path: Path, groups, deleted_paths, dry_run):
    lines = [f"Photo deduplication report\n{'='*40}\n"]
    for idx, group in enumerate(groups, 1):
        group_sorted = sorted(group, key=lambda p: p.score, reverse=True)
        lines.append(f"Group {idx}:")
        for info in group_sorted:
            action = "keep" if info == group_sorted[0] else ("would-delete" if dry_run else "deleted")
            lines.append(f"  [{action}] {info.path}  score={info.score:.1f}")
        lines.append("")
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()

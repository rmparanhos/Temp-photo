from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import imagehash
from PIL import Image

from . import cache as _cache

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp", ".bmp", ".heic"}

HASH_SIZE = 16
HASH_MAX_BITS = HASH_SIZE * HASH_SIZE  # max possible Hamming distance between two hashes


@dataclass
class PhotoInfo:
    path: Path
    score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)
    phash: Optional[object] = None
    error: Optional[str] = None


def load_photos(directory: Path, recursive: bool) -> list[PhotoInfo]:
    pattern = "**/*" if recursive else "*"
    return [
        PhotoInfo(path=p)
        for p in sorted(directory.glob(pattern))
        if p.suffix.lower() in SUPPORTED_EXTS and p.is_file()
    ]


def compute_hashes(
    photos: list[PhotoInfo],
    progress: Optional[Callable[[int], None]] = None,
) -> None:
    for i, info in enumerate(photos):
        cached = _cache.get_hash(info.path)
        if cached is not None:
            info.phash = cached
        else:
            try:
                with Image.open(info.path) as img:
                    info.phash = imagehash.phash(img.convert("RGB"), hash_size=HASH_SIZE)
                _cache.put_hash(info.path, info.phash)
            except Exception as e:
                info.error = str(e)
        if progress:
            progress(i + 1)
    _cache.flush()


def group_similar(photos: list[PhotoInfo], threshold: int) -> list[list[PhotoInfo]]:
    """
    Union-find grouping by pHash Hamming distance.
    Photos with distance <= threshold are considered similar.
    """
    valid = [p for p in photos if p.phash is not None]
    parent = list(range(len(valid)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        parent[find(a)] = find(b)

    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            if valid[i].phash - valid[j].phash <= threshold:
                union(i, j)

    buckets: dict[int, list[PhotoInfo]] = defaultdict(list)
    for i, info in enumerate(valid):
        buckets[find(i)].append(info)

    return [group for group in buckets.values() if len(group) > 1]

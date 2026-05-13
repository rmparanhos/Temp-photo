from __future__ import annotations

from typing import Callable, Optional

from PIL import Image

from . import cache as _cache
from .scanner import PhotoInfo
from .scorer import score_photo


def score_all_photos(
    photos: list[PhotoInfo],
    threshold: float,
    progress: Optional[Callable[[int], None]] = None,
) -> list[PhotoInfo]:
    """Score every photo against the global max_mp; return those below threshold."""
    # First pass: find max_mp across all photos (use cache when available)
    max_mp = 0.0
    for info in photos:
        parts = _cache.get_score_parts(info.path)
        if parts is not None:
            max_mp = max(max_mp, parts["mp"])
            continue
        try:
            with Image.open(info.path) as img:
                w, h = img.size
                max_mp = max(max_mp, (w * h) / 1_000_000)
        except Exception:
            pass

    # Second pass: score each photo
    for i, info in enumerate(photos):
        score_photo(info, max_mp)
        if progress:
            progress(i + 1)

    _cache.flush()
    return [p for p in photos if p.error is None and p.score < threshold]

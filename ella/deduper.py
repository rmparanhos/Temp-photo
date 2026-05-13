from __future__ import annotations

from typing import Callable, Optional

from .scanner import PhotoInfo, compute_hashes, group_similar
from .scorer import score_group


def find_duplicates(
    photos: list[PhotoInfo],
    threshold: int,
    on_hash_progress: Optional[Callable[[int], None]] = None,
    on_groups_found: Optional[Callable[[int], None]] = None,
    on_group_scored: Optional[Callable[[int], None]] = None,
) -> list[list[PhotoInfo]]:
    """
    Full dedup pipeline: hash → group → score.

    on_hash_progress(i)    — called after hashing photo i
    on_groups_found(n)     — called once after grouping, before scoring starts
    on_group_scored(i)     — called after scoring group i
    """
    compute_hashes(photos, on_hash_progress)
    groups = group_similar(photos, threshold)
    if on_groups_found:
        on_groups_found(len(groups))
    for i, group in enumerate(groups):
        score_group(group)
        if on_group_scored:
            on_group_scored(i)
    return groups

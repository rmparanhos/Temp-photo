from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

from . import cache as _cache
from .scanner import PhotoInfo

WEIGHTS: dict[str, float] = {
    "sharpness": 0.35,
    "exposure": 0.25,
    "resolution": 0.20,
    "noise": 0.15,
    "exif": 0.05,
}

LABELS: dict[str, str] = {
    "sharpness": "sharpness",
    "exposure": "exposure",
    "resolution": "resolution",
    "noise": "noise",
    "exif": "exif",
}


def _laplacian_variance(gray: np.ndarray) -> float:
    """
    Sharpness estimator: variance of the Laplacian response.
    The Laplacian detects rapid intensity changes (edges). A sharp photo
    has well-defined edges, producing high variance. A blurry photo has
    smooth transitions, producing low variance.
    """
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    padded = np.pad(gray.astype(np.float32), 1, mode="reflect")
    from numpy.lib.stride_tricks import sliding_window_view
    windows = sliding_window_view(padded, (3, 3))
    result = (windows * kernel).sum(axis=(-2, -1))
    return float(result.var())


def _exposure_score(arr_rgb: np.ndarray) -> float:
    """
    Penalises under/over-exposure.
    Ideal mean brightness is ~128 (mid-tone). Rewards high standard deviation
    (good contrast). Returns 0–100.
    """
    gray = arr_rgb.mean(axis=2)
    brightness_score = (1 - abs(gray.mean() - 128) / 128) * 50
    contrast_score = min(gray.std() / 64, 1.0) * 50
    return brightness_score + contrast_score


def _resolution_score_from_mp(mp: float, max_mp: float) -> float:
    return (mp / max_mp * 100) if max_mp > 0 else 0.0


def _noise_score(gray: np.ndarray) -> float:
    """
    Estimates noise via residual between original and median-blurred image.
    A low residual means the image is clean; high residual means noisy.
    """
    blurred = np.array(
        Image.fromarray(gray).filter(ImageFilter.MedianFilter(size=3))
    ).astype(float)
    residual = np.abs(gray.astype(float) - blurred).mean()
    return max(0.0, 100.0 - residual * 5)


def _exif_score(img: Image.Image) -> float:
    """
    Rewards low ISO (less noise) and fast shutter speed (less motion blur).
    Returns 50 (neutral) when EXIF data is unavailable.
    """
    try:
        exif = img._getexif() or {}
    except Exception:
        return 50.0

    ISO_TAG = 34855
    SHUTTER_TAG = 33434

    score = 50.0
    if ISO_TAG in exif:
        score += max(0.0, (1 - exif[ISO_TAG] / 6400)) * 25
    if SHUTTER_TAG in exif:
        try:
            shutter = float(exif[SHUTTER_TAG])
            score += max(0.0, min(25.0, (1 / max(shutter, 1e-6)) / 60 * 25))
        except Exception:
            pass
    return min(score, 100.0)


def score_photo(info: PhotoInfo, max_mp: float) -> None:
    # Check cache for the expensive absolute parts
    parts = _cache.get_score_parts(info.path)
    if parts is not None:
        breakdown = {
            "sharpness": parts["sharpness"],
            "exposure":  parts["exposure"],
            "resolution": _resolution_score_from_mp(parts["mp"], max_mp),
            "noise":     parts["noise"],
            "exif":      parts["exif"],
        }
        info.score = sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS)
        info.score_breakdown = breakdown
        return

    try:
        with Image.open(info.path) as img:
            img_rgb = img.convert("RGB")
            arr = np.array(img_rgb)
            gray = arr.mean(axis=2).astype(np.uint8)
            w, h = img_rgb.size
            mp = (w * h) / 1_000_000

            parts = {
                "sharpness": min(_laplacian_variance(gray) / 5000 * 100, 100.0),
                "exposure":  _exposure_score(arr),
                "noise":     _noise_score(gray),
                "exif":      _exif_score(img),
                "mp":        mp,
            }
            _cache.put_score_parts(info.path, parts)

        breakdown = {**parts, "resolution": _resolution_score_from_mp(parts["mp"], max_mp)}
        breakdown.pop("mp")
        info.score = sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS)
        info.score_breakdown = breakdown
    except Exception as e:
        info.error = str(e)
        info.score = 0.0
        info.score_breakdown = {}


def score_group(group: list[PhotoInfo]) -> None:
    max_mp = 0.0
    for info in group:
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
    for info in group:
        score_photo(info, max_mp)
    _cache.flush()
    group.sort(key=lambda p: p.score, reverse=True)

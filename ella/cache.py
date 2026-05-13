from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import imagehash

CACHE_PATH = Path.home() / ".ella" / "hash_cache.json"

# {"/abs/path": {"mtime": float, "size": int, "hash": "hex", "score_parts": {...}}}
_store: dict[str, dict] = {}
_loaded = False


def _load() -> None:
    global _store, _loaded
    if _loaded:
        return
    if CACHE_PATH.exists():
        try:
            _store = json.loads(CACHE_PATH.read_text())
        except Exception:
            _store = {}
    _loaded = True


def _entry(path: Path) -> Optional[dict]:
    """Return the cache entry for path if it's still valid (mtime + size match)."""
    _load()
    entry = _store.get(str(path.resolve()))
    if entry is None:
        return None
    stat = path.stat()
    if entry["mtime"] != stat.st_mtime or entry["size"] != stat.st_size:
        return None
    return entry


def get_hash(path: Path) -> Optional[object]:
    entry = _entry(path)
    if entry is None or "hash" not in entry:
        return None
    try:
        return imagehash.hex_to_hash(entry["hash"])
    except Exception:
        return None


def put_hash(path: Path, phash: object) -> None:
    _load()
    key = str(path.resolve())
    stat = path.stat()
    entry = _store.setdefault(key, {"mtime": stat.st_mtime, "size": stat.st_size})
    entry["mtime"] = stat.st_mtime
    entry["size"] = stat.st_size
    entry["hash"] = str(phash)


def get_score_parts(path: Path) -> Optional[dict]:
    """
    Returns cached absolute score parts: sharpness, exposure, noise, exif, mp.
    Resolution is excluded because it's relative to the group's max_mp.
    """
    entry = _entry(path)
    if entry is None or "score_parts" not in entry:
        return None
    return entry["score_parts"]


def put_score_parts(path: Path, parts: dict) -> None:
    _load()
    key = str(path.resolve())
    stat = path.stat()
    entry = _store.setdefault(key, {"mtime": stat.st_mtime, "size": stat.st_size})
    entry["mtime"] = stat.st_mtime
    entry["size"] = stat.st_size
    entry["score_parts"] = parts


def flush() -> None:
    if not _loaded:
        return
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(_store, indent=2))

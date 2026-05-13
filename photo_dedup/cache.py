from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import imagehash

CACHE_PATH = Path.home() / ".ella" / "hash_cache.json"

# {"/abs/path": {"mtime": float, "size": int, "hash": "hexstring"}}
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


def get(path: Path) -> Optional[object]:
    _load()
    key = str(path.resolve())
    entry = _store.get(key)
    if entry is None:
        return None
    stat = path.stat()
    if entry["mtime"] != stat.st_mtime or entry["size"] != stat.st_size:
        return None
    try:
        return imagehash.hex_to_hash(entry["hash"])
    except Exception:
        return None


def put(path: Path, phash: object) -> None:
    _load()
    stat = path.stat()
    _store[str(path.resolve())] = {
        "mtime": stat.st_mtime,
        "size": stat.st_size,
        "hash": str(phash),
    }


def flush() -> None:
    if not _loaded:
        return
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(_store, indent=2))

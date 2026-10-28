"""Content hashing of frozen artifacts (spec 6.1 step 8, section 17)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_hash(obj: Any) -> str:
    """Hash of JSON with sorted keys and no insignificant whitespace."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256_bytes(text.encode("utf-8"))


def expand(root: Path, patterns: Iterable[str]) -> list[Path]:
    """Files under `root` matching any glob pattern, minus caches, sorted and unique."""
    found: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file() and not (set(path.relative_to(root).parts) & _IGNORED_PARTS):
                if path.suffix != ".pyc":
                    found.add(path)
    return sorted(found)


def hash_files(root: Path, files: Iterable[Path]) -> str:
    """Order-independent hash over (relative path, content hash) pairs.

    Raises FileNotFoundError if no files are given: hashing nothing would
    silently produce a constant and hide a misconfigured freeze set.
    """
    entries = sorted((p.relative_to(root).as_posix(), sha256_file(p)) for p in files)
    if not entries:
        raise FileNotFoundError(f"no files to hash under {root}")
    digest = hashlib.sha256()
    for rel, content_hash in entries:
        digest.update(f"{rel}\0{content_hash}\n".encode())
    return digest.hexdigest()


def hash_patterns(root: Path, patterns: Iterable[str]) -> str:
    return hash_files(root, expand(root, patterns))

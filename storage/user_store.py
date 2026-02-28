from __future__ import annotations
from pathlib import Path
from storage.paths import user_root


def ensure_user_dirs(username: str) -> Path:
    root = user_root(username)
    root.mkdir(parents=True, exist_ok=True)
    return root
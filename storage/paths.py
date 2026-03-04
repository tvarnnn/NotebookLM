from __future__ import annotations
from pathlib import Path

BASE_DATA = Path("/data") if Path("/data").exists() else Path("data")


def user_root(username: str) -> Path:
    return BASE_DATA / "users" / username


def notebooks_root(username: str) -> Path:
    return user_root(username) / "notebooks"


def index_path(username: str) -> Path:
    return notebooks_root(username) / "index.json"


def notebook_root(username: str, notebook_id: str) -> Path:
    return notebooks_root(username) / notebook_id


def ensure_notebook_dirs(username: str, notebook_id: str) -> None:
    root = notebook_root(username, notebook_id)
    for p in [
        root / "files_raw",
        root / "files_extracted",
        root / "chroma",
        root / "chat",
        root / "artifacts" / "reports",
        root / "artifacts" / "quizzes",
        root / "artifacts" / "podcasts",
    ]:
        p.mkdir(parents=True, exist_ok=True)

def notebook_dir(username: str, notebook_id: str):
    return notebook_root(username, notebook_id)
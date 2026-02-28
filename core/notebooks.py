from __future__ import annotations

import uuid
from typing import List, Tuple

from storage.index_store import (
    NotebookMeta,
    list_notebooks,
    upsert_notebook,
    delete_notebook,
    _now_iso,
)
from storage.paths import ensure_notebook_dirs


def create_notebook(username: str, name: str) -> NotebookMeta:
    clean_name = (name or "").strip() or "Notebook"
    nb_id = str(uuid.uuid4())

    meta = NotebookMeta(
        id=nb_id,
        name=clean_name,
        created_at=_now_iso(),
        updated_at=_now_iso(),
    )
    upsert_notebook(username, meta)
    ensure_notebook_dirs(username, nb_id)
    return meta


def remove_notebook(username: str, notebook_id: str) -> None:
    if notebook_id:
        delete_notebook(username, notebook_id)


def list_notebook_choices(username: str) -> List[Tuple[str, str]]:
    notebooks = list_notebooks(username)
    choices: List[Tuple[str, str]] = []

    for nb in notebooks:
        nb_id = getattr(nb, "id", None)
        nb_name = getattr(nb, "name", None)

        # Guard against corrupted entries
        if not isinstance(nb_id, str) or len(nb_id) < 8:
            continue
        if not isinstance(nb_name, str) or not nb_name.strip():
            continue

        choices.append((nb_name.strip(), nb_id.strip()))

    return choices
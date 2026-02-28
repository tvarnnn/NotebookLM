from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from storage.paths import index_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NotebookMeta:
    id: str
    name: str
    created_at: str
    updated_at: str


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {"notebooks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def list_notebooks(username: str) -> List[NotebookMeta]:
    data = _read_json(index_path(username))
    out: List[NotebookMeta] = []
    for it in data.get("notebooks", []):
        out.append(
            NotebookMeta(
                id=it["id"],
                name=it["name"],
                created_at=it["created_at"],
                updated_at=it["updated_at"],
            )
        )
    return out


def upsert_notebook(username: str, meta: NotebookMeta) -> None:
    path = index_path(username)
    data = _read_json(path)

    items = data.get("notebooks", [])
    for i, it in enumerate(items):
        if it["id"] == meta.id:
            items[i] = asdict(meta)
            break
    else:
        items.append(asdict(meta))

    data["notebooks"] = items
    _write_json(path, data)


def delete_notebook(username: str, notebook_id: str) -> None:
    path = index_path(username)
    data = _read_json(path)
    data["notebooks"] = [
        it for it in data.get("notebooks", [])
        if it["id"] != notebook_id
    ]
    _write_json(path, data)
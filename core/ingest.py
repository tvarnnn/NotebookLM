from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.extract import extract_any, extract_url
from core.chunking import chunk_text
from core.vectorstore import upsert_chunks

from storage.paths import notebook_dir


@dataclass
class SourceItem:
    id: str
    type: str
    enabled: bool
    raw_path: str
    text_path: str
    location_hint: str = ""


def _sources_file(username: str, notebook_id: str) -> Path:
    return notebook_dir(username, notebook_id) / "sources.json"


def _load_sources(username: str, notebook_id: str) -> list[SourceItem]:
    p = _sources_file(username, notebook_id)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    items = []
    for s in data.get("sources", []):
        items.append(
            SourceItem(
                id=s["id"],
                type=s["type"],
                enabled=bool(s.get("enabled", True)),
                raw_path=s["raw_path"],
                text_path=s["text_path"],
                location_hint=s.get("location_hint", ""),
            )
        )
    return items


def _save_sources(username: str, notebook_id: str, sources: list[SourceItem]) -> None:
    p = _sources_file(username, notebook_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sources": [
            {
                "id": s.id,
                "type": s.type,
                "enabled": s.enabled,
                "raw_path": s.raw_path,
                "text_path": s.text_path,
                "location_hint": s.location_hint,
            }
            for s in sources
        ]
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def list_sources(username: str, notebook_id: str) -> list[SourceItem]:
    return _load_sources(username, notebook_id)


def set_source_enabled(username: str, notebook_id: str, source_id: str, enabled: bool) -> None:
    sources = _load_sources(username, notebook_id)
    for s in sources:
        if s.id == source_id:
            s.enabled = bool(enabled)
    _save_sources(username, notebook_id, sources)


def ingest_files(*, username: str, notebook_id: str, files: list[Path]) -> list[str]:
    nb = notebook_dir(username, notebook_id)
    raw_dir = nb / "files_raw"
    ext_dir = nb / "files_extracted"
    chroma_dir = nb / "chroma"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ext_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(username, notebook_id)
    ingested_names: list[str] = []

    for src in files:
        if not src.exists():
            continue

        extracted = extract_any(src)
        if extracted is None:
            continue

        # copy raw
        raw_path = raw_dir / src.name
        shutil.copyfile(src, raw_path)

        # save extracted text
        text_path = ext_dir / (src.stem + ".txt")
        text_path.write_text(extracted.text, encoding="utf-8", errors="ignore")

        # update sources.json
        item = SourceItem(
            id=src.name,
            type=src.suffix.lower().lstrip("."),
            enabled=True,
            raw_path=str(Path("files_raw") / src.name),
            text_path=str(Path("files_extracted") / text_path.name),
            location_hint=extracted.location_hint,
        )
        # replace if same id
        sources = [s for s in sources if s.id != item.id]
        sources.append(item)

        # chunk + upsert
        chunks = chunk_text(
            extracted.text,
            source_id=item.id,
            source_type=item.type,
            base_location=item.location_hint or "Text",
        )
        upsert_chunks(chroma_dir, chunks)

        ingested_names.append(src.name)

    _save_sources(username, notebook_id, sources)
    return ingested_names


def ingest_url(*, username: str, notebook_id: str, url: str) -> Optional[str]:
    url = (url or "").strip()
    if not url:
        return None

    nb = notebook_dir(username, notebook_id)
    raw_dir = nb / "files_raw"
    ext_dir = nb / "files_extracted"
    chroma_dir = nb / "chroma"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ext_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    extracted = extract_url(url)
    # create safe id
    safe_id = url.replace("https://", "").replace("http://", "").replace("/", "_")[:120]
    source_id = f"url_{safe_id}.txt"

    raw_path = raw_dir / source_id
    raw_path.write_text(url, encoding="utf-8")

    text_path = ext_dir / source_id
    text_path.write_text(extracted.text, encoding="utf-8", errors="ignore")

    sources = _load_sources(username, notebook_id)
    item = SourceItem(
        id=source_id,
        type="url",
        enabled=True,
        raw_path=str(Path("files_raw") / source_id),
        text_path=str(Path("files_extracted") / source_id),
        location_hint="URL",
    )
    sources = [s for s in sources if s.id != item.id]
    sources.append(item)
    _save_sources(username, notebook_id, sources)

    chunks = chunk_text(
        extracted.text,
        source_id=item.id,
        source_type=item.type,
        base_location=item.location_hint,
    )
    upsert_chunks(chroma_dir, chunks)
    return source_id
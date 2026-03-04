# core/rag.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from core.groq import groq_chat

COLLECTION_NAME = "chunks"


@dataclass(frozen=True)
class RagChunk:
    text: str
    source_id: str
    location: str


def _get_collection(chroma_dir: Path):
    chroma_dir = Path(chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_or_create_collection(COLLECTION_NAME)


def retrieve_chunks(chroma_dir: Path, question: str, k: int = 5) -> list[RagChunk]:
    col = _get_collection(chroma_dir)

    res: dict[str, Any] = col.query(
        query_texts=[question],
        n_results=k,
        include=["documents", "metadatas"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]

    out: list[RagChunk] = []
    for doc, md in zip(docs, metas):
        md = md or {}
        out.append(
            RagChunk(
                text=str(doc or ""),
                source_id=str(md.get("source_id", "unknown")),
                location=str(md.get("location", "unknown")),
            )
        )
    return out


def format_citations(chunks: list[RagChunk]) -> str:
    seen = set()
    lines = []
    idx = 1
    for c in chunks:
        key = (c.source_id, c.location)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"[{idx}] {c.source_id} — {c.location}")
        idx += 1
    return "\n".join(lines) if lines else "No citations available."


def answer_with_rag(*, chroma_dir: Path, question: str, model: str = "llama-3.1-8b-instant") -> tuple[str, str]:
    chunks = retrieve_chunks(chroma_dir, question, k=6)

    context_blocks = []
    for i, c in enumerate(chunks, 1):
        # keep short-ish
        snippet = c.text.strip()
        if len(snippet) > 1200:
            snippet = snippet[:1200] + "..."
        context_blocks.append(f"[{i}] SOURCE={c.source_id} | LOC={c.location}\n{snippet}")

    context = "\n\n".join(context_blocks).strip()

    prompt = (
        "You are a NotebookLM-style assistant.\n"
        "Use ONLY the provided context snippets to answer.\n"
        "If the answer is not in the context, say you don't have enough information.\n"
        "Cite sources by referencing the bracket numbers like [1], [2].\n\n"
        f"QUESTION:\n{question}\n\n"
        f"CONTEXT SNIPPETS:\n{context if context else '(no context)'}\n\n"
        "ANSWER:\n"
    )

    llm = groq_chat(model=model, temperature=0.2)
    resp = llm.invoke(prompt)
    answer = (resp.content or "").strip()

    citations = format_citations(chunks)
    return answer, citations
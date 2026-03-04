from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from core.rag import answer_with_rag
from storage.paths import notebook_root

ArtifactKind = Literal["reports", "quizzes", "podcasts"]


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _artifacts_dir(username: str, notebook_id: str, kind: ArtifactKind) -> Path:
    root = notebook_root(username, notebook_id)
    out = root / "artifacts" / kind
    out.mkdir(parents=True, exist_ok=True)
    return out


def list_artifacts(username: str, notebook_id: str, kind: ArtifactKind) -> list[str]:
    d = _artifacts_dir(username, notebook_id, kind)
    # return as strings so Gradio File can display them
    files = sorted(d.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(p) for p in files]


def _chroma_dir(username: str, notebook_id: str) -> Path:
    return notebook_root(username, notebook_id) / "chroma"


def generate_report(username: str, notebook_id: str, topic: str | None = None) -> str:
    chroma_dir = _chroma_dir(username, notebook_id)
    prompt = (
        "Write a concise report based ONLY on the provided notebook context.\n"
        "Include:\n"
        "- 5-10 bullet key takeaways\n"
        "- Short summary paragraph\n"
        "- Any important definitions\n"
        "- If you lack info, say what is missing\n"
    )
    if topic:
        prompt += f"\nFocus topic: {topic}\n"

    answer, citations = answer_with_rag(chroma_dir=chroma_dir, question=prompt)

    out_dir = _artifacts_dir(username, notebook_id, "reports")
    out_path = out_dir / f"report_{_ts()}.md"
    out_path.write_text(
        "# Report\n\n"
        f"{answer}\n\n"
        "## Sources\n\n"
        f"{citations}\n",
        encoding="utf-8",
    )
    return str(out_path)


def generate_quiz(username: str, notebook_id: str, n_questions: int = 8) -> str:
    chroma_dir = _chroma_dir(username, notebook_id)
    prompt = (
        f"Create a quiz with {n_questions} questions based ONLY on the provided notebook context.\n"
        "Format:\n"
        "Q1) ...\n"
        "A) ...\n"
        "B) ...\n"
        "C) ...\n"
        "D) ...\n"
        "Answer: X\n"
        "Explanation: ... (must reference context)\n"
        "Repeat.\n"
        "If not enough info, reduce number of questions and say so.\n"
    )

    answer, citations = answer_with_rag(chroma_dir=chroma_dir, question=prompt)

    out_dir = _artifacts_dir(username, notebook_id, "quizzes")
    out_path = out_dir / f"quiz_{_ts()}.md"
    out_path.write_text(
        "# Quiz\n\n"
        f"{answer}\n\n"
        "## Sources\n\n"
        f"{citations}\n",
        encoding="utf-8",
    )
    return str(out_path)


def generate_podcast_script(
    username: str,
    notebook_id: str,
    length: str = "3-5 minutes",
) -> str:
    chroma_dir = _chroma_dir(username, notebook_id)
    prompt = (
        "Write a podcast-style script based ONLY on the provided notebook context.\n"
        f"Target length: {length}.\n"
        "Include a hook, intro, 3-5 segments, and closing recap.\n"
        "Keep it natural and conversational.\n"
        "If info is missing, call it out.\n"
    )

    answer, citations = answer_with_rag(chroma_dir=chroma_dir, question=prompt)

    out_dir = _artifacts_dir(username, notebook_id, "podcasts")
    out_path = out_dir / f"podcast_script_{_ts()}.txt"
    out_path.write_text(
        "PODCAST SCRIPT\n\n"
        f"{answer}\n\n"
        "SOURCES\n\n"
        f"{citations}\n",
        encoding="utf-8",
    )
    return str(out_path)
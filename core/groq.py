from __future__ import annotations

import os
from langchain_groq import ChatGroq


def groq_chat(*, model: str = "llama-3.1-8b-instant", temperature: float = 0.2) -> ChatGroq:
    api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY in environment (.env).")

    # langchain_groq reads GROQ_API_KEY from env, need to make sure it exists
    return ChatGroq(model=model, temperature=temperature)
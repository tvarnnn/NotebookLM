from __future__ import annotations

from pathlib import Path
from typing import Any

import gradio as gr

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from core.notebooks import create_notebook, list_notebook_choices, remove_notebook
from core.ingest import ingest_files, ingest_url, list_sources, set_source_enabled
from core.rag import answer_with_rag
from core.artifacts import (
    generate_report,
    generate_quiz,
    generate_podcast_script,
    list_artifacts,
)
from storage.user_store import ensure_user_dirs
from storage.paths import notebook_root

APP_TITLE = "NotebookLM Clone"


# Identity
def extract_username(profile: Any) -> str:
    if profile is None:
        return "local_user"

    if isinstance(profile, str):
        s = profile.strip()
        low = s.lower()
        if low.startswith("logout") and "(" in s and s.endswith(")"):
            inside = s[s.find("(") + 1 : -1].strip()
            return inside or "local_user"
        return "local_user"

    if isinstance(profile, dict):
        return (
            (profile.get("preferred_username") or "").strip()
            or (profile.get("name") or "").strip()
            or (profile.get("email") or "").strip()
            or "local_user"
        )

    return (
        (getattr(profile, "preferred_username", None) or "").strip()
        or (getattr(profile, "name", None) or "").strip()
        or (getattr(profile, "email", None) or "").strip()
        or "local_user"
    )


# UI helpers
def sources_table(username: str, notebook_id: str):
    if not notebook_id:
        return []
    return [[s.id, bool(s.enabled)] for s in list_sources(username, notebook_id)]


def init_user(profile):
    username = extract_username(profile)
    ensure_user_dirs(username)

    choices = list_notebook_choices(username)
    selected = choices[0][1] if choices else None
    status = (
        f"Signed in as: {username}"
        if profile is not None
        else f"Local dev mode (user: {username})"
    )
    dropdown_update = gr.update(choices=choices, value=selected)
    return username, status, dropdown_update, sources_table(username, selected)


# Notebook CRUD
def on_create_notebook(username: str, name: str):
    create_notebook(username, name)
    choices = list_notebook_choices(username)
    selected = choices[0][1] if choices else None
    return gr.update(choices=choices, value=selected), "", sources_table(username, selected)


def on_delete_notebook(username: str, notebook_id: str):
    if notebook_id:
        remove_notebook(username, notebook_id)
    choices = list_notebook_choices(username)
    selected = choices[0][1] if choices else None
    return gr.update(choices=choices, value=selected), sources_table(username, selected)


def on_select_notebook(username: str, notebook_id: str):
    return sources_table(username, notebook_id)


# Ingestion
def on_ingest(username: str, notebook_id: str, uploaded_files):
    if not notebook_id:
        return "Select a notebook first.", []
    if not uploaded_files:
        return "No files uploaded.", []

    paths = [Path(f.name) for f in uploaded_files if getattr(f, "name", None)]
    ingested = ingest_files(username=username, notebook_id=notebook_id, files=paths)

    if not ingested:
        return "No supported files ingested.", sources_table(username, notebook_id)

    return f"Ingested: {', '.join(ingested)}", sources_table(username, notebook_id)


def on_ingest_url(username: str, notebook_id: str, url: str):
    if not notebook_id:
        return "Select a notebook first.", []
    url = (url or "").strip()
    if not url:
        return "No URL provided.", sources_table(username, notebook_id)

    ingested_id = ingest_url(username=username, notebook_id=notebook_id, url=url)
    if not ingested_id:
        return "URL ingest failed or unsupported.", sources_table(username, notebook_id)

    return f"Ingested URL: {ingested_id}", sources_table(username, notebook_id)


def on_sources_edit(username: str, notebook_id: str, table):
    if not notebook_id:
        return table

    if table is None:
        return sources_table(username, notebook_id)

    try:
        rows = table.values.tolist()
    except Exception:
        rows = table  # list of lists

    for row in rows or []:
        if not row or len(row) < 2:
            continue
        source_id = str(row[0])
        enabled = bool(row[1])
        set_source_enabled(username, notebook_id, source_id, enabled)

    return sources_table(username, notebook_id)


# Chat (messages format)
def _ensure_messages(history: Any) -> list[dict]:
    if history is None:
        return []

    if isinstance(history, list) and history:
        if isinstance(history[0], dict) and "role" in history[0] and "content" in history[0]:
            return history  # already correct
        if isinstance(history[0], (list, tuple)) and len(history[0]) == 2:
            out: list[dict] = []
            for u, a in history:
                if u is not None and str(u).strip():
                    out.append({"role": "user", "content": str(u)})
                if a is not None and str(a).strip():
                    out.append({"role": "assistant", "content": str(a)})
            return out

    return []


def on_chat_send(username: str, notebook_id: str, message: str, history):
    history = _ensure_messages(history)

    msg = (message or "").strip()
    if not msg:
        return history, ""

    if not notebook_id:
        history.append({"role": "user", "content": msg})
        history.append({"role": "assistant", "content": "Select a notebook first."})
        return history, ""

    chroma_dir = notebook_root(username, notebook_id) / "chroma"
    try:
        answer, citations = answer_with_rag(chroma_dir=chroma_dir, question=msg)
        bot_text = (answer or "").strip()
        if citations:
            bot_text = f"{bot_text}\n\nSources:\n{citations}"
    except Exception as e:
        bot_text = f"Error while answering: {e}"

    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": bot_text})
    return history, ""


# Artifacts
def refresh_artifacts(username: str, notebook_id: str):
    if not notebook_id:
        return [], [], []
    return (
        list_artifacts(username, notebook_id, "reports"),
        list_artifacts(username, notebook_id, "quizzes"),
        list_artifacts(username, notebook_id, "podcasts"),
    )


def on_make_report(username: str, notebook_id: str, topic: str):
    if not notebook_id:
        return "Select a notebook first.", []
    path = generate_report(username, notebook_id, (topic or "").strip() or None)
    return f"Generated: {Path(path).name}", list_artifacts(username, notebook_id, "reports")


def on_make_quiz(username: str, notebook_id: str, n_q: float | int):
    if not notebook_id:
        return "Select a notebook first.", []
    try:
        n = int(n_q)
    except Exception:
        n = 8
    n = max(1, min(n, 25))
    path = generate_quiz(username, notebook_id, n_questions=n)
    return f"Generated: {Path(path).name}", list_artifacts(username, notebook_id, "quizzes")


def on_make_podcast(username: str, notebook_id: str, length: str):
    if not notebook_id:
        return "Select a notebook first.", []
    length = (length or "").strip() or "3-5 minutes"
    path = generate_podcast_script(username, notebook_id, length=length)
    return f"Generated: {Path(path).name}", list_artifacts(username, notebook_id, "podcasts")


# UI
with gr.Blocks(title=APP_TITLE) as demo:
    gr.Markdown(f"# {APP_TITLE}")

    with gr.Row():
        login = gr.LoginButton()
        status = gr.Markdown("")

    user_state = gr.State("local_user")

    with gr.Row():
        with gr.Column(scale=1, min_width=260):
            gr.Markdown("## Notebooks")
            nb_dropdown = gr.Dropdown(label="Select Notebook", interactive=True)
            nb_name = gr.Textbox(label="New notebook name", placeholder="Notebook 1")

            with gr.Row():
                nb_create = gr.Button("+ New", variant="primary")
                nb_delete = gr.Button("Delete Selected", variant="stop")

            gr.Markdown("### Ingested Sources")
            sources_box = gr.Dataframe(headers=["Source", "Enabled"], interactive=True)

        with gr.Column(scale=3):
            with gr.Tabs():
                with gr.Tab("Sources"):
                    upload = gr.File(
                        label="Upload sources (PDF / PPTX / TXT)",
                        file_count="multiple",
                        file_types=[".pdf", ".pptx", ".txt"],
                    )
                    url = gr.Textbox(label="Add URL", placeholder="https://...")

                    with gr.Row():
                        ingest_btn = gr.Button("Ingest Files", variant="primary")
                        ingest_url_btn = gr.Button("Ingest URL", variant="secondary")
                    ingest_status = gr.Markdown("")

                with gr.Tab("Chat"):
                    gr.Markdown("RAG chat with citations")
                    chat = gr.Chatbot(label="Chat", height=420, value=[])
                    msg = gr.Textbox(label="Message", placeholder="Ask a question...")
                    send = gr.Button("Send", variant="primary")

                with gr.Tab("Artifacts"):
                    gr.Markdown("Generate artifacts from the notebook.")

                    with gr.Row():
                        report_topic = gr.Textbox(
                            label="Report topic (optional)",
                            placeholder="e.g., Summarize key ideas",
                        )
                        report_btn = gr.Button("Generate Report", variant="primary")

                    report_status = gr.Markdown("")
                    report_files = gr.File(label="Reports", file_count="multiple")

                    gr.Markdown("---")

                    with gr.Row():
                        quiz_n = gr.Number(label="Quiz questions", value=8, precision=0)
                        quiz_btn = gr.Button("Generate Quiz", variant="primary")

                    quiz_status = gr.Markdown("")
                    quiz_files = gr.File(label="Quizzes", file_count="multiple")

                    gr.Markdown("---")

                    with gr.Row():
                        podcast_len = gr.Textbox(label="Podcast length", value="3-5 minutes")
                        podcast_btn = gr.Button("Generate Podcast Script", variant="primary")

                    podcast_status = gr.Markdown("")
                    podcast_files = gr.File(label="Podcast Scripts", file_count="multiple")

    # init
    demo.load(
        fn=init_user,
        inputs=[login],
        outputs=[user_state, status, nb_dropdown, sources_box],
    )

    # notebook actions
    nb_create.click(
        fn=on_create_notebook,
        inputs=[user_state, nb_name],
        outputs=[nb_dropdown, nb_name, sources_box],
    )

    nb_delete.click(
        fn=on_delete_notebook,
        inputs=[user_state, nb_dropdown],
        outputs=[nb_dropdown, sources_box],
    )

    nb_dropdown.change(
        fn=on_select_notebook,
        inputs=[user_state, nb_dropdown],
        outputs=[sources_box],
    )

    # refresh artifacts when notebook changes
    nb_dropdown.change(
        fn=refresh_artifacts,
        inputs=[user_state, nb_dropdown],
        outputs=[report_files, quiz_files, podcast_files],
    )

    # ingestion
    ingest_btn.click(
        fn=on_ingest,
        inputs=[user_state, nb_dropdown, upload],
        outputs=[ingest_status, sources_box],
    )

    ingest_url_btn.click(
        fn=on_ingest_url,
        inputs=[user_state, nb_dropdown, url],
        outputs=[ingest_status, sources_box],
    )

    sources_box.change(
        fn=on_sources_edit,
        inputs=[user_state, nb_dropdown, sources_box],
        outputs=[sources_box],
    )

    # chat
    send.click(
        fn=on_chat_send,
        inputs=[user_state, nb_dropdown, msg, chat],
        outputs=[chat, msg],
    )
    msg.submit(
        fn=on_chat_send,
        inputs=[user_state, nb_dropdown, msg, chat],
        outputs=[chat, msg],
    )

    # artifacts
    report_btn.click(
        fn=on_make_report,
        inputs=[user_state, nb_dropdown, report_topic],
        outputs=[report_status, report_files],
    )

    quiz_btn.click(
        fn=on_make_quiz,
        inputs=[user_state, nb_dropdown, quiz_n],
        outputs=[quiz_status, quiz_files],
    )

    podcast_btn.click(
        fn=on_make_podcast,
        inputs=[user_state, nb_dropdown, podcast_len],
        outputs=[podcast_status, podcast_files],
    )

demo.launch()
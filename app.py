from __future__ import annotations

from pathlib import Path
import gradio as gr

from core.notebooks import create_notebook, list_notebook_choices, remove_notebook
from core.ingest import ingest_files, list_sources, set_source_enabled
from storage.user_store import ensure_user_dirs

APP_TITLE = "NotebookLM Clone"


def extract_username(profile) -> str:
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
def sources_table(username: str, notebook_id: str):
    if not notebook_id:
        return []
    return [[s.id, s.enabled] for s in list_sources(username, notebook_id)]


def init_user(profile) -> tuple[str, str, dict, list]:
    username = extract_username(profile)
    ensure_user_dirs(username)

    choices = list_notebook_choices(username)
    selected = choices[0][1] if choices else None
    status = f"Signed in as: {username}" if profile is not None else f"Local dev mode (user: {username})"
    dropdown_update = gr.update(choices=choices, value=selected)
    return username, status, dropdown_update, sources_table(username, selected)


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


def on_sources_edit(username: str, notebook_id: str, table):
    if not notebook_id:
        return table

    if table is None:
        return sources_table(username, notebook_id)

    try:
        rows = table.values.tolist()
    except Exception:
        rows = table

    for row in rows or []:
        if row is None:
            continue
        if len(row) >= 2:
            source_id = str(row[0])
            enabled = bool(row[1])
            set_source_enabled(username, notebook_id, source_id, enabled)

    return sources_table(username, notebook_id)


with gr.Blocks(title=APP_TITLE) as demo:
    gr.Markdown(f"# {APP_TITLE}")

    # OAuth button + status
    with gr.Row():
        login = gr.LoginButton()
        status = gr.Markdown("")

    # store username as a simple string state
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
                    ingest_btn = gr.Button("Ingest", variant="primary")
                    ingest_status = gr.Markdown("")

                with gr.Tab("Chat"):
                    gr.Markdown("RAG chat (group task)")
                    gr.Chatbot(height=400)

                with gr.Tab("Artifacts"):
                    gr.Markdown("Artifacts (group task)")

    # On load: compute username from OAuth profile, store it, populate UI
    demo.load(
        fn=init_user,
        inputs=[login],
        outputs=[user_state, status, nb_dropdown, sources_box],
    )

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

    ingest_btn.click(
        fn=on_ingest,
        inputs=[user_state, nb_dropdown, upload],
        outputs=[ingest_status, sources_box],
    )

    sources_box.change(
        fn=on_sources_edit,
        inputs=[user_state, nb_dropdown, sources_box],
        outputs=[sources_box],
    )

demo.launch()
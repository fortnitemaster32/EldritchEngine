import os
import questionary
from rich.panel import Panel

from ui_core import console, clear_screen, pick_cache, offer_pdf_export
import book_writer

def _find_resume_book_sessions(script_dir) -> list[str]:
    sessions = []
    logs_dir = os.path.join(script_dir, "logs")
    if not os.path.isdir(logs_dir): return sessions

    for name in sorted(os.listdir(logs_dir), reverse=True):
        path = os.path.join(logs_dir, name)
        if not os.path.isdir(path): continue
        if name.startswith("book_") and os.path.exists(os.path.join(path, "state.json")):
            sessions.append(path)
    return sessions

def run_book_mode(script_dir):
    console.print(Panel.fit("📖  [bold gold1]Book Writing Mode[/bold gold1]", border_style="gold1"))
    
    resume_sessions = _find_resume_book_sessions(script_dir)
    action = "New Book"
    if resume_sessions:
        action = questionary.select("Resume a session or start new?", choices=["Start New Book", "Resume Session"]).ask()
    
    if action == "Resume Session":
        session_path = questionary.select("Select session to resume:", choices=resume_sessions).ask()
        if not session_path: return
        clear_screen()
        wf = book_writer.BookWriterWorkflow("", "", resume_session_path=session_path)
        result = wf.run()
        offer_pdf_export(result, script_dir)
        return

    research_notes = ""
    if questionary.confirm("Use cached research?", default=False).ask():
        research_notes = pick_cache()

    user_prompt = questionary.text("What is your book about?").ask()
    if not user_prompt: return

    style_choice = questionary.select("Choose a style:", choices=["Fantasy", "Sci-Fi", "Mystery", "Literary", "Other"]).ask()
    if style_choice == "Other":
        style_choice = questionary.text("Describe the tone:").ask() or "Custom"

    book_title = questionary.text("Enter book title (or leave blank for AI):").ask()
    if not book_title:
        title_agent = book_writer.LMStudioAgent("Title Gen", "Generator", "Suggest titles.")
        res = title_agent.chat(f"Topic: {user_prompt}", context=research_notes[:10000])
        book_title = res.splitlines()[0] if res else "Untitled Book"

    auto_accept = questionary.confirm("Enable auto-accept mode?", default=False).ask()

    if not questionary.confirm("Start book writing?").ask(): return
    clear_screen()
    try:
        wf = book_writer.BookWriterWorkflow(user_prompt, research_notes, book_title=book_title, book_style=style_choice, auto_accept=auto_accept)
        result = wf.run()
        offer_pdf_export(result, script_dir)
    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")

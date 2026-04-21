import os
import json
import questionary
from rich.panel import Panel
from datetime import datetime

from ui_core import console, pick_font_theme
from pdf_exporter import export_book_dir_to_pdf, export_markdown_file_to_pdf

def run_history_mode(script_dir):
    console.print(Panel.fit("📜  [bold gold1]History & PDF Export[/bold gold1]", border_style="gold1"))

    choices = []
    logs_dir = os.path.join(script_dir, "logs")
    if os.path.isdir(logs_dir):
        for name in sorted(os.listdir(logs_dir), reverse=True):
            path = os.path.join(logs_dir, name)
            if not os.path.isdir(path): continue
            if name.startswith("book_") and os.path.exists(os.path.join(path, "state.json")):
                with open(os.path.join(path, "state.json"), "r") as f:
                    state = json.load(f)
                title = state.get("book_title", "Untitled Book")
                choices.append(questionary.Choice(title=f"📖 [Book] {title} ({name})", value={"type": "book", "path": path, "title": title}))
            elif name.startswith("work_log_") and os.path.exists(os.path.join(path, "4_Editor_2.md")):
                 choices.append(questionary.Choice(title=f"📝 [Essay] {name}", value={"type": "file", "path": os.path.join(path, "4_Editor_2.md"), "title": name}))

    outputs_dir = os.path.join(script_dir, "outputs")
    if os.path.isdir(outputs_dir):
        for name in sorted(os.listdir(outputs_dir), reverse=True):
            if name.lower().endswith(".md"):
                choices.append(questionary.Choice(title=f"📄 {name}", value={"type": "file", "path": os.path.join(outputs_dir, name), "title": name}))

    if not choices:
        console.print("[yellow]No older generations found.[/yellow]")
        return

    selected = questionary.select("Select a generation to export:", choices=choices + [questionary.Choice("Back", value=None)]).ask()
    if not selected: return

    font_theme = pick_font_theme()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_pdf = os.path.join(outputs_dir, f"history_export_{timestamp}.pdf")

    try:
        if selected["type"] == "book":
            export_book_dir_to_pdf(selected["path"], selected["title"], output_pdf, font_theme=font_theme)
        else:
            export_markdown_file_to_pdf(selected["path"], output_pdf, font_theme=font_theme)
        console.print(Panel.fit(f"✅ [bold green]Exported to PDF:[/bold green]\n{output_pdf}", border_style="green"))
    except Exception as exc:
        console.print(f"[bold red]PDF export failed:[/bold red] {exc}")

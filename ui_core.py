import os
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from datetime import datetime
import research_cache
import agent_writer
from pdf_exporter import export_book_dir_to_pdf, export_markdown_file_to_pdf

console = Console()

GENRES = [
    "Article / Essay",
    "Short Story",
    "Op-Ed / Opinion Piece",
    "Blog Post",
    "Analytical Report",
    "Poem",
    "Speech / Monologue",
    "Other (describe in prompt)",
]

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_header():
    console.print(Panel.fit(
        "[bold gold1]EldritchEngine[/bold gold1]\n"
        "[dim]Eldritch Writing Engine  •  v2.0[/dim]",
        border_style="gold1",
        padding=(1, 6)
    ))

def check_llm_connection():
    """Verify LM Studio is running before starting modes that require it."""
    if not agent_writer.LMStudioAgent.check_connection():
        console.print(Panel.fit(
            "[bold red]CRITICAL ERROR: LM Studio Connection Failed[/bold red]\n\n"
            "The engine cannot reach the local LLM server at [bold underline]http://localhost:1234/v1[/bold underline].\n\n"
            "1. Open [bold cyan]LM Studio[/bold cyan]\n"
            "2. Go to the [bold cyan]Local Server[/bold cyan] tab (↔ icon)\n"
            "3. Ensure a model is loaded and the server is [bold green]STARTED[/bold green]\n"
            "4. Verify the port is set to [bold]1234[/bold]",
            title="Connection Error",
            border_style="red",
            padding=(1, 2)
        ))
        questionary.press_any_key_to_continue().ask()
        return False
    return True

def get_local_files(script_dir):
    input_dir = os.path.join(script_dir, "inputs")
    os.makedirs(input_dir, exist_ok=True)
    extensions = (".pdf", ".png", ".jpg", ".jpeg", ".webp")
    files = []
    for root, _, filenames in os.walk(input_dir):
        for f in filenames:
            if f.lower().endswith(extensions):
                rel = os.path.relpath(os.path.join(root, f), input_dir)
                files.append(os.path.join(input_dir, rel))
    return sorted(files)

def pick_cache() -> str:
    """Let the user choose cached research entries. Returns combined research_notes str."""
    caches = research_cache.list_caches()
    if not caches:
        console.print("[yellow]No cached research found. Run Research Mode first.[/yellow]")
        return ""

    table = Table(title="Cached Research (Latest Versions)", border_style="cyan", show_lines=True)
    table.add_column("#",           style="bold", width=3)
    table.add_column("Type",        style="magenta", width=18)
    table.add_column("Source",      style="cyan")
    table.add_column("Words",       style="green", justify="right")
    table.add_column("Pages",       style="yellow", justify="right")
    table.add_column("Saved",       style="dim")

    for idx, c in enumerate(caches, 1):
        ts = c["timestamp"][:16].replace("T", "  ")
        table.add_row(str(idx), c["type"], c["base_name"][:50], f"{c['word_count']:,}", str(c["page_count"]), ts)
    console.print(table)

    choices = [questionary.Choice(title=f"[{c['type']}] {c['base_name'][:50]} ({c['word_count']:,} words)", value=c) for c in caches]
    console.print("\n[dim]Use [bold]<Space>[/bold] to select multiple caches, then press [bold]<Enter>[/bold] to confirm.[/dim]")
    chosen = questionary.checkbox("Select research cache(s) to use:", choices=choices).ask()

    if not chosen: return ""

    combined_notes = []
    for c in chosen:
        data = research_cache.load_cache_by_path(c["path"])
        console.print(f"[green]✓ Loaded cache:[/green] [{c['type']}] {c['base_name']}")
        header = f"### {c['type'].upper()} NOTES FOR: {c['base_name']} ###\n"
        combined_notes.append(header + data["research_notes"])
    return "\n\n---\n\n".join(combined_notes)

def pick_font_theme() -> str:
    from pdf_exporter import FONT_THEMES
    themes = list(FONT_THEMES.keys())
    return questionary.select("Select a font theme for the PDF:", choices=themes, default="Modern Sans").ask() or "Modern Sans"

def offer_pdf_export(result: dict | None, script_dir):
    if not result: return

    if not questionary.confirm("Export finished writing output to PDF?", default=True).ask():
        return

    font_theme = pick_font_theme()
    outputs_dir = os.path.join(script_dir, "outputs")
    os.makedirs(outputs_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if result.get("type") == "book":
        output_pdf = os.path.join(outputs_dir, f"book_export_{timestamp}.pdf")
        try:
            export_book_dir_to_pdf(result["log_dir"], result.get("title", "Untitled Book"), output_pdf, font_theme=font_theme)
            console.print(Panel.fit(f"✅ [bold green]Book exported to PDF:[/bold green]\n{output_pdf}", border_style="green"))
        except Exception as exc:
            console.print(f"[bold red]PDF export failed:[/bold red] {exc}")
    else:
        output_file = result.get("output_file")
        if not output_file or not os.path.exists(output_file):
            console.print("[bold red]No output file found to export.[/bold red]")
            return
        output_pdf = os.path.join(outputs_dir, f"text_export_{timestamp}.pdf")
        try:
            export_markdown_file_to_pdf(output_file, output_pdf, title=result.get("title", "Untitled Document"), font_theme=font_theme)
            console.print(Panel.fit(f"✅ [bold green]Exported to PDF:[/bold green]\n{output_pdf}", border_style="green"))
        except Exception as exc:
            console.print(f"[bold red]PDF export failed:[/bold red] {exc}")

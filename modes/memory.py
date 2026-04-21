import os
import questionary
from rich.panel import Panel
from ui_core import console, clear_screen, get_local_files
import permanent_memory

def run_memory_mode(script_dir):
    while True:
        clear_screen()
        console.print(Panel.fit(
            "🧠 [bold gold1]Permanent Memory (Local RAG)[/bold gold1]\n"
            "[dim]Index your research once, use it forever across all modes[/dim]",
            border_style="gold1"
        ))
        
        choice = questionary.select(
            "Memory Action:",
            choices=[
                "Index New Data (PDFs/Text)",
                "View Cognitive Atlas (Topic Graph)",
                "Query Memory Vault",
                "Clear Memory",
                "[Back]"
            ]
        ).ask()
        
        if not choice or choice == "[Back]":
            break
            
        if choice == "Index New Data (PDFs/Text)":
            local_files = get_local_files(script_dir)
            files = [f for f in local_files if f.lower().endswith((".pdf", ".md", ".txt"))]
            if not files:
                console.print("[red]No compatible files found in inputs/ folder.[/red]")
                questionary.press_any_key_to_continue().ask()
                continue
                
            selected_file = questionary.select("Select file to index:", choices=files).ask()
            if selected_file:
                # Basic text extraction for now
                content = ""
                if selected_file.lower().endswith(".pdf"):
                    import fitz
                    doc = fitz.open(selected_file)
                    content = "\n".join([page.get_text() for page in doc])
                else:
                    with open(selected_file, "r", encoding="utf-8") as f:
                        content = f.read()
                
                permanent_memory.memory.index_text(content, os.path.basename(selected_file))
                console.print(f"[green]Successfully indexed {selected_file}![/green]")
                questionary.press_any_key_to_continue().ask()

        elif choice == "View Cognitive Atlas (Topic Graph)":
            permanent_memory.memory.print_cognitive_atlas()
            questionary.press_any_key_to_continue().ask()

        elif choice == "Query Memory Vault":
            q = questionary.text("What do you want to recall?").ask()
            if q:
                results = permanent_memory.memory.query(q)
                console.print(Panel(results or "No matching memories found.", title=f"Recalling: {q}", border_style="cyan"))
                questionary.press_any_key_to_continue().ask()

        elif choice == "Clear Memory":
            if questionary.confirm("Are you sure? This will wipe your Permanent Memory vault.", default=False).ask():
                permanent_memory.memory.index = []
                permanent_memory.memory._save_index()
                console.print("[bold red]Memory Vault Cleared.[/bold red]")
                questionary.press_any_key_to_continue().ask()

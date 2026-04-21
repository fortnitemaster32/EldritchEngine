import os
import questionary
from rich.panel import Panel
from rich.table import Table
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
                "Check Vault Stats",
                "Mass Index Unadded Logs (Deep Scan)",
                "Index New Data (PDFs/Text)",
                "View Cognitive Atlas (Topic Graph)",
                "Query Memory Vault",
                "Clear Memory",
                "[Back]"
            ]
        ).ask()
        
        if not choice or choice == "[Back]":
            break

        if choice == "Check Vault Stats":
            stats = permanent_memory.memory.get_storage_stats()
            table = Table(title="Memory Vault Forensic Audit", border_style="gold1")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="magenta")
            table.add_row("Indexed Files", f"{stats['files']}")
            table.add_row("Semantic Chunks", f"{stats['chunks']}")
            table.add_row("Disk Usage", f"{stats['size_kb']} KB")
            console.print(table)
            questionary.press_any_key_to_continue().ask()

        elif choice == "Mass Index Unadded Logs (Deep Scan)":
            log_root = os.path.join(script_dir, "logs")
            unindexed = []
            for root, dirs, files in os.walk(log_root):
                for f in files:
                    if f.lower().endswith(".md"):
                        rel_path = os.path.relpath(os.path.join(root, f), log_root)
                        if not permanent_memory.memory.is_file_indexed(rel_path):
                            unindexed.append((os.path.join(root, f), rel_path))
            
            if not unindexed:
                console.print("[yellow]All logs are already indexed in Permanent Memory.[/yellow]")
                questionary.press_any_key_to_continue().ask()
                continue
            
            console.print(f"[cyan]Found {len(unindexed)} unindexed research logs.[/cyan]")
            if questionary.confirm(f"Index all {len(unindexed)} files now?", default=True).ask():
                for full_path, rel_path in unindexed:
                    try:
                        with open(full_path, "r", encoding="utf-8") as fh:
                            content = fh.read()
                        permanent_memory.memory.index_text(content, rel_path)
                    except Exception as e:
                        console.print(f"[red]Error indexing {rel_path}: {e}[/red]")
                console.print("[bold green]Mass Ingestion Complete![/bold green]")
                questionary.press_any_key_to_continue().ask()

        elif choice == "Index New Data (PDFs/Text)":
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

import os
import sys
import questionary

# Core helpers (Fast loads)
from ui_core import console, clear_screen, print_header, check_llm_connection

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    try:
        while True:
            clear_screen()
            print_header()

            mode = questionary.select(
                "Select a mode:",
                choices=[
                    questionary.Choice("🔬  Research Mode", value="research"),
                    questionary.Choice("🏛️   Deep Research", value="deep_research"),
                    questionary.Choice("📝  Essay Mode", value="essay"),
                    questionary.Choice("🔄  Iterative Mode", value="iterative"),
                    questionary.Choice("✍️   Short Writing", value="short"),
                    questionary.Choice("📖  Book Writing", value="book"),
                    questionary.Choice("🛠️   Custom Workflow", value="custom"),
                    questionary.Choice("📜  History & Export", value="history"),
                    questionary.Choice("⚙️   Settings", value="settings"),
                    questionary.Choice("❌  Exit", value="exit"),
                ]
            ).ask()

            if not mode or mode == "exit":
                break

            # Check connection for LLM-dependent modes
            if mode not in ["history", "settings"]:
                if not check_llm_connection():
                    continue

            clear_screen()
            print_header()

            try:
                if mode == "research":
                    from modes.research import run_research_mode
                    run_research_mode(SCRIPT_DIR)
                elif mode == "deep_research":
                    from modes.research import run_deep_research_mode
                    run_deep_research_mode(SCRIPT_DIR)
                elif mode == "essay":
                    from modes.writing import run_essay_mode
                    run_essay_mode(SCRIPT_DIR)
                elif mode == "iterative":
                    from modes.writing import run_iterative_mode
                    run_iterative_mode(SCRIPT_DIR)
                elif mode == "short":
                    from modes.writing import run_short_mode
                    run_short_mode(SCRIPT_DIR)
                elif mode == "book":
                    from modes.book import run_book_mode
                    run_book_mode(SCRIPT_DIR)
                elif mode == "custom":
                    from modes.custom import run_custom_mode
                    run_custom_mode(SCRIPT_DIR)
                elif mode == "history":
                    from modes.history import run_history_mode
                    run_history_mode(SCRIPT_DIR)
                elif mode == "settings":
                    from modes.settings import run_settings_mode
                    run_settings_mode()
            except KeyboardInterrupt:
                console.print("\n[yellow]Action cancelled by user. Returning to menu...[/yellow]")
                questionary.press_any_key_to_continue().ask()
                continue
            except Exception as e:
                console.print(f"\n[bold red]MODE ERROR:[/bold red] {e}")
                questionary.press_any_key_to_continue().ask()

            console.print("\n[bold green]✓ Mode completed![/bold green]")
            if not questionary.confirm("Return to main menu?", default=True).ask():
                break
    except Exception as fatal_error:
        import traceback
        error_details = traceback.format_exc()
        report_path = os.path.join(SCRIPT_DIR, "CRASH_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# ELDRITCH ENGINE CRASH REPORT\n\n")
            f.write(f"**Timestamp**: {datetime.now().isoformat()}\n")
            f.write(f"**Error**: {fatal_error}\n\n")
            f.write(f"## Stack Trace\n```python\n{error_details}\n```\n\n")
            f.write(f"## System Context\n")
            f.write(f"- Python: {sys.version}\n")
            f.write(f"- Platform: {sys.platform}\n")
        
        console.print(Panel(
            f"[bold red]FATAL SYSTEM CRASH[/bold red]\n\nA serious error occurred that closed the engine.\n"
            f"A forensic report has been generated at:\n[bold cyan]{report_path}[/bold cyan]",
            title="Sentinel Shutdown",
            border_style="red"
        ))
        sys.exit(1)

if __name__ == "__main__":
    from datetime import datetime
    main()

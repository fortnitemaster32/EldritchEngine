import questionary
from rich.panel import Panel
from ui_core import console, clear_screen
import config_manager

def run_settings_mode():
    while True:
        clear_screen()
        console.print(Panel.fit("⚙️  [bold gold1]Engine Settings[/bold gold1]", border_style="gold1"))
        
        config = config_manager.load_config()
        
        choices = [
            questionary.Choice(f"Concurrency (Current: {config['max_concurrency']})", value="concurrency"),
            questionary.Choice(f"LM Studio URL (Current: {config['lm_studio_url']})", value="url"),
            questionary.Choice(f"Max Context Window (Current: {config.get('max_context_window', 32768)})", value="context"),
            questionary.Choice("View Prompt Registry", value="prompts"),
            questionary.Choice("Back", value="back")
        ]
        
        choice = questionary.select("Select a setting to change:", choices=choices).ask()
        
        if not choice or choice == "back":
            break
            
        if choice == "concurrency":
            val = questionary.text("Enter max parallel tasks (e.g. 2, 4, 8):", default=str(config['max_concurrency'])).ask()
            if val and val.isdigit():
                config['max_concurrency'] = int(val)
                config_manager.save_config(config)
                console.print(f"[green]✓ Set max concurrency to {val}[/green]")
                questionary.press_any_key_to_continue().ask()
                
        elif choice == "url":
            val = questionary.text("Enter LM Studio Base URL:", default=config['lm_studio_url']).ask()
            if val:
                config['lm_studio_url'] = val
                config_manager.save_config(config)
                console.print(f"[green]✓ Set LM Studio URL to {val}[/green]")
                questionary.press_any_key_to_continue().ask()

        elif choice == "context":
            val = questionary.text("Enter Max Context Window (e.g. 32768, 65536):", default=str(config.get('max_context_window', 32768))).ask()
            if val and val.isdigit():
                config['max_context_window'] = int(val)
                config_manager.save_config(config)
                console.print(f"[green]✓ Set Max Context Window to {val}[/green]")
                questionary.press_any_key_to_continue().ask()

        elif choice == "prompts":
            from rich.table import Table
            table = Table(title="Prompt File Registry", border_style="gold1")
            table.add_column("Workflow", style="cyan")
            table.add_column("Agent/Phase", style="magenta")
            table.add_column("File in prompts/", style="green")
            
            registry = [
                ("Deep Research", "PhDs", "phd_philosopher.md, phd_psychologist.md, phd_literary.md, phd_sociologist.md"),
                ("Deep Research", "Synthesis", "chief_scholar.md"),
                ("Essay Mode", "Architect", "architect.md"),
                ("Essay Mode", "Writers", "writer_visionary.md, writer_analyst.md, writer_challenger.md, writer_storyteller.md"),
                ("Essay Mode", "Editors", "editor_sculptor.md, editor_finisher.md"),
                ("Essay Mode", "Literacy", "lexicographer.md, precisionist.md"),
                ("Short Writing", "Planner", "short_planner.md"),
                ("Short Writing", "Writers", "short_writer_creative.md, short_writer_logical.md"),
                ("Book Mode", "Architect", "book_planner.md"),
                ("Book Mode", "Auditor", "structural_auditor.md"),
                ("Book Mode", "Chapter Team", "iterative_writer_alpha.md, iterative_writer_beta.md, iterative_editor.md, iterative_critic.md"),
                ("Book Mode", "Utility", "book_condenser.md, citation_manager.md, book_title_gen.md"),
            ]
            
            for w, a, f in registry:
                table.add_row(w, a, f)
            
            clear_screen()
            console.print(table)
            console.print("\n[dim]Edit these files in the /prompts directory to change behavior.[/dim]")
            questionary.press_any_key_to_continue().ask()

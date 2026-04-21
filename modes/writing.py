import os
import questionary
import textwrap
from rich.panel import Panel
from rich.text import Text

from ui_core import console, clear_screen, get_local_files, pick_cache, offer_pdf_export, GENRES
import agent_writer
import short_writer
import iterative_writer
import research_cache

def run_essay_mode(script_dir):
    console.print(Panel.fit(
        "📝  [bold gold1]Essay Mode[/bold gold1]\n"
        "[dim]Full multi-agent research → planning → writing pipeline[/dim]",
        border_style="gold1"
    ))

    research_notes = ""
    selected_pdf = ""
    use_research = questionary.confirm(
        "Use research material (PDF or cache)? Highly recommended for deep, informed essays.",
        default=True
    ).ask()
    
    if use_research is None: return

    if use_research:
        use_cache = questionary.confirm("Use cached research? (No = select a PDF fresh)", default=True).ask()
        if use_cache is None: return

        if use_cache:
            research_notes = pick_cache()
            if not research_notes:
                console.print("[yellow]No cache selected. Falling back to fresh research.[/yellow]")
                use_cache = False

        if not use_cache:
            pdfs = [f for f in get_local_files(script_dir) if f.lower().endswith(".pdf")]
            chosen = questionary.checkbox("Select PDF(s) to process:", choices=pdfs).ask()
            if not chosen: return
            selected_pdf = chosen[0]

    user_prompt = questionary.text("What essay do you want to write?").ask()
    if not user_prompt: return

    import permanent_memory
    if questionary.confirm("Connect to Permanent Memory vault?", default=True).ask():
        with console.status("[cyan]Searching Permanent Memory...[/cyan]"):
            memories = permanent_memory.memory.query(user_prompt)
            if memories:
                research_notes = f"{research_notes}\n\n### PERMANENT MEMORY RECALL ###\n{memories}"
                console.print("[green]Connected to Permanent Memory. Relevant data retrieved.[/green]")

    use_thesis = questionary.confirm("Generate & select a thesis statement?", default=False).ask()
    use_enricher = questionary.confirm("Enable Enricher Mode?", default=False).ask()

    target_words_str = questionary.text("Optional: Enter target word count:").ask()
    target_words = int(target_words_str) if target_words_str and target_words_str.isdigit() else 0

    console.print("\n[bold cyan]Project Summary:[/bold cyan]")
    console.print(f"  Source  : {selected_pdf or ('Cache' if research_notes else 'Prompt only')}")
    console.print(f"  Prompt  : {user_prompt}")
    console.print(f"  Length  : {f'~{target_words:,} words' if target_words else 'Natural Length'}")

    if not questionary.confirm("Start the engine?").ask(): return

    clear_screen()
    console.print("[bold gold1]Engine Starting...[/bold gold1]\n")

    from ui_core import TelemetryDisplay
    telemetry = TelemetryDisplay()

    try:
        workflow = agent_writer.AgenticWorkflow(selected_pdf, user_prompt, preloaded_research=research_notes, use_enricher=use_enricher)
        
        with telemetry:
            workflow.conduct_research(telemetry=telemetry)

        if not research_notes and workflow.research_notes:
            if questionary.confirm("Save research to cache?", default=True).ask():
                source_name = os.path.basename(selected_pdf) if selected_pdf else "prompt_only"
                research_cache.save_research(source_name=source_name, prompt=user_prompt, research_notes=workflow.research_notes, page_count=len(workflow.pdf_pages))

        selected_thesis = ""
        if use_thesis:
            with telemetry:
                options = workflow.generate_thesis_options(telemetry=telemetry)
            if options:
                formatted = [questionary.Choice(title=f"{i+1}. {textwrap.fill(opt, 70)}\n", value=opt) for i, opt in enumerate(options)]
                selected_thesis = questionary.select("Select a Thesis:", choices=formatted).ask() or ""

        with telemetry:
            result = workflow.run(selected_thesis=selected_thesis, target_word_count=target_words, telemetry=telemetry)
        
        offer_pdf_export(result, script_dir)

    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")

def run_short_mode(script_dir):
    console.print(Panel.fit("✍️   [bold magenta]Short Writing Mode[/bold magenta]", border_style="magenta"))
    research_notes = ""
    if questionary.confirm("Use cached research?", default=False).ask():
        research_notes = pick_cache()

    user_prompt = questionary.text("What do you want to write?").ask()
    if not user_prompt: return

    import permanent_memory
    if questionary.confirm("Connect to Permanent Memory vault?", default=True).ask():
        with console.status("[cyan]Searching Permanent Memory...[/cyan]"):
            memories = permanent_memory.memory.query(user_prompt)
            if memories:
                research_notes = f"{research_notes}\n\n### PERMANENT MEMORY RECALL ###\n{memories}"
                console.print("[green]Connected to Permanent Memory. Relevant data retrieved.[/green]")
    genre = questionary.select("Select type:", choices=GENRES).ask()
    if not genre: return

    length_choice = questionary.select("Approximate target length:", choices=[
        questionary.Choice("Short  (~500 words)", value=500),
        questionary.Choice("Medium (~1,000 words)", value=1000),
        questionary.Choice("Long   (~2,000 words)", value=2000),
    ]).ask()
    if not length_choice: return

    if not questionary.confirm("Start writing?").ask(): return
    clear_screen()
    from ui_core import TelemetryDisplay
    telemetry = TelemetryDisplay()
    try:
        wf = short_writer.ShortWriterWorkflow(user_prompt=user_prompt, genre=genre, target_words=length_choice, research_notes=research_notes)
        with telemetry:
            result = wf.run(telemetry=telemetry)
        offer_pdf_export(result, script_dir)
    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")

def run_iterative_mode(script_dir):
    console.print(Panel.fit("🔄  [bold gold1]Iterative Mode[/bold gold1]", border_style="gold1"))
    research_notes = ""
    use_cache = questionary.confirm("Use cached research?", default=True).ask()
    selected_pdf = ""
    if use_cache:
        research_notes = pick_cache()
    else:
        local_files = get_local_files(script_dir)
        pdfs = [f for f in local_files if f.lower().endswith(".pdf")]
        chosen = questionary.checkbox("Select PDF(s):", choices=pdfs).ask()
        if chosen: selected_pdf = chosen[0]

    user_prompt = questionary.text("What do you want to write?").ask()
    if not user_prompt: return

    import permanent_memory
    if questionary.confirm("Connect to Permanent Memory vault?", default=True).ask():
        with console.status("[cyan]Searching Permanent Memory...[/cyan]"):
            memories = permanent_memory.memory.query(user_prompt)
            if memories:
                research_notes = f"{research_notes}\n\n### PERMANENT MEMORY RECALL ###\n{memories}"
                console.print("[green]Connected to Permanent Memory. Relevant data retrieved.[/green]")

    from ui_core import TelemetryDisplay
    telemetry = TelemetryDisplay()

    if not use_cache and selected_pdf:
        console.print("[bold gold1]Running research...[/bold gold1]")
        wf = agent_writer.AgenticWorkflow(selected_pdf, user_prompt)
        with telemetry:
            wf.conduct_research(telemetry=telemetry)
        research_notes = wf.research_notes

    try:
        wf = iterative_writer.IterativeWriterWorkflow(user_prompt, research_notes)
        with telemetry:
            result = wf.run(telemetry=telemetry)
        offer_pdf_export(result, script_dir)

    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")

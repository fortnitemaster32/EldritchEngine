import os
import questionary
from rich.panel import Panel
from datetime import datetime
import subprocess

from ui_core import console, clear_screen, get_local_files
import agent_writer
import deep_research_mode
import research_cache

def run_research_mode(script_dir):
    console.print(Panel.fit(
        "🔬  [bold cyan]Research Mode[/bold cyan]\n"
        "[dim]Run the Scholar on a PDF and save notes to cache[/dim]",
        border_style="cyan"
    ))

    local_files = get_local_files(script_dir)
    pdfs = [f for f in local_files if f.lower().endswith(".pdf")]
    if not pdfs:
        console.print("[red]No PDFs found in the inputs/ folder.[/red]")
        return

    selected_pdf = questionary.select(
        "Select a PDF to research:",
        choices=pdfs + [questionary.Choice("[Back]", value="back")]
    ).ask()
    
    if not selected_pdf or selected_pdf == "back":
        return

    research_prompt = questionary.text(
        "Optional: Enter a focus prompt for the research "
        "(leave blank for general extraction):",
        instruction="e.g. 'Focus on Bertrand Russell\\'s epistemological arguments'"
    ).ask()
    
    if research_prompt is None: return # Back/Cancel
    research_prompt = research_prompt or "General extraction — document all details comprehensively."

    comics_mode = questionary.confirm("Enable Comics Mode? (Extract images from PDF)", default=False).ask()
    if comics_mode is None: return

    console.print(f"\n[bold]PDF:[/bold] {selected_pdf}")
    console.print(f"[bold]Prompt:[/bold] {research_prompt}")
    console.print(f"[bold]Comics Mode:[/bold] {'ON' if comics_mode else 'OFF'}")

    confirm = questionary.confirm("Start the Scholar?").ask()
    if not confirm:
        return

    clear_screen()
    console.print("[bold gold1]Scholar Starting...[/bold gold1]\n")

    wf = agent_writer.AgenticWorkflow(selected_pdf, research_prompt, extract_images=comics_mode)
    wf.conduct_research()

    if not wf.research_notes:
        console.print("[red]Research produced no output. Exiting.[/red]")
        return

    source_name = os.path.basename(selected_pdf)
    cache_id = research_cache.save_research(
        source_name=source_name,
        prompt=research_prompt,
        research_notes=wf.research_notes,
        page_count=len(wf.pdf_pages),
    )
    console.print(Panel.fit(
        f"✅ [bold green]Research saved to cache![/bold green]\n\n"
        f"Cache ID : [bold]{cache_id}[/bold]\n"
        f"Words    : [bold]{len(wf.research_notes.split()):,}[/bold]\n"
        f"Pages    : [bold]{len(wf.pdf_pages)}[/bold]",
        border_style="green"
    ))

def _git_commit(message, script_dir):
    """Internal helper to commit changes."""
    try:
        subprocess.run(["git", "add", "."], cwd=script_dir, check=True, capture_output=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=script_dir, check=True, capture_output=True, text=True)
        if not status.stdout.strip():
            return "No changes to commit."
        subprocess.run(["git", "commit", "-m", message], cwd=script_dir, check=True, capture_output=True)
        return f"Committed: {message}"
    except Exception as e:
        return f"Git Error: {str(e)}"

def run_deep_research_mode(script_dir):
    console.print(Panel.fit(
        "🏛️   [bold gold1]Deep Research Mode[/bold gold1]\n"
        "[dim]4 Parallel PhDs analyze, debate, and synthesize a master paper[/dim]",
        border_style="gold1"
    ))

    local_files = get_local_files(script_dir)
    pdfs = [f for f in local_files if f.lower().endswith(".pdf")]
    if not pdfs:
        console.print("[red]No PDFs found in the inputs/ folder.[/red]")
        return

    selected_pdfs = questionary.checkbox(
        "Select PDF(s) to research (Multi-select enabled for overnight runs):",
        choices=pdfs
    ).ask()
    
    if not selected_pdfs:
        return

    research_prompt = questionary.text(
        "Optional: Enter a focus prompt for the research "
        "(leave blank for general comprehensive analysis):",
        instruction="e.g. 'Analyze the structural power dynamics and psychological archetypes'"
    ).ask()
    
    if research_prompt is None: return
    research_prompt = research_prompt or "Conduct an exhaustive, multi-disciplinary analysis of this text."

    comics_mode = questionary.confirm("Enable Comics Mode? (Extract images during standard research)", default=False).ask()
    if comics_mode is None: return

    console.print(f"\n[bold]Selected PDFs ({len(selected_pdfs)}):[/bold] {', '.join(selected_pdfs)}")
    console.print(f"[bold]Prompt:[/bold] {research_prompt}")
    console.print(f"[bold]Comics Mode:[/bold] {'ON' if comics_mode else 'OFF'}")

    confirm = questionary.confirm("Start the Batch Deep Research Protocol?").ask()
    if not confirm:
        return

    # --- Git: Pre-Research Snapshot ---
    git_msg_pre = f"Pre-research snapshot: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    console.print(f"[dim]{_git_commit(git_msg_pre, script_dir)}[/dim]")

    for pdf in selected_pdfs:
        clear_screen()
        console.print(Panel.fit(f"🚀 [bold gold1]Processing: {pdf}[/bold gold1]", border_style="gold1"))
        console.print("[bold gold1]Assembling the Scholars...[/bold gold1]\n")

        try:
            wf = deep_research_mode.DeepResearchWorkflow(pdf, research_prompt)
            wf.run()
            
            console.print(f"\n[bold gold1]Starting Standard Factual Research for {pdf}...[/bold gold1]")
            regular_wf = agent_writer.AgenticWorkflow(pdf, research_prompt, extract_images=comics_mode)
            regular_wf.conduct_research()
            
            if regular_wf.research_notes:
                source_name = os.path.basename(pdf)
                cache_id = research_cache.save_research(
                    source_name=source_name,
                    prompt=research_prompt,
                    research_notes=regular_wf.research_notes,
                    page_count=len(regular_wf.pdf_pages),
                )
                
                standard_log_path = os.path.join(wf.log_dir, "4_Standard_Research_Notes.md")
                with open(standard_log_path, "w", encoding="utf-8") as f:
                    f.write(f"# Standard Research Notes: {pdf}\n\n" + regular_wf.research_notes)

                console.print(Panel.fit(
                    f"✅ [bold green]Dual-Pass Research for {pdf} Complete![/bold green]\n\n"
                    f"1. Deep Synthesis:  [cyan]Saved in logs[/cyan]\n"
                    f"2. Factual Cache:   [cyan]{cache_id}[/cyan]",
                    border_style="green"
                ))

        except Exception as exc:
            console.print(f"\n[bold red]ERROR processing {pdf}:[/bold red] {exc}")
            continue 

    git_msg_post = f"Post-research batch complete: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    console.print(f"\n[dim]{_git_commit(git_msg_post, script_dir)}[/dim]")

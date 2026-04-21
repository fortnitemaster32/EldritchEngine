import os
import sys
import questionary
import concurrent.futures
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add current dir to path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agent_writer
import research_cache
import config_manager

console = Console()

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def run_retro_synthesis(log_dir):
    console.print(Panel.fit(f"🔄 [bold gold1]Retroactive Synthesis[/bold gold1]\nTarget: {log_dir}", border_style="gold1"))
    
    if not os.path.isdir(log_dir):
        console.print("[red]Directory not found.[/red]")
        return

    # 1. Load data
    compiled_notes = {}
    critiques = {}
    
    files = os.listdir(log_dir)
    for f in files:
        path = os.path.join(log_dir, f)
        if f.endswith("_Notes.md") and f[0].isdigit():
            name = f.split("_", 1)[1].rsplit("_", 1)[0].replace("_", " ")
            with open(path, "r", encoding="utf-8") as fh:
                compiled_notes[name] = fh.read()
        elif f.endswith("_Critique.md") and f[0].isdigit():
            name = f.split("_", 1)[1].rsplit("_", 1)[0].replace("_", " ")
            with open(path, "r", encoding="utf-8") as fh:
                critiques[name] = fh.read()

    if not compiled_notes:
        console.print("[red]No research notes found in this directory.[/red]")
        return

    user_prompt = questionary.text("What was the original research prompt?", default="General Analysis").ask()
    
    # 2. Setup Chief Scholar
    chief_scholar = agent_writer.LMStudioAgent(
        "Chief Scholar", "Synthesis Lead",
        "You are the Chief Scholar. Your goal is to synthesize multiple conflicting disciplinary perspectives into a cohesive masterwork."
    )

    # 3. Generate Outline
    console.print("\n[bold green]Generating Master Outline...[/bold green]")
    all_research_and_debate = "### ORIGINAL RESEARCH NOTES ###\n"
    for name, notes in compiled_notes.items():
        all_research_and_debate += f"\n#### {name} ####\n{notes}\n"
    all_research_and_debate += "\n\n### DEBATE AND CRITIQUES ###\n"
    for name, critique in critiques.items():
        all_research_and_debate += f"\n#### {name}'s Critique ####\n{critique}\n"

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
        prog.add_task("Mapping Themes...", total=None)
        outline_prompt = (
            f"TOPIC: {user_prompt}\n\n"
            "TASK: Create a 10-15 chapter outline for a 20,000+ word master thesis based on the notes provided. "
            "Output only a numbered list of chapters."
        )
        outline_res = chief_scholar.chat(outline_prompt, context=all_research_and_debate[:100000])
    
    chapters = [line.strip() for line in outline_res.splitlines() if line.strip() and line.strip()[0].isdigit() and "." in line]
    if not chapters: chapters = ["1. Comprehensive Synthesis"]

    # 4. Parallel Chapter Drafting
    max_workers = config_manager.get_setting("max_concurrency")
    console.print(f"\n[bold green]Writing {len(chapters)} Chapters ({max_workers} Parallely)...[/bold green]")
    
    from ui_core import TelemetryDisplay
    telemetry = TelemetryDisplay()
    sections = [None] * len(chapters)
    
    def draft_chapter(idx, chapter_title):
        def on_update(data):
            telemetry.update(f"Ch {idx+1}: {chapter_title[:20]}...", data)
            telemetry.refresh()

        section_prompt = (
            f"CHAPTER: {chapter_title}\n\n"
            "TASK: Write a 1,500-2,000 word analytical deep-dive. Compare the 4 scholars explicitly. "
            "Maintain extreme academic rigor."
        )
        content = chief_scholar.chat(section_prompt, context=all_research_and_debate[:120000], on_update=on_update)
        telemetry.update(f"Ch {idx+1}: {chapter_title[:20]}...", {"status": "[bold green]Done[/bold green]", "tps": 0, "tokens": 0})
        telemetry.refresh()
        return idx, f"# {chapter_title}\n\n{content}"

    with telemetry:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chapter = {
                executor.submit(draft_chapter, i, title): title 
                for i, title in enumerate(chapters)
            }
            
            for future in concurrent.futures.as_completed(future_to_chapter):
                idx, content = future.result()
                sections[idx] = content


    # 5. Save
    final_paper = "\n\n---\n\n".join(sections)
    output_path = os.path.join(log_dir, "RE_SYNTHESIZED_MASTER_THESIS.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# RE-SYNTHESIZED MASTER THESIS\n\nPrompt: {user_prompt}\n\n" + final_paper)
    
    console.print(f"\n[bold green]COMPLETED![/bold green] Saved to: [cyan]{output_path}[/cyan]")

if __name__ == "__main__":
    logs_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    deep_logs = [d for d in os.listdir(logs_base) if d.startswith("deep_research_")]
    if not deep_logs:
        print("No deep research logs found.")
        sys.exit(0)
    
    selected_logs = questionary.checkbox(
        "Select log folder(s) to re-synthesize (Multi-select enabled):", 
        choices=deep_logs
    ).ask()
    
    if selected_logs:
        for log in selected_logs:
            clear_screen()
            run_retro_synthesis(os.path.join(logs_base, log))
            console.print(f"\n[bold gold1]Finished Batch Processing for {log}[/bold gold1]\n")
        
        console.print("[bold green]All selected batches complete![/bold green]")

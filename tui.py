"""
tui.py — Agentic Writer Studio — Main Launcher
Modes:
  🔬  Research Mode   — Run the Scholar on a PDF and save notes to cache
  📝  Essay Mode      — Full multi-agent essay pipeline (agent_writer.py)
  🔄  Iterative Mode  — Plan and write paragraph-by-paragraph with live review
  ✍️   Short Mode      — Lean 3-agent short-form pipeline (short_writer.py)
"""

import os
import sys
import textwrap
import questionary
from rich.console import Console
from rich.panel   import Panel
from rich.table   import Table
from rich.text    import Text
from datetime     import datetime

import agent_writer
import short_writer
import iterative_writer
import deep_research_mode
import modular_writer
import research_cache

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def get_local_files():
    input_dir = "inputs"
    os.makedirs(input_dir, exist_ok=True)
    extensions = (".pdf", ".png", ".jpg", ".jpeg", ".webp")
    files = []
    for root, _, filenames in os.walk(input_dir):
        for f in filenames:
            if f.lower().endswith(extensions):
                rel = os.path.relpath(os.path.join(root, f), input_dir)
                files.append(os.path.join(input_dir, rel))
    return sorted(files)


def print_header():
    console.print(Panel.fit(
        "[bold gold1]AGENTIC WRITER STUDIO[/bold gold1]\n"
        "[dim]Multi-Agent Writing Engine  •  v2.0[/dim]",
        border_style="gold1",
        padding=(1, 6)
    ))


def pick_cache() -> str:
    """Let the user choose cached research entries. Returns combined research_notes str."""
    caches = research_cache.list_caches()
    if not caches:
        console.print("[yellow]No cached research found. Run Research Mode first.[/yellow]")
        return ""

    # Build display table
    table = Table(title="Cached Research (Latest Versions)", border_style="cyan", show_lines=True)
    table.add_column("#",           style="bold", width=3)
    table.add_column("Type",        style="magenta", width=18)
    table.add_column("Source",      style="cyan")
    table.add_column("Words",       style="green", justify="right")
    table.add_column("Pages",       style="yellow", justify="right")
    table.add_column("Saved",       style="dim")

    for idx, c in enumerate(caches, 1):
        ts = c["timestamp"][:16].replace("T", "  ")
        table.add_row(
            str(idx),
            c["type"],
            c["base_name"][:50],
            f"{c['word_count']:,}",
            str(c["page_count"]),
            ts,
        )
    console.print(table)

    choices = [
        questionary.Choice(
            title=f"[{c['type']}] {c['base_name'][:50]} ({c['word_count']:,} words)",
            value=c
        )
        for c in caches
    ]
    
    console.print("\n[dim]Use [bold]<Space>[/bold] to select multiple caches, then press [bold]<Enter>[/bold] to confirm.[/dim]")
    chosen = questionary.checkbox(
        "Select research cache(s) to use:",
        choices=choices
    ).ask()

    if not chosen:
        return ""

    combined_notes = []
    for c in chosen:
        data = research_cache.load_cache_by_path(c["path"])
        console.print(f"[green]✓ Loaded cache:[/green] [{c['type']}] {c['base_name']}")
        header = f"### {c['type'].upper()} NOTES FOR: {c['base_name']} ###\n"
        combined_notes.append(header + data["research_notes"])
        
    return "\n\n---\n\n".join(combined_notes)


# ---------------------------------------------------------------------------
# Mode: Research
# ---------------------------------------------------------------------------

def run_research_mode():
    console.print(Panel.fit(
        "🔬  [bold cyan]Research Mode[/bold cyan]\n"
        "[dim]Run the Scholar on a PDF and save notes to cache[/dim]",
        border_style="cyan"
    ))

    local_files = get_local_files()
    pdfs = [f for f in local_files if f.lower().endswith(".pdf")]
    if not pdfs:
        console.print("[red]No PDFs found in the inputs/ folder.[/red]")
        return

    selected_pdf = questionary.select(
        "Select a PDF to research:",
        choices=pdfs
    ).ask()
    if not selected_pdf:
        return

    research_prompt = questionary.text(
        "Optional: Enter a focus prompt for the research "
        "(leave blank for general extraction):",
        instruction="e.g. 'Focus on Bertrand Russell\\'s epistemological arguments'"
    ).ask() or "General extraction — document all details comprehensively."

    comics_mode = questionary.confirm("Enable Comics Mode? (Extract images from PDF)", default=False).ask()

    console.print(f"\n[bold]PDF:[/bold] {selected_pdf}")
    console.print(f"[bold]Prompt:[/bold] {research_prompt}")
    console.print(f"[bold]Comics Mode:[/bold] {'ON' if comics_mode else 'OFF'}")

    confirm = questionary.confirm("Start the Scholar?").ask()
    if not confirm:
        return

    clear_screen()
    console.print("[bold gold1]Scholar Starting...[/bold gold1]\n")

    # Build a workflow just for research — no writing pipeline needed
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


# ---------------------------------------------------------------------------
# Mode: Deep Research (Parallel PhDs)
# ---------------------------------------------------------------------------

def run_deep_research_mode():
    console.print(Panel.fit(
        "🏛️   [bold gold1]Deep Research Mode[/bold gold1]\n"
        "[dim]4 Parallel PhDs analyze, debate, and synthesize a master paper[/dim]",
        border_style="gold1"
    ))

    local_files = get_local_files()
    pdfs = [f for f in local_files if f.lower().endswith(".pdf")]
    if not pdfs:
        console.print("[red]No PDFs found in the inputs/ folder.[/red]")
        return

    selected_pdf = questionary.select(
        "Select a PDF to research:",
        choices=pdfs
    ).ask()
    if not selected_pdf:
        return

    research_prompt = questionary.text(
        "Optional: Enter a focus prompt for the research "
        "(leave blank for general comprehensive analysis):",
        instruction="e.g. 'Analyze the structural power dynamics and psychological archetypes'"
    ).ask() or "Conduct an exhaustive, multi-disciplinary analysis of this text."

    comics_mode = questionary.confirm("Enable Comics Mode? (Extract images during standard research)", default=False).ask()

    console.print(f"\n[bold]PDF:[/bold] {selected_pdf}")
    console.print(f"[bold]Prompt:[/bold] {research_prompt}")
    console.print(f"[bold]Comics Mode:[/bold] {'ON' if comics_mode else 'OFF'}")

    confirm = questionary.confirm("Start the Deep Research Protocol? (This will take a while)").ask()
    if not confirm:
        return

    clear_screen()
    console.print("[bold gold1]Assembling the Scholars...[/bold gold1]\n")

    try:
        wf = deep_research_mode.DeepResearchWorkflow(selected_pdf, research_prompt)
        wf.run()
        
        console.print("\n[bold gold1]Starting Standard Research Protocol...[/bold gold1]")
        regular_wf = agent_writer.AgenticWorkflow(selected_pdf, research_prompt, extract_images=comics_mode)
        regular_wf.conduct_research()
        
        if regular_wf.research_notes:
            source_name = os.path.basename(selected_pdf)
            cache_id = research_cache.save_research(
                source_name=source_name,
                prompt=research_prompt,
                research_notes=regular_wf.research_notes,
                page_count=len(regular_wf.pdf_pages),
            )
            console.print(Panel.fit(
                f"✅ [bold green]Standard Research saved to cache![/bold green]\n\n"
                f"Cache ID : [bold]{cache_id}[/bold]\n"
                f"Words    : [bold]{len(regular_wf.research_notes.split()):,}[/bold]\n"
                f"Pages    : [bold]{len(regular_wf.pdf_pages)}[/bold]",
                border_style="green"
            ))

    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")
        raise

# ---------------------------------------------------------------------------
# Mode: Essay
# ---------------------------------------------------------------------------

def run_essay_mode():
    console.print(Panel.fit(
        "📝  [bold gold1]Essay Mode[/bold gold1]\n"
        "[dim]Full multi-agent research → planning → writing pipeline[/dim]",
        border_style="gold1"
    ))

    # --- Research source ---
    research_notes = ""
    use_cache = questionary.confirm(
        "Use cached research? (No = select a PDF to research fresh)",
        default=True
    ).ask()

    selected_pdf = ""
    if use_cache:
        research_notes = pick_cache()
        if not research_notes:
            console.print("[yellow]No cache selected. Falling back to fresh research.[/yellow]")
            use_cache = False

    if not use_cache:
        local_files = get_local_files()
        choices = ["[PROMPT ONLY] No source file"] + local_files
        chosen = questionary.checkbox(
            "Select PDF(s) to process:",
            choices=choices
        ).ask() or []
        is_prompt_only = "[PROMPT ONLY] No source file" in chosen
        chosen = [f for f in chosen if f != "[PROMPT ONLY] No source file"]
        selected_pdf = chosen[0] if chosen else ""

    # --- Prompt ---
    user_prompt = questionary.text(
        "What essay do you want to write?",
        instruction="e.g. 'Write a deep philosophical analysis of Russell\\'s theory of knowledge'"
    ).ask()
    if not user_prompt:
        return

    # --- Options ---
    use_thesis  = questionary.confirm("Generate & select a thesis statement?", default=False).ask()

    # --- Target Word Count ---
    target_words_str = questionary.text(
        "Optional: Enter a target word count (e.g. '3000', '10000'). Leave blank for natural LLM length:",
        instruction="Note: Extremely high numbers may exceed local model token limits."
    ).ask()
    
    target_words = 0
    if target_words_str and target_words_str.isdigit():
        target_words = int(target_words_str)

    # --- Summary ---
    console.print("\n[bold cyan]Project Summary:[/bold cyan]")
    console.print(f"  Source  : {selected_pdf or ('Cache' if research_notes else 'Prompt only')}")
    console.print(f"  Prompt  : {user_prompt}")
    console.print(f"  Thesis  : {'ON' if use_thesis else 'OFF'}")
    console.print(f"  Length  : {f'~{target_words:,} words' if target_words else 'Natural Length'}")

    if not questionary.confirm("Start the engine?").ask():
        return

    clear_screen()
    console.print("[bold gold1]Engine Starting...[/bold gold1]\n")

    try:
        workflow = agent_writer.AgenticWorkflow(
            selected_pdf, user_prompt,
            extract_images=False,
            preloaded_research=research_notes
        )
        workflow.conduct_research()

        # Offer to cache fresh research
        if not research_notes and workflow.research_notes:
            if questionary.confirm(
                "Save this research to cache for future runs?", default=True
            ).ask():
                source_name = os.path.basename(selected_pdf) if selected_pdf else "prompt_only"
                cid = research_cache.save_research(
                    source_name=source_name,
                    prompt=user_prompt,
                    research_notes=workflow.research_notes,
                    page_count=len(workflow.pdf_pages),
                )
                console.print(f"[green]✓ Research cached as:[/green] {cid}")

        selected_thesis = ""
        if use_thesis:
            options = workflow.generate_thesis_options()
            if options:
                formatted = [
                    questionary.Choice(
                        title=f"{i+1}. {textwrap.fill(opt, 70)}\n",
                        value=opt
                    )
                    for i, opt in enumerate(options)
                ]
                selected_thesis = questionary.select(
                    "Select a Thesis Statement:", choices=formatted
                ).ask() or ""
                if selected_thesis:
                    console.print(Panel(
                        Text(selected_thesis, style="bold green"),
                        title="Selected Thesis", border_style="green"
                    ))

        workflow.run(selected_thesis=selected_thesis, target_word_count=target_words)
        console.print(f"\n[bold green]COMPLETE![/bold green]  Logs: [cyan]{workflow.log_dir}[/cyan]")

    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")
        raise


# ---------------------------------------------------------------------------
# Mode: Short Writing
# ---------------------------------------------------------------------------

def run_short_mode():
    console.print(Panel.fit(
        "✍️   [bold magenta]Short Writing Mode[/bold magenta]\n"
        "[dim]Lean 3-agent pipeline  •  Planner → Writer loop → Editor[/dim]",
        border_style="magenta"
    ))

    # --- Research source ---
    research_notes = ""
    use_cache = questionary.confirm(
        "Use cached research as source material? (No = write from prompt only)",
        default=False
    ).ask()
    if use_cache:
        research_notes = pick_cache()

    # --- Prompt ---
    user_prompt = questionary.text(
        "What do you want to write?",
        instruction="e.g. 'A short story about a detective who questions reality'"
    ).ask()
    if not user_prompt:
        return

    # --- Genre ---
    genre = questionary.select(
        "Select the type of piece:",
        choices=GENRES
    ).ask()
    if not genre:
        return

    # --- Target length ---
    length_choice = questionary.select(
        "Approximate target length:",
        choices=[
            questionary.Choice("Short  (~500 words)",   value=500),
            questionary.Choice("Medium (~1 000 words)", value=1000),
            questionary.Choice("Long   (~2 000 words)", value=2000),
            questionary.Choice("Extended (~3 500 words)", value=3500),
        ]
    ).ask()
    if not length_choice:
        return

    # --- Summary ---
    console.print("\n[bold magenta]Project Summary:[/bold magenta]")
    console.print(f"  Genre   : {genre}")
    console.print(f"  Target  : ~{length_choice:,} words")
    console.print(f"  Prompt  : {user_prompt}")
    console.print(f"  Research: {'Cache loaded' if research_notes else 'None (prompt only)'}")

    if not questionary.confirm("Start writing?").ask():
        return

    clear_screen()
    console.print("[bold gold1]Short Writer Starting...[/bold gold1]\n")

    try:
        wf = short_writer.ShortWriterWorkflow(
            user_prompt=user_prompt,
            genre=genre,
            target_words=length_choice,
            research_notes=research_notes,
        )
        wf.run()
    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")
        raise


# ---------------------------------------------------------------------------
# Mode: Iterative
# ---------------------------------------------------------------------------

def run_iterative_mode():
    console.print(Panel.fit(
        "🔄  [bold gold1]Iterative Mode[/bold gold1]\n"
        "[dim]Plan an outline, then generate and review paragraph-by-paragraph[/dim]",
        border_style="gold1"
    ))

    # --- Research source ---
    research_notes = ""
    use_cache = questionary.confirm(
        "Use cached research? (No = select a PDF to research fresh)",
        default=True
    ).ask()

    selected_pdf = ""
    if use_cache:
        research_notes = pick_cache()
        if not research_notes:
            console.print("[yellow]No cache selected. Falling back to fresh research.[/yellow]")
            use_cache = False

    if not use_cache:
        local_files = get_local_files()
        choices = ["[PROMPT ONLY] No source file"] + local_files
        chosen = questionary.checkbox(
            "Select PDF(s) to process:",
            choices=choices
        ).ask() or []
        is_prompt_only = "[PROMPT ONLY] No source file" in chosen
        chosen = [f for f in chosen if f != "[PROMPT ONLY] No source file"]
        selected_pdf = chosen[0] if chosen else ""

    # --- Prompt ---
    user_prompt = questionary.text(
        "What do you want to write?",
        instruction="e.g. 'Write an essay about the symbolism of the green light'"
    ).ask()
    if not user_prompt:
        return

    # --- Paragraph Count & Style ---
    para_count_str = questionary.text(
        "Optional: Enter exact paragraph count for the outline (e.g. 5). Leave blank to let the Planner decide:",
    ).ask()
    para_count = int(para_count_str) if para_count_str and para_count_str.isdigit() else 0

    style_choice = questionary.text(
        "Optional: Enter a specific stylistic instruction (e.g. 'Hemingway', 'Aggressive academic', 'Poetic'):",
        instruction="This will be enforced on every paragraph."
    ).ask()

    # Run fresh research if needed
    if not use_cache and not is_prompt_only:
        console.print("[bold gold1]Running standard research first...[/bold gold1]")
        from agent_writer import AgenticWorkflow
        wf = AgenticWorkflow(selected_pdf, user_prompt, extract_images=False)
        wf.conduct_research()
        research_notes = wf.research_notes

    # Execute
    try:
        wf = iterative_writer.IterativeWriterWorkflow(user_prompt, research_notes, para_count, style_choice)
        wf.run()
    except Exception as exc:
        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")
        raise


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_custom_mode():
    console.clear()
    console.print(Panel.fit(
        "🛠️  [bold cyan]Custom Workflow Builder[/bold cyan]\n"
        "[dim]Design your own multi-agent pipeline in plain English.[/dim]",
        border_style="cyan"
    ))

    # ── Source Document ──────────────────────────────────────────────────────
    input_dir = "inputs"
    os.makedirs(input_dir, exist_ok=True)
    pdfs = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]
    if not pdfs:
        console.print(f"[bold red]No PDFs found in '{input_dir}/'. Add your source document there first.[/bold red]")
        return
    pdf_choice = questionary.select("Which source document should agents work from?", choices=pdfs).ask()
    if not pdf_choice:
        return
    pdf_path = os.path.join(input_dir, pdf_choice)

    # ── Topic / Prompt ───────────────────────────────────────────────────────
    topic = questionary.text("What is the topic or goal of this workflow?").ask()
    if not topic:
        return

    # ── Workflow Name ────────────────────────────────────────────────────────
    workflow_name = questionary.text("Give this workflow a name (e.g. 'Debate & Synthesis'):").ask()
    if not workflow_name:
        workflow_name = "My Custom Workflow"

    # ── Build Stages ─────────────────────────────────────────────────────────
    stages = []
    console.print("\n[bold yellow]Now let's build your stages. A stage is a group of agents that work together.[/bold yellow]")

    while True:
        stage_num = len(stages) + 1
        console.print(f"\n[bold magenta]── Stage {stage_num} ──[/bold magenta]")

        stage_name = questionary.text(f"Name for Stage {stage_num} (e.g. 'First Draft', 'Review', 'Synthesis'):").ask()
        if not stage_name:
            stage_name = f"Stage {stage_num}"

        stage_type = questionary.select(
            "Should the agents in this stage run…",
            choices=[
                questionary.Choice("At the same time (parallel) — faster, independent outputs", value="parallel"),
                questionary.Choice("One after another (sequential) — each agent sees the previous output", value="sequential"),
            ]
        ).ask()
        if not stage_type:
            break

        stage_instruction = questionary.text(
            "What is the overall instruction for this stage? (Agents will receive this as their task context):"
        ).ask() or ""

        # ── Build Agents for this Stage ──────────────────────────────────────
        agents = []
        console.print(f"[dim]Now add agents to '{stage_name}'. Each agent has a name, a role, and a system prompt.[/dim]")

        while True:
            agent_num = len(agents) + 1
            console.print(f"\n  [bold green]Agent {agent_num}[/bold green]")

            agent_name = questionary.text(f"  Agent {agent_num} name (e.g. 'The Critic', 'Writer A'):").ask()
            if not agent_name:
                break

            agent_role = questionary.text(f"  What is {agent_name}'s role in one short phrase (e.g. 'Devil's Advocate'):").ask() or "Worker"

            console.print(f"  [dim]Describe {agent_name}'s personality, expertise and behaviour in plain English.[/dim]")
            console.print(f"  [dim]Example: 'You are a cynical literary critic. You tear apart every argument with precision and cite weaknesses bluntly.'[/dim]")
            agent_prompt = questionary.text(f"  {agent_name}'s system prompt:").ask()
            if not agent_prompt:
                agent_prompt = f"You are {agent_name}, a {agent_role}. Complete the task thoroughly."

            agents.append({
                "name": agent_name,
                "role": agent_role,
                "system_prompt": agent_prompt
            })

            if not questionary.confirm(f"  Add another agent to '{stage_name}'?", default=False).ask():
                break

        if agents:
            stages.append({
                "name": stage_name,
                "type": stage_type,
                "instruction": stage_instruction,
                "agents": agents
            })
            console.print(f"[green]✔ Stage '{stage_name}' added with {len(agents)} agent(s).[/green]")

        if not questionary.confirm("Add another stage to this workflow?", default=False).ask():
            break

    if not stages:
        console.print("[red]No stages defined. Returning to menu.[/red]")
        return

    # ── Review & Confirm ─────────────────────────────────────────────────────
    console.print("\n[bold gold1]── Workflow Summary ──[/bold gold1]")
    console.print(f"[bold]Name:[/bold]  {workflow_name}")
    console.print(f"[bold]Topic:[/bold] {topic}")
    for s_idx, s in enumerate(stages):
        console.print(f"\n  [bold magenta]Stage {s_idx+1}: {s['name']} ({s['type']})[/bold magenta]")
        console.print(f"  Instruction: [dim]{s['instruction'] or '(none)'}[/dim]")
        for a in s["agents"]:
            console.print(f"    • [green]{a['name']}[/green] [{a['role']}] — {a['system_prompt'][:60]}...")

    if not questionary.confirm("\nLooks good? Run this workflow now?").ask():
        return

    # ── Optionally Save ──────────────────────────────────────────────────────
    if questionary.confirm("Save this workflow so you can reuse it later?", default=False).ask():
        os.makedirs("workflows", exist_ok=True)
        safe_name = workflow_name.lower().replace(" ", "_").replace("/", "-")
        save_path = os.path.join("workflows", f"{safe_name}.json")
        config = {"name": workflow_name, "stages": stages}
        with open(save_path, "w", encoding="utf-8") as f:
            import json
            json.dump(config, f, indent=2)
        console.print(f"[green]Saved to {save_path}[/green]")

    # ── Execute ──────────────────────────────────────────────────────────────
    config = {"name": workflow_name, "stages": stages}
    wf = modular_writer.ModularWorkflow(config, pdf_path, topic)
    wf.run()

def main():
    clear_screen()
    print_header()

    mode = questionary.select(
        "Select a mode:",
        choices=[
            questionary.Choice(
                title="🔬  Research Mode    — Run the Scholar on a PDF, save to cache",
                value="research"
            ),
            questionary.Choice(
                title="🏛️   Deep Research    — 4 PhDs analyze, debate, and synthesize a master paper",
                value="deep_research"
            ),
            questionary.Choice(
                title="📝  Essay Mode       — Full multi-agent deep-analysis essay",
                value="essay"
            ),
            questionary.Choice(
                title="🔄  Iterative Mode   — Plan and write paragraph-by-paragraph with live review",
                value="iterative"
            ),
            questionary.Choice(
                title="✍️   Short Writing    — Lean pipeline for articles, stories & more",
                value="short"
            ),
            questionary.Choice(
                title="🛠️   Custom Workflow  — Run your own modular agent pipelines",
                value="custom"
            ),
        ]
    ).ask()

    if not mode:
        sys.exit(0)

    clear_screen()
    print_header()

    if mode == "research":
        run_research_mode()
    elif mode == "deep_research":
        run_deep_research_mode()
    elif mode == "essay":
        run_essay_mode()
    elif mode == "iterative":
        run_iterative_mode()
    elif mode == "short":
        run_short_mode()
    elif mode == "custom":
        run_custom_mode()

if __name__ == "__main__":
    main()

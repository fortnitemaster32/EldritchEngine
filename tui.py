"""
tui.py — EldritchEngine — Main Launcher
Modes:
  🔬  Research Mode   — Run the Scholar on a PDF and save notes to cache
  📝  Essay Mode      — Full multi-agent essay pipeline (agent_writer.py)
  🔄  Iterative Mode  — Plan and write paragraph-by-paragraph with live review
  ✍️   Short Mode      — Lean 3-agent short-form pipeline (short_writer.py)
  📖  Book Mode       — Extensive planning → Page-by-page iterative book writing
"""

import os
import json
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
import book_writer

console = Console()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

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
    input_dir = os.path.join(SCRIPT_DIR, "inputs")
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
        "[bold gold1]EldritchEngine[/bold gold1]\n"
        "[dim]Eldritch Writing Engine  •  v2.0[/dim]",
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


def _find_resume_book_sessions() -> list[str]:
    sessions = []
    logs_dir = os.path.join(SCRIPT_DIR, "logs")
    if not os.path.isdir(logs_dir):
        return sessions

    for name in sorted(os.listdir(logs_dir), reverse=True):
        path = os.path.join(logs_dir, name)
        if not os.path.isdir(path):
            continue
        if name.startswith("book_") and os.path.exists(os.path.join(path, "state.json")):
            sessions.append(path)
    return sessions


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
    selected_pdf = ""
    use_research = questionary.confirm(
        "Use research material (PDF or cache)? Highly recommended for deep, informed essays. (No = write from prompt only)",
        default=True
    ).ask()

    if use_research:
        use_cache = questionary.confirm(
            "Use cached research? (No = select a PDF to research fresh)",
            default=True
        ).ask()

        if use_cache:
            research_notes = pick_cache()
            if not research_notes:
                console.print("[yellow]No cache selected. Falling back to fresh research.[/yellow]")
                use_cache = False

        if not use_cache:
            local_files = get_local_files()
            choices = local_files  # Removed the prompt only option since it's now separate
            chosen = questionary.checkbox(
                "Select PDF(s) to process:",
                choices=choices
            ).ask() or []
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
    use_enricher = questionary.confirm("Enable Enricher Mode? (Adds Lexicographer and Precisionist for enhanced vocabulary - takes longer)", default=False).ask()

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
    console.print(f"  Enricher: {'ON' if use_enricher else 'OFF'}")
    console.print(f"  Length  : {f'~{target_words:,} words' if target_words else 'Natural Length'}")

    if not questionary.confirm("Start the engine?").ask():
        return

    clear_screen()
    console.print("[bold gold1]Engine Starting...[/bold gold1]\n")

    try:
        workflow = agent_writer.AgenticWorkflow(
            selected_pdf, user_prompt,
            extract_images=False,
            preloaded_research=research_notes,
            use_enricher=use_enricher
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

def _ai_generate_system_prompt(agent_name: str, agent_role: str, workflow_topic: str, description: str) -> str:
    """Ask the local LLM to write a system prompt for the agent."""
    helper = agent_writer.LMStudioAgent(
        "Prompt Engineer", "Meta Agent",
        "You are an expert AI prompt engineer. Write a precise, effective system prompt for an AI agent based on the description. Ensure the generated system prompt instructs the agent to produce direct, concise outputs without unnecessary introductions, meta-commentary, or fluff. Output ONLY the system prompt text itself, no commentary."
    )
    request = (
        f"Write a system prompt for an AI agent with these details:\n"
        f"- Name: {agent_name}\n"
        f"- Role: {agent_role}\n"
        f"- Workflow Topic: {workflow_topic}\n"
        f"- What this agent should do: {description}\n"
        f"Ensure the prompt forbids the agent from adding extra fluff, introductions, or meta-comments in their outputs; focus on direct, concise responses.\n"
    )
    with console.status("[cyan]AI is generating the system prompt…[/cyan]"):
        result = helper.chat(request, context="")
    return result.strip()


def _build_context_feed_choice(stage_idx: int, all_stages: list) -> str:
    """Ask the user how this agent should receive its input context."""
    choices = [
        questionary.Choice("Entire accumulated conversation state (default)", value="all_previous"),
        questionary.Choice("Topic/goal only — no prior outputs", value="topic_only"),
        questionary.Choice("Research notes only — no prior outputs", value="research_only"),
        questionary.Choice("All outputs from the previous stage", value="last_stage_all"),
    ]
    if stage_idx > 0:
        prev_stage = all_stages[stage_idx - 1]
        for a in prev_stage.get("agents", []):
            choices.append(questionary.Choice(
                f"Only the output of '{a['name']}' from the previous stage",
                value=f"last_stage_agent:{a['name']}"
            ))

    feed = questionary.select("What information should this agent receive?", choices=choices).ask()
    return feed or "all_previous"


def _display_workflow_summary(config: dict):
    console.print("\n[bold gold1]── Workflow Summary ──[/bold gold1]")
    console.print(f"  [bold]Name:[/bold]  {config['name']}")
    console.print(f"  [bold]Research:[/bold] {'Yes' if config.get('requires_research') else 'No'}")
    for s_idx, s in enumerate(config.get("stages", [])):
        console.print(f"\n  [bold magenta]Stage {s_idx+1}: {s['name']} ({s['type']})[/bold magenta]")
        console.print(f"  Instruction: [dim]{s.get('instruction') or '(none)'}[/dim]")
        for a in s.get("agents", []):
            feed_label = a.get("context_feed", "all_previous")
            preview    = a.get("system_prompt", "")[:60]
            console.print(
                f"    • [green]{a['name']}[/green] [{a['role']}]  feed=[cyan]{feed_label}[/cyan]\n"
                f"      prompt: [dim]{preview}…[/dim]"
            )


def _save_workflow(config: dict) -> str:
    os.makedirs(os.path.join(SCRIPT_DIR, "workflows"), exist_ok=True)
    safe_name  = config["name"].lower().replace(" ", "_").replace("/", "-")
    save_path  = os.path.join(os.path.join(SCRIPT_DIR, "workflows"), f"{safe_name}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return save_path


def _build_workflow_tui(topic: str) -> dict | None:
    """Interactive builder — returns a config dict or None on cancel."""

    workflow_name = questionary.text("Give this workflow a name (e.g. 'Debate & Synthesis'):").ask()
    if not workflow_name:
        return None
    workflow_name = workflow_name.strip() or "My Custom Workflow"

    requires_research = questionary.confirm(
        "Does this workflow need source material (PDF / research cache)?",
        default=False
    ).ask()

    stages: list[dict] = []
    console.print("\n[bold yellow]Now build your stages. A stage is a group of agents that run together.[/bold yellow]")

    while True:
        stage_num = len(stages) + 1
        console.print(f"\n[bold magenta]── Stage {stage_num} ──[/bold magenta]")

        stage_name = (
            questionary.text(f"Name for Stage {stage_num} (e.g. 'Draft', 'Review', 'Synthesis'):").ask()
            or f"Stage {stage_num}"
        )

        stage_type = questionary.select(
            "Should agents in this stage run…",
            choices=[
                questionary.Choice("At the same time (parallel) — independent outputs", value="parallel"),
                questionary.Choice("One after another (sequential) — each sees previous output", value="sequential"),
            ]
        ).ask()
        if not stage_type:
            break

        stage_instruction = (
            questionary.text("Overall instruction for this stage (context for all agents):").ask() or ""
        )

        agents: list[dict] = []
        console.print(f"[dim]Add agents to '{stage_name}'. Each needs a name, role and system prompt.[/dim]")

        while True:
            agent_num = len(agents) + 1
            console.print(f"\n  [bold green]Agent {agent_num}[/bold green]")

            agent_name = questionary.text(f"  Name (e.g. 'The Critic', 'Writer A'):").ask()
            if not agent_name:
                break
            agent_name = agent_name.strip()

            agent_role = (
                questionary.text(f"  One-line role (e.g. 'Devil's Advocate'):").ask() or "Worker"
            ).strip()

            # System prompt: manual or AI-generated
            prompt_mode = questionary.select(
                f"  How should {agent_name}'s system prompt be created?",
                choices=[
                    questionary.Choice("I'll write it myself", value="manual"),
                    questionary.Choice("Let the AI generate it from my description", value="ai"),
                ]
            ).ask()

            if prompt_mode == "ai":
                description = questionary.text(
                    f"  Describe what {agent_name} should do (plain English):"
                ).ask() or f"{agent_name} completes the task."
                agent_prompt = _ai_generate_system_prompt(agent_name, agent_role, topic, description)
                console.print(Panel(agent_prompt, title=f"{agent_name} — Generated Prompt", border_style="cyan"))
                if not questionary.confirm("  Use this generated prompt?", default=True).ask():
                    agent_prompt = questionary.text(f"  Edit the prompt:").ask() or agent_prompt
            else:
                console.print(f"  [dim]Example: 'You are a cynical literary critic who tears apart every argument bluntly.'[/dim]")
                agent_prompt = (
                    questionary.text(f"  {agent_name}'s system prompt:").ask()
                    or f"You are {agent_name}, a {agent_role}. Complete the task thoroughly."
                )

            # Context feed
            context_feed = _build_context_feed_choice(len(stages), stages)

            agents.append({
                "name":         agent_name,
                "role":         agent_role,
                "system_prompt": agent_prompt,
                "context_feed": context_feed,
            })

            if not questionary.confirm(f"  Add another agent to '{stage_name}'?", default=False).ask():
                break

        if agents:
            stages.append({
                "name":        stage_name,
                "type":        stage_type,
                "instruction": stage_instruction,
                "agents":      agents,
            })
            console.print(f"[green]✔ Stage '{stage_name}' added ({len(agents)} agent(s)).[/green]")

        if not questionary.confirm("Add another stage?", default=False).ask():
            break

    if not stages:
        console.print("[red]No stages defined. Cancelling.[/red]")
        return None

    return {
        "name":              workflow_name,
        "requires_research": requires_research,
        "stages":            stages,
    }


def _get_research_for_workflow(workflow_name: str) -> str:
    """Let user pick a PDF/cached research, or skip. Returns research text."""
    cache_dir = os.path.join(SCRIPT_DIR, "research_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cached = [f for f in os.listdir(cache_dir) if f.endswith(".md")]

    input_dir = os.path.join(SCRIPT_DIR, "inputs")
    os.makedirs(input_dir, exist_ok=True)
    pdfs = [f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")]

    source_choices = []
    if cached:
        source_choices.append(questionary.Choice("Use a cached research file", value="cache"))
    if pdfs:
        source_choices.append(questionary.Choice("Load a PDF and cache it now", value="pdf"))
    source_choices.append(questionary.Choice("Skip — no research material", value="none"))

    source = questionary.select("Source material:", choices=source_choices).ask()

    if source == "cache":
        chosen = questionary.select("Select cached research:", choices=cached).ask()
        if chosen:
            with open(os.path.join(cache_dir, chosen), "r", encoding="utf-8") as f:
                return f.read()

    elif source == "pdf":
        pdf_choice = questionary.select("Select PDF:", choices=pdfs).ask()
        if pdf_choice:
            pdf_path = os.path.join(input_dir, pdf_choice)
            notes    = research_cache.get_or_create_cache(pdf_path, modular_writer.extract_pdf_text)
            return notes

    return ""


def run_custom_mode():
    console.clear()
    console.print(Panel.fit(
        "🛠️  [bold cyan]Custom Workflow Mode[/bold cyan]\n"
        "[dim]Design and run your own multi-agent pipelines.[/dim]",
        border_style="cyan"
    ))

    os.makedirs(os.path.join(SCRIPT_DIR, "workflows"), exist_ok=True)
    saved = [f for f in os.listdir(os.path.join(SCRIPT_DIR, "workflows")) if f.endswith(".json")]

    # ── Entry: New or Load ────────────────────────────────────────────────────
    entry_choices = [questionary.Choice("Create a new workflow", value="new")]
    if saved:
        entry_choices.append(questionary.Choice("Run a saved workflow", value="run"))
        entry_choices.append(questionary.Choice("Delete a saved workflow", value="delete"))
    entry_choices.append(questionary.Choice("Back to Main Menu", value="back"))

    action = questionary.select("What would you like to do?", choices=entry_choices).ask()
    if not action or action == "back":
        return

    # ── Load Saved ────────────────────────────────────────────────────────────
    if action == "run":
        chosen = questionary.select("Choose a saved workflow:", choices=saved).ask()
        if not chosen:
            return
        with open(os.path.join(os.path.join(SCRIPT_DIR, "workflows"), chosen), "r", encoding="utf-8") as f:
            config = json.load(f)
        _display_workflow_summary(config)

    elif action == "delete":
        chosen = questionary.select("Choose workflow to delete:", choices=saved).ask()
        if chosen and questionary.confirm(f"Delete '{chosen}'?", default=False).ask():
            os.remove(os.path.join(os.path.join(SCRIPT_DIR, "workflows"), chosen))
            console.print(f"[red]Deleted {chosen}.[/red]")
        return

    # ── Build New ─────────────────────────────────────────────────────────────
    else:
        topic = questionary.text("What is the topic or goal of this workflow?").ask()
        if not topic:
            return

        config = _build_workflow_tui(topic)
        if not config:
            return
        config["topic"] = topic

        _display_workflow_summary(config)

        if not questionary.confirm("\nLooks good?").ask():
            return

        # Always save new workflows
        save_path = _save_workflow(config)
        console.print(f"[green]✔ Workflow saved to {save_path}[/green]")

    # ── Topic override for saved workflows ────────────────────────────────────
    if action == "run":
        topic = config.get("topic", "")
        override = questionary.text(
            f"Topic/prompt for this run (Enter to use saved: '{topic[:60]}'):").ask()
        if override:
            topic = override

    # ── Research material ─────────────────────────────────────────────────────
    research_notes = ""
    if config.get("requires_research"):
        research_notes = _get_research_for_workflow(config["name"])

    # ── Run ───────────────────────────────────────────────────────────────────
    wf = modular_writer.ModularWorkflow(config, topic, research_notes)
    wf.run()


# ---------------------------------------------------------------------------
# Mode: Book Writing
# ---------------------------------------------------------------------------

def run_book_mode():
    try:
        console.print(Panel.fit(
            "📖  [bold gold1]Book Writing Mode[/bold gold1]\n"
            "[dim]Extensive planning → Page-by-page iterative drafting with context condensation[/dim]",
            border_style="gold1"
        ))

        resume_sessions = _find_resume_book_sessions()
        if resume_sessions:
            resume_choice = questionary.confirm(
                "Resume an existing book session?",
                default=False
            ).ask()
            if resume_choice:
                selected = questionary.select(
                    "Choose a session to resume:",
                    choices=[
                        questionary.Choice(title=os.path.basename(path), value=path)
                        for path in resume_sessions
                    ]
                ).ask()
                if selected:
                    try:
                        wf = book_writer.BookWriterWorkflow(resume_dir=selected)
                        wf.run()
                    except Exception as exc:
                        console.print(f"\n[bold red]ERROR:[/bold red] {exc}")
                        raise
                    return

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
            "What book do you want to write?",
            instruction="e.g. 'Write a fantasy novel about a young wizard discovering ancient magic'"
        ).ask()
        if not user_prompt:
            return

        # --- Style selection ---
        style_choice = questionary.select(
            "Choose a style and atmosphere for your book:",
            choices=[
                "Fantasy",
                "Science Fiction",
                "Mystery/Thriller",
                "Literary Fiction",
                "Romance",
                "Horror",
                "Historical",
                "Other (custom)"
            ]
        ).ask()
        if style_choice == "Other (custom)":
            style_choice = questionary.text(
                "Describe the tone, style, and atmosphere you want:",
                instruction="e.g. 'Dark, cinematic epic fantasy with lyrical prose'"
            ).ask() or "Custom"

        # --- Book title ---
        title_choice = questionary.select(
            "Would you like to name the book or have AI generate the title?",
            choices=[
                "Enter title myself",
                "AI generate title"
            ]
        ).ask()

        book_title = ""
        if title_choice == "Enter title myself":
            book_title = questionary.text("Enter your book title:").ask() or "Untitled Book"
        else:
            title_agent = book_writer.LMStudioAgent(
                "Title Generator", "Book Title Generator",
                "You are a creative book title generator. Given a book idea and style, suggest five strong and memorable book titles. Output only a numbered list of titles, no explanation."
            )
            title_prompt = (
                f"Book idea: {user_prompt}\n"
                f"Style: {style_choice}\n\n"
                "Suggest five compelling book titles in a numbered list. Output only the titles."
            )
            response = title_agent.chat(title_prompt, context=research_notes[:20000])
            lines = [line.strip() for line in response.splitlines() if line.strip()]
            suggestions = []
            for line in lines:
                if line[0].isdigit() and "." in line:
                    suggestions.append(line.split(".", 1)[1].strip())
                else:
                    suggestions.append(line)
            generated_title = suggestions[0] if suggestions else "Untitled Book"
            book_title = questionary.text(
                f"AI generated title suggestion: {generated_title}\nEnter your title or press Enter to keep this:",
                default=generated_title
            ).ask() or generated_title

        # --- Summary ---
        console.print("\n[bold gold1]Project Summary:[/bold gold1]")
        console.print(f"  Title   : {book_title}")
        console.print(f"  Style   : {style_choice}")
        console.print(f"  Prompt  : {user_prompt}")
        console.print(f"  Research: {'Cache loaded' if research_notes else 'None (prompt only)'}")

        # --- Auto-accept mode ---
        auto_accept = questionary.confirm(
            "Enable auto-accept mode? (Automatically accept drafts and continue without prompts)",
            default=False
        ).ask()

        if not questionary.confirm("Start book writing? (This will be iterative and may take time)").ask():
            return

        clear_screen()
        console.print("[bold gold1]Book Writing Starting...[/bold gold1]\n")

        try:
            wf = book_writer.BookWriterWorkflow(user_prompt, research_notes, book_title=book_title, book_style=style_choice, auto_accept=auto_accept)
            wf.run()
        except Exception as exc:
            console.print(f"\n[bold red]ERROR:[/bold red] {exc}")
            raise
    except KeyboardInterrupt:
        console.print("\n[dim]Returning to main menu...[/dim]")
        return


def main():
    while True:
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
                    title="�  Book Writing     — Extensive planning → Page-by-page iterative drafting",
                    value="book"
                ),
            ]
        ).ask()

        if not mode:
            break

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
        elif mode == "book":
            run_book_mode()

        console.print("\n[bold green]✓ Mode completed![/bold green]")

        if not questionary.confirm("Return to main menu?", default=True).ask():
            break

if __name__ == "__main__":
    main()

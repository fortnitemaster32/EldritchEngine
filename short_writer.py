"""
short_writer.py — Short Writing Mode
A lean 3-agent pipeline: Planner → Rolling Writer → Editor.
Accepts optional pre-loaded research notes (from cache) to skip the Scholar phase.
"""

import os
import math
from openai import OpenAI
from typing import List, Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

WORDS_PER_SECTION = 450   # Target words the Writer produces per API call
ROLLING_WORD_WINDOW = 700  # How many recent words to pass as "already written" context


from agent_writer import LMStudioAgent

# ---------------------------------------------------------------------------
# Short Writing Workflow
# ---------------------------------------------------------------------------

class ShortWriterWorkflow:
    """
    A fast, focused pipeline for producing short-form written pieces
    (articles, op-eds, short stories, essays, poems, etc.)

    Parameters
    ----------
    user_prompt : str
        The topic, premise, or creative brief.
    genre : str
        The type of piece (e.g. "short story", "op-ed", "poem", "article").
    target_words : int
        Approximate word count for the finished piece.
    research_notes : str
        Pre-loaded research notes from the cache (can be empty string).
    """

    def __init__(self, user_prompt: str, genre: str, target_words: int,
                 research_notes: str = ""):
        self.user_prompt    = user_prompt
        self.genre          = genre
        self.target_words   = target_words
        self.research_notes = research_notes

        self.log_dir = os.path.join(
            os.path.join(SCRIPT_DIR, "logs"), f"short_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(self.log_dir, exist_ok=True)

        self.planner = LMStudioAgent(
            "The Planner", "Structural Planner",
            self._load_prompt("short_planner.md")
        )
        self.writer = LMStudioAgent(
            "The Writer", "Prose Writer",
            self._load_prompt("short_writer.md")
        )
        self.editor = LMStudioAgent(
            "The Editor", "Final Polisher",
            self._load_prompt("short_editor.md")
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join(SCRIPT_DIR, "prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read().strip()
        raise FileNotFoundError(f"Missing prompt file: {path}")

    def _log_step(self, name: str, content: str):
        path = os.path.join(self.log_dir, f"{name}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# {name}\n\n{content}")

    def _research_context(self, max_chars: int = 50000) -> str:
        if self.research_notes:
            return f"### RESEARCH NOTES ###\n{self.research_notes[:max_chars]}"
        return ""

    # ------------------------------------------------------------------
    # Phase 1 — Planning
    # ------------------------------------------------------------------

    def plan(self) -> str:
        console.print("\n[bold cyan]The Planner is drafting the outline...[/bold cyan]")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      console=console) as prog:
            prog.add_task("[cyan]Planning...", total=None)
            outline = self.planner.chat(
                (
                    f"Genre: {self.genre}\n"
                    f"Prompt: {self.user_prompt}\n"
                    f"Target length: approximately {self.target_words} words\n\n"
                    "Task: Create a detailed section-by-section outline. "
                    "Label each section with its purpose and an approximate word count."
                ),
                context=self._research_context()
            )
        self._log_step("0_Outline", outline)
        return outline

    # ------------------------------------------------------------------
    # Phase 2 — Rolling-window writing loop
    # ------------------------------------------------------------------

    def write(self, outline: str) -> str:
        num_sections = max(2, math.ceil(self.target_words / WORDS_PER_SECTION))
        words_per_section = self.target_words // num_sections
        written_sections: List[str] = []

        console.print(
            f"\n[bold cyan]The Writer is composing "
            f"{num_sections} sections (~{words_per_section} words each)...[/bold cyan]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as prog:
            task = prog.add_task("Writing section 1 ...", total=num_sections)

            for i in range(num_sections):
                is_first = i == 0
                is_last  = i == num_sections - 1

                # Rolling context — last N words already written
                rolling = ""
                if written_sections:
                    all_so_far = "\n\n".join(written_sections)
                    last_words = all_so_far.split()[-ROLLING_WORD_WINDOW:]
                    rolling = " ".join(last_words)

                position = (
                    "opening section" if is_first
                    else ("final section — bring the piece to a decisive close" if is_last
                          else f"section {i + 1} of {num_sections}")
                )

                prompt = (
                    f"FULL OUTLINE:\n{outline}\n\n"
                    + (
                        f"ALREADY WRITTEN (continue seamlessly from the last word):\n"
                        f"...{rolling}\n\n"
                        if rolling else
                        "This is the OPENING — begin the piece immediately.\n\n"
                    )
                    + f"TASK: Write the {position}. "
                    + f"Aim for approximately {words_per_section} words. "
                    + (
                        "IMPORTANT: This is the FINAL section — deliver a strong, "
                        "conclusive ending. Do not trail off."
                        if is_last else
                        "Do NOT wrap up or conclude the piece yet — more sections follow."
                    )
                )

                section_text = self.writer.chat(
                    prompt,
                    context=self._research_context(max_chars=30000)
                )
                written_sections.append(section_text)

                prog.update(
                    task,
                    advance=1,
                    description=(
                        f"Writing section {i + 2} of {num_sections}..."
                        if not is_last else "Writing complete ✓"
                    )
                )

        full_draft = "\n\n".join(written_sections)
        self._log_step("1_Draft", full_draft)
        return full_draft

    # ------------------------------------------------------------------
    # Phase 3 — Final edit
    # ------------------------------------------------------------------

    def edit(self, draft: str, outline: str) -> str:
        console.print("\n[bold magenta]The Editor is polishing the final piece...[/bold magenta]")
        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      console=console) as prog:
            prog.add_task("[magenta]Editing...", total=None)
            final = self.editor.chat(
                (
                    f"ORIGINAL OUTLINE:\n{outline}\n\n"
                    f"FULL DRAFT:\n{draft}\n\n"
                    "Task: Polish this into a final, publication-ready piece. "
                    "Fix transitions, sharpen the opening and closing, eliminate "
                    "redundancy. Do NOT significantly shorten the piece."
                ),
                context=f"Genre: {self.genre} | Target: ~{self.target_words} words"
            )
        self._log_step("2_Final", final)
        return final

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run(self) -> str:
        console.print(Panel.fit(
            f"✍️  [bold gold1]Short Writing Mode[/bold gold1]\n"
            f"[dim]Genre: {self.genre} | Target: ~{self.target_words} words[/dim]",
            border_style="gold1"
        ))

        outline = self.plan()
        console.print(Panel(
            Markdown(outline),
            title="[bold cyan]Outline[/bold cyan]",
            border_style="cyan"
        ))

        draft  = self.write(outline)
        final  = self.edit(draft, outline)

        # Save output
        os.makedirs(os.path.join(SCRIPT_DIR, "outputs"), exist_ok=True)
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join("outputs", f"short_work_{timestamp}.md")
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write(final)

        console.print(Panel.fit(
            f"✅ [bold green]Complete![/bold green]\n\n"
            f"Output: [bold underline]{output_file}[/bold underline]\n"
            f"Logs:   [bold underline]{self.log_dir}[/bold underline]",
            border_style="green"
        ))
        return final

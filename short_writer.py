"""
short_writer.py — Short Writing Mode
A lean 3-agent pipeline: Planner → Rolling Writer → Editor.
Accepts optional pre-loaded research notes (from cache) to skip the Scholar phase.
"""

import os
import math
from concurrent.futures import ThreadPoolExecutor
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
        self.writer_creative = LMStudioAgent(
            "The Creative Writer", "Imaginative Storyteller",
            self._load_prompt("short_writer_creative.md")
        )
        self.writer_logical = LMStudioAgent(
            "The Logical Writer", "Structured Prose Specialist",
            self._load_prompt("short_writer_logical.md")
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

    def _research_context(self, max_chars: int = 200000) -> str:
        if self.research_notes:
            return f"### RESEARCH NOTES ###\n{self.research_notes[:max_chars]}"
        return ""

    def _measure_word_count(self, text: str) -> int:
        return len(text.split())

    def _generate_additional_section(
        self,
        outline: str,
        writer_agent,
        writer_type: str,
        written_sections: List[str],
        remaining_words: int,
        telemetry=None
    ) -> str:
        if remaining_words <= 50:
            return ""

        console.print(
            f"\n[bold cyan]{writer_agent.name} is adding a bridging continuation to reach the target length ({remaining_words} more words)...[/bold cyan]"
        )

        all_so_far = "\n\n".join(written_sections)
        last_words = all_so_far.split()[-ROLLING_WORD_WINDOW:]
        rolling = " ".join(last_words)

        prompt = (
            f"FULL OUTLINE:\n{outline}\n\n"
            + (
                f"ALREADY WRITTEN (continue seamlessly from the last word):\n"
                f"...{rolling}\n\n"
            )
            + f"TASK: Continue the piece, adding approximately {remaining_words} words to move the draft toward the target length. "
            "Begin with a natural transitional sentence that bridges from the previous section into this one. "
            "This is the FINAL section — bring the piece to a strong, decisive close without repeating or restating already written text. "
            "Do NOT trail off or add meta-commentary."
        )

        def on_update(data):
            if telemetry:
                telemetry.update(f"Add Section ({writer_type})", data)
                telemetry.refresh()

        continuation_text = writer_agent.chat(
            prompt,
            context=self._research_context(),
            on_update=on_update
        )
        return continuation_text

    # ------------------------------------------------------------------
    # Phase 1 — Planning
    # ------------------------------------------------------------------

    def plan(self, telemetry=None) -> str:
        console.print("\n[bold cyan]The Planner is drafting the outline...[/bold cyan]")
        def on_update(data):
            if telemetry:
                telemetry.update("The Planner", data)
                telemetry.refresh()
        
        outline = self.planner.chat(
            (
                f"Genre: {self.genre}\n"
                f"Prompt: {self.user_prompt}\n"
                f"Target length: approximately {self.target_words} words\n\n"
                "Task: Create a detailed section-by-section outline. "
                "Label each section with its purpose and an approximate word count."
            ),
            context=self._research_context(),
            on_update=on_update
        )
        self._log_step("0_Outline", outline)
        return outline

    # ------------------------------------------------------------------
    # Phase 2 — Parallel dual-writer composition
    # ------------------------------------------------------------------

    def _generate_draft(self, outline: str, writer_agent, writer_type: str, telemetry=None) -> str:
        """Generate a complete draft using the given writer agent."""
        num_sections = max(2, math.ceil(self.target_words / WORDS_PER_SECTION))
        words_per_section = math.ceil(self.target_words / num_sections)
        written_sections: List[str] = []

    def _run_draft_loop(self, outline, writer_agent, writer_type, num_sections, words_per_section, written_sections, telemetry, prog=None, task=None):
        for i in range(num_sections):
            is_first = i == 0
            is_last  = i == num_sections - 1

            def on_update(data):
                if telemetry:
                    telemetry.update(f"{writer_agent.name} (S{i+1})", data)
                    telemetry.refresh()

            # Rolling context
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
            )

            section_text = writer_agent.chat(
                prompt,
                context=self._research_context(),
                on_update=on_update
            )
            written_sections.append(section_text)
            if telemetry: telemetry.update(f"{writer_agent.name} (S{i+1})", {"status": "[green]Done[/green]", "tps": 0, "tokens": 0})
            
            if prog and task:
                prog.update(task, advance=1, description=f"Writing section {i+2} ({writer_type})..." if i+1 < num_sections else "Done")

        if not telemetry:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as prog:
                task = prog.add_task(f"Writing section 1 ({writer_type})...", total=num_sections)
                self._run_draft_loop(outline, writer_agent, writer_type, num_sections, words_per_section, written_sections, telemetry, prog, task)
        else:
            self._run_draft_loop(outline, writer_agent, writer_type, num_sections, words_per_section, written_sections, telemetry)

        full_draft = "\n\n".join(written_sections)
        total_words = self._measure_word_count(full_draft)
        if total_words < self.target_words:
            remaining = self.target_words - total_words
            continuation = self._generate_additional_section(
                outline, writer_agent, writer_type, written_sections, remaining, telemetry
            )
            if continuation.strip():
                written_sections.append(continuation)
                full_draft = "\n\n".join(written_sections)

        return full_draft

    def write(self, outline: str, telemetry=None) -> tuple[str, str]:
        """Generate two parallel drafts: one creative, one logical."""
        console.print(
            f"\n[bold yellow]Two Writers are now composing in parallel...[/bold yellow]"
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            creative_future = executor.submit(
                self._generate_draft, outline, self.writer_creative, "creative", telemetry
            )
            logical_future = executor.submit(
                self._generate_draft, outline, self.writer_logical, "logical", telemetry
            )

            creative_draft = creative_future.result()
            self._log_step("1_CreativeDraft", creative_draft)

            logical_draft = logical_future.result()
            self._log_step("1_LogicalDraft", logical_draft)

        return creative_draft, logical_draft

    # ------------------------------------------------------------------
    # Phase 3 — Merge & polish
    # ------------------------------------------------------------------

    def edit(self, creative_draft: str, logical_draft: str, outline: str, telemetry=None) -> str:
        console.print("\n[bold magenta]The Editor is merging and polishing...[/bold magenta]")
        def on_update(data):
            if telemetry:
                telemetry.update("The Editor", data)
                telemetry.refresh()
        
        final = self.editor.chat(
            (
                f"ORIGINAL OUTLINE:\n{outline}\n\n"
                f"CREATIVE DRAFT:\n{creative_draft}\n\n"
                f"LOGICAL DRAFT:\n{logical_draft}\n\n"
                "Task: Merge the best parts of both drafts into one final piece."
            ),
            context=f"Genre: {self.genre} | Target: ~{self.target_words} words\n{self._research_context(max_chars=30000)}",
            on_update=on_update
        )
        self._log_step("2_Final", final)
        return final

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def run(self, telemetry=None) -> str:
        console.print(Panel.fit(
            f"✍️  [bold gold1]Short Writing Mode[/bold gold1]\n"
            f"[dim]Genre: {self.genre} | Target: ~{self.target_words} words[/dim]",
            border_style="gold1"
        ))

        outline = self.plan(telemetry=telemetry)
        console.print(Panel(
            Markdown(outline),
            title="[bold cyan]Outline[/bold cyan]",
            border_style="cyan"
        ))

        creative_draft, logical_draft = self.write(outline, telemetry=telemetry)
        final = self.edit(creative_draft, logical_draft, outline, telemetry=telemetry)

        # Save output
        os.makedirs(os.path.join(SCRIPT_DIR, "outputs"), exist_ok=True)
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(SCRIPT_DIR, "outputs", f"short_work_{timestamp}.md")
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write(final)

        console.print(Panel.fit(
            f"✅ [bold green]Complete![/bold green]\n\n"
            f"Output: [bold underline]{output_file}[/bold underline]\n"
            f"Logs:   [bold underline]{self.log_dir}[/bold underline]",
            border_style="green"
        ))
        return {
            "type": "single",
            "output_file": output_file,
            "title": self.user_prompt,
        }

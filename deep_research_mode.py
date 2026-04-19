"""
deep_research_mode.py — Parallel PhD Research System

Phase 1: Parallel Research (4 scholars process the PDF using a rolling window).
Phase 2: Debate (Each scholar critiques the aggregated notes of the others).
Phase 3: Synthesis (Chief Scholar combines everything into a master paper).
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
import math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import agent_writer
import research_cache

console = Console()

class DeepResearchWorkflow:
    def __init__(self, pdf_path: str, user_prompt: str):
        self.pdf_path = pdf_path
        self.user_prompt = user_prompt
        self.log_dir = os.path.join(os.path.join(SCRIPT_DIR, "logs"), f"deep_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.pdf_pages = []
        if pdf_path:
            # We don't need image extraction for deep text research here
            doc = agent_writer.AgenticWorkflow(pdf_path, user_prompt)
            self.pdf_pages = doc.pdf_pages

        self.scholars = [
            agent_writer.LMStudioAgent(
                "Dr. Evelyn Hart", "Philosopher",
                self._load_prompt("phd_philosopher.md")
            ),
            agent_writer.LMStudioAgent(
                "Dr. Marcus Reid", "Psychologist",
                self._load_prompt("phd_psychologist.md")
            ),
            agent_writer.LMStudioAgent(
                "Dr. Elena Rostova", "Literary Critic",
                self._load_prompt("phd_literary.md")
            ),
            agent_writer.LMStudioAgent(
                "Dr. Jamal Tariq", "Sociologist",
                self._load_prompt("phd_sociologist.md")
            )
        ]

        self.chief_scholar = agent_writer.LMStudioAgent(
            "The Chief Scholar", "Synthesizer",
            self._load_prompt("chief_scholar.md")
        )
        
        self.debate_prompt = self._load_prompt("debate_critique.md")

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join(SCRIPT_DIR, "prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        raise FileNotFoundError(f"Missing prompt file: {path}")

    def _log_step(self, name: str, content: str):
        path = os.path.join(self.log_dir, f"{name}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# {name}\n\n{content}")

    def run(self):
        if not self.pdf_pages:
            console.print("[red]No PDF content available.[/red]")
            return

        total_pages = len(self.pdf_pages)
        chunk_size = 5
        
        console.print(Panel.fit(
            "🔬 [bold gold1]Deep Research Mode[/bold gold1]\n"
            "[dim]4 parallel PhDs • Debate • Synthesis[/dim]",
            border_style="gold1"
        ))

        # --- Phase 1: Parallel Research ---
        console.print(f"\n[bold cyan]Phase 1: 4 Scholars analyzing {total_pages} pages...[/bold cyan]")
        
        scholar_notes = {s.name: [] for s in self.scholars}
        
        # To avoid hitting local LLMs too hard, we might do chunks sequentially but scholars parallel per chunk,
        # OR scholars sequentially but chunks parallel.
        # Safest for LM Studio (which often handles 1 request at a time well, or errors if overloaded):
        # We will iterate through chunks. For each chunk, the 4 scholars analyze it.
        # To speed it up, we'll try ThreadPoolExecutor, but user might need to ensure LM Studio supports parallel requests.
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            chunk_task = progress.add_task("Processing Chunks...", total=math.ceil(total_pages/chunk_size))
            
            for i in range(0, total_pages, chunk_size):
                chunk = "\n".join(self.pdf_pages[i : i + chunk_size])
                chunk_desc = f"Pages {i+1} to {min(i + chunk_size, total_pages)}"
                
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {}
                    for scholar in self.scholars:
                        prior_research = "\n\n".join(scholar_notes[scholar.name])
                        prior_context_header = (
                            f"### YOUR PRIOR RESEARCH SO FAR ###\n"
                            f"{prior_research[-30000:]}\n\n"
                            f"### CURRENT SECTION TO ANALYSE ###\n"
                        ) if prior_research else ""
                        
                        full_context = prior_context_header + chunk
                        prompt = (
                            f"PROMPT: {self.user_prompt}\n"
                            f"SECTION: {chunk_desc}\n"
                            f"TASK: Perform your specialized disciplinary analysis on this section. "
                            f"Maintain continuity with your prior research."
                        )
                        futures[executor.submit(scholar.chat, prompt, context=full_context[:100000])] = scholar.name
                        
                    for future in as_completed(futures):
                        name = futures[future]
                        res = future.result()
                        scholar_notes[name].append(f"## {chunk_desc}\n\n{res}")
                
                progress.update(chunk_task, advance=1)

        # Log individual scholar notes
        compiled_notes = {}
        for scholar in self.scholars:
            full_notes = "\n\n".join(scholar_notes[scholar.name])
            compiled_notes[scholar.name] = full_notes
            self._log_step(f"1_{scholar.name.replace(' ', '_')}_Notes", full_notes)

        # --- Phase 2: Debate ---
        console.print("\n[bold magenta]Phase 2: Scholars are debating and critiquing...[/bold magenta]")
        
        critiques = {}
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            debate_task = progress.add_task("Debating...", total=4)
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                for scholar in self.scholars:
                    # Assemble peers' notes
                    peers_notes = ""
                    for other in self.scholars:
                        if other.name != scholar.name:
                            peers_notes += f"\n\n### {other.name} ({other.role}) FINDINGS ###\n{compiled_notes[other.name]}"
                    
                    full_prompt = (
                        f"{self.debate_prompt}\n\n"
                        f"YOUR ORIGINAL DISCIPLINE: {scholar.role}\n\n"
                        f"TASK: Write your critique based on the peers' findings provided in the context."
                    )
                    
                    futures[executor.submit(scholar.chat, full_prompt, context=peers_notes)] = scholar.name
                
                for future in as_completed(futures):
                    name = futures[future]
                    res = future.result()
                    critiques[name] = res
                    self._log_step(f"2_{name.replace(' ', '_')}_Critique", res)
                    progress.update(debate_task, advance=1)

        # --- Phase 3: Synthesis ---
        console.print("\n[bold green]Phase 3: The Chief Scholar is synthesizing the final paper...[/bold green]")
        
        all_research_and_debate = "### ORIGINAL RESEARCH NOTES ###\n"
        for name, notes in compiled_notes.items():
            all_research_and_debate += f"\n#### {name} ####\n{notes}\n"
            
        all_research_and_debate += "\n\n### DEBATE AND CRITIQUES ###\n"
        for name, critique in critiques.items():
            all_research_and_debate += f"\n#### {name}'s Critique ####\n{critique}\n"

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            prog.add_task("Synthesizing Final Masterwork...", total=None)
            final_paper = self.chief_scholar.chat(
                f"PROMPT: {self.user_prompt}\n\nTASK: Synthesize the research and debate into a definitive masterwork.",
                context=all_research_and_debate[:120000]
            )
            
        self._log_step("3_Final_Synthesis", final_paper)
        
        # Save output
        os.makedirs(os.path.join(SCRIPT_DIR, "outputs"), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(SCRIPT_DIR, "outputs", f"deep_research_paper_{timestamp}.md")
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write(final_paper)
            
        # Cache the final paper so it can be used in other modes
        cache_id = research_cache.save_research(
            source_name=os.path.basename(self.pdf_path) + " (Deep Research)",
            prompt=self.user_prompt,
            research_notes=final_paper,
            page_count=len(self.pdf_pages),
        )

        console.print(Panel.fit(
            f"✅ [bold green]Deep Research Complete![/bold green]\n\n"
            f"Output: [bold underline]{output_file}[/bold underline]\n"
            f"Logs:   [bold underline]{self.log_dir}[/bold underline]\n"
            f"Saved to Cache as: [bold]{cache_id}[/bold]",
            border_style="green"
        ))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        console.print("[bold red]Usage:[/bold red] python deep_research_mode.py <pdf_path> \"<prompt>\"")
        sys.exit(1)
    
    pdf = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    workflow = DeepResearchWorkflow(pdf, prompt)
    workflow.run()

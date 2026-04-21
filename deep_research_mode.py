"""
deep_research_mode.py — Parallel PhD Research System

Phase 1: Parallel Research (4 scholars process the PDF using a rolling window).
Phase 2: Debate (Each scholar critiques the aggregated notes of the others).
Phase 3: Synthesis (Chief Scholar combines everything into a master paper).
"""

import os
import sys
import concurrent.futures
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import math
import agent_writer
import research_cache
import config_manager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
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
        # --- Phase 3: Thematic Mapping (Master Outline) ---
        console.print("\n[bold green]Phase 3: The Chief Scholar is generating a 20k-word Master Outline...[/bold green]")
        
        all_research_and_debate = "### ORIGINAL RESEARCH NOTES ###\n"
        for name, notes in compiled_notes.items():
            all_research_and_debate += f"\n#### {name} ####\n{notes}\n"
            
        all_research_and_debate += "\n\n### DEBATE AND CRITIQUES ###\n"
        for name, critique in critiques.items():
            all_research_and_debate += f"\n#### {name}'s Critique ####\n{critique}\n"

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            prog.add_task("Mapping Themes & Chapters...", total=None)
            outline_prompt = (
                f"TOPIC: {self.user_prompt}\n\n"
                "TASK: Based on the research notes and debates provided, create a comprehensive 10-15 chapter outline "
                "for a 20,000+ word master thesis. Each chapter should be a deep-dive into a specific intersection of the disciplines. "
                "Output only a numbered list of chapters with descriptive titles."
            )
            outline_res = self.chief_scholar.chat(outline_prompt, context=all_research_and_debate[:100000])
            
        self._log_step("3_Master_Outline", outline_res)
        
        # Parse chapters
        chapters = []
        for line in outline_res.splitlines():
            line = line.strip()
            if line and line[0].isdigit() and "." in line:
                chapters.append(line)
        
        if not chapters:
            chapters = ["1. Introduction and Core Analysis", "2. Disciplinary Intersections", "3. Synthesis of Scholarly Debate", "4. Conclusion"]

        # --- Phase 4: Sectional Synthesis (Long-Form Drafting) ---
        console.print(f"\n[bold green]Phase 4: Sectional Synthesis ({len(chapters)} Chapters, 2 Parallely)...[/bold green]")
        
        from ui_core import TelemetryDisplay
        telemetry = TelemetryDisplay()
        final_paper_sections = [None] * len(chapters)
        
        def draft_chapter(idx, chapter_title):
            def on_update(data):
                telemetry.update(f"Ch {idx+1}: {chapter_title[:20]}...", data)
                telemetry.refresh()

            section_prompt = (
                f"YOU ARE WRITING A CHAPTER FOR A 20,000 WORD MASTER THESIS.\n"
                f"CURRENT CHAPTER: {chapter_title}\n\n"
                "TASK: Write a 1,500-2,000 word analytical deep-dive for this chapter. "
                "You MUST weave together the perspectives of the 4 PhDs (Hart, Reid, Tariq, Rostova), "
                "explicitly noting where they agree, disagree, or provide complementary nuance. "
                "Maintain extreme information density and academic rigor."
            )
            section_content = self.chief_scholar.chat(section_prompt, context=all_research_and_debate[:120000], on_update=on_update)
            telemetry.update(f"Ch {idx+1}: {chapter_title[:20]}...", {"status": "[bold green]Done[/bold green]", "tps": 0, "tokens": 0})
            telemetry.refresh()
            return idx, f"# {chapter_title}\n\n{section_content}"

        with telemetry:
            max_workers = config_manager.get_setting("max_concurrency")
            console.print(f"  [dim]Using {max_workers} parallel workers...[/dim]")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_chapter = {
                    executor.submit(draft_chapter, i, title): title 
                    for i, title in enumerate(chapters)
                }
                
                for future in concurrent.futures.as_completed(future_to_chapter):
                    idx, content = future.result()
                    final_paper_sections[idx] = content

        final_paper = "\n\n---\n\n".join(final_paper_sections)
        output_file = os.path.join(self.log_dir, "5_Final_Master_Thesis.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# FINAL MASTER THESIS: {os.path.basename(self.pdf_path)}\n\n" + final_paper)
        
        # --- Phase 5: Aggregated Dossier (High Density) ---
        console.print("\n[bold cyan]Phase 5: Compiling the Aggregated Scholarly Dossier (High Density)...[/bold cyan]")
        
        dossier_content = f"# Aggregated Scholarly Dossier: {os.path.basename(self.pdf_path)}\n\n"
        dossier_content += f"**Research Focus**: {self.user_prompt}\n\n"
        dossier_content += "This document contains the complete, unedited research notes from all four specialized scholars. Use this for maximum information density.\n\n"
        
        for scholar in self.scholars:
            dossier_content += f"\n\n{'='*40}\n"
            dossier_content += f"# DISCIPLINE: {scholar.role} ({scholar.name})\n"
            dossier_content += f"{'='*40}\n\n"
            dossier_content += compiled_notes[scholar.name]
            
        dossier_path = os.path.join(self.log_dir, "6_Aggregated_Scholarly_Dossier.md")
        with open(dossier_path, "w", encoding="utf-8") as f:
            f.write(dossier_content)
            
        # Cache the dossier separately
        dossier_cache_id = research_cache.save_research(
            source_name=os.path.basename(self.pdf_path) + " (Full Scholarly Dossier)",
            prompt=self.user_prompt,
            research_notes=dossier_content,
            page_count=len(self.pdf_pages),
        )

        console.print(Panel.fit(
            f"✅ [bold green]Deep Research Complete![/bold green]\n\n"
            f"1. Final Thesis:  [cyan]{output_file}[/cyan]\n"
            f"2. Dossier Cache: [cyan]{dossier_cache_id}[/cyan]",
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

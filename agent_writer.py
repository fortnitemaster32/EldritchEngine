import os
import sys
import fitz  # PyMuPDF
from openai import OpenAI
from typing import List, Dict
import json
import time
import threading
import re
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.markdown import Markdown

console = Console()

class LMStudioAgent:
    def __init__(self, name: str, role: str, system_prompt: str, base_url: str = "http://localhost:1234/v1"):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.client = OpenAI(base_url=base_url, api_key="lm-studio")
        self.model = "local-model"

    def chat(self, user_input: str, context: str = "", history: List[Dict] = None) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        
        full_content = f"### PDF CONTEXT ###\n{context}\n\n### TASK ###\n{user_input}" if context else user_input
        messages.append({"role": "user", "content": full_content})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error communicating with LM Studio: {e}"

class AgenticWorkflow:
    def _load_prompt(self, filename: str) -> str:
        path = os.path.join(SCRIPT_DIR, "prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        raise FileNotFoundError(f"Missing prompt file: {path}")

    def __init__(self, pdf_path: str, user_prompt: str, extract_images: bool = False,
                 preloaded_research: str = "", use_enricher: bool = False):
        self.pdf_path = pdf_path
        self.user_prompt = user_prompt
        self.log_dir = os.path.join(SCRIPT_DIR, "logs", f"work_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.pdf_pages = []
        self.image_count = 0
        if pdf_path:
            self.pdf_pages, self.image_count = self._extract_pdf_content(pdf_path, extract_images=extract_images)
        
        self.pdf_content = "\n".join(self.pdf_pages)
        # If pre-loaded research is provided (from cache), use it directly
        self.research_notes = preloaded_research
        self.use_enricher = use_enricher

        # Enricher agents (optional)
        if use_enricher:
            self.lexicographer = LMStudioAgent(
                "The Lexicographer", "Vocabulary Curator",
                self._load_prompt("lexicographer.md")
            )
            self.precisionist = LMStudioAgent(
                "The Precisionist", "Synonym Specialist",
                self._load_prompt("precisionist.md")
            )

        # 0. The Scholar (Deep Research)
        self.scholar = LMStudioAgent(
            "The Scholar", "Lead Researcher",
            self._load_prompt("scholar.md")
        )
        
        # 1. The Strategist (Thesis Generator)
        self.strategist = LMStudioAgent(
            "The Strategist", "Lead Philosopher",
            self._load_prompt("strategist.md")
        )

        # 2. The Manager (Architect)
        self.manager = LMStudioAgent(
            "The Architect", 
            "Project Manager",
            self._load_prompt("architect.md")
        )
        
        # 3. The 4 Writers (Distinct Personalities)
        self.writer_profiles = [
            {
                "name": "The Visionary",
                "role": "Creative/Conceptual",
                "prompt": self._load_prompt("writer_visionary.md")
            },
            {
                "name": "The Analyst",
                "role": "Rigorous/Academic",
                "prompt": self._load_prompt("writer_analyst.md")
            },
            {
                "name": "The Challenger",
                "role": "Critical/Provocative",
                "prompt": self._load_prompt("writer_challenger.md")
            },
            {
                "name": "The Storyteller",
                "role": "Narrative/Engaging",
                "prompt": self._load_prompt("writer_storyteller.md")
            }
        ]
        
        self.writers = [
            LMStudioAgent(profile["name"], profile["role"], profile["prompt"])
            for profile in self.writer_profiles
        ]
        self.reviewers = [
            LMStudioAgent("The Auditor", "Logical Reviewer", 
                self._load_prompt("reviewer_auditor.md")),
            LMStudioAgent("The Stylist", "Linguistic Reviewer", 
                self._load_prompt("reviewer_stylist.md"))
        ]
        
        # 7. The 2 Editors
        self.editors = [
            LMStudioAgent("The Sculptor", "Structural Editor", 
                self._load_prompt("editor_sculptor.md")),
            LMStudioAgent("The Finisher", "Final Polisher", 
                self._load_prompt("editor_finisher.md"))
        ]
        
        self.fact_checker = LMStudioAgent(
            "The Auditor", "Fact Checker",
            self._load_prompt("fact_checker.md")
        )

    def _extract_pdf_content(self, pdf_path: str, extract_images: bool = False) -> tuple:
        console.print(f"[bold cyan]Reading PDF:[/bold cyan] {pdf_path}")
        try:
            doc = fitz.open(pdf_path)
            pages = []
            image_count = 0
            
            img_dir = os.path.join(self.log_dir, "extracted_images")
            os.makedirs(img_dir, exist_ok=True)
            
            for i, page in enumerate(doc):
                pages.append(page.get_text())
                
                if extract_images:
                    for img_index, img in enumerate(page.get_images(full=True)):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        image_filename = f"page_{i+1}_img_{img_index}.{image_ext}"
                        with open(os.path.join(img_dir, image_filename), "wb") as f:
                            f.write(image_bytes)
                        image_count += 1
                    
            if extract_images:
                console.print(f"[bold green]Extracted {image_count} images.[/bold green]")
            return pages, image_count
        except Exception as e:
            console.print(f"[bold red]Error reading PDF:[/bold red] {e}")
            return [], 0

    def conduct_research(self):
        # --- Skip if research was pre-loaded from cache ---
        if self.research_notes:
            console.print("[bold green]✓ Using pre-loaded research notes (cache hit — skipping Scholar).[/bold green]")
            return

        if not self.pdf_pages:
            self.research_notes = "No PDF content available for research. Proceeding with user prompt only."
            return

        chunk_size = 5
        total_pages = len(self.pdf_pages)
        research_outputs = []

        console.print(f"\n[bold cyan]The Scholar is analyzing {total_pages} pages in {chunk_size}-page chunks...[/bold cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task_id = progress.add_task("Conducting Research...", total=total_pages)
            
            for i in range(0, total_pages, chunk_size):
                chunk = "\n".join(self.pdf_pages[i : i + chunk_size])
                chunk_desc = f"Pages {i+1} to {min(i + chunk_size, total_pages)}"
                
                # Build a rolling summary of prior research so the Scholar has continuity
                prior_research = "\n\n".join(research_outputs)
                prior_context_header = (
                    f"### PRIOR RESEARCH (everything documented so far — use this for continuity) ###\n"
                    f"{prior_research[-40000:]}\n\n"  # Last ~40k chars to stay within token budget
                    f"### CURRENT SECTION TO ANALYSE ###\n"
                ) if research_outputs else ""
                
                full_chunk_context = prior_context_header + chunk
                
                response = self.scholar.chat(
                    (
                        f"PROMPT: {self.user_prompt}\n"
                        f"SECTION: {chunk_desc}\n"
                        f"TASK: Perform an exhaustive extraction of all details, character arcs, and specific arguments within this section. "
                        f"Cross-reference with prior research above — if characters or arguments were introduced earlier, continue their arc. "
                        f"Do not summarize; document every specific detail."
                    ),
                    context=full_chunk_context[:120000]
                )
                research_outputs.append(f"## Research: {chunk_desc}\n\n{response}")
                progress.update(task_id, advance=len(self.pdf_pages[i : i + chunk_size]))

        self.research_notes = "\n\n".join(research_outputs)
        self._log_step("0_Scholar_Research_Notes", self.research_notes)
        
        # Save to logs
        research_file = os.path.join(self.log_dir, "research_notes.md")
        with open(research_file, "w", encoding="utf-8") as f:
            f.write(f"# Research Notes for: {self.user_prompt}\n\n{self.research_notes}")

    def generate_thesis_options(self) -> List[str]:
        task_desc = "[bold cyan]The Strategist is analyzing the landscape..."
        with Progress(SpinnerColumn(), TextColumn(task_desc), console=console) as progress:
            task_id = progress.add_task("Generating Thesis Options...", total=None)
            response = self.strategist.chat(
                f"Topic: {self.user_prompt}\nTask: Generate 10 unique thesis statements.",
                context=self.research_notes[:100000]
            )
            self._log_step("0_Strategist_Theses", response)
            
            # Simple parsing for numbered list
            theses = re.findall(r'\d+\.\s*(.*)', response)
            if not theses:
                # Fallback if AI doesn't number correctly
                theses = [line.strip() for line in response.split('\n') if line.strip() and len(line) > 20][:10]
            
            return theses[:10]

    def _log_step(self, agent_name: str, content: str):
        path = os.path.join(self.log_dir, f"{agent_name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {agent_name} Output\n\n{content}")

    def run(self, extra_section: str = "", selected_thesis: str = "", target_word_count: int = 0):
        console.print(Panel.fit("🚀 [bold gold1]Starting Multi-Agent Writing System[/bold gold1]", border_style="gold1"))
        
        # If a thesis was provided, augment the user prompt
        full_prompt = self.user_prompt
        if selected_thesis:
            full_prompt = f"{self.user_prompt}\n\nCORE THESIS TO PROVE: {selected_thesis}"

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            
            # --- PHASE 1: STRATEGY ---
            task_id_arch = progress.add_task("[cyan]The Architect is drafting the Strategic Plan...", total=None)
            writer_details = "\n".join([f"- {w['name']} ({w['role']}): {w['prompt']}" for w in self.writer_profiles])
            
            manager_prompt = (
                f"Original User Prompt: {full_prompt}\n\n"
                f"PDF Context contains {self.image_count} extracted images.\n"
                f"You have 4 specialized writers available:\n{writer_details}\n\n"
                "Please enhance the user's prompt and create a 4-part Mission Brief. "
                "Explicitly assign sections to writers. Incorporate image references if they exist.\n"
                + (f"CRITICAL: The final essay MUST be around {target_word_count} words long. You must assign each of the 4 writers a specific word count target of {target_word_count // 4} words to reach this goal." if target_word_count > 0 else "")
            )
            
            mission_brief = self.manager.chat(manager_prompt, context=self.research_notes[:100000])
            self._log_step("0_Architect_Plan", mission_brief)
            progress.remove_task(task_id_arch)
            
            # Optional: Lexicographer for enhanced vocabulary
            thesaurus = ""
            if self.use_enricher and hasattr(self, 'lexicographer'):
                task_id_lex = progress.add_task("[cyan]The Lexicographer is curating vocabulary...", total=None)
                thesaurus = self.lexicographer.chat(
                    f"Topic: {full_prompt}\n\nResearch Context:\n{self.research_notes[:50000]}\n\nCurate a thesaurus of ~200 sophisticated, topic-specific terms.",
                    context=self.research_notes[:50000]
                )
                self._log_step("0.5_Lexicographer_Thesaurus", thesaurus)
                progress.remove_task(task_id_lex)
            
            console.print(Panel(Markdown(mission_brief), title="[bold cyan]Mission Brief[/bold cyan]", border_style="cyan"))

            # --- PHASE 2: WRITING (Parallel) ---
            # ... (Existing Writing Logic) ...
            writer_tasks = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                for i, writer in enumerate(self.writers):
                    task_id = progress.add_task(f"[green]{writer.name} is drafting...", total=None)
                    future = executor.submit(
                        writer.chat,
                        f"Mission Brief:\n{mission_brief}\n\nYour Persona: {self.writer_profiles[i]['prompt']}\n\nTask: Execute your assigned section."
                        + (f"\n\nCRITICAL LENGTH REQUIREMENT: You MUST write exactly {target_word_count // 4} words. Expand your arguments thoroughly. Do not stop until you hit this length." if target_word_count > 0 else "")
                        + (f"\n\nENHANCED VOCABULARY THESAURUS:\n{thesaurus}" if thesaurus else ""),
                        self.research_notes[:100000]
                    )
                    writer_tasks.append((task_id, future, i+1))
                
                writer_outputs_map = {}
                for task_id, future, section_num in writer_tasks:
                    output = future.result()
                    writer_outputs_map[section_num] = output
                    self._log_step(f"1_Writer_{section_num}", output)
                    progress.remove_task(task_id)

            writer_outputs = [writer_outputs_map[i+1] for i in range(len(self.writers))]
            combined_draft = "\n\n".join(writer_outputs)
            self._log_step("2_Combined_Draft", combined_draft)
            
            # Optional: Precisionist for synonym suggestions
            synonym_suggestions = ""
            if self.use_enricher and hasattr(self, 'precisionist'):
                task_id_prec = progress.add_task("[yellow]The Precisionist is suggesting synonyms...", total=None)
                synonym_suggestions = self.precisionist.chat(
                    f"Draft:\n{combined_draft}\n\nProvide synonym suggestions to enhance literary quality.",
                    context=self.research_notes[:50000]
                )
                self._log_step("2.5_Precisionist_Suggestions", synonym_suggestions)
                progress.remove_task(task_id_prec)

            # --- PHASE 3: REVIEW (Parallel) ---
            review_tasks = []
            with ThreadPoolExecutor(max_workers=2) as executor:
                for i, reviewer in enumerate(self.reviewers):
                    task_id = progress.add_task(f"[yellow]{reviewer.name} is auditing the draft...", total=None)
                    future = executor.submit(
                        reviewer.chat,
                        f"Mission Brief:\n{mission_brief}\n\nDraft:\n{combined_draft}",
                        context=self.research_notes[:80000] + (f"\n\nSYNONYM SUGGESTIONS:\n{synonym_suggestions}" if synonym_suggestions else "")
                    )
                    review_tasks.append((task_id, future, i+1))
                
                reviews_map = {}
                for task_id, future, review_num in review_tasks:
                    review = future.result()
                    reviews_map[review_num] = review
                    self._log_step(f"3_Reviewer_{review_num}", review)
                    progress.remove_task(task_id)

            reviews = [reviews_map[i+1] for i in range(2)]

            # --- PHASE 4: EDITING ---
            current_content = combined_draft
            
            for i, editor in enumerate(self.editors):
                task_id = progress.add_task(f"[magenta]{editor.name} is performing pass {i+1}...", total=None)
                
                # Ground the editor in the research notes as well as the mission brief
                thesis_text = f"\n\n### MANDATORY THESIS TO PRESERVE ###\n{selected_thesis}" if selected_thesis else ""
                editor_context = f"### ORIGINAL RESEARCH ###\n{self.research_notes[:80000]}\n\n### MISSION BRIEF ###\n{mission_brief[:10000]}{thesis_text}"
                
                thesis_instruction = f"\n\nCRITICAL: You MUST ensure that the final essay explicitly proves the MANDATORY THESIS provided in the context." if selected_thesis else ""
                
                editor_prompt = (
                    f"### CURRENT DRAFT ###\n{current_content}\n\n"
                    f"### PEER REVIEWS ###\n{reviews[0]}\n\n{reviews[1]}\n\n"
                    + (f"### ENHANCED VOCABULARY THESAURUS ###\n{thesaurus}\n\n" if thesaurus else "")
                    + (f"### SYNONYM SUGGESTIONS ###\n{synonym_suggestions}\n\n" if synonym_suggestions else "")
                    + f"CRITICAL INSTRUCTION: You are the final editor. DO NOT write meta-commentary, greetings, or say 'I am prepared'. "
                    f"Your ONLY output must be the fully edited, final essay text itself. Execute the edits."
                    f"{thesis_instruction}"
                )
                
                current_content = editor.chat(
                    editor_prompt,
                    context=editor_context
                )
                self._log_step(f"4_Editor_{i+1}", current_content)
                progress.remove_task(task_id)


        with console.status("[red]The Auditor is fact-checking the final essay...[/red]"):
            fact_check_res = self.fact_checker.chat(f"### FINAL ESSAY ###\n{current_content}\n\nTASK: Fact-check this essay against the research notes. Be brutal. Highlight any hallucinated quotes, misrepresented facts, or unsupported claims.", context=self.research_notes[:80000])
        self._log_step("5_Auditor_Fact_Check", fact_check_res)
        console.print(Panel(Markdown(fact_check_res), title="Fact-Check Report", border_style="red"))
        
        # Append fact-check to the output file
        current_content += f"\n\n---\n## Fact-Check Report\n\n{fact_check_res}"

        # FINAL OUTPUT (Unique Filename)
        os.makedirs(os.path.join(SCRIPT_DIR, "outputs"), exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(SCRIPT_DIR, "outputs", f"final_written_work_{timestamp}.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(current_content)

        console.print(Panel.fit(
            f"✅ [bold green]Workflow Complete![/bold green]\n\n"
            f"Output saved to: [bold underline]{output_file}[/bold underline]\n"
            f"Step-by-step logs saved in: [bold underline]{self.log_dir}[/bold underline]",
            border_style="green"
        ))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        console.print("[bold red]Usage:[/bold red] python agent_writer.py <pdf_path> \"<prompt>\"")
        sys.exit(1)
    
    pdf = sys.argv[1]
    prompt = " ".join(sys.argv[2:])
    
    workflow = AgenticWorkflow(pdf, prompt)
    workflow.run()

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
import config_manager

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
    def __init__(self, name: str, role: str, system_prompt: str, base_url: str = None):
        if base_url is None:
            base_url = config_manager.get_setting("lm_studio_url")
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.client = OpenAI(base_url=base_url, api_key="lm-studio")
        self.model = "local-model"

    def chat(self, user_input: str, context: str = "", history: List[Dict] = None, on_update: callable = None) -> str:
        max_context = config_manager.get_setting("max_context_window") or 32768
        
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        
        full_content = f"### PDF CONTEXT ###\n{context}\n\n### TASK ###\n{user_input}" if context else user_input
        
        # Estimate tokens (Roughly 4 chars = 1 token)
        estimated_tokens = (len(self.system_prompt) + len(full_content)) // 4
        
        if estimated_tokens > max_context:
            console.print(f"[bold yellow]⚠️  Context Guard:[/bold yellow] Estimated tokens ({estimated_tokens}) exceed Max Context Window ({max_context}).")
            console.print("[dim]Truncating context to fit hardware limits...[/dim]")
            
            # Truncate context to fit (leave room for system prompt and buffer)
            allowed_chars = (max_context - 2000) * 4
            context = context[:allowed_chars]
            full_content = f"### PDF CONTEXT (TRUNCATED) ###\n{context}\n\n### TASK ###\n{user_input}"
        
        messages.append({"role": "user", "content": full_content})
        
        start_time = time.time()
        first_token_time = None
        token_count = 0
        full_response = []

        if on_update:
            on_update({"status": f"Ingesting {estimated_tokens}t...", "tps": 0, "tokens": 0})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                stream=True
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    if first_token_time is None:
                        first_token_time = time.time()
                    
                    text = chunk.choices[0].delta.content
                    full_response.append(text)
                    token_count += 1
                    
                    if on_update and first_token_time:
                        elapsed = time.time() - first_token_time
                        tps = token_count / elapsed if elapsed > 0 else 0
                        on_update({
                            "status": "Generating",
                            "tps": tps,
                            "tokens": token_count,
                            "elapsed": elapsed
                        })
        except Exception as e:
            if "context_length" in str(e).lower() or "maximum context" in str(e).lower():
                console.print(Panel.fit(
                    "❌ [bold red]CRITICAL ERROR: Context Window Exceeded[/bold red]\n\n"
                    f"The prompt is too large for your current LM Studio settings.\n"
                    f"Requested: ~{estimated_tokens} tokens\n\n"
                    "SOLUTIONS:\n"
                    "1. Increase 'Context Overflow Policy' in LM Studio to 'Truncate'.\n"
                    "2. Increase 'Context Length' in LM Studio (if your VRAM allows).\n"
                    "3. Reduce 'Max Context Window' in EldritchEngine Settings.",
                    border_style="red"
                ))
            else:
                console.print(f"[bold red]API Error:[/bold red] {e}")
            raise e

        return "".join(full_response)

    @staticmethod
    def check_connection(base_url: str = None) -> bool:
        if base_url is None:
            base_url = config_manager.get_setting("lm_studio_url")
        import urllib.request
        import urllib.error
        hosts = [base_url]
        if "localhost" in base_url:
            hosts.append(base_url.replace("localhost", "127.0.0.1"))
        
        for url in hosts:
            try:
                urllib.request.urlopen(f"{url}/models", timeout=2)
                return True
            except:
                continue
        return False

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
        self.research_notes = preloaded_research
        self.use_enricher = use_enricher

        # Agents
        self.scholar = LMStudioAgent("The Scholar", "Lead Researcher", self._load_prompt("scholar.md"))
        self.strategist = LMStudioAgent("The Strategist", "Lead Philosopher", self._load_prompt("strategist.md"))
        self.manager = LMStudioAgent("The Manager", "Architect", self._load_prompt("manager.md"))
        self.author = LMStudioAgent("The Author", "Master Writer", self._load_prompt("author.md"))
        self.editor = LMStudioAgent("The Editor", "Chief Editor", self._load_prompt("editor.md"))

    def _extract_pdf_content(self, pdf_path, extract_images):
        import fitz
        doc = fitz.open(pdf_path)
        pages = []
        img_count = 0
        for page in doc:
            pages.append(page.get_text())
        return pages, img_count

    def _log_step(self, name: str, content: str):
        path = os.path.join(self.log_dir, f"{name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def conduct_research(self, telemetry=None):
        if self.research_notes: return
        console.print(f"\n[bold cyan]Phase 0: Researching...[/bold cyan]")
        outputs = []
        chunk_size = 5
        for i in range(0, len(self.pdf_pages), chunk_size):
            chunk = "\n".join(self.pdf_pages[i : i + chunk_size])
            def update(data):
                if telemetry: telemetry.update("The Scholar", data); telemetry.refresh()
            res = self.scholar.chat(f"Extract notes for: {self.user_prompt}", context=chunk, on_update=update)
            outputs.append(res)
        self.research_notes = "\n\n".join(outputs)
        self._log_step("0_Research", self.research_notes)

    def generate_thesis_options(self, telemetry=None) -> List[str]:
        console.print("\n[bold cyan]Phase 1: Generating Thesis...[/bold cyan]")
        def update(data):
            if telemetry: telemetry.update("The Strategist", data); telemetry.refresh()
        res = self.strategist.chat(f"Generate 3 thesis statements for: {self.user_prompt}", context=self.research_notes, on_update=update)
        return [line.strip() for line in res.splitlines() if line.strip() and line.strip()[0].isdigit()]

    def run(self, selected_thesis: str = "", target_word_count: int = 0, telemetry=None) -> str:
        # Planning
        console.print("\n[bold cyan]Phase 2: Planning...[/bold cyan]")
        def update_m(data):
            if telemetry: telemetry.update("The Manager", data); telemetry.refresh()
        blueprint = self.manager.chat(f"Plan essay for: {self.user_prompt}\nTHESIS: {selected_thesis}", context=self.research_notes, on_update=update_m)
        
        # Writing
        console.print("\n[bold cyan]Phase 3: Writing...[/bold cyan]")
        sections = [line.strip() for line in blueprint.splitlines() if line.strip() and line.strip()[0].isdigit()]
        if not sections: sections = ["I. Introduction", "II. Analysis", "III. Conclusion"]
        
        parts = []
        for i, s in enumerate(sections, 1):
            def update_a(data):
                if telemetry: telemetry.update(f"Author (Sec {i})", data); telemetry.refresh()
            p = self.author.chat(f"Write section: {s}", context=f"Plan: {blueprint}\nResearch: {self.research_notes[:150000]}", on_update=update_a)
            parts.append(p)
            
        full_draft = "\n\n".join(parts)
        
        # Editing
        console.print("\n[bold cyan]Phase 4: Editing...[/bold cyan]")
        def update_e(data):
            if telemetry: telemetry.update("The Editor", data); telemetry.refresh()
        final = self.editor.chat("Polish the draft.", context=full_draft, on_update=update_e)
        self._log_step("4_Final", final)
        return final

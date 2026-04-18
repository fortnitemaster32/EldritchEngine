import os
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
import fitz

import agent_writer
import research_cache

console = Console()

class ModularWorkflow:
    def __init__(self, config: dict, pdf_path: str, user_prompt: str):
        self.pdf_path = pdf_path
        self.user_prompt = user_prompt
        self.config = config
        self.workflow_name = self.config.get("name", "Custom Workflow")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_dir = os.path.join("logs", f"modular_{timestamp}")
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Initialize Cache
        self.research_notes = research_cache.get_or_create_cache(pdf_path, self._extract_pdf_content)


    def _extract_pdf_content(self, pdf_path: str, extract_images: bool = False) -> tuple:
        console.print(f"[bold cyan]Reading PDF:[/bold cyan] {pdf_path}")
        try:
            doc = fitz.open(pdf_path)
            pages = []
            for i, page in enumerate(doc):
                pages.append(page.get_text())
            return ("\n".join(pages), [])
        except Exception as e:
            console.print(f"[bold red]Error reading PDF: {e}[/bold red]")
            return ("", [])

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join("prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        raise FileNotFoundError(f"Missing prompt file: {path}")

    def _log_step(self, stage_name: str, agent_name: str, content: str):
        safe_stage = stage_name.replace(" ", "_")
        safe_agent = agent_name.replace(" ", "_")
        path = os.path.join(self.log_dir, f"{safe_stage}_{safe_agent}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {agent_name} Output\n\n{content}")

    def run(self):
        console.print(Panel.fit(f"🚀 [bold gold1]Starting Modular Workflow: {self.workflow_name}[/bold gold1]", border_style="gold1"))
        
        current_state = f"TOPIC: {self.user_prompt}\n\n"
        
        for stage_idx, stage in enumerate(self.config.get("stages", [])):
            stage_name = stage.get("name", f"Stage {stage_idx+1}")
            stage_type = stage.get("type", "sequential")
            instruction = stage.get("instruction", "")
            agents_cfg = stage.get("agents", [])
            
            console.print(f"\n[bold magenta]=== Stage {stage_idx+1}: {stage_name} ({stage_type}) ===[/bold magenta]")
            
            # Initialize Agents for this stage
            agents = []
            for a_cfg in agents_cfg:
                # Support inline system prompts (from TUI) or prompt files (from JSON)
                if "system_prompt" in a_cfg:
                    prompt_text = a_cfg["system_prompt"]
                else:
                    prompt_text = self._load_prompt(a_cfg.get("prompt_file", ""))
                agents.append(agent_writer.LMStudioAgent(
                    a_cfg.get("name", "Unknown Agent"),
                    a_cfg.get("role", "Worker"),
                    prompt_text
                ))
            
            stage_outputs = []
            
            if stage_type == "parallel":
                with console.status(f"[cyan]Running {len(agents)} agents in parallel...[/cyan]"):
                    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
                        futures = []
                        for agent in agents:
                            prompt = f"{instruction}\n\n### PREVIOUS STATE ###\n{current_state}\n\nTASK: Execute your role based on the topic and previous state."
                            futures.append(executor.submit(agent.chat, prompt, context=self.research_notes[:80000]))
                        
                        for i, future in enumerate(futures):
                            output = future.result()
                            stage_outputs.append((agents[i].name, output))
                            self._log_step(f"{stage_idx}_{stage_name}", agents[i].name, output)
            else:
                # Sequential (one by one, passing context forward)
                for agent in agents:
                    with console.status(f"[cyan]{agent.name} is working...[/cyan]"):
                        prompt = f"{instruction}\n\n### PREVIOUS STATE ###\n{current_state}\n\nTASK: Execute your role."
                        output = agent.chat(prompt, context=self.research_notes[:80000])
                        stage_outputs.append((agent.name, output))
                        self._log_step(f"{stage_idx}_{stage_name}", agent.name, output)
                        # In sequential, state updates immediately
                        current_state += f"\n\n### ADDITION BY {agent.name} ###\n{output}"
            
            # If parallel, update state all at once
            if stage_type == "parallel":
                for name, output in stage_outputs:
                    current_state += f"\n\n### CONTRIBUTION BY {name} ###\n{output}"
                    
        # Final Output
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join("outputs", f"modular_workflow_{timestamp}.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(current_state)

        console.print(Panel.fit(
            f"✅ [bold green]Modular Workflow Complete![/bold green]\n\n"
            f"Output saved to: [bold underline]{output_file}[/bold underline]\n"
            f"Step-by-step logs saved in: [bold underline]{self.log_dir}[/bold underline]",
            border_style="green"
        ))

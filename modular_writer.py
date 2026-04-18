import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
import fitz

import agent_writer
import research_cache

console = Console()

# ─── Context Feed Options ─────────────────────────────────────────────────────
FEED_ALL_PREVIOUS   = "all_previous"      # entire accumulated state (default)
FEED_TOPIC_ONLY     = "topic_only"        # just the user's topic/prompt
FEED_RESEARCH_ONLY  = "research_only"     # just research notes (context param)
FEED_LAST_STAGE_ALL = "last_stage_all"    # all outputs from previous stage
FEED_LAST_STAGE_AGENT = "last_stage_agent"  # one specific agent from prev stage


class ModularWorkflow:
    def __init__(self, config: dict, user_prompt: str, research_notes: str = ""):
        self.user_prompt    = user_prompt
        self.config         = config
        self.workflow_name  = self.config.get("name", "Custom Workflow")
        self.research_notes = research_notes

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_dir = os.path.join("logs", f"modular_{timestamp}")
        os.makedirs(self.log_dir, exist_ok=True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join("prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        raise FileNotFoundError(f"Missing prompt file: {path}")

    def _log_step(self, stage_name: str, agent_name: str, content: str):
        safe = lambda s: s.replace(" ", "_")
        path = os.path.join(self.log_dir, f"{safe(stage_name)}_{safe(agent_name)}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {agent_name} Output\n\n{content}")

    def _build_context_for_agent(
        self,
        a_cfg: dict,
        current_state: str,
        last_stage_outputs: list[tuple[str, str]],  # [(agent_name, output), ...]
    ) -> tuple[str, str]:
        """Return (prompt_body, context_for_api) for the agent's API call."""
        feed = a_cfg.get("context_feed", FEED_ALL_PREVIOUS)

        if feed == FEED_TOPIC_ONLY:
            body = f"TOPIC: {self.user_prompt}"
            ctx  = ""

        elif feed == FEED_RESEARCH_ONLY:
            body = f"TOPIC: {self.user_prompt}"
            ctx  = self.research_notes[:80000]

        elif feed == FEED_LAST_STAGE_ALL:
            parts = "\n\n".join(
                f"### {name} ###\n{out}" for name, out in last_stage_outputs
            )
            body = f"TOPIC: {self.user_prompt}\n\n### PREVIOUS STAGE OUTPUTS ###\n{parts}"
            ctx  = self.research_notes[:80000] if self.research_notes else ""

        elif feed.startswith(FEED_LAST_STAGE_AGENT + ":"):
            target = feed.split(":", 1)[1]
            matched = next(
                (out for name, out in last_stage_outputs if name == target), ""
            )
            body = (
                f"TOPIC: {self.user_prompt}\n\n"
                f"### OUTPUT FROM {target} ###\n{matched}"
            )
            ctx  = self.research_notes[:80000] if self.research_notes else ""

        else:  # FEED_ALL_PREVIOUS (default)
            body = current_state
            ctx  = self.research_notes[:80000] if self.research_notes else ""

        return body, ctx

    # ── Main Run ──────────────────────────────────────────────────────────────

    def run(self):
        console.print(Panel.fit(
            f"🚀 [bold gold1]Starting Modular Workflow: {self.workflow_name}[/bold gold1]",
            border_style="gold1"
        ))

        current_state      = f"TOPIC: {self.user_prompt}\n\n"
        last_stage_outputs: list[tuple[str, str]] = []

        for stage_idx, stage in enumerate(self.config.get("stages", [])):
            stage_name  = stage.get("name", f"Stage {stage_idx+1}")
            stage_type  = stage.get("type", "sequential")
            instruction = stage.get("instruction", "")
            agents_cfg  = stage.get("agents", [])

            console.print(
                f"\n[bold magenta]=== Stage {stage_idx+1}: {stage_name} "
                f"({stage_type}) ===[/bold magenta]"
            )

            # Build agent objects
            agents = []
            for a_cfg in agents_cfg:
                if "system_prompt" in a_cfg:
                    prompt_text = a_cfg["system_prompt"]
                else:
                    prompt_text = self._load_prompt(a_cfg.get("prompt_file", ""))
                agents.append((
                    agent_writer.LMStudioAgent(
                        a_cfg.get("name", "Unknown Agent"),
                        a_cfg.get("role", "Worker"),
                        prompt_text
                    ),
                    a_cfg  # carry cfg so we can resolve context_feed
                ))

            stage_outputs: list[tuple[str, str]] = []

            def _run_agent(agent_and_cfg):
                agent, a_cfg = agent_and_cfg
                body, ctx = self._build_context_for_agent(
                    a_cfg, current_state, last_stage_outputs
                )
                full_prompt = (
                    f"{instruction}\n\n{body}\n\nTASK: Execute your role."
                    if instruction else
                    f"{body}\n\nTASK: Execute your role."
                )
                return agent.name, agent.chat(full_prompt, context=ctx)

            if stage_type == "parallel":
                with console.status(
                    f"[cyan]Running {len(agents)} agents in parallel…[/cyan]"
                ):
                    with ThreadPoolExecutor(max_workers=len(agents)) as ex:
                        results = list(ex.map(_run_agent, agents))
                for name, output in results:
                    stage_outputs.append((name, output))
                    self._log_step(f"{stage_idx}_{stage_name}", name, output)
                    current_state += f"\n\n### CONTRIBUTION BY {name} ###\n{output}"
            else:
                for agent_and_cfg in agents:
                    agent, _ = agent_and_cfg
                    with console.status(f"[cyan]{agent.name} is working…[/cyan]"):
                        name, output = _run_agent(agent_and_cfg)
                    stage_outputs.append((name, output))
                    self._log_step(f"{stage_idx}_{stage_name}", name, output)
                    current_state += f"\n\n### ADDITION BY {name} ###\n{output}"

            # Show stage outputs
            for name, output in stage_outputs:
                console.print(Panel(output, title=f"{name} Output", border_style="dim"))

            last_stage_outputs = stage_outputs  # pass to next stage

        # ── Final Output ──────────────────────────────────────────────────────
        os.makedirs("outputs", exist_ok=True)
        timestamp   = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join("outputs", f"modular_workflow_{timestamp}.md")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(current_state)

        console.print(Panel.fit(
            f"✅ [bold green]Modular Workflow Complete![/bold green]\n\n"
            f"Output saved to: [bold underline]{output_file}[/bold underline]\n"
            f"Logs in: [bold underline]{self.log_dir}[/bold underline]",
            border_style="green"
        ))


# ── Standalone PDF helper (for TUI to use separately) ────────────────────────

def extract_pdf_text(pdf_path: str) -> str:
    try:
        doc   = fitz.open(pdf_path)
        pages = [page.get_text() for page in doc]
        return "\n".join(pages)
    except Exception as e:
        console.print(f"[bold red]Error reading PDF: {e}[/bold red]")
        return ""

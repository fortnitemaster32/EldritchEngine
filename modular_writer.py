import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.panel import Panel
import fitz
import questionary

import agent_writer
import research_cache

console = Console()

FEED_ALL_PREVIOUS     = "all_previous"
FEED_TOPIC_ONLY       = "topic_only"
FEED_RESEARCH_ONLY    = "research_only"
FEED_LAST_STAGE_ALL   = "last_stage_all"
FEED_LAST_STAGE_AGENT = "last_stage_agent"
FEED_PINNED           = "pinned"


def _inject_variables(text: str, variables: dict) -> str:
    for key, value in variables.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))
    return text


class ModularWorkflow:
    def __init__(self, config: dict, user_prompt: str, research_notes: str = ""):
        self.config         = config
        self.research_notes = research_notes
        self.variables      = config.get("variables", {})
        self.workflow_name  = config.get("name", "Custom Workflow")
        self.user_prompt    = _inject_variables(user_prompt, self.variables)

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

    def _log(self, stage_name: str, agent_name: str, content: str):
        safe = lambda s: s.replace(" ", "_")
        path = os.path.join(self.log_dir, f"{safe(stage_name)}_{safe(agent_name)}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {agent_name}\n\n{content}")

    def _make_agent(self, a_cfg: dict) -> agent_writer.LMStudioAgent:
        if "system_prompt" in a_cfg:
            prompt = _inject_variables(a_cfg["system_prompt"], self.variables)
        else:
            prompt = self._load_prompt(a_cfg.get("prompt_file", ""))
        return agent_writer.LMStudioAgent(
            a_cfg.get("name", "Agent"),
            a_cfg.get("role", "Worker"),
            prompt
        )

    def _build_prompt(self, a_cfg: dict, instruction: str, current_state: str,
                      last_outputs: list, pinned: str) -> tuple[str, str]:
        feed    = a_cfg.get("context_feed", FEED_ALL_PREVIOUS)
        instr   = _inject_variables(instruction, self.variables)
        pin_blk = f"\n\n### PINNED (TREAT AS GROUND TRUTH) ###\n{pinned}" if pinned else ""
        res     = self.research_notes[:80000] if self.research_notes else ""

        if feed == FEED_TOPIC_ONLY:
            body, ctx = f"TOPIC: {self.user_prompt}{pin_blk}", ""
        elif feed == FEED_RESEARCH_ONLY:
            body, ctx = f"TOPIC: {self.user_prompt}{pin_blk}", res
        elif feed == FEED_PINNED:
            body, ctx = f"TOPIC: {self.user_prompt}{pin_blk}", res
        elif feed == FEED_LAST_STAGE_ALL:
            parts = "\n\n".join(f"### {n} ###\n{o}" for n, o in last_outputs)
            body  = f"TOPIC: {self.user_prompt}\n\n### PREVIOUS STAGE ###\n{parts}{pin_blk}"
            ctx   = res
        elif feed.startswith(FEED_LAST_STAGE_AGENT + ":"):
            target  = feed.split(":", 1)[1]
            matched = next((o for n, o in last_outputs if n == target), "")
            body    = f"TOPIC: {self.user_prompt}\n\n### {target} OUTPUT ###\n{matched}{pin_blk}"
            ctx     = res
        else:  # all_previous
            body, ctx = current_state + pin_blk, res

        full = f"{instr}\n\n{body}\n\nTASK: Execute your role." if instr else f"{body}\n\nTASK: Execute your role."
        return full, ctx

    # ── Stage Handlers ────────────────────────────────────────────────────────

    def _run_extractor(self, stage_outputs: list, instruction: str) -> str:
        combined = "\n\n".join(f"### {n} ###\n{o}" for n, o in stage_outputs)
        ext = agent_writer.LMStudioAgent(
            "Extractor", "Content Extractor",
            "You extract exactly the content requested. Output ONLY the extracted content."
        )
        with console.status("[yellow]Extractor running…[/yellow]"):
            return ext.chat(f"{instruction}\n\n### OUTPUT ###\n{combined}", context="").strip()

    def _handle_checkpoint(self, stage: dict, current_state: str,
                            last_outputs: list, pinned: str) -> str:
        name  = stage.get("name", "Checkpoint")
        instr = stage.get("instruction", "Review outputs and pin any content to carry forward.")
        console.print(Panel.fit(f"⏸️  [bold yellow]{name}[/bold yellow]\n[dim]{instr}[/dim]",
                                border_style="yellow"))

        if last_outputs:
            for i, (n, o) in enumerate(last_outputs):
                console.print(Panel(o, title=f"[{i+1}] {n}", border_style="dim"))
        else:
            console.print(Panel(current_state[-3000:], title="Current State", border_style="dim"))

        if pinned:
            console.print(Panel(pinned, title="Currently Pinned", border_style="yellow"))

        action = questionary.select("What would you like to do?", choices=[
            questionary.Choice("Pin a specific agent's entire output", value="pin_agent"),
            questionary.Choice("Type/paste content to pin", value="pin_custom"),
            questionary.Choice("Write feedback/instructions for next stages", value="feedback"),
            questionary.Choice("Continue without changes", value="skip"),
        ]).ask()

        new_pinned = pinned
        if action == "pin_agent" and last_outputs:
            idx = questionary.select("Which agent's output?",
                choices=[questionary.Choice(n, value=i) for i, (n, _) in enumerate(last_outputs)]
            ).ask()
            if idx is not None:
                new_pinned += f"\n\n---\n{last_outputs[idx][1]}"
                console.print("[green]✔ Pinned.[/green]")
        elif action == "pin_custom":
            text = questionary.text("Paste or type content to pin:").ask()
            if text:
                new_pinned += f"\n\n---\n{text}"
                console.print("[green]✔ Pinned.[/green]")
        elif action == "feedback":
            fb = questionary.text("Write feedback/instructions for next stages:").ask()
            if fb:
                new_pinned += f"\n\n--- HUMAN INSTRUCTION ---\n{fb}"
                console.print("[green]✔ Feedback pinned.[/green]")

        return new_pinned.strip()

    def _handle_conditional(self, stage: dict, current_state: str,
                             last_outputs: list, pinned: str) -> tuple[list, str]:
        name      = stage.get("name", "Quality Gate")
        judge_cfg = stage.get("judge", {})
        condition = _inject_variables(
            judge_cfg.get("condition", "Output ONLY 'PASS' or 'FAIL'."), self.variables)

        console.print(f"\n[bold red]⚖️  {name}[/bold red]")
        judge = self._make_agent(judge_cfg)

        combined     = "\n\n".join(f"### {n} ###\n{o}" for n, o in last_outputs)
        judge_prompt = (f"TOPIC: {self.user_prompt}\n\n"
                        f"### CONTENT TO EVALUATE ###\n{combined}\n\n{condition}")

        with console.status("[red]Judge evaluating…[/red]"):
            verdict = judge.chat(judge_prompt, context="")
        self._log(name, judge.name, verdict)
        console.print(Panel(verdict, title="Judge Verdict", border_style="red"))

        passed = "PASS" in verdict.upper() and "FAIL" not in verdict.upper()
        current_state += f"\n\n### JUDGE ({name}) ###\nVerdict: {'PASS' if passed else 'FAIL'}\n{verdict}"

        if passed:
            console.print("[green]✔ Quality gate PASSED.[/green]")
            return last_outputs, current_state

        console.print("[yellow]✗ Quality gate FAILED. Running revision path…[/yellow]")
        on_fail      = stage.get("on_fail", {})
        fail_instr   = on_fail.get("instruction", "Revise based on the judge's feedback.")
        fail_type    = on_fail.get("type", "sequential")
        fail_agents  = [(self._make_agent(a), a) for a in on_fail.get("agents", [])]
        fail_outputs: list = []

        def _run_fail(ac):
            agent, a_cfg = ac
            p, ctx = self._build_prompt(a_cfg, fail_instr, current_state, last_outputs, pinned)
            return agent.name, agent.chat(p, context=ctx)

        if fail_type == "parallel" and fail_agents:
            with console.status("[yellow]Revision agents running…[/yellow]"):
                with ThreadPoolExecutor(max_workers=len(fail_agents)) as ex:
                    fail_outputs = list(ex.map(_run_fail, fail_agents))
        else:
            for ac in fail_agents:
                name_out, out = _run_fail(ac)
                fail_outputs.append((name_out, out))
                current_state += f"\n\n### REVISION BY {name_out} ###\n{out}"

        for n, o in fail_outputs:
            self._log(f"{name}_revision", n, o)
            console.print(Panel(o, title=f"Revision: {n}", border_style="yellow"))

        return fail_outputs, current_state

    # ── Main Run ──────────────────────────────────────────────────────────────

    def run(self):
        console.print(Panel.fit(
            f"🚀 [bold gold1]Starting: {self.workflow_name}[/bold gold1]", border_style="gold1"))
        if self.variables:
            console.print("[dim]Variables: " +
                          ", ".join(f"{k}={v}" for k, v in self.variables.items()) + "[/dim]")

        current_state: str       = f"TOPIC: {self.user_prompt}\n\n"
        last_outputs:  list      = []
        pinned:        str       = ""

        for i, stage in enumerate(self.config.get("stages", [])):
            s_name  = stage.get("name", f"Stage {i+1}")
            s_type  = stage.get("type", "sequential")
            instr   = stage.get("instruction", "")
            ext_cfg = stage.get("extractor", "")

            console.print(f"\n[bold magenta]=== Stage {i+1}: {s_name} ({s_type}) ===[/bold magenta]")

            if s_type == "checkpoint":
                pinned = self._handle_checkpoint(stage, current_state, last_outputs, pinned)
                if pinned:
                    current_state += f"\n\n### PINNED BY HUMAN ###\n{pinned}"
                continue

            if s_type == "conditional":
                last_outputs, current_state = self._handle_conditional(
                    stage, current_state, last_outputs, pinned)
                continue

            agents = [(self._make_agent(a), a) for a in stage.get("agents", [])]
            stage_outputs: list = []

            def _run(ac, _cs=current_state, _lo=last_outputs, _p=pinned, _instr=instr):
                ag, a_cfg = ac
                prompt, ctx = self._build_prompt(a_cfg, _instr, _cs, _lo, _p)
                return ag.name, ag.chat(prompt, context=ctx)

            if s_type == "parallel":
                with console.status(f"[cyan]{len(agents)} agents running in parallel…[/cyan]"):
                    with ThreadPoolExecutor(max_workers=max(len(agents), 1)) as ex:
                        stage_outputs = list(ex.map(_run, agents))
                for n, o in stage_outputs:
                    current_state += f"\n\n### {n} ###\n{o}"
            else:
                for ac in agents:
                    ag, _ = ac
                    with console.status(f"[cyan]{ag.name} working…[/cyan]"):
                        n, o = _run(ac)
                    stage_outputs.append((n, o))
                    current_state += f"\n\n### {n} ###\n{o}"

            for n, o in stage_outputs:
                self._log(f"{i}_{s_name}", n, o)
                console.print(Panel(o, title=n, border_style="dim"))

            if ext_cfg:
                extracted = self._run_extractor(
                    stage_outputs, _inject_variables(ext_cfg, self.variables))
                console.print(Panel(extracted, title="Extracted", border_style="yellow"))
                pinned        += f"\n\n--- EXTRACTED ({s_name}) ---\n{extracted}"
                current_state += f"\n\n### EXTRACTED ({s_name}) ###\n{extracted}"
                self._log(f"{i}_{s_name}", "Extractor", extracted)

            last_outputs = stage_outputs

        # ── Save output ───────────────────────────────────────────────────────
        os.makedirs("outputs", exist_ok=True)
        ts   = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join("outputs", f"modular_{ts}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(current_state)
            if pinned:
                f.write(f"\n\n---\n## Pinned Content\n\n{pinned}")

        console.print(Panel.fit(
            f"✅ [bold green]Complete![/bold green]\n"
            f"Output: [underline]{path}[/underline]\nLogs: [underline]{self.log_dir}[/underline]",
            border_style="green"))


def extract_pdf_text(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        return "\n".join(p.get_text() for p in doc)
    except Exception as e:
        console.print(f"[red]Error reading PDF: {e}[/red]")
        return ""

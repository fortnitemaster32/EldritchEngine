import os
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from agent_writer import LMStudioAgent

console = Console()

class IterativeWriterWorkflow:
    def __init__(self, user_prompt: str, research_notes: str, para_count: int = 0, style_choice: str = ""):
        self.user_prompt = user_prompt
        self.research_notes = research_notes
        self.para_count = para_count
        self.style_choice = style_choice
        
        os.makedirs("outputs", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_file = os.path.join("outputs", f"iterative_draft_{timestamp}.md")
        
        self.planner = LMStudioAgent(
            "The Planner", "Essay Architect",
            self._load_prompt("iterative_planner.md")
        )
        self.writer_a = LMStudioAgent(
            "Writer Alpha", "Essay Drafter A",
            self._load_prompt("iterative_writer_alpha.md")
        )
        self.writer_b = LMStudioAgent(
            "Writer Beta", "Essay Drafter B",
            self._load_prompt("iterative_writer_beta.md")
        )
        self.editor = LMStudioAgent(
            "The Editor", "Paragraph Polisher",
            self._load_prompt("iterative_editor.md")
        )
        self.critique = LMStudioAgent(
            "The Critic", "Paragraph Evaluator",
            self._load_prompt("iterative_critic.md")
        )
        self.fact_checker = LMStudioAgent(
            "The Auditor", "Fact Checker",
            self._load_prompt("fact_checker.md")
        )

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join("prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        raise FileNotFoundError(f"Missing prompt file: {path}")

    def update_live_doc(self, approved_text: str, candidate_text: str = ""):
        content = approved_text
        if candidate_text:
            content += f"\n\n### [CURRENTLY REVIEWING]\n{candidate_text}\n"
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(content.strip())

    def run(self):
        console.print(Panel.fit(
            f"🔄 [bold gold1]Iterative Mode[/bold gold1]\n"
            f"[dim]Live editing: {self.output_file}[/dim]",
            border_style="gold1"
        ))

        # Step 1: Thesis & Outline
        with console.status("[cyan]The Planner is generating the Thesis and Outline...[/cyan]"):
            plan_prompt = (
                f"Topic/Prompt: {self.user_prompt}\n\n"
                "Create a detailed, paragraph-by-paragraph outline for this essay. "
                "1. Start with a clear THESIS STATEMENT.\n"
                + (f"2. Format the rest of your response as exactly {self.para_count} distinct paragraph plans.\n" if self.para_count > 0 else "2. Format the rest of your response as a series of distinct paragraph plans.\n")
                + "CRITICAL: You MUST wrap the detailed plan for EACH individual paragraph entirely inside a <paragraph_plan>...</paragraph_plan> XML block. Do not put multiple paragraphs in one block.\n"
                "Include an Intro, several Body paragraphs, and a Conclusion."
            )
            outline_res = self.planner.chat(plan_prompt, context=self.research_notes[:80000])
        
        console.print(Panel(Markdown(outline_res), title="Essay Thesis & Outline", border_style="cyan"))
        
        self.update_live_doc(outline_res)
        console.print(f"\n[bold magenta]Open this file in your editor to view or manually edit the outline: {self.output_file}[/bold magenta]")
        
        while True:
            action = questionary.select(
                "Outline Action:",
                choices=[
                    "Accept Outline (Proceed to writing)",
                    "Reload from file (If you manually edited it)",
                    "Redo with instructions",
                    "Redo (Regenerate)"
                ]
            ).ask()
            
            if action == "Accept Outline (Proceed to writing)":
                break
            elif action == "Reload from file (If you manually edited it)":
                with open(self.output_file, "r", encoding="utf-8") as f:
                    outline_res = f.read().strip()
                console.print("[green]Outline reloaded from file![/green]")
                break
            elif action == "Redo with instructions":
                feedback = questionary.text("Enter your instructions for the new outline:").ask()
                with console.status("[cyan]Regenerating outline with feedback...[/cyan]"):
                    outline_res = self.planner.chat(plan_prompt + f"\n\nUSER FEEDBACK: {feedback}", context=self.research_notes[:80000])
                self.update_live_doc(outline_res)
                console.print(Panel(Markdown(outline_res), title="Essay Thesis & Outline (Updated)", border_style="cyan"))
            elif action == "Redo (Regenerate)":
                with console.status("[cyan]Regenerating outline...[/cyan]"):
                    outline_res = self.planner.chat(plan_prompt + "\n\nCRITICAL: Make it structurally different and better this time.", context=self.research_notes[:80000])
                self.update_live_doc(outline_res)
                console.print(Panel(Markdown(outline_res), title="Essay Thesis & Outline (V2)", border_style="cyan"))

        import re
        # Extract paragraphs from XML tags
        paragraphs_plan = re.findall(r'<paragraph_plan>(.*?)</paragraph_plan>', outline_res, re.DOTALL)
        paragraphs_plan = [p.strip() for p in paragraphs_plan if p.strip()]
        
        if not paragraphs_plan:
            # Fallback parsing if LLM ignores XML tags
            paragraphs_plan = []
            current_para = []
            for line in outline_res.split('\n'):
                # Look for lines starting with a number and dot like '1. ' or '10. '
                if line.strip() and line.strip()[0].isdigit() and "." in line[:5] and len(line) < 100:
                    if current_para:
                        paragraphs_plan.append("\n".join(current_para))
                    current_para = [line]
                elif current_para:
                    current_para.append(line)
            if current_para:
                paragraphs_plan.append("\n".join(current_para))
                
            if len(paragraphs_plan) < 3:
                # Ultimate fallback
                paragraphs_plan = [p.strip() for p in outline_res.split('\n\n') if len(p.strip()) > 30 and 'thesis' not in p.lower()]

        approved_draft = f"# {self.user_prompt}\n\n"
        self.update_live_doc(approved_draft)
        
        console.print(f"[bold green]Outline accepted. {len(paragraphs_plan)} paragraphs to write.[/bold green]")
        console.print(f"[bold magenta]We will now begin writing. The live updates will overwrite the outline in: {self.output_file}[/bold magenta]")
        questionary.confirm("Press Enter when you are ready to begin drafting...").ask()

        # Step 2: Iterative Writing
        for i, para_plan in enumerate(paragraphs_plan):
            console.print(f"\n[bold gold1]Drafting Paragraph {i+1}/{len(paragraphs_plan)}...[/bold gold1]")
            console.print(f"[dim]Plan: {para_plan}[/dim]")
            
            candidate_para = ""
            action = "Generate Fresh"
            
            # Lexicon Memory: Get last 150 words of approved draft
            recent_text = " ".join(approved_draft.split()[-150:]) if approved_draft else ""
            lexicon_instruction = f"\n\nCRITICAL LEXICON TRACKING: Do NOT reuse distinct vocabulary or exact transition phrases found in the preceding text:\n\"{recent_text}\"" if recent_text else ""
            
            while True:
                style_instruction = f"\n\nMANDATORY STYLE/TONE: {self.style_choice}" if self.style_choice else ""
                
                if action in ["Generate Fresh", "Redo (Regenerate)"]:
                    write_prompt = (
                        f"### ESSAY OUTLINE ###\n{outline_res}\n\n"
                        f"### APPROVED DRAFT SO FAR ###\n{approved_draft}\n\n"
                        f"### CURRENT PARAGRAPH PLAN ###\n{para_plan}\n\n"
                        "TASK: Draft ONLY the text for this specific paragraph. Make it substantive, dense, and engaging (5-8 sentences). "
                        "Ensure it flows perfectly from the Approved Draft So Far. Do NOT output meta-commentary, greetings, or explanations. Just the paragraph text."
                        f"{style_instruction}{lexicon_instruction}"
                    )
                    
                    with console.status("[green]Phase 1/2: 2 Writers drafting in parallel...[/green]"):
                        with ThreadPoolExecutor(max_workers=2) as executor:
                            future_a = executor.submit(self.writer_a.chat, write_prompt, context=self.research_notes[:80000])
                            future_b = executor.submit(self.writer_b.chat, write_prompt, context=self.research_notes[:80000])
                            draft_a = future_a.result()
                            draft_b = future_b.result()
                        
                    edit_prompt = (
                        f"### ESSAY OUTLINE ###\n{outline_res}\n\n"
                        f"### APPROVED DRAFT SO FAR ###\n{approved_draft}\n\n"
                        f"### DRAFT A ###\n{draft_a}\n\n"
                        f"### DRAFT B ###\n{draft_b}\n\n"
                        "TASK: Combine and polish Draft A and Draft B. Keep the very best parts, arguments, and prose from both to create the ultimate, perfectly flowing paragraph. "
                        "Ensure academic rigor, seamless flow, and dense structure. Output ONLY the finalized paragraph text. Do NOT output meta-commentary."
                        f"{style_instruction}{lexicon_instruction}"
                    )
                    with console.status("[magenta]Phase 2/2: The Editor is combining and polishing...[/magenta]"):
                        candidate_para = self.editor.chat(edit_prompt, context=self.research_notes[:80000])

                elif action == "Redo with instructions":
                    revise_prompt = (
                        f"### APPROVED DRAFT SO FAR ###\n{approved_draft}\n\n"
                        f"### CURRENT PARAGRAPH ###\n{candidate_para}\n\n"
                        f"### USER INSTRUCTIONS FOR REVISION ###\n{feedback}\n\n"
                        "TASK: Revise the CURRENT PARAGRAPH specifically to incorporate the user's instructions. "
                        "Maintain flow with the previous text. Output ONLY the revised paragraph text. Do NOT output meta-commentary."
                        f"{style_instruction}"
                    )
                    with console.status("[magenta]The Editor is revising based on instructions...[/magenta]"):
                        candidate_para = self.editor.chat(revise_prompt, context=self.research_notes[:80000])
                elif action == "Smooth Manual Edits (Reload from file and polish)":
                    with open(self.output_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    import re
                    match = re.search(r'### \[CURRENTLY REVIEWING\]\n(.*)', content, re.DOTALL)
                    if match:
                        manual_para = match.group(1).strip()
                        smooth_prompt = (
                            f"### APPROVED DRAFT SO FAR ###\n{approved_draft}\n\n"
                            f"### MANUALLY EDITED PARAGRAPH ###\n{manual_para}\n\n"
                            "TASK: Smooth and elevate this manually edited paragraph so its prose perfectly matches the academic tone of the Approved Draft. "
                            "Do not change the underlying meaning or points made by the user, just elevate the vocabulary and flow. "
                            "Output ONLY the finalized paragraph text. Do NOT output meta-commentary."
                        )
                        with console.status("[magenta]The Editor is smoothing your manual edits...[/magenta]"):
                            candidate_para = self.editor.chat(smooth_prompt, context=self.research_notes[:80000])
                    else:
                        console.print("[red]Could not find the reviewing block. Proceeding with current candidate.[/red]")
                
                self.update_live_doc(approved_draft, candidate_para)
                
                if action in ["Generate Fresh", "Redo (Regenerate)", "Redo with instructions", "Smooth Manual Edits (Reload from file and polish)"]:
                    with console.status("[yellow]The Critic is evaluating...[/yellow]"):
                        critique_res = self.critique.chat(f"Paragraph to critique:\n{candidate_para}", context="")
                
                console.print(Panel(candidate_para, title=f"Paragraph {i+1} Candidate", border_style="green"))
                console.print(Panel(critique_res, title="The Critic's Evaluation", border_style="yellow"))
                
                action = questionary.select(
                    "Action:",
                    choices=[
                        "Accept and Continue",
                        "Redo with instructions",
                        "Redo (Regenerate)",
                        "Smooth Manual Edits (Reload from file and polish)",
                        "Keep Candidate but Edit Manually (Skip to next)"
                    ]
                ).ask()
                
                if action == "Accept and Continue":
                    approved_draft += candidate_para + "\n\n"
                    self.update_live_doc(approved_draft)
                    break
                elif action == "Redo with instructions":
                    feedback = questionary.text("Enter your instructions to edit this paragraph:").ask()
                    continue
                elif action == "Redo (Regenerate)":
                    continue
                elif action == "Smooth Manual Edits (Reload from file and polish)":
                    continue
                else:
                    console.print("[yellow]Candidate appended. Please make your manual edits in the file. Moving to next paragraph...[/yellow]")
                    approved_draft += candidate_para + "\n\n"
                    self.update_live_doc(approved_draft)
                    break
                    
        with console.status("[red]The Auditor is fact-checking the final essay...[/red]"):
            fact_check_res = self.fact_checker.chat(f"### FINAL ESSAY ###\n{approved_draft}\n\nTASK: Fact-check this essay against the research notes. Be brutal. Highlight any hallucinated quotes, misrepresented facts, or unsupported claims.", context=self.research_notes[:80000])
        console.print(Panel(Markdown(fact_check_res), title="Fact-Check Report", border_style="red"))
        
        # Append fact-check to output file
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n---\n## Fact-Check Report\n\n{fact_check_res}")

        console.print(Panel.fit(
            f"✅ [bold green]Iterative writing complete![/bold green]\n\n"
            f"Final Essay saved to: [bold underline]{self.output_file}[/bold underline]",
            border_style="green"
        ))

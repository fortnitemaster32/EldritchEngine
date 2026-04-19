"""
book_writer.py — Book Writing Mode
An iterative book writing workflow with extensive planning, page-by-page drafting,
context condensation, and user editing capabilities.
"""

import os
import re
import json
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from agent_writer import LMStudioAgent

console = Console()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

class BookWriterWorkflow:
    def __init__(self, user_prompt: str = "", research_notes: str = "", book_title: str = "", book_style: str = "", resume_dir: str = None, auto_accept: bool = False):
        self.user_prompt = user_prompt
        self.research_notes = research_notes
        self.book_title = book_title
        self.book_style = book_style
        self.auto_accept = auto_accept
        self.book_summary = ""
        self.last_page_summary = ""
        self.state = {
            "status": "new",
            "current_chapter": 0,
            "current_page": 0,
            "chapters": [],
            "book_title": self.book_title,
            "book_style": self.book_style,
            "book_summary": self.book_summary,
            "last_page_summary": self.last_page_summary,
        }

        if resume_dir:
            self.log_dir = resume_dir
        else:
            self.log_dir = os.path.join(
                os.path.join(SCRIPT_DIR, "logs"), f"book_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
        os.makedirs(self.log_dir, exist_ok=True)

        self.state_path = os.path.join(self.log_dir, "state.json")
        self.chapters_dir = os.path.join(self.log_dir, "chapters")
        os.makedirs(self.chapters_dir, exist_ok=True)

        # Context files directory
        self.context_dir = os.path.join(self.log_dir, "context_files")
        os.makedirs(self.context_dir, exist_ok=True)

        if resume_dir:
            self._load_state()
            self.user_prompt = self.state.get("user_prompt", self.user_prompt)
            self.research_notes = self.state.get("research_notes", self.research_notes)
            self.chapters = self.state.get("chapters", [])
            self.book_title = self.state.get("book_title", self.book_title)
            self.book_style = self.state.get("book_style", self.book_style)
            self.book_summary = self.state.get("book_summary", self.book_summary)
            self.last_page_summary = self.state.get("last_page_summary", self.last_page_summary)
        else:
            self.chapters = []

        # Agents
        self.planner = LMStudioAgent(
            "The Architect", "Book Planner",
            self._load_prompt("architect.md")  # Reuse architect prompt, enhance for books
        )
        self.strategist = LMStudioAgent(
            "The Strategist", "Topic and Chapter Organizer",
            self._load_prompt("strategist.md")
        )
        self.writer_a = LMStudioAgent(
            "Writer Alpha", "Page Drafter A",
            self._load_prompt("iterative_writer_alpha.md")
        )
        self.writer_b = LMStudioAgent(
            "Writer Beta", "Page Drafter B",
            self._load_prompt("iterative_writer_beta.md")
        )
        self.editor = LMStudioAgent(
            "The Editor", "Page Polisher",
            self._load_prompt("iterative_editor.md")
        )
        self.condenser = LMStudioAgent(
            "The Condenser", "Context Summarizer",
            "You are a context condenser. Given a master outline and previous chapters, create a concise summary of only the most relevant information for writing the next page. Focus on character states, plot threads, and thematic elements that directly impact the upcoming page. Output in clean Markdown format."
        )
        self.critic = LMStudioAgent(
            "The Critic", "Page Evaluator",
            self._load_prompt("iterative_critic.md")
        )
        self.title_agent = LMStudioAgent(
            "Title Generator", "Book Title Generator",
            "You are a creative book title generator. Given a book idea and style, suggest five strong and memorable book titles. Output only a numbered list of titles, no explanation."
        )

    def _load_prompt(self, filename: str) -> str:
        path = os.path.join(SCRIPT_DIR, "prompts", filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        raise FileNotFoundError(f"Missing prompt file: {path}")

    def _log(self, filename: str, content: str):
        path = os.path.join(self.log_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _load_state(self):
        if os.path.exists(self.state_path):
            with open(self.state_path, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        else:
            self.state = {
                "status": "new",
                "current_chapter": 0,
                "current_page": 0,
                "chapters": [],
            }

    def save_state(self):
        self.state.update({
            "user_prompt": self.user_prompt,
            "research_notes": self.research_notes,
            "book_title": self.book_title,
            "book_style": self.book_style,
            "book_summary": self.book_summary,
            "last_page_summary": self.last_page_summary,
            "chapters": self.chapters,
            "last_saved": datetime.now().isoformat(),
        })
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def _safe_filename(self, text: str) -> str:
        safe = "".join(c if c.isalnum() or c in " _-." else "_" for c in text)
        return safe.strip().replace(" ", "_")

    def _save_chapter_file(self, chapter_index: int, chapter_title: str, page_texts: list[str]):
        filename = f"Chapter_{chapter_index+1}_{self._safe_filename(chapter_title)}.md"
        path = os.path.join(self.chapters_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# {chapter_title}\n\n" + "\n\n".join(page_texts))
        return path

    def _measure_word_count(self, text: str) -> int:
        return len(text.split())

    def _generate_page_drafts(self, prompt: str) -> tuple[str, str]:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(self.writer_a.chat, prompt, self.research_notes[:20000])
            future_b = executor.submit(self.writer_b.chat, prompt, self.research_notes[:20000])
            draft_a = future_a.result()
            draft_b = future_b.result()
        return draft_a, draft_b

    def _summarize_text(self, text: str, sentences: int = 2) -> str:
        prompt = f"Summarize the following text in {sentences} concise sentences:\n\n{text}\n\nSummary:"
        return self.condenser.chat(prompt, context="")

    def generate_book_title(self) -> str:
        prompt = f"Book idea: {self.user_prompt}\nStyle: {self.book_style}\n\nSuggest five compelling book titles in a numbered list. Output only titles."
        response = self.title_agent.chat(prompt, context=self.research_notes[:20000])
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        titles = []
        for line in lines:
            if line[0].isdigit() and "." in line:
                titles.append(line.split(".", 1)[1].strip())
            else:
                titles.append(line)
        return titles[0] if titles else "Untitled Book"

    def _format_resume_overview(self) -> str:
        chapter_index = self.state.get("current_chapter", 0)
        page_index = self.state.get("current_page", 0)
        title = self.book_title or "Untitled Book"
        style = self.book_style or "No style selected"
        summary = self.book_summary or "No summary available yet."
        last_page = self.last_page_summary or "No last page summary available yet."

        position = f"Chapter {chapter_index + 1}, Page {page_index + 1}" if chapter_index < len(self.chapters) else "End of planned book"
        return (
            f"Title: {title}\n"
            f"Style: {style}\n"
            f"Current position: {position}\n\n"
            f"Book summary:\n{summary}\n\n"
            f"Last page summary:\n{last_page}"
        )

    def _load_completed_chapter(self, chapter_index: int) -> list[str]:
        if chapter_index >= len(self.chapters):
            return []
        chapter_title = self.chapters[chapter_index]["title"]
        filename = f"Chapter_{chapter_index+1}_{self._safe_filename(chapter_title)}.md"
        path = os.path.join(self.chapters_dir, filename)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().splitlines()
        # Remove title line if present
        if content and content[0].startswith("# "):
            content = content[1:]
        # Rebuild pages by blank lines; this is a best-effort fallback
        pages = [p.strip() for p in "\n".join(content).split("\n\n") if p.strip()]
        return pages

    def plan_book(self) -> dict:
        """Phase 1: Comprehensive Planning"""
        console.print(Panel.fit(
            "📚 [bold gold1]Phase 1: Comprehensive Book Planning[/bold gold1]",
            border_style="gold1"
        ))

        plan_prompt = f"""
Topic/Prompt: {self.user_prompt}
Style/Atmosphere: {self.book_style}
Book Title: {self.book_title or 'TBD'}

Task: Create an extremely detailed, hierarchical outline for an entire book based on this prompt.
Structure the outline as follows:

1. **Book Title**
2. **Genre/Style**
3. **Overall Summary** (2-3 paragraphs)
4. **Main Characters** (detailed bios, arcs, motivations)
5. **Key Themes and Motifs**
6. **Plot Structure**:
   - **Part 1**: [Title] - Summary
     - **Chapter 1**: [Title] - Detailed summary (what happens, key scenes, character developments)
       - **Page 1**: Brief description of content (approx 500-800 words)
       - **Page 2**: ...
     - **Chapter 2**: ...
   - **Part 2**: ...
7. **World-Building Elements** (if applicable)
8. **Tone and Voice Guidelines**
9. **Estimated Total Pages**: [number]

Be exhaustive in detail. Each chapter should have 5-15 pages, each page described specifically.
Output in clean Markdown format.
"""

        outline_path = os.path.join(self.log_dir, "0_Book_Outline.md")
        if os.path.exists(outline_path):
            console.print(f"[cyan]Loading existing outline from {outline_path}[/cyan]")
            with open(outline_path, "r", encoding="utf-8") as f:
                outline = f.read()
        else:
            with console.status("[cyan]The Architect is planning the entire book...[/cyan]"):
                outline = self.planner.chat(plan_prompt, context=self.research_notes[:50000])

            self._log("0_Book_Outline.md", outline)

        # Parse outline to extract structure
        console.print(Panel(Markdown(outline), title="Book Outline", border_style="cyan"))

        if questionary.confirm("Edit the outline manually?", default=False).ask():
            console.print(f"Outline saved to: {os.path.join(self.log_dir, '0_Book_Outline.md')}")
            console.print("Edit the file manually, then press Enter to continue.")
            input("Press Enter when done editing...")
            with open(os.path.join(self.log_dir, "0_Book_Outline.md"), "r", encoding="utf-8") as f:
                outline = f.read()

        # Phase 2: Detailed Topic Planning
        console.print(Panel.fit(
            "📝 [bold gold1]Phase 2: Detailed Topic and Page Planning[/bold gold1]",
            border_style="gold1"
        ))

        detailed_plan_path = os.path.join(self.log_dir, "1_Detailed_Topics.md")
        if os.path.exists(detailed_plan_path):
            console.print(f"[cyan]Loading existing detailed plan from {detailed_plan_path}[/cyan]")
            with open(detailed_plan_path, "r", encoding="utf-8") as f:
                detailed_plan = f.read()
        else:
            topic_plan_prompt = f"""
Initial Outline:
{outline}

Task: Based on the initial outline, create a detailed plan with 20-40 unique, non-repetitive topics that cover the entire book comprehensively. Ensure topics are diverse and avoid redundancy.

For each topic:
- Provide a brief description
- Create 2-3 specific page descriptions (each page ~500-800 words) that develop this topic

Then, group these topics into 10-15 logical chapters. Each chapter should contain 3-6 topics, resulting in 6-18 pages per chapter.

Structure the output as:

**Chapter 1: [Title]**
- **Topic 1: [Title]**
  - Page 1: [Detailed description of content]
  - Page 2: [Detailed description]
  - Page 3: [If needed]
- **Topic 2: [Title]**
  - etc.

Ensure the topics flow logically across chapters and cover all aspects of the book without repetition.
Output in clean Markdown format.
"""

            with console.status("[cyan]The Strategist is creating detailed topics and pages...[/cyan]"):
                detailed_plan = self.strategist.chat(topic_plan_prompt, context=self.research_notes[:50000])

            self._log("1_Detailed_Topics.md", detailed_plan)

        console.print(Panel(Markdown(detailed_plan), title="Detailed Topic Plan", border_style="cyan"))

        if questionary.confirm("Edit the detailed plan manually?", default=False).ask():
            console.print(f"Detailed plan saved to: {os.path.join(self.log_dir, '1_Detailed_Topics.md')}")
            console.print("Edit the file manually, then press Enter to continue.")
            input("Press Enter when done editing...")
            with open(os.path.join(self.log_dir, "1_Detailed_Topics.md"), "r", encoding="utf-8") as f:
                detailed_plan = f.read()

        chapters = self._parse_detailed_plan(detailed_plan)
        self.chapters = chapters
        if not self.book_summary:
            self.book_summary = self._summarize_text(outline[:12000], sentences=3)
        self.state.update({
            "status": "in_progress",
            "current_chapter": 0,
            "current_page": 0,
            "chapters": chapters,
            "book_title": self.book_title,
            "book_style": self.book_style,
            "book_summary": self.book_summary,
            "last_page_summary": self.last_page_summary,
        })
        self.save_state()
        return chapters

    def _parse_detailed_plan(self, plan: str) -> list:
        """Extract chapters and pages from the detailed topic plan."""
        chapters = []
        current_chapter = None
        current_pages = []
        chapter_pattern = re.compile(r'Chapter\s*\d+:', re.IGNORECASE)
        page_pattern = re.compile(r'[•\-]\s*Page\s*\d+:', re.IGNORECASE)

        for line in plan.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if chapter_pattern.search(stripped):
                if current_chapter:
                    chapters.append({"title": current_chapter, "pages": current_pages})
                current_chapter = stripped
                current_pages = []
                continue

            if current_chapter and page_pattern.search(stripped):
                # Extract the page description after the colon
                page_desc = stripped.split(':', 1)[1].strip() if ':' in stripped else stripped
                current_pages.append(page_desc)

        if current_chapter:
            chapters.append({"title": current_chapter, "pages": current_pages})

        return chapters
        """Extract chapters and pages from the outline."""
        chapters = []
        current_chapter = None
        current_pages = []
        chapter_pattern = re.compile(r'chapter\s*\d+', re.IGNORECASE)
        page_pattern = re.compile(r'page\s*\d+', re.IGNORECASE)

        for line in outline.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if chapter_pattern.search(stripped) and ':' in stripped:
                if current_chapter:
                    chapters.append({"title": current_chapter, "pages": current_pages})
                current_chapter = stripped
                current_pages = []
                continue

            if current_chapter and page_pattern.search(stripped) and ':' in stripped:
                current_pages.append(stripped)

        if current_chapter:
            chapters.append({"title": current_chapter, "pages": current_pages})

        return chapters

    def condense_context(self, master_outline: str, previous_chapters: list, current_chapter: dict, page_index: int) -> str:
        """Create condensed context for current page"""
        context_prompt = f"""
Master Outline:
{master_outline}

Previous Chapters Written:
{'\n\n'.join([f'Chapter: {ch["title"]}\nContent: {ch["content"][:2000]}...' for ch in previous_chapters])}

Current Chapter: {current_chapter['title']}
Current Page: {page_index + 1} - {current_chapter['pages'][page_index] if page_index < len(current_chapter['pages']) else 'Continuation'}

Task: Condense the most relevant context for writing this page. Include:
- Current character states and motivations
- Active plot threads
- Thematic elements to maintain
- Key world-building details
- Immediate setup from previous page/chapter

Keep it concise but comprehensive. Output in Markdown.
"""

        condensed = self.condenser.chat(context_prompt, context="")
        context_file = f"context_chapter_{len(previous_chapters)+1}_page_{page_index+1}.md"
        self._log(os.path.join("context_files", context_file), condensed)
        return condensed

    def write_page(self, master_outline: str, condensed_context: str, chapter_title: str, page_desc: str, page_index: int, previous_pages: list) -> str:
        """Write a single page"""
        rolling_context = "\n\n".join(previous_pages[-3:]) if previous_pages else ""  # Last 3 pages

        write_prompt = f"""
Master Outline:
{master_outline[:10000]}

Condensed Context:
{condensed_context}

Chapter: {chapter_title}
Page {page_index + 1}: {page_desc}

Rolling Context (Previous Pages):
{rolling_context}

Task: Write this page of the book. Aim for 500-800 words. Maintain consistent tone, character voices, and plot continuity. Begin seamlessly from the previous page if applicable. Do NOT summarize or conclude the book yet.
"""

        with console.status(f"[green]Writing Page {page_index + 1}...[/green]"):
            draft_a, draft_b = self._generate_page_drafts(write_prompt)

        edit_prompt = f"""
Draft A:
{draft_a}

Draft B:
{draft_b}

Task: Combine the best elements from both drafts into a single, polished page. Maintain flow, eliminate redundancies, enhance prose quality.
"""

        with console.status("[magenta]Editing Page...[/magenta]"):
            page_content = self.editor.chat(edit_prompt, context="")

        if self._measure_word_count(page_content) < 650:
            expand_prompt = f"The current page is too short. Expand this page to at least 650 words while retaining its structure, tone, and character arc. Do not change the meaning unnecessarily.\n\nCurrent Page:\n{page_content}"
            page_content = self.editor.chat(expand_prompt, context="")

        return page_content

    def review_page(self, page_content: str, master_outline: str, chapter_title: str, page_index: int) -> str:
        """Review the page"""
        critique_prompt = f"Page Content:\n{page_content}\n\nMaster Outline:\n{master_outline[:5000]}\n\nTask: Evaluate this page for plot consistency, character development, thematic coherence, and writing quality. Provide constructive feedback."

        with console.status("[yellow]Reviewing Page...[/yellow]"):
            critique = self.critic.chat(critique_prompt, context="")

        console.print(Panel(page_content, title=f"Page {page_index + 1} Draft", border_style="green"))
        console.print(Panel(critique, title="Critique", border_style="yellow"))

        return critique

    def run(self):
        console.print(Panel.fit(
            "📖 [bold gold1]Book Writing Mode[/bold gold1]\n"
            "[dim]Extensive planning → Page-by-page drafting with context condensation[/dim]",
            border_style="gold1"
        ))

        if not self.chapters:
            chapters = self.plan_book()
        else:
            chapters = self.chapters
            console.print(Panel.fit(
                f"[green]Resuming saved book session from {self.log_dir}[/green]",
                border_style="green"
            ))
            overview = self._format_resume_overview()
            console.print(Panel(overview, title="Book Resume Overview", border_style="cyan"))

        written_chapters = []
        start_chapter = self.state.get("current_chapter", 0)
        start_page = self.state.get("current_page", 0)

        for ch_idx in range(start_chapter, len(chapters)):
            chapter = chapters[ch_idx]
            console.print(f"\n[bold gold1]Writing Chapter {ch_idx + 1}: {chapter['title']}[/bold gold1]")

            chapter_content = self._load_completed_chapter(ch_idx)
            p_start = start_page if ch_idx == start_chapter else len(chapter_content)

            for p_idx in range(p_start, len(chapter['pages'])):
                page_desc = chapter['pages'][p_idx]
                page_content = None

                while True:
                    console.print(f"[bold cyan]Page {p_idx + 1}: {page_desc[:50]}...[/bold cyan]")
                    if page_content is None:
                        condensed_context = self.condense_context(
                            open(os.path.join(self.log_dir, "0_Book_Outline.md")).read(),
                            written_chapters,
                            chapter,
                            p_idx
                        )
                        page_content = self.write_page(
                            open(os.path.join(self.log_dir, "0_Book_Outline.md")).read(),
                            condensed_context,
                            chapter['title'],
                            page_desc,
                            p_idx,
                            chapter_content
                        )

                    critique = self.review_page(
                        page_content,
                        open(os.path.join(self.log_dir, "0_Book_Outline.md")).read(),
                        chapter['title'],
                        p_idx,
                    )

                    if self.auto_accept:
                        action = "Accept and Continue"
                    else:
                        action = questionary.select(
                            f"Action for Page {p_idx + 1}:",
                            choices=[
                                "Accept and Continue",
                                "Edit Manually",
                                "Revise with Feedback",
                                "Restart Page",
                                "Pause and Exit"
                            ]
                        ).ask()

                    if action == "Accept and Continue":
                        chapter_content.append(page_content)
                        self._save_chapter_file(ch_idx, chapter['title'], chapter_content)
                        if p_idx + 1 < len(chapter['pages']):
                            self.state["current_chapter"] = ch_idx
                            self.state["current_page"] = p_idx + 1
                        else:
                            self.state["current_chapter"] = ch_idx + 1
                            self.state["current_page"] = 0
                        self.state["status"] = "in_progress"
                        self.state["chapters"] = chapters
                        self.last_page_summary = self._summarize_text(page_content, sentences=2)
                        self.state["last_page_summary"] = self.last_page_summary
                        self.save_state()
                        break

                    if action == "Edit Manually":
                        draft_file = os.path.join(self.log_dir, f"draft_page_{ch_idx+1}_{p_idx+1}.md")
                        with open(draft_file, "w", encoding="utf-8") as f:
                            f.write(page_content)
                        console.print(f"Draft saved to: {draft_file}")
                        console.print("Edit the file manually, then press Enter.")
                        input("Press Enter when done...")
                        with open(draft_file, "r", encoding="utf-8") as f:
                            page_content = f.read()
                        continue

                    if action == "Revise with Feedback":
                        revise_prompt = f"Original Page:\n{page_content}\n\nCritique:\n{critique}\n\nTask: Revise the page based on the critique."
                        page_content = self.editor.chat(revise_prompt, context="")
                        continue

                    if action == "Restart Page":
                        page_content = None
                        continue

                    if action == "Pause and Exit":
                        self.state["current_chapter"] = ch_idx
                        self.state["current_page"] = p_idx
                        self.state["status"] = "paused"
                        self.state["chapters"] = chapters
                        self.save_state()
                        console.print(Panel.fit(
                            f"⏸️ [bold yellow]Book progress saved. You can resume later from {self.log_dir}[/bold yellow]",
                            border_style="yellow"
                        ))
                        return

                # end page loop

            written_chapters.append({"title": chapter['title'], "content": "\n\n".join(chapter_content)})

        self.state["status"] = "complete"
        self.save_state()

        console.print(Panel.fit(
            f"✅ [bold green]Book Writing Complete![/bold green]\n\n"
            f"Chapters saved in: [bold underline]{self.chapters_dir}[/bold underline]\n"
            f"Logs: [bold underline]{self.log_dir}[/bold underline]",
            border_style="green"
        ))

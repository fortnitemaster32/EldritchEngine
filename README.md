# EldritchEngine

The ultimate multi-agent AI writing system powered by [**LM Studio**](https://lmstudio.ai/). Transform PDFs and images into professional, high-impact literature using a coordinated team of specialized AI agents.

## Disclaimer
This project was developed with the assistance of AI tools. While efforts have been made to ensure quality and accuracy, please review and verify all outputs before use.

> **Deep Research Tip**: Always combine Deep Research with a regular research cache for optimal output quality. You can use regular research alone, but avoid using only Deep Research without the cache.

## License
This project is licensed under the MIT License for personal, non-commercial use. For organizational or commercial use.

## The Agentic Architecture
This system utilizes a sophisticated pipeline of specialized agents, each with a distinct persona and mission, broken into specific modes of operation.

### Research Modes
Instead of researching on every single run, research is now separated and cached.
- **Scholar**: Analyzes PDFs in rolling chunks to capture extreme detail, storing notes in `research_cache/`.
- **Deep Research Protocol (4 Parallel PhDs)**: For exhaustive analysis, four specialists (Philosophy, Psychology, Literature, Sociology) process the text in parallel. They then **debate and critique** each other's findings before a **Chief Scholar** synthesizes a massive, multi-disciplinary master paper.

### Essay Mode
A comprehensive 4-phase pipeline for deep, complex topics:
1. **The Architect**: Analyzes your project and drafts a comprehensive Strategic Plan, assigning sections to writers.
2. **The Writers**: Four distinct personalities (Visionary, Analyst, Challenger, Storyteller) draft sections in parallel.
3. **The Reviewers**: Auditor (Logic/Accuracy) and Stylist (Tone/Flow) perform parallel in-depth critiques.
4. **The Editors**: Sculptor (Structure) and Finisher (Final Polish) create the definitive version through sequential editing passes.

**Enricher Mode** (Optional): Adds two additional agents for enhanced literary quality:
- **The Lexicographer**: Curates a thesaurus of ~200 sophisticated, topic-specific terms provided as context to writers and editors.
- **The Precisionist**: Suggests synonym replacements for key words/phrases, provided as guidance to reviewers and editors (without rewriting the draft).

### Iterative Mode
This mode provides a structured, iterative approach to writing. First, a planner agent generates a detailed outline based on your topic. Then, the writing process proceeds paragraph by paragraph: each paragraph is drafted by a writer agent, reviewed by a critic for improvements, and edited if necessary. This allows for live feedback and revisions at each step, ensuring high precision and quality control throughout the composition.

### Short Writing Mode
A highly efficient, parallel-writer pipeline for articles, stories, and op-eds:
1. **The Planner**: Constructs a precise, section-by-section outline.
2. **Two Parallel Writers**: Generate the same piece from different creative approaches—one emphasizing imagination, imagery, and emotional depth; the other prioritizing clarity, logical flow, and structural integrity.
3. **The Editor**: Merges the best parts of both drafts into a final, polished piece, preserving strong imagery and bold expression alongside clear, coherent structure. Uses the original research cache when available.

### Custom Workflow Mode
Design and run your own multi-agent pipelines. Build custom stages with sequential or parallel agents, each with tailored system prompts and context feeds.

## Project Structure
- `tui.py`: The main interactive Terminal User Interface.
- `agent_writer.py`: The core engine orchestrating the full Essay mode.
- `short_writer.py`: The lean engine for short-form content.
- `iterative_writer.py`: The engine for paragraph-by-paragraph iterative writing with review.
- `deep_research_mode.py`: The orchestrator for the parallel PhD debate protocol.
- `modular_writer.py`: The engine for custom user-defined workflows.
- `research_cache.py`: Utilities for saving and loading Scholar notes to skip re-reading PDFs.
- `prompts/`: **Customizable agent personalities.** Edit these Markdown files to change how agents behave.
- `workflows/`: Saved JSON configurations for custom workflows.
- `inputs/`: Place your PDF and image files here for processing.
- `outputs/`: Finished documents are saved here.
- `logs/`: Detailed session logs, intermediate drafts, and step-by-step outputs.
- `research_cache/`: Saved JSON files containing extracted PDF context.

## Recommended Model
For best performance, I recommend using the **Gemma 4 E2B IT** model in LM Studio based on my qualatative experience. It performs exceptionally well relative to its size, especially for initial testing runs. Having 64k token context window provides ample space for research and essay modes without truncation issues.

## Getting Started
1.  Ensure **LM Studio** is running with the Local Server active (usually `http://localhost:1234`).
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Launch the studio:
    ```powershell
    python tui.py
    ```

## ✨ Key Features
- **Keyboard-Driven TUI**: Rapid mode and file selection.
- **Decoupled Research Caching**: Analyze a massive PDF once, then write 10 different essays about it without re-reading the book.
- **Deep Research Debate**: PhD agents literally debate each other's findings to eliminate blind spots.
- **High-Volume Output**: Deep Research and Retro-Synthesis are tuned to produce 20,000+ word masterworks by forcing recursive depth.
- **Context Guard**: Hardware-aware monitoring prevents LM Studio crashes by automatically truncating and warning when limits are reached.
- **Parallel Processing**: Agents work in parallel to significantly reduce wait times.
- **Rolling Context Windows**: Enables writing extremely long, coherent pieces without memory overflow.

## 🗃️ Prompt Registry
The following table maps agents/workflows to their external prompt files in `prompts/`. Edit these to change behavior.

| Workflow | Agent | Prompt File |
| :--- | :--- | :--- |
| **Deep Research** | Philosophers | `phd_philosopher.md` |
| | Psychologists | `phd_psychologist.md` |
| | Literary Critics | `phd_literary.md` |
| | Sociologists | `phd_sociologist.md` |
| | Debate Phase | `debate_critique.md` |
| | Synthesis | `chief_scholar.md` |
| **Essay Mode** | The Architect | `architect.md` |
| | The Writers | `writer_visionary.md`, `writer_analyst.md`, etc. |
| | The Reviewers | `reviewer_stylist.md`, `reviewer_auditor.md` |
| | The Editors | `editor_sculptor.md`, `editor_finisher.md` |
| **Short Writing** | The Planner | `short_planner.md` |
| | Creative Writer | `short_writer_creative.md` |
| | Logical Writer | `short_writer_logical.md` |
| | Editor | `short_editor.md` |
| **Iterative** | Planner | `iterative_planner.md` |
| | Writers | `iterative_writer_alpha.md`, `iterative_writer_beta.md` |
| | Editor | `iterative_editor.md` |
| **Book Mode** | Condenser | `book_condenser.md` |
| | Title Gen | `book_title_gen.md` |
| **Retro-Synth** | Synthesis | `chief_scholar_synthesis.md` |

## ⚠️ Safety & Hardware
If you encounter "Context Window Exceeded" errors, the engine will guide you through fixing them in LM Studio. You can also adjust the **Max Context Window** in the Settings menu to match your GPU's VRAM.


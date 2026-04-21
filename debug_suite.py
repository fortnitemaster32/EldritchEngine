import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch
from rich.console import Console
from rich.panel import Panel
import traceback

# Add current dir to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

console = Console()

class GhostAgent:
    """A Mock Agent that returns dummy text instantly without AI usage."""
    def __init__(self, name, role, system_prompt):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
    
    def chat(self, user_input, context="", history=None, on_update=None):
        if on_update:
            on_update({"status": "Ghost Ingesting...", "tps": 0, "tokens": 0})
        
        # Return different dummy content based on the prompt to test parsing logic
        if "Suggest five compelling book titles" in user_input:
            return "1. Ghost Book\n2. Phantoms of Code\n3. The Silent Engine\n4. Digital Echoes\n5. Void Script"
        if "create a detailed section-by-section outline" in user_input or "Mission Brief" in user_input:
            return "# Ghost Outline\n\n## Section 1\nThis is a dummy section plan.\n\n<paragraph_plan>\nDraft a ghost paragraph.\n</paragraph_plan>"
        if "Merge these into a single" in user_input or "Combine and polish" in user_input:
            return "This is a polished ghost paragraph that merges multiple drafts into one cohesive unit of simulated literature."
        
        return "Ghost Research Notes Content"

class EldritchRobustnessTest(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        console.print(Panel.fit("[bold cyan]EldritchEngine Ghost-Debug Suite[/bold cyan]\n[dim]Testing logic with ZERO AI usage[/dim]", border_style="cyan"))

    def test_01_prompt_integrity(self):
        """Verify all mandatory prompt files exist."""
        console.print("\n[bold underline]Test 01: Prompt Integrity Scan[/bold underline]")
        prompt_dir = os.path.join(SCRIPT_DIR, "prompts")
        mandatory_prompts = [
            "scholar.md", "strategist.md", "architect.md", "writer_visionary.md", 
            "editor_sculptor.md", "short_planner.md", "short_writer_creative.md",
            "short_writer_logical.md", "short_editor.md", "iterative_planner.md"
        ]
        
        for p in mandatory_prompts:
            path = os.path.join(prompt_dir, p)
            exists = os.path.exists(path)
            status = "[green]OK[/green]" if exists else "[red]MISSING[/red]"
            console.print(f"  - {p:<30} {status}")
            self.assertTrue(exists, f"Mandatory prompt file missing: {p}")

    @patch('agent_writer.LMStudioAgent', side_effect=GhostAgent)
    def test_02_essay_workflow_logic(self, mock_agent):
        """Test Essay Mode logic (Research -> Plan -> Write) using Ghost Agents."""
        console.print("\n[bold underline]Test 02: Essay Mode Logic (Ghost Mode)[/bold underline]")
        try:
            import agent_writer
            # Create workflow with no PDF (prompt only)
            wf = agent_writer.AgenticWorkflow(None, "Testing Ghost Logic")
            # Set dummy pdf pages to trigger research loop
            wf.pdf_pages = ["Page 1 content"]
            
            # Simulate research
            wf.conduct_research()
            self.assertTrue(len(wf.research_notes) > 0, "Research notes should not be empty")
            
            # Simulate full run
            result = wf.run(target_word_count=100)
            self.assertIn("output_file", result)
            console.print(f"  OK: Essay Workflow Completed Logic Check.")
        except Exception:
            console.print(f"FAILED:\n{traceback.format_exc()}")
            raise

    @patch('agent_writer.LMStudioAgent', side_effect=GhostAgent)
    def test_03_short_writing_logic(self, mock_agent):
        """Test Short Writing logic."""
        console.print("\nTest 03: Short Writing Logic (Ghost Mode)")
        try:
            import short_writer
            wf = short_writer.ShortWriterWorkflow("Test Topic", "article", 500)
            result = wf.run()
            self.assertIn("output_file", result)
            console.print(f"  OK: Short Writing Workflow Completed Logic Check.")
        except Exception:
            console.print(f"FAILED:\n{traceback.format_exc()}")
            raise

    def test_04_pdf_exporter_sanitization(self):
        """Test if PDF exporter correctly strips meta-tags."""
        console.print("\nTest 04: PDF Metadata Sanitization")
        import pdf_exporter
        raw_md = "Title\n\n<critique>This should be removed</critique>\nActual content.\n<paragraph_plan>Remove me too</paragraph_plan>"
        clean_md = pdf_exporter._clean_engine_metadata(raw_md)
        
        self.assertNotIn("<critique>", clean_md)
        self.assertNotIn("<paragraph_plan>", clean_md)
        self.assertIn("Actual content.", clean_md)
        console.print("  OK: PDF Sanitizer successfully stripped internal XML tags.")

if __name__ == "__main__":
    unittest.main(verbosity=0)

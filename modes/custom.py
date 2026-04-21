import os
import json
import questionary
from rich.panel import Panel
from ui_core import console, offer_pdf_export
import agent_writer
import modular_writer

def _ai_generate_system_prompt(agent_name, agent_role, workflow_topic, description):
    helper = agent_writer.LMStudioAgent("Prompt Engineer", "Meta Agent", "You are an expert AI prompt engineer. Write a precise system prompt.")
    request = f"Write a system prompt for {agent_name} ({agent_role}) on {workflow_topic}: {description}"
    with console.status("[cyan]AI is generating the system prompt…[/cyan]"):
        return helper.chat(request, context="").strip()

def _build_context_feed_choice(stage_idx, all_stages):
    choices = [
        questionary.Choice("Entire accumulated conversation state", value="all_previous"),
        questionary.Choice("Topic/goal only", value="topic_only"),
        questionary.Choice("Research notes only", value="research_only"),
        questionary.Choice("All outputs from the previous stage", value="last_stage_all"),
    ]
    return questionary.select("What information should this agent receive?", choices=choices).ask() or "all_previous"

def _display_workflow_summary(config):
    console.print("\n[bold gold1]── Workflow Summary ──[/bold gold1]")
    console.print(f"  [bold]Name:[/bold]  {config['name']}")
    for s_idx, s in enumerate(config.get("stages", [])):
        console.print(f"  [bold magenta]Stage {s_idx+1}: {s['name']}[/bold magenta]")

def _save_workflow(config, script_dir):
    wf_dir = os.path.join(script_dir, "workflows")
    os.makedirs(wf_dir, exist_ok=True)
    safe_name = config["name"].lower().replace(" ", "_")
    save_path = os.path.join(wf_dir, f"{safe_name}.json")
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return save_path

def _build_workflow_tui(topic):
    workflow_name = questionary.text("Give this workflow a name:").ask()
    if not workflow_name: return None
    requires_research = questionary.confirm("Does this workflow need source material?", default=False).ask()
    stages = []
    while True:
        stage_name = questionary.text(f"Name for Stage {len(stages)+1}:").ask() or f"Stage {len(stages)+1}"
        stage_type = questionary.select("Stage type:", choices=[
            questionary.Choice("Parallel", value="parallel"),
            questionary.Choice("Sequential", value="sequential"),
        ]).ask()
        if not stage_type: break
        agents = []
        while True:
            a_name = questionary.text(f"Agent {len(agents)+1} Name:").ask()
            if not a_name: break
            a_role = questionary.text(f"Agent {len(agents)+1} Role:").ask() or "Worker"
            prompt_mode = questionary.select("System prompt mode:", choices=["manual", "ai"]).ask()
            if prompt_mode == "ai":
                desc = questionary.text(f"Describe what {a_name} should do:").ask()
                a_prompt = _ai_generate_system_prompt(a_name, a_role, topic, desc)
            else:
                a_prompt = questionary.text(f"{a_name} system prompt:").ask() or "Work."
            agents.append({"name": a_name, "role": a_role, "system_prompt": a_prompt, "context_feed": _build_context_feed_choice(len(stages), stages)})
            if not questionary.confirm("Add another agent?").ask(): break
        stages.append({"name": stage_name, "type": stage_type, "agents": agents})
        if not questionary.confirm("Add another stage?").ask(): break
    return {"name": workflow_name, "requires_research": requires_research, "stages": stages}

def run_custom_mode(script_dir):
    console.print(Panel.fit("🛠️  [bold cyan]Custom Workflow Mode[/bold cyan]", border_style="cyan"))
    wf_dir = os.path.join(script_dir, "workflows")
    os.makedirs(wf_dir, exist_ok=True)
    saved = [f for f in os.listdir(wf_dir) if f.endswith(".json")]
    
    action = questionary.select("Action:", choices=["New", "Run", "Delete", "Back"]).ask()
    if action == "Back": return

    if action == "Run" and saved:
        chosen = questionary.select("Choose workflow:", choices=saved).ask()
        if not chosen: return
        with open(os.path.join(wf_dir, chosen), "r") as f: config = json.load(f)
        topic = questionary.text("Topic:", default=config.get("topic", "")).ask()
        research_notes = ""
        if config.get("requires_research"):
            from ui_core import pick_cache
            research_notes = pick_cache()
        wf = modular_writer.ModularWorkflow(config, topic, research_notes)
        result = wf.run()
        offer_pdf_export(result, script_dir)
    elif action == "New":
        topic = questionary.text("Goal:").ask()
        if not topic: return
        config = _build_workflow_tui(topic)
        if config:
            config["topic"] = topic
            _save_workflow(config, script_dir)
            wf = modular_writer.ModularWorkflow(config, topic, "")
            result = wf.run()
            offer_pdf_export(result, script_dir)

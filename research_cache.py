"""
Research Cache — save and load Scholar research notes so the LLM pipeline
does not have to re-read a PDF every single run.

Cache files are stored as JSON in the `research_cache/` directory.
"""

import json
import os
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, "research_cache")


def _ensure_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def save_research(source_name: str, prompt: str, research_notes: str, page_count: int) -> str:
    """
    Persist research notes to disk.
    Returns the cache ID (filename stem) so the caller can reference it later.
    """
    _ensure_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Sanitise the source name so it is safe as a filename
    safe = re.sub(r"[^\w\s-]", "", source_name).strip().replace(" ", "_")[:50]
    cache_id = f"{safe}_{timestamp}"

    payload = {
        "id": cache_id,
        "source_name": source_name,
        "prompt": prompt,
        "research_notes": research_notes,
        "page_count": page_count,
        "word_count": len(research_notes.split()),
        "timestamp": datetime.now().isoformat(),
    }

    path = os.path.join(CACHE_DIR, f"{cache_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)

    return cache_id


def list_caches() -> list:
    """
    Return a list of cache metadata dicts (research_notes excluded for speed).
    Sorted newest-first.
    """
    _ensure_dir()
    results = []
    seen = set()  # Tracks (base_name, research_type) to only show the newest

    for fname in sorted(os.listdir(CACHE_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            
            source_name = data.get("source_name", "Unknown")
            is_deep = "(Deep Research)" in source_name
            base_name = source_name.replace(" (Deep Research)", "").strip()
            rtype = "Deep Academic" if is_deep else "Standard Literary"
            
            # Archive/hide older runs of the same document & same research type
            key = (base_name, rtype)
            if key in seen:
                continue
            seen.add(key)

            results.append(
                {
                    "id": data.get("id", fname.replace(".json", "")),
                    "source_name": source_name,
                    "base_name": base_name,
                    "type": rtype,
                    "prompt": data.get("prompt", ""),
                    "page_count": data.get("page_count", 0),
                    "word_count": data.get("word_count", 0),
                    "timestamp": data.get("timestamp", ""),
                    "path": path,
                }
            )
        except Exception:
            pass  # Silently skip corrupt entries
    return results


def load_cache_by_path(path: str) -> dict:
    """Load a full cache entry (including research_notes) from its file path."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_cache_by_id(cache_id: str) -> dict:
    """Load a full cache entry by its ID string."""
    _ensure_dir()
    path = os.path.join(CACHE_DIR, f"{cache_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No cache found with id: {cache_id}")
    return load_cache_by_path(path)

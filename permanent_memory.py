import os
import json
import math
import time
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Import existing config
import config_manager

console = Console()

class PermanentMemory:
    """
    EldritchEngine 'Permanent Memory' (Local RAG).
    Uses LM Studio's /v1/embeddings to store and retrieve research semantically.
    """
    def __init__(self, vault_path: str = None):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.vault_dir = vault_path or os.path.join(self.script_dir, "vault")
        os.makedirs(self.vault_dir, exist_ok=True)
        self.memory_file = os.path.join(self.vault_dir, "memory.json")
        self.index = self._load_index()

    def _load_index(self) -> List[Dict]:
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_index(self):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2)

    def _get_embedding(self, text: str) -> List[float]:
        """Call LM Studio's embedding endpoint."""
        import urllib.request
        import json
        
        url = config_manager.get_setting("lm_studio_url")
        if not url.endswith("/v1"):
            url = f"{url.rstrip('/')}/v1"
        
        # --- NEW: Model Detection ---
        model_name = "default"
        try:
            with urllib.request.urlopen(f"{url}/models") as res:
                m_data = json.loads(res.read().decode("utf-8"))
                # Try to find an embedding model, otherwise use the first loaded model
                for m in m_data["data"]:
                    if "embed" in m["id"].lower():
                        model_name = m["id"]
                        break
                if model_name == "default" and m_data["data"]:
                    model_name = m_data["data"][0]["id"]
        except:
            pass # Fallback to default or nomic

        endpoint = f"{url}/embeddings"
        data = json.dumps({
            "model": model_name,
            "input": text
        }).encode("utf-8")
        
        try:
            req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["data"][0]["embedding"]
        except Exception as e:
            # Silent fail for now, UI will handle empty vector
            return []

    def index_text(self, text: str, source_name: str, chunk_size: int = 1000):
        """Chunk and index text into the vault."""
        # Simple overlap chunking
        chunks = []
        for i in range(0, len(text), chunk_size - 100):
            chunks.append(text[i:i + chunk_size])
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Indexing {source_name}...", total=len(chunks))
            
            for i, chunk in enumerate(chunks):
                vector = self._get_embedding(chunk)
                if vector:
                    self.index.append({
                        "id": f"{source_name}_{i}",
                        "source": source_name,
                        "text": chunk,
                        "vector": vector,
                        "timestamp": time.time()
                    })
                progress.update(task, advance=1)
        
        self._save_index()

    def query(self, query_text: str, top_k: int = 5) -> str:
        """Find the most relevant chunks for a query."""
        if not self.index:
            return ""
            
        query_vector = self._get_embedding(query_text)
        if not query_vector:
            return ""
            
        def cosine_similarity(v1, v2):
            dot_product = sum(a*b for a, b in zip(v1, v2))
            mag1 = math.sqrt(sum(a**2 for a in v1))
            mag2 = math.sqrt(sum(a**2 for a in v2))
            if not mag1 or not mag2: return 0
            return dot_product / (mag1 * mag2)
            
        scored_chunks = []
        for chunk in self.index:
            sim = cosine_similarity(query_vector, chunk["vector"])
            scored_chunks.append((sim, chunk))
            
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [item[1]["text"] for item in scored_chunks[:top_k]]
        
        return "\n\n---\n\n".join(top_chunks)

    def print_cognitive_atlas(self):
        """Easter Egg: Visualize the main topics in the memory vault."""
        if len(self.index) < 2:
            console.print("[yellow]Not enough memories to build an Atlas. Index at least 2 chunks first![/yellow]")
            return

        console.print("\n[bold gold1]Generating Cognitive Atlas (Topic Graph)...[/bold gold1]")
        
        # Simple K-Means implementation in pure Python
        import random
        k = min(3, len(self.index)) # Adjust K if we have very little data
        vectors = [item["vector"] for item in self.index if item["vector"]]
        if not vectors: 
            console.print("[red]No valid embedding vectors found in vault.[/red]")
            return
        
        # Initialize centroids safely
        centroids = random.sample(vectors, k)
        
        def dist(v1, v2):
            return math.sqrt(sum((a-b)**2 for a,b in zip(v1, v2)))
            
        for _ in range(5): # 5 iterations for rough clustering
            clusters = [[] for _ in range(k)]
            for item in self.index:
                v = item["vector"]
                dists = [dist(v, c) for c in centroids]
                closest = dists.index(min(dists))
                clusters[closest].append(item)
            
            # Re-calculate centroids
            for i in range(k):
                if not clusters[i]: continue
                v_sum = [0.0] * len(centroids[i])
                for item in clusters[i]:
                    for j, val in enumerate(item["vector"]):
                        v_sum[j] += val
                centroids[i] = [val / len(clusters[i]) for val in v_sum]
        
        # Name the clusters based on most frequent words (simple approach)
        from collections import Counter
        import re
        
        table = Table(title="Thematic Pillars of Your Memory Vault", border_style="gold1")
        table.add_column("Pillar", style="cyan", justify="right")
        table.add_column("Strength", style="magenta")
        table.add_column("Dominant Keywords", style="white")
        
        for i, cluster in enumerate(clusters):
            all_text = " ".join([item["text"] for item in cluster]).lower()
            words = re.findall(r'\b\w{5,}\b', all_text) # Only words with 5+ chars
            common = [w for w, count in Counter(words).most_common(5)]
            
            strength = len(cluster) / len(self.index)
            bar = "█" * int(strength * 20)
            
            table.add_row(f"Pillar {i+1}", f"{bar} {strength:.1%}", ", ".join(common))
            
        console.print(table)
        console.print("\n[dim]The 'Cognitive Atlas' uses K-Means clustering to map the semantic density of your vault.[/dim]")

memory = PermanentMemory()

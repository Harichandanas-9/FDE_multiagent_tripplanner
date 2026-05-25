"""FAISS vector memory with hashed-embedding fallback."""
from __future__ import annotations
import json, pickle
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from config import settings

try:
    import faiss
    HAS_FAISS = True
except Exception:
    HAS_FAISS = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except Exception:
    HAS_OPENAI = False


def _hash_embed(text: str, dim: int = 384) -> np.ndarray:
    rng = np.random.default_rng(abs(hash(text)) % (2**32))
    v = rng.standard_normal(dim).astype(np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


class VectorMemory:
    def __init__(self, store_dir: Optional[Path] = None, dim: int = 1536):
        self.dir = store_dir or settings.memory_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "faiss.index"
        self.meta_path = self.dir / "meta.json"
        self.dim = dim if HAS_OPENAI and settings.has_openai() else 384
        self.metadata: List[Dict[str, Any]] = []
        self._client = None
        if HAS_FAISS:
            self.index = faiss.IndexFlatIP(self.dim)
        else:
            self.index = None
            self._vectors: List[np.ndarray] = []
        self._load()

    def _load(self):
        if self.meta_path.exists():
            try: self.metadata = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception: self.metadata = []
        if HAS_FAISS and self.index_path.exists():
            try: self.index = faiss.read_index(str(self.index_path))
            except Exception: self.index = faiss.IndexFlatIP(self.dim)
        elif not HAS_FAISS:
            vp = self.dir / "vectors.pkl"
            if vp.exists():
                try: self._vectors = pickle.loads(vp.read_bytes())
                except Exception: self._vectors = []

    def _save(self):
        self.meta_path.write_text(json.dumps(self.metadata, indent=2, default=str),
                                    encoding="utf-8")
        if HAS_FAISS: faiss.write_index(self.index, str(self.index_path))
        else: (self.dir / "vectors.pkl").write_bytes(pickle.dumps(self._vectors))

    def _embed(self, text: str) -> np.ndarray:
        if HAS_OPENAI and settings.has_openai():
            try:
                if self._client is None:
                    self._client = OpenAI(api_key=settings.openai_api_key)
                r = self._client.embeddings.create(model=settings.embedding_model, input=text)
                v = np.array(r.data[0].embedding, dtype=np.float32)
                n = float(np.linalg.norm(v))
                return v / n if n > 0 else v
            except Exception: pass
        return _hash_embed(text, self.dim)

    def add(self, text: str, metadata: Dict[str, Any]):
        v = self._embed(text)
        if v.shape[0] != self.dim:
            self.dim = v.shape[0]
            if HAS_FAISS: self.index = faiss.IndexFlatIP(self.dim)
            else: self._vectors = []
            self.metadata = []
        if HAS_FAISS: self.index.add(v.reshape(1, -1))
        else: self._vectors.append(v)
        self.metadata.append({"text": text, **metadata})
        self._save()

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        if not self.metadata: return []
        v = self._embed(query)
        if HAS_FAISS and self.index.ntotal > 0:
            D, I = self.index.search(v.reshape(1, -1), min(k, self.index.ntotal))
            return [{**self.metadata[i], "score": float(D[0][j])}
                    for j, i in enumerate(I[0]) if 0 <= i < len(self.metadata)]
        scores = [(float(np.dot(v, x)), i) for i, x in enumerate(self._vectors)]
        scores.sort(reverse=True)
        return [{**self.metadata[i], "score": s} for s, i in scores[:k]]


_mem: Optional[VectorMemory] = None


def get_vector_memory() -> VectorMemory:
    global _mem
    if _mem is None: _mem = VectorMemory()
    return _mem

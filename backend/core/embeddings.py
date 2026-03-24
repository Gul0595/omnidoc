"""
core/embeddings.py — GPU-accelerated embeddings

Uses sentence-transformers with CUDA if RTX 4050 is available.
Falls back to Ollama nomic-embed-text, then HuggingFace API.
"""
import os, logging
import numpy as np
from typing import List

logger  = logging.getLogger(__name__)
_model  = None
_mode   = None


def _init():
    global _model, _mode
    if _mode:
        return
    try:
        from sentence_transformers import SentenceTransformer
        import torch
        device  = "cuda" if torch.cuda.is_available() else "cpu"
        _model  = SentenceTransformer(os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2"), device=device)
        _mode   = f"local_{device}"
        logger.info(f"Embeddings: sentence-transformers on {device.upper()}")
        return
    except Exception as e:
        logger.warning(f"sentence-transformers failed: {e}")
    _mode = "ollama" if os.getenv("OLLAMA_URL") else "huggingface"
    logger.info(f"Embeddings: {_mode}")


def embed_texts(texts: List[str]) -> np.ndarray:
    _init()
    if _mode and _mode.startswith("local"):
        return np.array(_model.encode(texts, batch_size=64, normalize_embeddings=True),
                        dtype=np.float32)
    if _mode == "ollama":
        return _embed_ollama(texts)
    return _embed_hf(texts)


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])


def _embed_ollama(texts: List[str]) -> np.ndarray:
    import httpx
    url   = os.getenv("OLLAMA_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    vecs  = []
    for t in texts:
        r = httpx.post(f"{url}/api/embeddings",
                       json={"model": model, "prompt": t}, timeout=30)
        r.raise_for_status()
        vecs.append(r.json()["embedding"])
    return np.array(vecs, dtype=np.float32)


def _embed_hf(texts: List[str]) -> np.ndarray:
    import httpx
    model = "sentence-transformers/all-MiniLM-L6-v2"
    r = httpx.post(
        f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model}",
        headers={"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY', '')}"},
        json={"inputs": texts, "options": {"wait_for_model": True}}, timeout=60)
    r.raise_for_status()
    return np.array(r.json(), dtype=np.float32)


def get_embed_dim() -> int:
    dims = {"all-MiniLM-L6-v2": 384, "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768, "nomic-embed-text": 768}
    return dims.get(os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2"), 384)

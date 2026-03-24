"""
core/rag_engine.py — Production RAG Engine

Features:
  - pgvector (PostgreSQL) — replaces FAISS, no data loss on restart
  - OCR auto-detection for scanned PDFs (pytesseract)
  - Table-aware chunking (pdfplumber)
  - Semantic paragraph chunking
  - BM25 + dense hybrid retrieval
  - GPU cross-encoder reranking (RTX 4050)
  - Sector-specific + universal fact patterns
  - Per-workspace isolation
  - Page-level citations with evidence quotes
"""
import os, re, logging
from typing import List, Optional, Tuple
import numpy as np

from core.embeddings import embed_texts, embed_query
from sectors import SectorConfig, get_sector

logger = logging.getLogger(__name__)

UNIVERSAL_EXTRACTIVE_SIGNALS = [
    "how much", "how many", "what is the", "what was the", "what are the",
    "total", "amount", "value", "cost", "price", "rate", "percentage", "%",
    "who is", "who was", "when", "what date", "what year", "deadline",
    "where", "address", "clause", "section", "article",
    "number", "quantity", "duration", "period", "count", "size",
]

UNIVERSAL_FACT_PATTERNS: List[Tuple[str, str]] = [
    (r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:million|billion|thousand))?', "monetary value"),
    (r'[\d,]+(?:\.\d+)?\s*%',                                      "percentage"),
    (r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b',                   "date"),
    (r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',
     "full date"),
    (r'\b\d{4}\b',                                                  "year"),
    (r'(?:Section|Clause|Article|Exhibit|Schedule)\s+[\d\.]+',     "reference"),
    (r'[\d,]+(?:\.\d+)?\s*(?:days?|months?|years?|weeks?)',        "duration"),
    (r'(?:Rs\.?|₹)\s*[\d,]+',                                      "INR amount"),
]


class RAGEngine:
    def __init__(self, workspace_id: str, sector_id: str = "it", db=None):
        self.workspace_id = workspace_id
        self.sector_id    = sector_id
        self.sector       = get_sector(sector_id)
        self.db           = db
        self._reranker    = None
        self._bm25        = None
        self._bm25_chunks: List[dict] = []

    def _get_reranker(self):
        if self._reranker is not None:
            return self._reranker
        try:
            from sentence_transformers import CrossEncoder
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2",
                                          device=device)
            logger.info(f"Reranker: {device.upper()}")
        except Exception as e:
            logger.warning(f"Reranker unavailable: {e}")
        return self._reranker

    # ── PDF extraction ────────────────────────────────────────────────────────

    def _extract_pdf(self, file_bytes: bytes, filename: str):
        import fitz
        chunks = []
        try:
            doc        = fitz.open(stream=file_bytes, filetype="pdf")
            page_count = len(doc)
            has_scanned = False
            for pnum, page in enumerate(doc):
                text = page.get_text().strip()
                if len(text) < 50:
                    text        = self._ocr_page(page)
                    has_scanned = True
                if text:
                    chunks.extend(self._chunk(text, filename, pnum + 1))
            # Tables
            table_chunks, has_tables = self._extract_tables(file_bytes, filename)
            chunks.extend(table_chunks)
            return chunks, page_count, has_scanned, has_tables
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return [], 0, False, False

    def _ocr_page(self, page) -> str:
        try:
            import pytesseract
            from PIL import Image
            import io
            # Windows path — configured in .env
            tess = os.getenv("TESSERACT_CMD")
            if tess:
                pytesseract.pytesseract.tesseract_cmd = tess
            mat = page.get_transformation_matrix(300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            return pytesseract.image_to_string(img, lang="eng").strip()
        except ImportError:
            logger.warning("pytesseract not installed. Run: pip install pytesseract Pillow")
            return ""
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

    def _extract_tables(self, file_bytes: bytes, filename: str):
        try:
            import pdfplumber, io
            chunks, has_tables = [], False
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for pnum, page in enumerate(pdf.pages):
                    for table in page.extract_tables() or []:
                        rows = [" | ".join(str(c or "").strip() for c in row)
                                for row in table if any(row)]
                        if rows:
                            has_tables = True
                            chunks.append({
                                "text": "\n".join(rows),
                                "source": filename, "page": pnum + 1,
                                "chunk_type": "table",
                                "workspace_id": self.workspace_id,
                                "sector_id": self.sector_id,
                            })
            return chunks, has_tables
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")
            return [], False

    def _chunk(self, text: str, filename: str, page: int) -> List[dict]:
        paras  = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks, buf = [], ""
        for p in paras:
            if len(buf) + len(p) < 500:
                buf += "\n" + p
            else:
                if buf.strip():
                    chunks.append({"text": buf.strip(), "source": filename,
                                   "page": page, "chunk_type": "text",
                                   "workspace_id": self.workspace_id,
                                   "sector_id": self.sector_id})
                buf = p
        if buf.strip():
            chunks.append({"text": buf.strip(), "source": filename,
                           "page": page, "chunk_type": "text",
                           "workspace_id": self.workspace_id,
                           "sector_id": self.sector_id})
        return chunks

    # ── Ingest ────────────────────────────────────────────────────────────────

    def ingest_bytes(self, file_bytes: bytes, filename: str,
                     doc_id: str) -> tuple:
        from api.database import VectorChunk
        chunks, page_count, has_scanned, has_tables = self._extract_pdf(
            file_bytes, filename)
        if not chunks:
            return 0, page_count, has_scanned, has_tables

        texts      = [c["text"] for c in chunks]
        embeddings = embed_texts(texts)

        for chunk, emb in zip(chunks, embeddings):
            vc = VectorChunk(
                doc_id=doc_id, workspace_id=self.workspace_id,
                sector_id=self.sector_id, source=chunk["source"],
                page=chunk["page"], chunk_type=chunk.get("chunk_type", "text"),
                text=chunk["text"], embedding=emb.tolist(),
            )
            self.db.add(vc)
        self.db.commit()
        # Invalidate BM25 cache
        self._bm25       = None
        self._bm25_chunks = []
        return len(chunks), page_count, has_scanned, has_tables

    def delete_doc_chunks(self, doc_id: str):
        from api.database import VectorChunk
        self.db.query(VectorChunk).filter(
            VectorChunk.doc_id == doc_id).delete()
        self.db.commit()
        self._bm25       = None
        self._bm25_chunks = []

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def _dense_retrieve(self, query: str, top_k: int = 20) -> List[dict]:
        from sqlalchemy import text as sql_text
        q_emb = embed_query(query)[0].tolist()
        rows  = self.db.execute(sql_text("""
            SELECT id, doc_id, source, page, chunk_type, text,
                   1 - (embedding <=> CAST(:qv AS vector)) AS score
            FROM vector_chunks
            WHERE workspace_id = :ws
            ORDER BY embedding <=> CAST(:qv AS vector)
            LIMIT :k
        """), {"qv": str(q_emb), "ws": self.workspace_id, "k": top_k}).fetchall()
        return [{"id": r.id, "doc_id": r.doc_id, "source": r.source,
                 "page": r.page, "chunk_type": r.chunk_type, "text": r.text}
                for r in rows]

    def _bm25_retrieve(self, query: str, top_k: int = 15) -> List[dict]:
        if not self._bm25:
            from api.database import VectorChunk
            from rank_bm25 import BM25Okapi
            rows = self.db.query(
                VectorChunk.id, VectorChunk.doc_id, VectorChunk.source,
                VectorChunk.page, VectorChunk.chunk_type, VectorChunk.text
            ).filter(VectorChunk.workspace_id == self.workspace_id).all()
            self._bm25_chunks = [{"id": r.id, "doc_id": r.doc_id,
                                   "source": r.source, "page": r.page,
                                   "chunk_type": r.chunk_type, "text": r.text}
                                  for r in rows]
            if self._bm25_chunks:
                self._bm25 = BM25Okapi(
                    [c["text"].lower().split() for c in self._bm25_chunks])
        if not self._bm25 or not self._bm25_chunks:
            return []
        scores   = self._bm25.get_scores(query.lower().split())
        top_idxs = scores.argsort()[-top_k:][::-1]
        return [self._bm25_chunks[i] for i in top_idxs if scores[i] > 0]

    def _rerank(self, query: str, candidates: List[dict],
                top_n: int = 4) -> List[dict]:
        if not candidates:
            return []
        rr = self._get_reranker()
        if rr is None:
            return candidates[:top_n]
        try:
            scores = rr.predict([(query, c["text"]) for c in candidates])
            ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
            return [c for _, c in ranked[:top_n]]
        except Exception as e:
            logger.warning(f"Reranking failed: {e}")
            return candidates[:top_n]

    def retrieve(self, query: str,
                 doc_ids: Optional[List[str]] = None) -> List[dict]:
        dense  = self._dense_retrieve(query, 20)
        kw     = self._bm25_retrieve(query, 15)
        seen, merged = set(), []
        for c in dense + kw:
            if c["id"] not in seen:
                seen.add(c["id"]); merged.append(c)
        if doc_ids:
            merged = [c for c in merged if c.get("doc_id") in doc_ids]
        return self._rerank(query, merged, top_n=4)

    # ── Intent ────────────────────────────────────────────────────────────────

    def is_extractive(self, query: str) -> bool:
        return any(s in query.lower() for s in UNIVERSAL_EXTRACTIVE_SIGNALS)

    def is_comparative(self, query: str) -> bool:
        signals = ["compare", "versus", "vs", "difference between", "contrast",
                   "across documents", "both documents", "which document"]
        return any(s in query.lower() for s in signals)

    def deterministic_extract(self, query: str,
                               chunks: List[dict]) -> Optional[dict]:
        all_patterns = list(self.sector.patterns) + UNIVERSAL_FACT_PATTERNS
        for chunk in chunks:
            for pattern, label in all_patterns:
                matches = re.findall(pattern, chunk["text"], re.IGNORECASE)
                if matches:
                    return {"answer": str(matches[0]), "pattern_label": label,
                            "source": chunk["source"], "doc_id": chunk.get("doc_id"),
                            "page": chunk["page"], "evidence": chunk["text"][:350],
                            "llm_used": False}
        return None

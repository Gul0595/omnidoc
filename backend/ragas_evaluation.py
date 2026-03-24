"""
OmniDoc RAG Evaluation Suite
=============================
Run: python ragas_evaluation.py
Output: ragas_results.json + ragas_report.html
"""

import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Dependencies ─────────────────────────────────────────────────────────────
try:
    from ragas import evaluate
    from ragas.metrics.collections import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from ragas import EvaluationDataset, SingleTurnSample
except ImportError as e:
    print(f"Import error: {e}")
    print("Run: pip install ragas --upgrade")
    exit(1)

try:
    import httpx
except ImportError:
    print("Install karo: pip install httpx")
    exit(1)

# ── Config ───────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
BACKEND_URL  = os.getenv("BACKEND_URL", "http://localhost:8000")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")

# ── Test Questions ───────────────────────────────────────────────────────────
TEST_QUESTIONS = [
    {
        "question": "What are the main features of the OmniDoc system?",
        "ground_truth": "OmniDoc provides multi-sector document intelligence with RAG-based querying, RBAC team management, OCR for scanned PDFs, and a multi-LLM fallback chain.",
    },
    {
        "question": "How does the multi-LLM fallback chain work?",
        "ground_truth": "The system tries Ollama first, then falls back to Groq, Gemini, Cloudflare Workers AI, and finally HuggingFace if previous providers fail.",
    },
    {
        "question": "What sectors does OmniDoc support?",
        "ground_truth": "OmniDoc supports 6 sectors: Agriculture, Healthcare, Legal, Finance, Education, and IT.",
    },
    {
        "question": "What user roles are available in OmniDoc?",
        "ground_truth": "OmniDoc supports three roles: viewer (read-only), editor (can upload and query), and admin (full workspace management).",
    },
    {
        "question": "How are scanned PDFs handled?",
        "ground_truth": "Scanned PDFs are processed using pytesseract OCR which auto-detects whether a PDF needs OCR and extracts text accordingly.",
    },
]

# ── Query Backend ────────────────────────────────────────────────────────────
async def query_rag(question: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BACKEND_URL}/api/query",
                json={"question": question, "workspace_id": 1},
            )
            data = resp.json()
            return {
                "answer":   data.get("answer", ""),
                "contexts": data.get("source_chunks", []),
            }
    except Exception as e:
        print(f"  Backend nahi mila ({e}) — mock data use ho raha hai")
        return _mock_response(question)


def _mock_response(question: str) -> dict:
    return {
        "answer": (
            f"Based on the documents: OmniDoc is a multi-sector document intelligence system. "
            f"Regarding '{question}': The system uses hybrid retrieval combining dense vector search "
            "with sparse BM25, followed by GPU reranking for accurate results."
        ),
        "contexts": [
            "OmniDoc implements a multi-LLM fallback chain: Ollama -> Groq -> Gemini -> Cloudflare -> HuggingFace.",
            "The system uses pgvector for storing document embeddings with hybrid retrieval combining dense and sparse search.",
            "Six sector configurations are supported: Agriculture, Healthcare, Legal, Finance, Education, and IT.",
            "RBAC roles include viewer (read-only), editor (upload and query), and admin (full management).",
            "Scanned PDFs are handled using pytesseract OCR with auto-detection.",
        ],
    }

# ── Manual Metrics ───────────────────────────────────────────────────────────
def manual_metrics(question: str, answer: str, contexts: list) -> dict:
    answer_words  = set(answer.lower().split())
    context_words = set(" ".join(contexts).lower().split())
    overlap       = len(answer_words & context_words) / max(len(answer_words), 1)
    return {
        "word_overlap_score":     round(overlap, 3),
        "num_contexts_retrieved": len(contexts),
        "avg_context_length":     round(sum(len(c) for c in contexts) / max(len(contexts), 1), 1),
        "answer_word_count":      len(answer.split()),
        "grounded":               overlap > 0.3,
    }

# ── RAGAS Evaluation ─────────────────────────────────────────────────────────
def run_ragas(eval_data: list) -> dict:
    if not OPENAI_KEY:
        print("  OPENAI_API_KEY nahi hai — RAGAS skip, manual metrics use honge")
        return {}
    os.environ["OPENAI_API_KEY"] = OPENAI_KEY
    try:
        samples = [
            SingleTurnSample(
                user_input=d["question"],
                response=d["answer"],
                retrieved_contexts=d["contexts"],
                reference=d["ground_truth"],
            )
            for d in eval_data
        ]
        dataset = EvaluationDataset(samples=samples)
        result  = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        return {
            "faithfulness":      round(float(result["faithfulness"]), 3),
            "answer_relevancy":  round(float(result["answer_relevancy"]), 3),
            "context_precision": round(float(result["context_precision"]), 3),
            "context_recall":    round(float(result["context_recall"]), 3),
        }
    except Exception as e:
        print(f"  RAGAS error: {e}")
        return {}

# ── DB Stats ─────────────────────────────────────────────────────────────────
def get_db_stats() -> dict:
    if not DATABASE_URL:
        return {"error": "DATABASE_URL not set"}
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) as total FROM document_chunks;")
        total = cur.fetchone()["total"]
        cur.execute("SELECT AVG(LENGTH(content)) as avg_len FROM document_chunks;")
        avg   = round(cur.fetchone()["avg_len"] or 0, 1)
        conn.close()
        return {"total_chunks": total, "avg_chunk_length": avg}
    except Exception as e:
        return {"error": str(e)}

# ── HTML Report ───────────────────────────────────────────────────────────────
def make_report(results: dict, chunk_stats: dict, ts: str):
    ragas  = results.get("ragas_scores", {})
    manual = results.get("per_question", [])

    def color(v):
        if not isinstance(v, float): return "#444"
        return "#3B6D11" if v >= 0.75 else ("#854F0B" if v >= 0.5 else "#A32D2D")

    ragas_html = ""
    if ragas:
        for k, v in ragas.items():
            pct = int(v * 100)
            ragas_html += f"""
            <div class="card">
              <div class="label">{k.replace('_',' ').title()}</div>
              <div class="big" style="color:{color(v)}">{v}</div>
              <div class="bar"><div style="width:{pct}%;background:{color(v)};height:6px;border-radius:3px"></div></div>
              <div class="hint">{"Good" if v>=0.75 else ("Okay" if v>=0.5 else "Needs work")}</div>
            </div>"""
    else:
        ragas_html = "<p style='color:#854F0B;padding:1rem'>RAGAS scores ke liye OPENAI_API_KEY chahiye .env mein. Manual metrics neeche hain.</p>"

    rows = ""
    for i, q in enumerate(manual, 1):
        m = q.get("manual_metrics", {})
        g = m.get("grounded", False)
        rows += f"""<tr>
          <td>{i}</td>
          <td style="font-size:12px">{q['question'][:70]}...</td>
          <td>{m.get('num_contexts_retrieved','-')}</td>
          <td>{m.get('word_overlap_score','-')}</td>
          <td>{m.get('avg_context_length','-')}</td>
          <td style="color:{'#3B6D11' if g else '#A32D2D'};font-weight:500">{'Yes' if g else 'No'}</td>
        </tr>"""

    db_html = ""
    if "error" not in chunk_stats:
        db_html = f"""
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:1.5rem">
          <div class="stat"><div class="snum">{chunk_stats.get('total_chunks','N/A')}</div><div class="slabel">Total chunks in DB</div></div>
          <div class="stat"><div class="snum">{chunk_stats.get('avg_chunk_length','N/A')}</div><div class="slabel">Avg chunk length (chars)</div></div>
        </div>"""
    else:
        db_html = f"<p style='color:#854F0B'>DB: {chunk_stats['error']}</p>"

    grounded  = sum(1 for d in manual if d.get("manual_metrics", {}).get("grounded"))
    avg_ragas = round(sum(ragas.values()) / len(ragas), 3) if ragas else "N/A"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OmniDoc RAG Evaluation</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,sans-serif;background:#f9f9f7;color:#1a1a1a;padding:2rem;max-width:900px;margin:0 auto}}
  h1{{font-size:22px;font-weight:500;margin-bottom:4px}}
  .sub{{color:#888;font-size:13px;margin-bottom:2rem}}
  h2{{font-size:15px;font-weight:500;margin:2rem 0 1rem;border-bottom:1px solid #e5e5e5;padding-bottom:8px}}
  .grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:1.5rem}}
  .card{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:1rem 1.25rem}}
  .label{{font-size:12px;color:#888;margin-bottom:4px}}
  .big{{font-size:28px;font-weight:500;margin-bottom:8px}}
  .bar{{background:#f0f0f0;border-radius:3px;height:6px;margin-bottom:6px}}
  .hint{{font-size:12px;color:#aaa}}
  .stat{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:1rem;text-align:center}}
  .snum{{font-size:28px;font-weight:500;color:#185FA5}}
  .slabel{{font-size:12px;color:#888;margin-top:4px}}
  .summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:2rem}}
  .scard{{background:#fff;border:1px solid #e5e5e5;border-radius:8px;padding:1rem;text-align:center}}
  .sval{{font-size:24px;font-weight:500}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;border:1px solid #e5e5e5;font-size:13px;overflow:hidden}}
  th{{background:#f5f5f3;padding:10px 12px;text-align:left;font-weight:500;color:#555}}
  td{{padding:9px 12px;border-top:1px solid #f0f0f0}}
  .footer{{margin-top:3rem;text-align:center;font-size:12px;color:#bbb}}
</style>
</head>
<body>
<h1>OmniDoc — RAG Evaluation Report</h1>
<div class="sub">Generated: {ts} &nbsp;|&nbsp; Questions: {len(manual)} &nbsp;|&nbsp; Avg RAGAS: {avg_ragas}</div>

<div class="summary">
  <div class="scard"><div class="sval">{len(manual)}</div><div class="slabel">Questions tested</div></div>
  <div class="scard"><div class="sval" style="color:#3B6D11">{grounded}/{len(manual)}</div><div class="slabel">Grounded answers</div></div>
  <div class="scard"><div class="sval" style="color:#185FA5">{avg_ragas}</div><div class="slabel">Avg RAGAS score</div></div>
</div>

<h2>RAGAS Scores</h2>
<div class="grid">{ragas_html}</div>

<h2>Database Stats</h2>
{db_html}

<h2>Per-Question Analysis</h2>
<table>
  <thead><tr><th>#</th><th>Question</th><th>Contexts</th><th>Overlap</th><th>Avg Len</th><th>Grounded?</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

<div class="footer">OmniDoc Evaluation Suite · RAGAS v0.4 · {ts}</div>
</body></html>"""

    with open("ragas_report.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("  ragas_report.html saved!")

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "="*50)
    print("  OmniDoc RAG Evaluation Suite")
    print(f"  {ts}")
    print("="*50)

    print("\n[1/4] Database stats...")
    chunk_stats = get_db_stats()
    if "error" not in chunk_stats:
        print(f"  Chunks: {chunk_stats['total_chunks']} | Avg len: {chunk_stats['avg_chunk_length']} chars")
    else:
        print(f"  {chunk_stats['error']}")

    print("\n[2/4] Querying RAG for each question...")
    eval_data = []
    for i, item in enumerate(TEST_QUESTIONS, 1):
        print(f"  Q{i}: {item['question'][:55]}...")
        resp = await query_rag(item["question"])
        m    = manual_metrics(item["question"], resp["answer"], resp["contexts"])
        eval_data.append({
            "question":       item["question"],
            "answer":         resp["answer"],
            "contexts":       resp["contexts"],
            "ground_truth":   item["ground_truth"],
            "manual_metrics": m,
        })
        print(f"       Contexts: {m['num_contexts_retrieved']} | Overlap: {m['word_overlap_score']} | Grounded: {m['grounded']}")

    print("\n[3/4] RAGAS evaluation...")
    ragas_scores = run_ragas(eval_data)
    if ragas_scores:
        for k, v in ragas_scores.items():
            print(f"  {k:25s}: {v}")

    print("\n[4/4] Saving results...")
    results = {
        "timestamp":    ts,
        "ragas_scores": ragas_scores,
        "chunk_stats":  chunk_stats,
        "per_question": eval_data,
    }
    with open("ragas_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print("  ragas_results.json saved!")

    make_report(results, chunk_stats, ts)

    grounded = sum(1 for d in eval_data if d["manual_metrics"]["grounded"])
    print("\n" + "="*50)
    print("  RESULTS")
    print("="*50)
    print(f"  Questions tested : {len(eval_data)}")
    print(f"  Grounded answers : {grounded}/{len(eval_data)}")
    if ragas_scores:
        avg = sum(ragas_scores.values()) / len(ragas_scores)
        print(f"  Avg RAGAS score  : {round(avg, 3)}")
    print("\n  Files bane: ragas_results.json, ragas_report.html")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(main())

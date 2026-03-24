"""
agents/coordinator.py — LangGraph multi-agent coordinator
"""

import json
from typing import AsyncIterator, TypedDict, List
from langgraph.graph import StateGraph, END
from core.llm_chain import get_llm_chain
from core.rag_engine import RAGEngine
from sectors import get_sector


class State(TypedDict):
    question:     str
    workspace_id: str
    sector_id:    str
    doc_ids:      List[str]
    user_id:      str
    intent:       str
    chunks:       List[dict]
    result:       dict
    final_answer: str
    llm_used:     bool
    llm_provider: str


def _classify(state: State) -> State:
    from api.database import SessionLocal
    db     = SessionLocal()
    engine = RAGEngine(state["workspace_id"], state["sector_id"], db=db)
    db.close()

    if engine.is_comparative(state["question"]):
        intent = "comparative"
    elif engine.is_extractive(state["question"]):
        intent = "extractive"
    else:
        intent = "descriptive"

    return {**state, "intent": intent}


def _retrieve(state: State) -> State:
    from api.database import SessionLocal
    db     = SessionLocal()
    engine = RAGEngine(state["workspace_id"], state["sector_id"], db=db)

    chunks = engine.retrieve(
        state["question"],
        doc_ids=state.get("doc_ids") or None
    )

    db.close()
    return {**state, "chunks": chunks}


def _route(state: State) -> str:
    return state["intent"]


async def _extract(state: State) -> State:
    from api.database import SessionLocal
    db     = SessionLocal()
    engine = RAGEngine(state["workspace_id"], state["sector_id"], db=db)

    hit = engine.deterministic_extract(state["question"], state["chunks"])
    db.close()

    if hit:
        return {
            **state,
            "result": {
                "answer": hit["answer"],
                "llm_used": False,
                "llm_provider": "none",
                "sources": [
                    {
                        "source": hit["source"],
                        "page": hit["page"],
                        "evidence": hit["evidence"],
                    }
                ],
            },
        }

    return {**state, "intent": "descriptive"}


async def _describe(state: State) -> State:
    sector = get_sector(state["sector_id"])
    chunks = state["chunks"]

    if not chunks:
        return {
            **state,
            "result": {
                "answer": "This information is not found in the uploaded documents.",
                "llm_used": True,
                "llm_provider": "none",
                "sources": [],
            },
        }

    context = "\n\n".join(
        f"[{c['source']}, Page {c['page']}]\n{c['text']}" for c in chunks
    )

    prompt = f"""
{sector.persona}

Answer ONLY from context.

Context:
{context}

Question: {state["question"]}
"""

    resp = await get_llm_chain().invoke(prompt)

    return {
        **state,
        "result": {
            "answer": resp.content,
            "llm_used": True,
            "llm_provider": resp.provider.value,
            "sources": [
                {"source": c["source"], "page": c["page"]}
                for c in chunks
            ],
        },
    }


async def _compare(state: State) -> State:
    sector = get_sector(state["sector_id"])
    chunks = state["chunks"]

    if not chunks:
        return {
            **state,
            "result": {
                "answer": "No documents found to compare.",
                "llm_used": True,
                "llm_provider": "none",
                "sources": [],
            },
        }

    context = "\n".join(c["text"] for c in chunks[:5])

    prompt = f"""
Compare documents:

{context}

Question: {state["question"]}
"""

    resp = await get_llm_chain().invoke(prompt)

    return {
        **state,
        "result": {
            "answer": resp.content,
            "llm_used": True,
            "llm_provider": resp.provider.value,
            "sources": [
                {"source": c["source"], "page": c["page"]}
                for c in chunks
            ],
        },
    }


# ✅ 🔥 FINAL FIXED SYNTHESIZE (WITH FALLBACK)
def _synthesize(state: State) -> State:
    from groq import Groq
    import os

    r       = state["result"]
    answer  = r.get("answer", "")
    sources = r.get("sources", [])

    # 🚨 fallback trigger
    if (
    not answer
    or "not found" in (answer or "").lower()
    or "no mention" in (answer or "").lower()
    or "not mentioned" in (answer or "").lower()
    ):
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))

            fallback = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "Answer using general knowledge if not found in documents."
                    },
                    {
                        "role": "user",
                        "content": state["question"]
                    }
                ]
            )

            answer = fallback.choices[0].message.content

        except Exception as e:
            answer = f"Fallback failed: {str(e)}"

    if sources:
        cites = "\n".join(
            f"[{i+1}] {s['source']} — Page {s['page']}"
            for i, s in enumerate(sources)
        )
        final = f"{answer}\n\nSources:\n{cites}"
    else:
        final = answer

    return {
        **state,
        "final_answer": final,
        "llm_used": True,
        "llm_provider": state.get("llm_provider", "fallback"),
    }


# GRAPH
graph = StateGraph(State)
graph.add_node("classify", _classify)
graph.add_node("retrieve", _retrieve)
graph.add_node("extractive", _extract)
graph.add_node("descriptive", _describe)
graph.add_node("comparative", _compare)
graph.add_node("synthesize", _synthesize)

graph.set_entry_point("classify")

graph.add_edge("classify", "retrieve")

graph.add_conditional_edges("retrieve", _route, {
    "extractive": "extractive",
    "descriptive": "descriptive",
    "comparative": "comparative",
})

graph.add_edge("extractive", "synthesize")
graph.add_edge("descriptive", "synthesize")
graph.add_edge("comparative", "synthesize")
graph.add_edge("synthesize", END)

compiled = graph.compile()


# STREAMING RESPONSE
async def run_query(
    question: str,
    workspace_id: str,
    sector_id: str,
    doc_ids: List[str],
    user_id: str
) -> AsyncIterator[dict]:

    init = State(
        question=question,
        workspace_id=workspace_id,
        sector_id=sector_id,
        doc_ids=doc_ids,
        user_id=user_id,
        intent="",
        chunks=[],
        result={},
        final_answer="",
        llm_used=False,
        llm_provider=""
    )

    async for step in compiled.astream(init):
        node = list(step.keys())[0]
        state = step[node]

        if node == "classify":
            yield {"type": "intent", "intent": state.get("intent", "")}
            yield {"type": "agent_step", "agent": "classifier",
                   "detail": f"Intent: {state.get('intent', '')}"}

        elif node == "retrieve":
            yield {"type": "agent_step", "agent": "retriever",
                   "detail": f"Retrieved {len(state.get('chunks', []))} chunks"}

        elif node in ("extractive", "descriptive", "comparative"):
            yield {"type": "agent_step", "agent": node,
                   "detail": f"Running {node} agent..."}

        elif node == "synthesize":
            prov = state.get("llm_provider", "")
            yield {
                "type": "agent_step",
                "agent": "synthesizer",
                "detail": f"Composing via {prov or 'fallback'}..."
            }

            for char in state.get("final_answer", ""):
                yield {"type": "token", "content": char}

    yield {
        "type": "done",
        "llm_used": init.get("llm_used", False),
        "llm_provider": init.get("llm_provider", "")
    }
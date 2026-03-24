import time, json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from api.database import get_db, QueryLog, Workspace
from api.auth_utils import get_current_user, require_workspace_access
from api.audit import log_activity
from agents.coordinator import run_query

router = APIRouter()


class QueryReq(BaseModel):
    question:     str
    workspace_id: str
    doc_ids:      Optional[List[str]] = None


class FeedbackReq(BaseModel):
    query_id: str
    rating:   int


@router.post("/ask")
async def ask(req: QueryReq, request: Request,
              db: Session = Depends(get_db),
              cu=Depends(get_current_user)):
    ws    = require_workspace_access(req.workspace_id, cu, db, "viewer")
    start = time.time()

    async def stream():
        agents, answer, intent, provider = [], "", "", ""
        async for chunk in run_query(
            question=req.question, workspace_id=req.workspace_id,
            sector_id=ws.sector_id, doc_ids=req.doc_ids or [],
            user_id=cu.id,
        ):
            t = chunk.get("type")
            if t == "intent":     intent = chunk.get("intent", "")
            if t == "agent_step": agents.append(chunk.get("agent", ""))
            if t == "token":      answer += chunk.get("content", "")
            if t == "done":
                provider = chunk.get("llm_provider", "")
                latency  = (time.time() - start) * 1000
                log = QueryLog(
                    user_id=cu.id, workspace_id=req.workspace_id,
                    sector_id=ws.sector_id, question=req.question,
                    answer=answer, intent=intent,
                    agents_used=",".join(agents),
                    llm_provider=provider, latency_ms=latency,
                    llm_used=chunk.get("llm_used", True),
                )
                db.add(log)
                log_activity(db, cu.id, "query", "workspace", req.workspace_id,
                             detail={"intent": intent, "provider": provider},
                             ip_address=request.client.host)
                db.commit()
                chunk["query_id"] = log.id
            yield f"data: {json.dumps(chunk)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/feedback")
def feedback(req: FeedbackReq, db: Session = Depends(get_db),
             cu=Depends(get_current_user)):
    log = db.query(QueryLog).filter(QueryLog.id == req.query_id).first()
    if log:
        log.feedback = max(1, min(5, req.rating)); db.commit()
    return {"message": "Feedback recorded. Thank you!"}


@router.get("/history/{workspace_id}")
def history(workspace_id: str, db: Session = Depends(get_db),
            cu=Depends(get_current_user)):
    require_workspace_access(workspace_id, cu, db, "viewer")
    logs = (db.query(QueryLog)
              .filter(QueryLog.workspace_id == workspace_id)
              .order_by(QueryLog.created_at.desc()).limit(30).all())
    return [{
        "id": l.id, "question": l.question, "answer": l.answer,
        "intent": l.intent, "sector_id": l.sector_id,
        "llm_provider": l.llm_provider,
        "latency_ms": round(l.latency_ms or 0, 1),
        "llm_used": l.llm_used, "feedback": l.feedback,
        "created_at": l.created_at.isoformat(),
    } for l in logs]

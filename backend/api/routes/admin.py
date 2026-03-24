from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from api.database import get_db, ActivityLog, QueryLog, User, Workspace
from api.auth_utils import get_current_user
from core.llm_chain import get_llm_chain

router = APIRouter()


@router.get("/llm-status")
def llm_status(cu=Depends(get_current_user)):
    return get_llm_chain().status()


@router.get("/audit")
def audit_log(limit: int = 50, db: Session = Depends(get_db),
              cu=Depends(get_current_user)):
    logs = (db.query(ActivityLog)
              .filter(ActivityLog.user_id == cu.id)
              .order_by(ActivityLog.created_at.desc())
              .limit(limit).all())
    return [{"id": l.id, "action": l.action,
             "resource_type": l.resource_type,
             "resource_id": l.resource_id,
             "detail": l.detail,
             "ip_address": l.ip_address,
             "created_at": l.created_at.isoformat()} for l in logs]


@router.get("/stats")
def stats(db: Session = Depends(get_db), cu=Depends(get_current_user)):
    return {
        "total_users":      db.query(User).count(),
        "total_workspaces": db.query(Workspace).filter(Workspace.owner_id == cu.id).count(),
        "total_queries":    db.query(QueryLog).filter(QueryLog.user_id == cu.id).count(),
        "llm_chain":        get_llm_chain().status(),
    }

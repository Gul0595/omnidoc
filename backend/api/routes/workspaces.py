from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from api.database import get_db, Workspace, Document, WorkspaceMember
from api.auth_utils import get_current_user, require_workspace_access
from api.audit import log_activity
from sectors import get_sector

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name:        str
    description: Optional[str] = ""
    sector_id:   str = "it"
    is_public:   bool = False


@router.get("")
def list_workspaces(db: Session = Depends(get_db),
                    cu=Depends(get_current_user)):
    owned     = db.query(Workspace).filter(Workspace.owner_id == cu.id).all()
    member_ids = [m.workspace_id for m in
                  db.query(WorkspaceMember).filter(WorkspaceMember.user_id == cu.id).all()]
    shared    = db.query(Workspace).filter(Workspace.id.in_(member_ids)).all()
    result    = []
    for ws in {ws.id: ws for ws in owned + shared}.values():
        s  = get_sector(ws.sector_id)
        dc = db.query(Document).filter(Document.workspace_id == ws.id).count()
        result.append({
            "id": ws.id, "name": ws.name, "description": ws.description,
            "sector_id": ws.sector_id, "sector_label": s.label,
            "sector_accent": s.accent, "is_public": ws.is_public,
            "document_count": dc,
        })
    return result


@router.post("")
def create_workspace(req: WorkspaceCreate, request: Request,
                     db: Session = Depends(get_db),
                     cu=Depends(get_current_user)):
    ws = Workspace(owner_id=cu.id, name=req.name,
                   description=req.description, sector_id=req.sector_id,
                   is_public=req.is_public)
    db.add(ws); db.flush()
    log_activity(db, cu.id, "create_workspace", "workspace", ws.id,
                 detail={"name": req.name, "sector": req.sector_id},
                 workspace_id=ws.id, ip_address=request.client.host)
    db.commit(); db.refresh(ws)
    s = get_sector(ws.sector_id)
    return {"id": ws.id, "name": ws.name, "description": ws.description,
            "sector_id": ws.sector_id, "sector_label": s.label,
            "sector_accent": s.accent, "is_public": ws.is_public,
            "document_count": 0}


@router.get("/{workspace_id}/stats")
def workspace_stats(workspace_id: str, db: Session = Depends(get_db),
                    cu=Depends(get_current_user)):
    ws   = require_workspace_access(workspace_id, cu, db, "viewer")
    docs = db.query(Document).filter(Document.workspace_id == workspace_id).all()
    from api.database import QueryLog
    qc   = db.query(QueryLog).filter(QueryLog.workspace_id == workspace_id).count()
    s    = get_sector(ws.sector_id)
    return {
        "workspace_id": workspace_id, "name": ws.name,
        "sector_id": ws.sector_id, "sector_label": s.label,
        "sector_accent": s.accent,
        "documents": len(docs),
        "total_pages": sum(d.page_count or 0 for d in docs),
        "total_chunks": sum(d.chunk_count or 0 for d in docs),
        "scanned_docs": sum(1 for d in docs if d.has_scanned),
        "table_docs": sum(1 for d in docs if d.has_tables),
        "queries_run": qc,
    }


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: str, request: Request,
                     db: Session = Depends(get_db),
                     cu=Depends(get_current_user)):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id,
                                     Workspace.owner_id == cu.id).first()
    if not ws:
        raise HTTPException(404, "Workspace not found or you are not the owner")
    log_activity(db, cu.id, "delete_workspace", "workspace", workspace_id,
                 ip_address=request.client.host)
    db.delete(ws); db.commit()
    return {"message": "Workspace deleted"}

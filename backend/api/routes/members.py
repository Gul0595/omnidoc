from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from api.database import get_db, WorkspaceMember, User
from api.auth_utils import get_current_user, require_workspace_access
from api.audit import log_activity

router = APIRouter()


class InviteReq(BaseModel):
    email: EmailStr
    role:  str = "viewer"


@router.get("/{workspace_id}/members")
def list_members(workspace_id: str, db: Session = Depends(get_db),
                 cu=Depends(get_current_user)):
    require_workspace_access(workspace_id, cu, db, "viewer")
    members = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id).all()
    result = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        if u:
            result.append({"user_id": u.id, "email": u.email,
                           "full_name": u.full_name or "",
                           "role": m.role,
                           "joined_at": m.joined_at.isoformat()})
    return result


@router.post("/{workspace_id}/members")
def invite_member(workspace_id: str, req: InviteReq, request: Request,
                  db: Session = Depends(get_db),
                  cu=Depends(get_current_user)):
    require_workspace_access(workspace_id, cu, db, "admin")
    if req.role not in ("viewer", "editor", "admin"):
        raise HTTPException(400, "Role must be viewer, editor, or admin")
    invited = db.query(User).filter(User.email == req.email).first()
    if not invited:
        raise HTTPException(404, "User not found — they must register first")
    existing = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == invited.id).first()
    if existing:
        raise HTTPException(409, "User is already a member")
    m = WorkspaceMember(workspace_id=workspace_id, user_id=invited.id,
                        role=req.role, invited_by=cu.id)
    db.add(m)
    log_activity(db, cu.id, "invite_member", "user", invited.id,
                 detail={"email": req.email, "role": req.role},
                 workspace_id=workspace_id, ip_address=request.client.host)
    db.commit()
    return {"message": f"{req.email} added as {req.role}"}


@router.patch("/{workspace_id}/members/{user_id}")
def change_role(workspace_id: str, user_id: str, body: dict,
                request: Request, db: Session = Depends(get_db),
                cu=Depends(get_current_user)):
    require_workspace_access(workspace_id, cu, db, "admin")
    new_role = body.get("role")
    if new_role not in ("viewer", "editor", "admin"):
        raise HTTPException(400, "Invalid role")
    m = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id).first()
    if not m:
        raise HTTPException(404, "Member not found")
    m.role = new_role
    log_activity(db, cu.id, "change_role", "user", user_id,
                 detail={"new_role": new_role}, workspace_id=workspace_id,
                 ip_address=request.client.host)
    db.commit()
    return {"message": f"Role updated to {new_role}"}


@router.delete("/{workspace_id}/members/{user_id}")
def remove_member(workspace_id: str, user_id: str, request: Request,
                  db: Session = Depends(get_db),
                  cu=Depends(get_current_user)):
    require_workspace_access(workspace_id, cu, db, "admin")
    m = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id).first()
    if not m:
        raise HTTPException(404, "Member not found")
    db.delete(m)
    log_activity(db, cu.id, "remove_member", "user", user_id,
                 workspace_id=workspace_id, ip_address=request.client.host)
    db.commit()
    return {"message": "Member removed"}

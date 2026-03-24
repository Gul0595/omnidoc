import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request
from sqlalchemy.orm import Session
from api.database import get_db, Document, Workspace
from api.auth_utils import get_current_user, require_workspace_access
from api.audit import log_activity

router   = APIRouter()
MAX_SIZE = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024


def _ingest(workspace_id: str, sector_id: str, doc_id: str,
            file_bytes: bytes, filename: str, user_id: str):
    from core.rag_engine import RAGEngine
    from api.database import SessionLocal, Document as Doc, User
    db  = SessionLocal()
    try:
        engine = RAGEngine(workspace_id, sector_id, db=db)
        cc, pc, has_scanned, has_tables = engine.ingest_bytes(
            file_bytes, filename, doc_id)
        doc = db.query(Doc).filter(Doc.id == doc_id).first()
        if doc:
            doc.chunk_count = cc; doc.page_count = pc
            doc.has_scanned = has_scanned; doc.has_tables = has_tables
            doc.indexed = True; db.commit()
        # Email notification
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.email:
            try:
                from tools.notifications import send_upload_complete
                ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
                send_upload_complete(user.email, user.full_name or "User",
                                     filename, ws.name if ws else workspace_id, cc, pc)
            except Exception:
                pass
    finally:
        db.close()


@router.post("/{workspace_id}/upload")
async def upload(workspace_id: str, request: Request,
                 bg: BackgroundTasks,
                 file: UploadFile = File(...),
                 db: Session = Depends(get_db),
                 cu=Depends(get_current_user)):
    ws   = require_workspace_access(workspace_id, cu, db, "editor")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, f"File exceeds {MAX_SIZE // (1024*1024)}MB limit")
    doc = Document(workspace_id=workspace_id, filename=file.filename,
                   file_size_kb=round(len(data) / 1024, 1),
                   uploaded_by=cu.id)
    db.add(doc); db.flush()
    # Optional R2 storage
    try:
        from tools.storage import upload_bytes
        upload_bytes(data, f"{workspace_id}/{doc.id}/{file.filename}")
        doc.storage_key = f"{workspace_id}/{doc.id}/{file.filename}"
    except Exception:
        pass
    log_activity(db, cu.id, "upload_document", "document", doc.id,
                 detail={"filename": file.filename, "size_kb": doc.file_size_kb},
                 workspace_id=workspace_id, ip_address=request.client.host)
    db.commit(); db.refresh(doc)
    bg.add_task(_ingest, workspace_id, ws.sector_id,
                doc.id, data, file.filename, cu.id)
    return {"id": doc.id, "filename": doc.filename,
            "file_size_kb": doc.file_size_kb,
            "page_count": 0, "chunk_count": 0,
            "has_tables": False, "has_scanned": False, "indexed": False}


@router.get("/{workspace_id}")
def list_docs(workspace_id: str, db: Session = Depends(get_db),
              cu=Depends(get_current_user)):
    require_workspace_access(workspace_id, cu, db, "viewer")
    docs = db.query(Document).filter(Document.workspace_id == workspace_id).all()
    return [{"id": d.id, "filename": d.filename,
             "file_size_kb": d.file_size_kb or 0,
             "page_count": d.page_count or 0,
             "chunk_count": d.chunk_count or 0,
             "has_tables": d.has_tables or False,
             "has_scanned": d.has_scanned or False,
             "indexed": d.indexed or False} for d in docs]


@router.delete("/{workspace_id}/{doc_id}")
def delete_doc(workspace_id: str, doc_id: str, request: Request,
               db: Session = Depends(get_db),
               cu=Depends(get_current_user)):
    ws  = require_workspace_access(workspace_id, cu, db, "editor")
    doc = db.query(Document).filter(Document.id == doc_id,
                                     Document.workspace_id == workspace_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    from core.rag_engine import RAGEngine
    RAGEngine(workspace_id, ws.sector_id, db=db).delete_doc_chunks(doc_id)
    log_activity(db, cu.id, "delete_document", "document", doc_id,
                 detail={"filename": doc.filename}, workspace_id=workspace_id,
                 ip_address=request.client.host)
    db.delete(doc); db.commit()
    return {"message": "Document and all its vectors permanently deleted"}

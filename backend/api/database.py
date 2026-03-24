"""
api/database.py — All database models

VectorChunk table uses pgvector for similarity search.
This replaces FAISS — vectors stored in PostgreSQL permanently.
"""
import os, uuid
from datetime import datetime
from sqlalchemy import (create_engine, Column, String, Float, Integer,
                        DateTime, Text, ForeignKey, Boolean, Index)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# ── CREDENTIAL: Set DATABASE_URL in .env ────────────────────────────────────
# Neon.tech free PostgreSQL: https://neon.tech
# Format: postgresql://user:password@host/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./omnidoc.db")

engine       = create_engine(DATABASE_URL, pool_pre_ping=True,
                              pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base         = declarative_base()
EMBED_DIM    = int(os.getenv("EMBED_DIM", "384"))

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR = True
except ImportError:
    from sqlalchemy import JSON
    Vector   = None
    PGVECTOR = False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"
    id              = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email           = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name       = Column(String)
    organisation    = Column(String)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    workspaces      = relationship("Workspace", back_populates="owner",
                                   foreign_keys="Workspace.owner_id")
    memberships     = relationship("WorkspaceMember", back_populates="user",
                                   foreign_keys="WorkspaceMember.user_id")
    queries         = relationship("QueryLog", back_populates="user",
                                   foreign_keys="QueryLog.user_id")
    activity_logs   = relationship("ActivityLog", back_populates="user")


class Workspace(Base):
    __tablename__ = "workspaces"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id     = Column(String, ForeignKey("users.id"), nullable=False)
    name         = Column(String, nullable=False)
    description  = Column(Text)
    sector_id    = Column(String, nullable=False, default="it")
    is_public    = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow)
    owner        = relationship("User", back_populates="workspaces",
                                foreign_keys=[owner_id])
    documents    = relationship("Document",        back_populates="workspace",
                                cascade="all, delete-orphan")
    members      = relationship("WorkspaceMember", back_populates="workspace",
                                cascade="all, delete-orphan")
    queries      = relationship("QueryLog",        back_populates="workspace")
    chunks       = relationship("VectorChunk",     back_populates="workspace",
                                cascade="all, delete-orphan")


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    user_id      = Column(String, ForeignKey("users.id"),      nullable=False)
    role         = Column(String, default="viewer")  # viewer | editor | admin
    invited_by   = Column(String, ForeignKey("users.id"))
    joined_at    = Column(DateTime, default=datetime.utcnow)
    workspace    = relationship("Workspace",          back_populates="members")
    user         = relationship("User",               back_populates="memberships",
                                foreign_keys=[user_id])


class Document(Base):
    __tablename__ = "documents"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    filename     = Column(String, nullable=False)
    file_size_kb = Column(Float)
    page_count   = Column(Integer)
    storage_key  = Column(String)
    chunk_count  = Column(Integer, default=0)
    has_tables   = Column(Boolean, default=False)
    has_scanned  = Column(Boolean, default=False)
    indexed      = Column(Boolean, default=False)
    uploaded_by  = Column(String, ForeignKey("users.id"))
    uploaded_at  = Column(DateTime, default=datetime.utcnow)
    workspace    = relationship("Workspace", back_populates="documents")
    chunks       = relationship("VectorChunk", back_populates="document",
                                cascade="all, delete-orphan")


class VectorChunk(Base):
    """One text chunk + its embedding vector. Stored in PostgreSQL via pgvector."""
    __tablename__ = "vector_chunks"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id       = Column(String, ForeignKey("documents.id"),  nullable=False)
    workspace_id = Column(String, ForeignKey("workspaces.id"), nullable=False)
    sector_id    = Column(String)
    source       = Column(String)
    page         = Column(Integer)
    chunk_type   = Column(String, default="text")
    text         = Column(Text, nullable=False)
    embedding    = Column(Vector(EMBED_DIM) if (PGVECTOR and Vector) else JSON)
    created_at   = Column(DateTime, default=datetime.utcnow)
    document     = relationship("Document",  back_populates="chunks")
    workspace    = relationship("Workspace", back_populates="chunks")
    __table_args__ = (
        Index("ix_vc_workspace", "workspace_id"),
        Index("ix_vc_doc",       "doc_id"),
    )


class QueryLog(Base):
    __tablename__ = "query_logs"
    id           = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(String, ForeignKey("users.id"),       nullable=True)
    workspace_id = Column(String, ForeignKey("workspaces.id"),  nullable=False)
    sector_id    = Column(String)
    question     = Column(Text, nullable=False)
    answer       = Column(Text)
    intent       = Column(String)
    agents_used  = Column(String)
    llm_provider = Column(String)
    latency_ms   = Column(Float)
    llm_used     = Column(Boolean)
    feedback     = Column(Integer)
    created_at   = Column(DateTime, default=datetime.utcnow)
    user         = relationship("User",      back_populates="queries",
                                foreign_keys=[user_id])
    workspace    = relationship("Workspace", back_populates="queries")


class ActivityLog(Base):
    """Full audit trail for compliance (healthcare, military, legal)."""
    __tablename__ = "activity_logs"
    id            = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id       = Column(String, ForeignKey("users.id"), nullable=False)
    workspace_id  = Column(String)
    action        = Column(String, nullable=False)
    resource_type = Column(String)
    resource_id   = Column(String)
    detail        = Column(Text)
    ip_address    = Column(String)
    created_at    = Column(DateTime, default=datetime.utcnow)
    user          = relationship("User", back_populates="activity_logs")
    __table_args__ = (
        Index("ix_al_user",      "user_id"),
        Index("ix_al_workspace", "workspace_id"),
        Index("ix_al_created",   "created_at"),
    )

"""Initial schema with pgvector

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa

revision      = "0001_initial"
down_revision = None
branch_labels = None
depends_on    = None
EMBED_DIM     = 384


def upgrade():
    # Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("users",
        sa.Column("id",              sa.String, primary_key=True),
        sa.Column("email",           sa.String, nullable=False, unique=True),
        sa.Column("hashed_password", sa.String, nullable=False),
        sa.Column("full_name",       sa.String),
        sa.Column("organisation",    sa.String),
        sa.Column("is_active",       sa.Boolean, server_default="true"),
        sa.Column("created_at",      sa.DateTime),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table("workspaces",
        sa.Column("id",          sa.String,  primary_key=True),
        sa.Column("owner_id",    sa.String,  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name",        sa.String,  nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("sector_id",   sa.String,  nullable=False, server_default="it"),
        sa.Column("is_public",   sa.Boolean, server_default="false"),
        sa.Column("created_at",  sa.DateTime),
    )

    op.create_table("workspace_members",
        sa.Column("id",           sa.String, primary_key=True),
        sa.Column("workspace_id", sa.String, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id",      sa.String, sa.ForeignKey("users.id"),      nullable=False),
        sa.Column("role",         sa.String, server_default="viewer"),
        sa.Column("invited_by",   sa.String, sa.ForeignKey("users.id")),
        sa.Column("joined_at",    sa.DateTime),
    )

    op.create_table("documents",
        sa.Column("id",           sa.String,  primary_key=True),
        sa.Column("workspace_id", sa.String,  sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("filename",     sa.String,  nullable=False),
        sa.Column("file_size_kb", sa.Float),
        sa.Column("page_count",   sa.Integer),
        sa.Column("storage_key",  sa.String),
        sa.Column("chunk_count",  sa.Integer, server_default="0"),
        sa.Column("has_tables",   sa.Boolean, server_default="false"),
        sa.Column("has_scanned",  sa.Boolean, server_default="false"),
        sa.Column("indexed",      sa.Boolean, server_default="false"),
        sa.Column("uploaded_by",  sa.String,  sa.ForeignKey("users.id")),
        sa.Column("uploaded_at",  sa.DateTime),
    )

    # Vector chunks — pgvector column for similarity search
    op.execute(f"""
        CREATE TABLE vector_chunks (
            id           TEXT PRIMARY KEY,
            doc_id       TEXT REFERENCES documents(id) ON DELETE CASCADE,
            workspace_id TEXT REFERENCES workspaces(id) ON DELETE CASCADE,
            sector_id    TEXT,
            source       TEXT,
            page         INTEGER,
            chunk_type   TEXT DEFAULT 'text',
            text         TEXT NOT NULL,
            embedding    vector({EMBED_DIM}),
            created_at   TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX ix_vc_workspace ON vector_chunks(workspace_id)")
    op.execute("CREATE INDEX ix_vc_doc ON vector_chunks(doc_id)")
    # IVFFlat index for fast ANN search (populate data first, then this index is used)
    op.execute(f"""
        CREATE INDEX ix_vc_embedding ON vector_chunks
        USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
    """)

    op.create_table("query_logs",
        sa.Column("id",           sa.String,  primary_key=True),
        sa.Column("user_id",      sa.String,  sa.ForeignKey("users.id")),
        sa.Column("workspace_id", sa.String,  sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("sector_id",    sa.String),
        sa.Column("question",     sa.Text,    nullable=False),
        sa.Column("answer",       sa.Text),
        sa.Column("intent",       sa.String),
        sa.Column("agents_used",  sa.String),
        sa.Column("llm_provider", sa.String),
        sa.Column("latency_ms",   sa.Float),
        sa.Column("llm_used",     sa.Boolean),
        sa.Column("feedback",     sa.Integer),
        sa.Column("created_at",   sa.DateTime),
    )

    op.create_table("activity_logs",
        sa.Column("id",            sa.String, primary_key=True),
        sa.Column("user_id",       sa.String, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id",  sa.String),
        sa.Column("action",        sa.String, nullable=False),
        sa.Column("resource_type", sa.String),
        sa.Column("resource_id",   sa.String),
        sa.Column("detail",        sa.Text),
        sa.Column("ip_address",    sa.String),
        sa.Column("created_at",    sa.DateTime),
    )
    op.create_index("ix_al_user",      "activity_logs", ["user_id"])
    op.create_index("ix_al_workspace", "activity_logs", ["workspace_id"])
    op.create_index("ix_al_created",   "activity_logs", ["created_at"])


def downgrade():
    for t in ["activity_logs", "query_logs", "vector_chunks",
              "documents", "workspace_members", "workspaces", "users"]:
        op.drop_table(t)

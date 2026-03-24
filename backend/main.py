"""
OmniDoc — Production FastAPI Backend
Multi-sector document intelligence with multi-LLM fallback chain.
"""
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB tables
    from api.database import engine, Base
    Base.metadata.create_all(bind=engine)
    # Init + log LLM chain
    from core.llm_chain import get_llm_chain
    try:
        chain = get_llm_chain()
        print(f"✓ LLM chain ready: {chain.status()}")
    except Exception as e:
        print(f"✗ LLM chain error: {e}")
        print("  → Set at least one LLM key in .env (GROQ_API_KEY recommended)")
    # Optional: Phoenix tracing
    try:
        import phoenix as px
        session = px.launch_app()
        print(f"✓ Phoenix tracing: {session.url}")
    except Exception:
        print("  Phoenix not available — pip install arize-phoenix to enable")
    yield


app = FastAPI(
    title="OmniDoc API",
    description="Multi-sector document intelligence — Agriculture, Healthcare, Education, Military, Household, IT",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:3000"),
        "https://*.vercel.app",   # Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.middleware import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Prometheus metrics
app.mount("/metrics", make_asgi_app())

# Routes
from api.routes import health, auth, sectors, workspaces, members, documents, query, admin

app.include_router(health.router,      prefix="/api/v1",                    tags=["health"])
app.include_router(auth.router,        prefix="/api/v1/auth",               tags=["auth"])
app.include_router(sectors.router,     prefix="/api/v1/sectors",            tags=["sectors"])
app.include_router(workspaces.router,  prefix="/api/v1/workspaces",         tags=["workspaces"])
app.include_router(members.router,     prefix="/api/v1/workspaces",         tags=["members"])
app.include_router(documents.router,   prefix="/api/v1/documents",          tags=["documents"])
app.include_router(query.router,       prefix="/api/v1/query",              tags=["query"])
app.include_router(admin.router,       prefix="/api/v1/admin",              tags=["admin"])

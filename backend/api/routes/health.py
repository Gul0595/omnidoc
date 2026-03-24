from fastapi import APIRouter
from datetime import datetime
from core.llm_chain import get_llm_chain

router = APIRouter()


@router.get("/health")
def health():
    try:
        chain = get_llm_chain().status()
    except Exception as e:
        chain = {"error": str(e)}
    return {
        "status": "ok", "service": "OmniDoc", "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "llm_chain": chain,
    }

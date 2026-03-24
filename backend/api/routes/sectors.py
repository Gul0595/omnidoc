from fastapi import APIRouter
from sectors import list_sectors, get_sector

router = APIRouter()


@router.get("")
def all_sectors():
    return list_sectors()


@router.get("/{sector_id}")
def sector_detail(sector_id: str):
    s = get_sector(sector_id)
    return {"id": s.id, "label": s.label, "accent": s.accent,
            "terminology": s.terminology, "suggestions": s.suggestions}

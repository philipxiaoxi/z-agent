from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/status")
def auth_status():
    return {"auth_required": bool(settings.AUTH_TOKEN)}

from fastapi import APIRouter

from app.api.routes.files import router as files_router
from app.api.routes.pools import router as pools_router
from app.api.routes.system import router as system_router

api_router = APIRouter()

api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(pools_router, prefix="/pools", tags=["pools"])
api_router.include_router(system_router, prefix="/system", tags=["system"])

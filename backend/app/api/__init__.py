from fastapi import APIRouter

from app.api.routes.agent import router as agent_router
from app.api.routes.files import router as files_router
from app.api.routes.pools import router as pools_router
from app.api.routes.sessions import router as sessions_router
from app.api.routes.system import router as system_router
from app.api.routes.auth import router as auth_router

api_router = APIRouter()

api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(files_router, prefix="/files", tags=["files"])
api_router.include_router(pools_router, prefix="/pools", tags=["pools"])
api_router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
api_router.include_router(system_router, prefix="/system", tags=["system"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

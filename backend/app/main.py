import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.core.config import settings
from app.api import api_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.tools.zcli_mcp_wrapper import get_zcli_mcp
    try:
        mcp = await get_zcli_mcp()
        logger.info("zcli MCP connected, tools: %s", list(mcp.functions.keys()))
    except Exception as e:
        logger.warning("zcli MCP not available: %s", e)
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


class SPAStaticFiles(StaticFiles):
    def lookup_path(self, path: str) -> tuple[str, os.stat_result | None]:
        full_path, stat_result = super().lookup_path(path)
        if stat_result is None:
            return super().lookup_path("index.html")
        return full_path, stat_result


static_dir = os.path.join(os.path.dirname(__file__), "..", settings.STATIC_DIR)
if os.path.isdir(static_dir):
    app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="static")

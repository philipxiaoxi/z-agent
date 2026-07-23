import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from app.core.config import settings
from app.api import api_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.mcp import load_mcp_config, get_registry

    registry = get_registry()
    configs = load_mcp_config(settings.MCP_SERVERS_CONFIG or None)

    for cfg in configs:
        if not cfg.enabled:
            continue
        try:
            mcp = await registry.get(cfg)
            logger.info("MCP [%s] connected: %d tools", cfg.name, len(mcp.functions))
        except Exception as e:
            logger.warning("MCP [%s] not available: %s", cfg.name, e)

    from app.core.dify.pool import DifyClientPool
    dify_pool = DifyClientPool()
    try:
        await dify_pool.initialize(settings.DIFY_WORKFLOWS_CONFIG or None)
        app.state.dify_pool = dify_pool
    except Exception as e:
        logger.warning("Dify workflows not available: %s", e)
        app.state.dify_pool = dify_pool

    yield

    await registry.close_all()
    await dify_pool.close()

    from app.core.tools.docker_tools import cleanup_leftover_containers
    cleanup_leftover_containers()


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if not settings.AUTH_TOKEN:
        return await call_next(request)

    path = request.url.path
    if path == "/api/auth/status" or not path.startswith("/api/"):
        return await call_next(request)

    auth = request.headers.get("Authorization")
    if not auth:
        return JSONResponse(status_code=401, content={"detail": "缺少认证凭证"})
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or token != settings.AUTH_TOKEN:
        return JSONResponse(status_code=401, content={"detail": "认证凭证无效"})
    return await call_next(request)


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

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/")
def root():
    return {"message": f"{settings.APP_NAME} is running"}

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from core.services.proxy_service import router as proxy_router
from core.handlers.handler import router as main_router
from utils.logger import setup_logger

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application starting up...")
    yield
    # Shutdown
    logger.info("Application shutting down...")


app = FastAPI(
    title="Dynamic JSON Translation Proxy",
    description="Proxies requests and translates JSON responses based on language in payload",
    version="2.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(proxy_router)
app.include_router(main_router, prefix="/v1", tags=["v1"])



if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
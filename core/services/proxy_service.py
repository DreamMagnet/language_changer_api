from fastapi import APIRouter, HTTPException
import asyncio
from core.schema.schemas import ProxyRequest
from core.handlers.proxy_handler import proxy_handler
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "translation-proxy"
    }


@router.post("/proxy", tags=["proxy"])
async def proxy_request(req: ProxyRequest):
    """
    Dynamic proxy endpoint with automatic JSON translation.

    Language extraction priority:
    1. Query parameters (params)
    2. Request payload
    """
    method = req.method.upper()
    # upstream_url = "https://datamosaix.dev.dt.bobcat.com/model_mgmt/dfm/process"
    upstream_url = "https://datamosaix.dev.dt.bobcat.com/model_mgmt/header/process"

    # Extract language (params take priority over payload)
    language = proxy_handler.extract_language(params=req.params, payload=req.payload)

    # Always proxy to the hardcoded upstream URL
    logger.info(f"Proxying {method} request to hardcoded URL: {upstream_url}")
    if language:
        logger.info(f"Translation language detected: {language}")

    try:
        async with asyncio.timeout(req.timeout):
            response = await proxy_handler.make_request(
                method=method,
                url=upstream_url,
                headers=req.headers,
                cookies=req.cookies,
                params=req.params,
                payload=req.payload,
                verify_ssl=req.verify_ssl
            )
    except asyncio.TimeoutError:
        logger.error(f"Request to upstream timed out after {req.timeout}s")
        raise HTTPException(status_code=504, detail=f"Request timeout after {req.timeout} seconds")

    return proxy_handler.process_response(response, language)
from fastapi import APIRouter
from core.schema.schemas import ReloadResponse
from core.handlers.translation_handler import translation_service
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter()


@router.post("/reload-translations", response_model=ReloadResponse)
async def reload_translations():
    """
    Manually reload translations from MongoDB.
    Useful for development and when translations are updated.
    """
    logger.info("Translation reload requested via admin endpoint")

    try:
        result = translation_service.reload()
        return ReloadResponse(
            status="success",
            message=f"Loaded {result['languages_loaded']} languages",
            languages_loaded=result['languages_loaded']
        )
    except Exception as e:
        logger.exception("Failed to reload translations")
        return ReloadResponse(
            status="error",
            message=str(e)
        )


@router.get("/languages")
async def get_available_languages():
    """Get list of available languages in the system"""
    try:
        languages = translation_service.get_available_languages()
        return {
            "status": "success",
            "count": len(languages),
            "languages": languages
        }
    except Exception as e:
        logger.exception("Failed to retrieve languages")
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "translation-proxy"
    }
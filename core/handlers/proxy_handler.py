from typing import Any, Dict, Optional
import httpx
from fastapi import HTTPException
from core.handlers.translation_handler import translation_service, JSONTranslator
from utils.logger import setup_logger

logger = setup_logger(__name__)


class ProxyHandler:
    """Handles proxy request processing and translation logic"""

    @staticmethod
    def extract_language(
            params: Optional[Dict[str, Any]] = None,
            payload: Optional[Any] = None
    ) -> Optional[str]:
        """
        Extract language from params (priority) or payload.
        Priority order: params > payload
        """
        # First, try to extract from query parameters
        if params and isinstance(params, dict):
            lang = (
                params.get("language") or
                params.get("lang") or
                params.get("locale") or
                params.get("languageId")
            )
            if isinstance(lang, str):
                normalized = lang.lower().strip()
                logger.debug(f"Extracted language from params: {normalized}")
                return normalized

        # Fallback to extracting from payload
        if payload and isinstance(payload, dict):
            lang = (
                payload.get("language") or
                payload.get("lang") or
                payload.get("locale") or
                payload.get("languageId")
            )
            if isinstance(lang, str):
                normalized = lang.lower().strip()
                logger.debug(f"Extracted language from payload: {normalized}")
                return normalized

        logger.debug("No language found in params or payload")
        return None

    @staticmethod
    async def make_request(
            method: str,
            url: str,
            headers: Optional[Dict[str, Any]],
            cookies: Optional[Dict[str, Any]],
            params: Optional[Dict[str, Any]],
            payload: Optional[Any],
            verify_ssl: bool
    ) -> httpx.Response:
        """Make HTTP request and handle errors

        Note: this function no longer accepts a timeout parameter. Callers should
        apply an asyncio timeout context manager around this call when necessary.
        """
        httpx_kwargs: Dict[str, Any] = {
            "method": method,
            "url": url,
        }

        # Add query parameters
        if params:
            httpx_kwargs["params"] = params

        # Add headers
        if headers:
            httpx_kwargs["headers"] = headers

        # Add cookies
        if cookies:
            httpx_kwargs["cookies"] = cookies

        # Add payload/body only if provided and method supports it
        if payload is not None and method not in {"GET", "HEAD", "OPTIONS"}:
            httpx_kwargs["json"] = payload

        try:
            # Use a client without any global timeout; caller controls the timeout
            async with httpx.AsyncClient(verify=verify_ssl) as client:
                response = await client.request(**httpx_kwargs)

                response.raise_for_status()
                logger.info(f"Upstream response: {response.status_code}")
                return response

        except httpx.HTTPStatusError as exc:
            logger.error(f"Upstream HTTP error: {exc.response.status_code}")
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"Upstream error: {exc.response.status_code} - {exc.response.text[:200]}",
            )
        except httpx.RequestError as exc:
            # httpx will raise a RequestError for connection issues and timeouts if not
            # caught by an outer asyncio.timeout; we map network errors to 502.
            logger.error(f"Request error: {str(exc)}")
            raise HTTPException(
                status_code=502,
                detail=f"Upstream unreachable: {str(exc)}"
            )

    @staticmethod
    def process_response(
            response: httpx.Response,
            language: Optional[str]
    ) -> Any:
        """Process response and apply translations if needed"""
        content_type = response.headers.get("content-type", "")
        logger.debug(f"Response content-type: {content_type}")

        # Non-JSON → return raw text
        if "application/json" not in content_type:
            logger.info("Non-JSON response, returning raw text")
            return response.text

        # Parse and potentially translate JSON
        try:
            data = response.json()
            logger.debug(f"Parsed JSON response type: {type(data).__name__}")

            if language:
                rules = translation_service.get_translations(language)
                if rules:
                    logger.info(f"Applying {len(rules)} translation rules for language: {language}")
                    translator = JSONTranslator(
                        rules=[{"path": path, "replace": value} for path, value in rules.items()]
                    )
                    data = translator.translate(data)
                    logger.info("Translation completed successfully")
                else:
                    logger.warning(f"No translations available for language: {language}")

            return data

        except ValueError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to parse JSON response from upstream"
            )
        except Exception as e:
            logger.exception(f"Failed to process response: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process response: {str(e)}"
            )


# Singleton instance
proxy_handler = ProxyHandler()
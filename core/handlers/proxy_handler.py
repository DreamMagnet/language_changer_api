from typing import Any, Dict, Optional
import httpx
import json
from fastapi import HTTPException
from constants.app_configuration import settings
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
    def inject_auth_token(headers: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Inject authentication token from environment into headers.
        If headers don't exist, create them. If Authorization header doesn't exist, add it.
        """
        if headers is None:
            headers = {}

        if settings.login_token:
            if "Authorization" not in headers:
                headers["login-token"] = f"{settings.login_token}"
                logger.debug("Injected auth token from environment")
            else:
                logger.debug("Authorization header already present, skipping injection")
        else:
            logger.warning("No login_token configured in environment")

        return headers

    @staticmethod
    def build_url_with_params(
            url: str,
            params: Optional[Dict[str, Any]],
            payload: Optional[Any]
    ) -> str:
        """
        Build URL with schema and params as query parameters.

        Rules:
        1. If schema exists in params dict, add it as: ?schema=value
        2. If params dict exists, add it as: &params={"json":"encoded"}
        3. If schema exists in payload (but not in params), extract and add to URL

        Returns:
            str: modified_url with query parameters
        """
        schema_value = None
        query_parts = []

        # Check for schema in params first (priority)
        if params and isinstance(params, dict) and "schema" in params:
            schema_value = params.get("schema")
            logger.debug(f"Found schema in params: {schema_value}")

        # Fallback to payload if schema not in params
        elif payload and isinstance(payload, dict) and "schema" in payload:
            schema_value = payload.get("schema")
            logger.debug(f"Found schema in payload: {schema_value}")

        # Add schema to query parts if found
        if schema_value:
            query_parts.append(f"schema={schema_value}")
            logger.debug(f"Added schema to query: schema={schema_value}")

        # Add params dict as JSON string to query
        if params and isinstance(params, dict):
            params_json = json.dumps(params, separators=(',', ':'))
            query_parts.append(f"params={params_json}")
            logger.debug(f"Added params to query: params={params_json}")

        # Build final URL
        if query_parts:
            separator = "&" if "?" in url else "?"
            query_string = "&".join(query_parts)
            url = f"{url}{separator}{query_string}"
            logger.info(f"Built final URL: {url}")

        return url

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
        # Inject authentication token from environment
        headers = ProxyHandler.inject_auth_token(headers)

        # Build URL with schema and params handling
        url = ProxyHandler.build_url_with_params(url, params, payload)

        httpx_kwargs: Dict[str, Any] = {
            "method": method,
            "url": url,
        }

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
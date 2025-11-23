from typing import Any, Dict, Optional
import httpx
from fastapi import APIRouter, HTTPException
from core.schema.schemas import ProxyRequest
from core.handlers.translation_handler import translation_service, JSONTranslator
from utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter()


def extract_language(payload: Optional[Any]) -> Optional[str]:
    """Extract language from payload - only works if payload is a dict"""
    if not payload or not isinstance(payload, dict):
        return None

    # Try multiple common language field names
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

    return None


def process_payload_params(payload: Optional[Dict[str, Any]]) -> tuple[
    Optional[Dict[str, Any]], Dict[str, Any], Optional[str]]:
    """
    Process payload to extract params, schema and clean payload.
    Returns: (cleaned_payload, query_params, schema)
    """
    if not payload or not isinstance(payload, dict):
        return payload, {}, None

    query_params = {}
    schema = payload.pop("schema", None)  # Remove schema from payload and add as query param
    params_str = payload.pop("params", None)  # Remove params from payload

    if schema:
        query_params["schema"] = schema
        logger.debug(f"Extracted schema as query param: {schema}")

    if params_str:
        try:
            # Handle both string JSON and dict for params
            if isinstance(params_str, str):
                import json
                params_dict = json.loads(params_str)
            else:
                params_dict = params_str

            if isinstance(params_dict, dict):
                query_params.update(params_dict)
                logger.debug(f"Extracted {len(params_dict)} params as query parameters")
            else:
                logger.warning(f"Invalid params format in payload: {type(params_str)}")
        except Exception as e:
            logger.error(f"Failed to parse params from payload: {e}")

    return payload, query_params, schema


@router.post("/proxy", tags=["proxy"])
async def proxy_request(req: ProxyRequest):
    """
    Dynamic proxy endpoint that works with any combination of:
    - URL only
    - URL + headers
    - URL + payload
    - URL + params
    - URL + cookies
    - Special payload fields: 'params' (converted to query params) and 'schema' (converted to query param)
    - Any combination of the above

    Automatically translates JSON responses based on language in payload.
    """
    method = req.method.upper()

    # Process payload to extract params and schema
    cleaned_payload, payload_query_params, schema = process_payload_params(req.payload)
    language = extract_language(cleaned_payload)

    logger.info(f"Proxying {method} request to: {req.url}")
    if language:
        logger.info(f"Translation language detected: {language}")
    if payload_query_params:
        logger.info(f"Payload params converted to query params: {list(payload_query_params.keys())}")
    if schema:
        logger.info(f"Schema extracted as query param: {schema}")

    # Configure HTTP client
    timeout = httpx.Timeout(timeout=req.timeout)

    async with httpx.AsyncClient(timeout=timeout, verify=req.verify_ssl) as client:
        try:
            # Build request kwargs dynamically
            httpx_kwargs: Dict[str, Any] = {
                "method": method,
                "url": str(req.url),
            }

            # Combine all query parameters (req.params + payload_query_params)
            all_query_params = {**(req.params or {}), **payload_query_params}
            if all_query_params:
                httpx_kwargs["params"] = all_query_params
                logger.debug(f"Combined query parameters: {list(all_query_params.keys())}")

            # Add optional parameters only if provided
            if req.headers:
                httpx_kwargs["headers"] = req.headers
                logger.debug(f"Request headers: {list(req.headers.keys())}")

            if req.cookies:
                httpx_kwargs["cookies"] = req.cookies
                logger.debug(f"Cookies: {list(req.cookies.keys())}")

            # Add cleaned payload/body only if provided and method supports it
            if cleaned_payload is not None and method not in {"GET", "HEAD", "OPTIONS"}:
                httpx_kwargs["json"] = cleaned_payload
                logger.debug(f"Request payload type: {type(cleaned_payload).__name__}")

            # Make the request
            response = await client.request(**httpx_kwargs)
            response.raise_for_status()

            logger.info(f"Upstream response: {response.status_code}")

        except httpx.HTTPStatusError as exc:
            logger.error(f"Upstream HTTP error: {exc.response.status_code}")
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"Upstream error: {exc.response.status_code} - {exc.response.text[:200]}",
            )
        except httpx.TimeoutException:
            logger.error(f"Request timeout after {req.timeout}s")
            raise HTTPException(
                status_code=504,
                detail=f"Request timeout after {req.timeout} seconds"
            )
        except httpx.RequestError as exc:
            logger.error(f"Request error: {str(exc)}")
            raise HTTPException(
                status_code=502,
                detail=f"Upstream unreachable: {str(exc)}"
            )

    # Check content type
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
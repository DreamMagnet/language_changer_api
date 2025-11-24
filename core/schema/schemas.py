from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator, HttpUrl


class ProxyRequest(BaseModel):
    """Schema for proxy request payload"""

    # url: HttpUrl = Field(..., description="Target URL to proxy to")
    method: str = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional headers"
    )
    params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional query parameters"
    )
    payload: Optional[Any] = Field(
        default=None,
        description="Optional request body (can be dict, list, or any JSON type)"
    )
    cookies: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional cookies as key-value pairs"
    )
    timeout: float = Field(
        default=20.0,
        ge=1.0,
        le=300.0,
        description="Request timeout in seconds"
    )
    verify_ssl: bool = Field(
        default=False,
        description="Whether to verify SSL certificates (default: False for dev)"
    )

    @field_validator("method")
    @classmethod
    def uppercase_method(cls, v):
        """Ensure HTTP method is uppercase"""
        return v.upper()

    class Config:
        json_schema_extra = {
            "example": {
                # "url": "https://api.example.com/data",
                "method": "POST",
                "headers": {"Authorization": "Bearer token"},
                "payload": {"language": "es", "query": "test"}
            }
        }


class TranslationRule(BaseModel):
    """Schema for a single translation rule"""

    path: str = Field(..., description="Dot-notation path (e.g., 'title' or 'items.*.name')")
    replace: Any = Field(..., description="Replacement value or mapping")


class ReloadResponse(BaseModel):
    """Schema for reload response"""

    status: str
    message: Optional[str] = None
    languages_loaded: Optional[int] = None
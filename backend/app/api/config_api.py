"""Public configuration endpoint for client bootstrap."""

from fastapi import APIRouter
from backend.app.config import settings
from backend.app.schemas.api import PublicConfigResponse

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("/public", response_model=PublicConfigResponse)
async def get_public_config():
    """Returns safe, redacted configuration for frontend client initialization."""
    return PublicConfigResponse(
        google_maps_browser_key=settings.GOOGLE_MAPS_BROWSER_KEY,
        has_routes_backend_key=bool(settings.GOOGLE_ROUTES_API_KEY),
        has_street_view_backend_key=bool(settings.GOOGLE_STREET_VIEW_API_KEY),
        has_gemini_backend_key=bool(settings.GEMINI_API_KEY),
        gemini_model=settings.GEMINI_MODEL,
        demo_mode_active=settings.is_offline_mode_required or settings.DEMO_MODE_DEFAULT,
        environment=settings.ENVIRONMENT,
        api_version="1.0.0",
    )

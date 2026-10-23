"""Google Street View Static API service with metadata pre-flight checks and rate control."""

import logging
from typing import Optional
from datetime import datetime, timezone
import httpx
from backend.app.config import settings
from backend.app.schemas.route import Coordinate

logger = logging.getLogger(__name__)

STREETVIEW_METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
STREETVIEW_IMAGE_URL = "https://maps.googleapis.com/maps/api/streetview"


class StreetViewMetadataResult:
    def __init__(self, is_available: bool, pano_id: Optional[str] = None, date_str: Optional[str] = None):
        self.is_available = is_available
        self.pano_id = pano_id
        self.date_str = date_str


async def check_street_view_availability(
    coord: Coordinate,
    radius_meters: int = 50,
) -> StreetViewMetadataResult:
    """Pre-flight check via Street View Metadata API to verify coverage before requesting images."""
    api_key = settings.GOOGLE_STREET_VIEW_API_KEY
    if not api_key:
        return StreetViewMetadataResult(is_available=False)

    params = {
        "location": f"{coord.lat},{coord.lng}",
        "radius": radius_meters,
        "key": api_key,
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(STREETVIEW_METADATA_URL, params=params)
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                if status == "OK":
                    return StreetViewMetadataResult(
                        is_available=True,
                        pano_id=data.get("pano_id"),
                        date_str=data.get("date"),
                    )
            return StreetViewMetadataResult(is_available=False)
    except Exception as exc:
        logger.warning("Street View metadata check failed: %s", exc)
        return StreetViewMetadataResult(is_available=False)


async def fetch_street_view_image_bytes(
    coord: Coordinate,
    heading: Optional[float] = None,
    pitch: int = 0,
    fov: int = 90,
) -> Optional[bytes]:
    """Fetches static street view image bytes for eligible road segment."""
    api_key = settings.GOOGLE_STREET_VIEW_API_KEY
    if not api_key:
        return None

    # First check metadata
    meta = await check_street_view_availability(coord)
    if not meta.is_available:
        logger.info("No Street View coverage at %s,%s", coord.lat, coord.lng)
        return None

    params = {
        "size": "600x400",
        "location": f"{coord.lat},{coord.lng}",
        "fov": fov,
        "pitch": pitch,
        "key": api_key,
    }
    if heading is not None:
        params["heading"] = f"{heading:.1f}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(STREETVIEW_IMAGE_URL, params=params)
            if response.status_code == 200 and "image" in response.headers.get("content-type", ""):
                return response.content
            return None
    except Exception as exc:
        logger.warning("Failed to retrieve Street View image bytes: %s", exc)
        return None

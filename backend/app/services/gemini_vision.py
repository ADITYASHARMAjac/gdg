"""Gemini Vision Analysis Service using official Google Gen AI SDK.

Inspects street imagery to produce structured physical road characteristics:
usable width, lanes, parking friction, obstacles, pedestrian context, and restrictions.
"""

import logging
import json
from typing import Optional
from backend.app.config import settings
from backend.app.schemas.road import (
    ObstructionLevel,
    PedestrianContext,
    VisionRoadAnalysis,
)

logger = logging.getLogger(__name__)

GEMINI_ANALYSIS_PROMPT = """You are a senior traffic engineer and geometric road safety inspector.
Analyze this street-level photograph of a road segment.
Inspect directly visible physical conditions:
1. Usable road width: estimate the clear carriageway width in meters between curb/parked cars. If obscured, mark as null.
2. Lane count: count marked or functional travel lanes. If ambiguous, mark as null.
3. Parking obstruction: evaluate curb parking density (none, low, moderate, high, blocked).
4. Visible obstacles: identify hazards such as construction, double parking, road surface defects, or delivery vehicles.
5. Pedestrian context: observe sidewalk adequacy, crosswalks, school zones, or shared street spaces.
6. Visible restrictions: notice signs like one-way, no entry, speed humps, or weight limits.
7. Confidence: rate your assessment confidence from 0.0 to 1.0.
8. Missing or uncertain information: list anything you cannot reliably ascertain from this perspective.
9. Evidence notes: provide brief factual observations supporting your findings.

Do NOT invent vehicle throughput numbers or guess exact traffic volumes. Distinguish clearly visible facts from inferences."""


def get_mock_vision_analysis(
    functional_class: str = "residential",
    road_name: Optional[str] = None,
) -> VisionRoadAnalysis:
    """Generates realistic deterministic vision output for offline testing and demo mode."""
    name_lower = (road_name or "").lower()
    if "arterial" in name_lower or "parkway" in name_lower or functional_class == "arterial":
        return VisionRoadAnalysis(
            usable_road_width_meters=14.0,
            visible_lane_count=4,
            parking_obstruction=ObstructionLevel.NONE,
            visible_obstacles=[],
            pedestrian_cyclist_activity=PedestrianContext.LOW,
            visible_road_restrictions=[],
            confidence=0.95,
            evidence_notes=["Wide multi-lane divided arterial with clear shoulders and no curb friction."],
        )
    elif "elm" in name_lower or "alley" in name_lower or functional_class == "narrow_residential":
        return VisionRoadAnalysis(
            usable_road_width_meters=4.2,
            visible_lane_count=1,
            parking_obstruction=ObstructionLevel.HIGH,
            visible_obstacles=["double_parking_deliveries"],
            pedestrian_cyclist_activity=PedestrianContext.SCHOOL_ZONE,
            visible_road_restrictions=["speed_bump_20kmh", "resident_only"],
            confidence=0.88,
            missing_or_uncertain_info=["turning_radius_at_intersection"],
            evidence_notes=["High density curbside parking; cars must yield to oncoming traffic in pinch points."],
        )
    elif "pine" in name_lower:
        return VisionRoadAnalysis(
            usable_road_width_meters=3.8,
            visible_lane_count=1,
            parking_obstruction=ObstructionLevel.HIGH,
            visible_obstacles=[],
            pedestrian_cyclist_activity=PedestrianContext.HIGH_PEDESTRIAN_ZONE,
            visible_road_restrictions=["school_crossing"],
            confidence=0.85,
            evidence_notes=["Narrow single-lane corridor without separated bike facilities."],
        )
    else:
        return VisionRoadAnalysis(
            usable_road_width_meters=8.5,
            visible_lane_count=2,
            parking_obstruction=ObstructionLevel.MODERATE,
            visible_obstacles=[],
            pedestrian_cyclist_activity=PedestrianContext.MODERATE_SIDEWALK,
            visible_road_restrictions=[],
            confidence=0.90,
            evidence_notes=["Two-lane collector avenue with marked curbside parking."],
        )


async def analyze_road_imagery_with_gemini(
    image_bytes: Optional[bytes],
    road_name: Optional[str] = None,
    functional_class: str = "residential",
    force_offline: bool = False,
) -> tuple[VisionRoadAnalysis, str]:
    """Inspects road image using official Google Gen AI SDK or offline deterministic mock."""
    # Check if offline fallback is required
    if force_offline or not settings.GEMINI_API_KEY or not image_bytes:
        provenance = "offline_deterministic_analyzer" if not image_bytes else "gemini_mock_no_key"
        return get_mock_vision_analysis(functional_class, road_name), provenance

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        
        # Request structured JSON matching VisionRoadAnalysis schema
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[image_part, GEMINI_ANALYSIS_PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VisionRoadAnalysis,
                temperature=0.2,
            ),
        )

        if response.text:
            analysis = VisionRoadAnalysis.model_validate_json(response.text)
            return analysis, f"gemini_{settings.GEMINI_MODEL}"
        else:
            raise ValueError("Empty response text from Gemini API")

    except Exception as exc:
        logger.warning("Gemini vision analysis failed (%s); using conservative fallback", exc)
        # Fallback to conservative analysis with low confidence
        fallback = get_mock_vision_analysis(functional_class, road_name)
        fallback.confidence = 0.5
        fallback.missing_or_uncertain_info.append(f"Gemini API invocation error: {str(exc)[:80]}")
        return fallback, "fallback_after_gemini_error"

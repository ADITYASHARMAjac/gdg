"""End-to-end routing pipeline orchestrator.

Integrates real-time Google Routes API generation, Street View imagery sampling,
Gemini multimodal road inspection, deterministic suitability scoring, and capacity-aware selection.
Operates strictly in live online mode.
"""

import logging
from typing import Optional
from backend.app.config import settings
from backend.app.schemas.api import CostWeightsConfig
from backend.app.schemas.road import VehicleType
from backend.app.schemas.route import (
    CandidateRoute,
    Coordinate,
    SelectedRouteDecision,
)
from backend.app.services.google_routes import get_candidate_routes
from backend.app.services.street_view import fetch_street_view_image_bytes
from backend.app.services.gemini_vision import analyze_road_imagery_with_gemini
from backend.app.engine.scoring import calculate_road_suitability
from backend.app.engine.routing import select_best_route
from backend.app.engine.registry import RouteAllocationRegistry

logger = logging.getLogger(__name__)


async def analyze_candidate_routes_pipeline(
    candidates: list[CandidateRoute],
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR,
    sample_interval_meters: float = 100.0,
) -> tuple[list[CandidateRoute], int, float, str]:
    """Inspects segments across live candidate routes via Street View and Gemini Vision."""
    total_segments = 0
    imagery_successes = 0
    provenance = f"gemini_{settings.GEMINI_MODEL}"

    for route in candidates:
        segment_suitabilities = []

        for seg in route.segments:
            total_segments += 1
            image_bytes = None

            # Fetch real Street View imagery if key is available
            if settings.GOOGLE_STREET_VIEW_API_KEY:
                image_bytes = await fetch_street_view_image_bytes(
                    seg.start_coord,
                    heading=seg.street_view_heading,
                )
                if image_bytes:
                    imagery_successes += 1
                    seg.has_imagery = True
                else:
                    seg.has_imagery = False
            else:
                seg.has_imagery = False

            # Live Gemini multimodal vision analysis
            vision = None
            if image_bytes and settings.GEMINI_API_KEY:
                vision, _ = await analyze_road_imagery_with_gemini(
                    image_bytes=image_bytes,
                    road_name=seg.name,
                    functional_class=seg.functional_class,
                )
            seg.vision_analysis = vision

            # Compute road suitability score from visual findings
            suitability = calculate_road_suitability(
                analysis=vision,
                functional_class=seg.functional_class,
                vehicle_type=vehicle_type,
                known_restrictions=seg.restrictions,
            )
            seg.suitability = suitability
            segment_suitabilities.append(suitability.suitability_score)

        # Update candidate route aggregate suitability & confidence
        if segment_suitabilities:
            route.suitability_score = round(sum(segment_suitabilities) / len(segment_suitabilities), 1)
            route.confidence = round(
                sum(s.suitability.confidence for s in route.segments if s.suitability) / max(1, len(route.segments)),
                2,
            )

    coverage_ratio = imagery_successes / max(1, total_segments)
    return candidates, total_segments, round(coverage_ratio, 2), provenance


async def run_flowsplit_pipeline(
    origin: Coordinate,
    destination: Coordinate,
    vehicle_type: VehicleType = VehicleType.PASSENGER_CAR,
    current_route_id: Optional[str] = None,
    weights: Optional[CostWeightsConfig] = None,
    registry: Optional[RouteAllocationRegistry] = None,
) -> tuple[SelectedRouteDecision, list[CandidateRoute], list[str]]:
    """Runs full online pipeline: Google Routes API -> Street View -> Gemini Vision -> FlowSplit selection."""
    # 1. Fetch live candidate routes from Google Routes API
    candidates, provider, warnings = await get_candidate_routes(
        origin, destination, vehicle_type
    )

    # 2. Road visual inspection and suitability scoring
    analyzed_candidates, _, _, _ = await analyze_candidate_routes_pipeline(
        candidates,
        vehicle_type=vehicle_type,
        sample_interval_meters=settings.SAMPLE_INTERVAL_METERS,
    )

    # 3. Capacity-aware route selection
    decision = select_best_route(
        candidates=analyzed_candidates,
        current_route_id=current_route_id,
        weights=weights,
        registry=registry,
        vehicle_type=vehicle_type,
    )

    return decision, analyzed_candidates, warnings

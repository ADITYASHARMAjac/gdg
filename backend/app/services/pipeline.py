"""End-to-end routing pipeline orchestrator.

Integrates route generation, street imagery sampling, vision analysis,
deterministic road suitability scoring, and capacity-aware route selection.
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
    demo_mode: bool = False,
) -> tuple[list[CandidateRoute], int, float, str]:
    """Inspects segments across candidate routes, runs vision analysis and updates suitability scores."""
    total_segments = 0
    imagery_successes = 0
    provenance = "gemini_vision" if not demo_mode and settings.GEMINI_API_KEY else "deterministic_offline_demo"

    for r_idx, route in enumerate(candidates):
        segment_suitabilities = []

        for s_idx, seg in enumerate(route.segments):
            total_segments += 1
            image_bytes = None

            # In live mode with API keys, fetch street view image
            if not demo_mode and settings.GOOGLE_STREET_VIEW_API_KEY:
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
                seg.has_imagery = True
                imagery_successes += 1

            # Vision analysis (Gemini or deterministic model)
            vision, prov = await analyze_road_imagery_with_gemini(
                image_bytes=image_bytes,
                road_name=seg.name,
                functional_class=seg.functional_class,
                force_offline=demo_mode or not settings.GEMINI_API_KEY,
            )
            seg.vision_analysis = vision

            # Compute deterministic suitability score
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
    force_demo: bool = False,
) -> tuple[SelectedRouteDecision, list[CandidateRoute], list[str]]:
    """Runs full pipeline: generates candidate routes, analyzes roads, and selects optimal route."""
    # 1. Candidate routes
    candidates, provider, warnings = await get_candidate_routes(
        origin, destination, vehicle_type, force_demo=force_demo
    )

    # 2. Road visual inspection and suitability scoring
    analyzed_candidates, _, _, _ = await analyze_candidate_routes_pipeline(
        candidates,
        vehicle_type=vehicle_type,
        sample_interval_meters=settings.SAMPLE_INTERVAL_METERS,
        demo_mode=force_demo or (provider == "deterministic_offline_demo"),
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

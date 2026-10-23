"""FastAPI endpoints for offline deterministic traffic simulation comparison."""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from backend.app.schemas.simulation import OfflineSimulationComparison
from backend.app.schemas.api import CostWeightsConfig
from backend.app.engine.simulation import compare_baseline_vs_flowsplit, build_offline_network

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])


class SimulationRunRequest(BaseModel):
    total_hourly_trips: int = Field(default=900, ge=100, le=5000, description="Simulated commuter trips per hour")
    weights: Optional[CostWeightsConfig] = None


@router.post("/run", response_model=OfflineSimulationComparison)
async def run_simulation(req: SimulationRunRequest):
    """Executes a head-to-head comparison between baseline GPS routing and FlowSplit capacity-aware routing."""
    comparison = compare_baseline_vs_flowsplit(
        total_trips=req.total_hourly_trips,
        weights=req.weights,
    )
    return comparison


@router.get("/network")
async def get_simulation_network():
    """Returns the deterministic 3-route benchmark network."""
    routes = build_offline_network()
    return {"candidates": routes}

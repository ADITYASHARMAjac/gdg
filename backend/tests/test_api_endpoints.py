"""Integration and unit tests for FastAPI endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.app.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "capabilities" in data


@pytest.mark.asyncio
async def test_public_config_redaction():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/config/public")
        assert response.status_code == 200
        data = response.json()
        # Ensure server secrets are NOT returned as strings
        assert "google_routes_api_key" not in data
        assert "gemini_api_key" not in data
        assert "has_routes_backend_key" in data
        assert "has_gemini_backend_key" in data


@pytest.mark.asyncio
async def test_candidates_endpoint_offline():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "origin": {"lat": 37.7749, "lng": -122.4494},
            "destination": {"lat": 37.7915, "lng": -122.3999},
            "demo_mode": True,
        }
        response = await ac.post("/api/routes/candidates", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["candidates"]) == 3
        assert data["is_demo"] is True


@pytest.mark.asyncio
async def test_candidates_invalid_coordinates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "origin": {"lat": 95.0, "lng": -122.4494},  # Invalid lat > 90
            "destination": {"lat": 37.7915, "lng": -122.3999},
        }
        response = await ac.post("/api/routes/candidates", json=payload)
        # Should be caught by Pydantic validation (422) or endpoint check (400)
        assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_analyze_and_select_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Fetch candidates
        c_res = await ac.post("/api/routes/candidates", json={
            "origin": {"lat": 37.7749, "lng": -122.4494},
            "destination": {"lat": 37.7915, "lng": -122.3999},
            "demo_mode": True,
        })
        candidates = c_res.json()["candidates"]

        # 2. Analyze routes
        a_res = await ac.post("/api/routes/analyze", json={
            "candidates": candidates,
            "demo_mode": True,
        })
        assert a_res.status_code == 200
        analyzed_candidates = a_res.json()["analyzed_candidates"]
        assert len(analyzed_candidates) == 3

        # 3. Select best route
        s_res = await ac.post("/api/routes/select", json={
            "candidates": analyzed_candidates,
            "demo_mode": True,
        })
        assert s_res.status_code == 200
        decision = s_res.json()
        assert decision["selected_route_id"] == "route-arterial-grand-pkwy"
        assert len(decision["candidate_breakdowns"]) == 3


@pytest.mark.asyncio
async def test_simulation_run_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/simulation/run", json={"total_hourly_trips": 900})
        assert response.status_code == 200
        data = response.json()
        assert data["baseline_result"]["overloaded_segments_count"] > 0
        assert data["flowsplit_result"]["overloaded_segments_count"] == 0
        assert data["queue_reduction_percent"] > 50.0


@pytest.mark.asyncio
async def test_road_analyze_and_retrieve():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        req = {
            "lat": 37.7749,
            "lng": -122.4194,
            "road_name": "Market Street Corridor",
            "vehicle_type": "passenger_car",
        }
        res = await ac.post("/api/roads/analyze", json=req)
        assert res.status_code == 200
        data = res.json()
        assert "road_id" in data
        assert data["suitability"]["suitability_score"] > 0.0

        road_id = data["road_id"]
        get_res = await ac.get(f"/api/roads/{road_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["road_id"] == road_id
        assert get_data["road_name"] == "Market Street Corridor"

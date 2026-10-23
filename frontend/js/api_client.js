/**
 * FlowSplit API Client
 * Centralized HTTP communication with FastAPI backend.
 */

const ApiClient = {
  baseUrl: window.location.origin,

  async getPublicConfig() {
    try {
      const res = await fetch(`${this.baseUrl}/api/config/public`);
      if (!res.ok) throw new Error(`Config fetch failed: ${res.statusText}`);
      return await res.json();
    } catch (err) {
      console.warn("Public config fetch failed:", err);
      return {
        google_maps_browser_key: null,
        has_routes_backend_key: false,
        has_street_view_backend_key: false,
        has_gemini_backend_key: false,
        demo_mode_active: true,
      };
    }
  },

  async getCandidateRoutes(origin, destination, vehicleType = "passenger_car", demoMode = false) {
    const payload = {
      origin: origin,
      destination: destination,
      vehicle_type: vehicleType,
      demo_mode: demoMode,
    };
    const res = await fetch(`${this.baseUrl}/api/routes/candidates`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Routes candidate generation failed (${res.status})`);
    }
    return await res.json();
  },

  async analyzeRoutes(candidates, vehicleType = "passenger_car", demoMode = false) {
    const payload = {
      candidates: candidates,
      vehicle_type: vehicleType,
      sample_interval_meters: 100.0,
      demo_mode: demoMode,
    };
    const res = await fetch(`${this.baseUrl}/api/routes/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Route analysis failed (${res.status})`);
    }
    return await res.json();
  },

  async selectBestRoute(candidates, currentRouteId = null, vehicleType = "passenger_car", demoMode = false) {
    const payload = {
      candidates: candidates,
      current_route_id: currentRouteId,
      vehicle_type: vehicleType,
      demo_mode: demoMode,
    };
    const res = await fetch(`${this.baseUrl}/api/routes/select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Route selection failed (${res.status})`);
    }
    return await res.json();
  },

  async runSimulation(totalTrips = 900) {
    const res = await fetch(`${this.baseUrl}/api/simulation/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ total_hourly_trips: totalTrips }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Simulation run failed (${res.status})`);
    }
    return await res.json();
  },
};

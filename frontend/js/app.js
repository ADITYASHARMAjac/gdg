/**
 * FlowSplit Main Application Controller
 * Orchestrates map rendering, route evaluation pipeline, user geolocation, and UI states.
 */

class FlowSplitApp {
  constructor() {
    this.mapController = new MapController('flowsplitMap');
    this.candidates = [];
    this.selectedRouteId = null;
    this.currentDecision = null;
    this.demoMode = false;
    this.config = null;
  }

  async init() {
    console.log("Initializing FlowSplit Application...");

    // 1. Fetch public backend configuration
    this.config = await ApiClient.getPublicConfig();
    this.demoMode = this.config.demo_mode_active || false;
    this.updateConfigStatusUI();

    // 2. Initialize Map Engine
    await this.mapController.init(this.config.google_maps_browser_key);
    this.mapController.onRouteSelected = (routeId) => this.handleRouteSelected(routeId);

    // 3. Initialize UI Subcomponents
    SimulationViewComponent.init();
    this.setupEventListeners();

    // 4. Run initial benchmark evaluation
    await this.evaluateCurrentRoute(true);
  }

  updateConfigStatusUI() {
    const statusText = document.getElementById('statusText');
    const statusDot = document.getElementById('statusDot');
    const demoBanner = document.getElementById('demoBannerTag');
    const demoBtnText = document.getElementById('demoModeBtnText');

    if (this.demoMode) {
      statusText.textContent = "Offline Benchmark Mode";
      statusDot.className = "status-dot";
      demoBanner.style.display = "inline-block";
      demoBtnText.textContent = "Switch to Live APIs";
    } else {
      statusText.textContent = "Google & Gemini Live APIs";
      statusDot.className = "status-dot live";
      demoBanner.style.display = "none";
      demoBtnText.textContent = "Switch to Offline Demo";
    }
  }

  setupEventListeners() {
    // Search Form Submit
    const searchForm = document.getElementById('routeSearchForm');
    if (searchForm) {
      searchForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await this.evaluateCurrentRoute(false);
      });
    }

    // Geolocation "Use my location" button
    const btnUseLoc = document.getElementById('btnUseLocation');
    if (btnUseLoc) {
      btnUseLoc.addEventListener('click', async () => {
        await this.handleUseGeolocation();
      });
    }

    // Preset Scenario buttons
    document.querySelectorAll('.preset-btn').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');

        const originVal = e.currentTarget.dataset.origin;
        const destVal = e.currentTarget.dataset.dest;
        document.getElementById('originInput').value = originVal;
        document.getElementById('destinationInput').value = destVal;

        await this.evaluateCurrentRoute(false);
      });
    });

    // Toggle Demo Mode Button
    const btnToggleDemo = document.getElementById('btnToggleDemoMode');
    if (btnToggleDemo) {
      btnToggleDemo.addEventListener('click', async () => {
        this.demoMode = !this.demoMode;
        this.updateConfigStatusUI();
        await this.evaluateCurrentRoute(false);
      });
    }

    // Confirm Route Button
    const btnConfirm = document.getElementById('btnConfirmRoute');
    if (btnConfirm) {
      btnConfirm.addEventListener('click', () => {
        const textSpan = document.getElementById('btnConfirmRouteText');
        textSpan.textContent = "✓ Route Active & Monitored";
        btnConfirm.classList.remove('btn-success');
        btnConfirm.classList.add('btn-primary');
        setTimeout(() => {
          textSpan.textContent = "Use This Recommended Route";
          btnConfirm.classList.remove('btn-primary');
          btnConfirm.classList.add('btn-success');
        }, 4000);
      });
    }

    // Map control buttons
    document.getElementById('btnZoomIn')?.addEventListener('click', () => this.mapController.zoomIn());
    document.getElementById('btnZoomOut')?.addEventListener('click', () => this.mapController.zoomOut());
    document.getElementById('btnResetView')?.addEventListener('click', () => this.mapController.resetView());
  }

  async handleUseGeolocation() {
    const feedback = document.getElementById('geolocationFeedback');
    feedback.textContent = "Requesting location permission...";

    try {
      const pos = await GeolocationService.getCurrentPosition();
      const coordStr = `${pos.lat}, ${pos.lng}`;
      document.getElementById('originInput').value = coordStr;
      feedback.textContent = `Location acquired (±${Math.round(pos.accuracy)}m)`;
      this.mapController.setUserLocation(pos.lat, pos.lng);
    } catch (err) {
      console.warn("Geolocation failed:", err);
      feedback.textContent = err.message;
    }
  }

  parseCoordinate(inputStr, defaultCoord) {
    if (!inputStr) return defaultCoord;
    const parts = inputStr.split(',').map(s => parseFloat(s.trim()));
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      return { lat: parts[0], lng: parts[1] };
    }
    return defaultCoord;
  }

  async evaluateCurrentRoute(isInitial = false) {
    const originStr = document.getElementById('originInput').value;
    const destStr = document.getElementById('destinationInput').value;
    const vehicleType = document.getElementById('vehicleTypeSelect').value || 'passenger_car';

    const origin = this.parseCoordinate(originStr, { lat: 37.7749, lng: -122.4494 });
    const destination = this.parseCoordinate(destStr, { lat: 37.7915, lng: -122.3999 });

    this.mapController.origin = origin;
    this.mapController.destination = destination;

    // Show loading state
    const spinner = document.getElementById('routeSearchSpinner');
    const btnText = document.getElementById('routeSearchBtnText');
    if (spinner) spinner.style.display = 'inline-block';
    if (btnText) btnText.textContent = "Analyzing Imagery & Capacity...";

    try {
      // 1. Fetch Candidate Routes
      const candidatesRes = await ApiClient.getCandidateRoutes(
        origin,
        destination,
        vehicleType,
        this.demoMode
      );
      this.candidates = candidatesRes.candidates || [];

      // Update provenance notice
      const provNotice = document.getElementById('provenanceText');
      if (provNotice) {
        if (candidatesRes.is_demo) {
          provNotice.textContent = "Deterministic offline benchmark active. Evaluates traffic-aware time, road imagery suitability, and residential choke-points.";
        } else {
          provNotice.textContent = "Live Google Routes & Gemini multimodal vision inspection active. Assessing road widths, curbside friction, and safety context.";
        }
      }

      // 2. Visual inspection & suitability scoring
      const analysisRes = await ApiClient.analyzeRoutes(
        this.candidates,
        vehicleType,
        this.demoMode
      );
      this.candidates = analysisRes.analyzed_candidates;

      // 3. FlowSplit Capacity-Aware Route Selection
      this.currentDecision = await ApiClient.selectBestRoute(
        this.candidates,
        null,
        vehicleType,
        this.demoMode
      );

      this.selectedRouteId = this.currentDecision.selected_route_id;

      // 4. Update UI Components
      RouteComparisonComponent.renderCandidateList(
        this.candidates,
        this.selectedRouteId,
        (id) => this.handleRouteSelected(id)
      );

      RouteComparisonComponent.updateSelectedDecisionCard(this.currentDecision);

      const selectedRoute = this.candidates.find(r => r.id === this.selectedRouteId);
      if (selectedRoute) {
        RoadDetailsComponent.renderSegmentInspection(selectedRoute);
      }

      // 5. Update Map
      this.mapController.setRoutes(this.candidates, this.selectedRouteId);

    } catch (err) {
      console.error("Evaluation failed:", err);
      alert(`Routing evaluation failed: ${err.message}`);
    } finally {
      if (spinner) spinner.style.display = 'none';
      if (btnText) btnText.textContent = "Evaluate Routes";
    }
  }

  handleRouteSelected(routeId) {
    this.selectedRouteId = routeId;
    this.mapController.setSelectedRoute(routeId);

    // Re-render candidate list with active selection
    RouteComparisonComponent.renderCandidateList(
      this.candidates,
      this.selectedRouteId,
      (id) => this.handleRouteSelected(id)
    );

    // Update selected route card and deep-dive
    const route = this.candidates.find(r => r.id === routeId);
    if (route && this.currentDecision) {
      const mockDecision = {
        ...this.currentDecision,
        selected_route_id: routeId,
        selected_route: route,
      };
      RouteComparisonComponent.updateSelectedDecisionCard(mockDecision);
      RoadDetailsComponent.renderSegmentInspection(route);
    }
  }
}

// Start application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  const app = new FlowSplitApp();
  app.init();
});

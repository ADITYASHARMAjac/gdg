/**
 * Simulation View Component
 * Controls the interactive Traffic Simulation Lab modal comparing Baseline vs FlowSplit.
 */

const SimulationViewComponent = {
  modalEl: null,

  init() {
    this.modalEl = document.getElementById('simulationModal');
    const btnOpen = document.getElementById('btnOpenSimulation');
    const btnClose = document.getElementById('btnCloseSimulation');
    const btnRun = document.getElementById('btnRunSimSimulation');

    if (btnOpen) {
      btnOpen.addEventListener('click', () => {
        this.openModal();
      });
    }

    if (btnClose) {
      btnClose.addEventListener('click', () => {
        this.closeModal();
      });
    }

    if (btnRun) {
      btnRun.addEventListener('click', async () => {
        const input = document.getElementById('simDemandInput');
        const trips = parseInt(input.value, 10) || 900;
        await this.runSimulation(trips);
      });
    }

    // Close on backdrop click
    if (this.modalEl) {
      this.modalEl.addEventListener('click', (e) => {
        if (e.target === this.modalEl) this.closeModal();
      });
    }
  },

  openModal() {
    if (this.modalEl) {
      this.modalEl.style.display = 'flex';
      this.runSimulation(900);
    }
  },

  closeModal() {
    if (this.modalEl) {
      this.modalEl.style.display = 'none';
    }
  },

  async runSimulation(trips = 900) {
    try {
      const data = await ApiClient.runSimulation(trips);
      this.renderSimulationResults(data);
    } catch (err) {
      console.error("Failed to run traffic simulation:", err);
      alert(`Simulation failed: ${err.message}`);
    }
  },

  renderSimulationResults(data) {
    const base = data.baseline_result;
    const flow = data.flowsplit_result;

    // 1. Average transit time
    const baseTimeMin = (base.average_travel_time_seconds / 60).toFixed(1);
    const flowTimeMin = (flow.average_travel_time_seconds / 60).toFixed(1);
    document.getElementById('simBaselineAvgTime').textContent = `${baseTimeMin} min`;
    document.getElementById('simFlowSplitAvgTime').textContent = `${flowTimeMin} min`;
    document.getElementById('simTimeDeltaBadge').textContent = `−${data.travel_time_delta_percent.toFixed(0)}% Transit Time`;

    // 2. Queue Length
    document.getElementById('simBaselineQueue').textContent = `${Math.round(base.maximum_queue_vehicles)} vehicles`;
    document.getElementById('simFlowSplitQueue').textContent = `${Math.round(flow.maximum_queue_vehicles)} vehicles`;
    document.getElementById('simQueueDeltaBadge').textContent = `−${data.queue_reduction_percent.toFixed(0)}% Queue`;

    // 3. Overloaded segments
    document.getElementById('simBaselineOverloaded').textContent = `${base.overloaded_segments_count} segments`;
    document.getElementById('simFlowSplitOverloaded').textContent = `${flow.overloaded_segments_count} segments`;

    // 4. Volume Allocation Table
    const tbody = document.getElementById('simAllocationsTableBody');
    if (tbody) {
      tbody.innerHTML = '';
      (data.candidates || []).forEach(cand => {
        const baseAlloc = base.route_allocations[cand.id] || 0;
        const flowAlloc = flow.route_allocations[cand.id] || 0;
        const isShortcut = cand.id.includes('shortcut');

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${cand.name}</strong></td>
          <td>${isShortcut ? '250 veh/hr' : (cand.id.includes('arterial') ? '1,800 veh/hr' : '850 veh/hr')}</td>
          <td><span class="badge ${cand.suitability_score >= 75 ? 'badge-success' : 'badge-danger'}">${Math.round(cand.suitability_score)}/100</span></td>
          <td style="color: ${baseAlloc > 400 && isShortcut ? '#f87171' : 'inherit'}; font-weight: 700;">
            ${baseAlloc} trips (${Math.round((baseAlloc / data.total_hourly_demand_vehicles) * 100)}%)
          </td>
          <td style="color: #34d399; font-weight: 700;">
            ${flowAlloc} trips (${Math.round((flowAlloc / data.total_hourly_demand_vehicles) * 100)}%)
          </td>
          <td>
            <span class="badge ${isShortcut && baseAlloc > 250 ? 'badge-danger' : 'badge-success'}">
              ${isShortcut && baseAlloc > 250 ? 'GRIDLOCK IN BASELINE' : 'CAPACITY PROTECTED'}
            </span>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    // 5. Verdict text
    const verdictEl = document.getElementById('simVerdictText');
    if (verdictEl) {
      verdictEl.textContent = (
        `Simulation Results for ${data.total_hourly_demand_vehicles} Commuter Trips: ` +
        `Baseline navigation directed ${base.route_allocations['route-shortcut-elm-alley'] || 'most'} drivers onto the narrow residential shortcut ` +
        `causing severe spillover gridlock and an average delay of ${baseTimeMin} minutes. ` +
        `FlowSplit's capacity-aware algorithm prevented all overloaded segments, lowering maximum queue length by ${data.queue_reduction_percent.toFixed(0)}% ` +
        `and reducing transit time down to ${flowTimeMin} minutes.`
      );
    }
  },
};

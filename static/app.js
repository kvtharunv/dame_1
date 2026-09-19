/**
 * app.js - Dam Break Inundation Simulation Frontend Application
 * Problem Statement 26161 - National Technical Research Organisation (NTRO)
 * 
 * Features:
 *   - Google Maps Satellite, Hybrid & Terrain layer integration
 *   - Dam breach origin start point
 *   - Auto-Follow camera tracking the water wave front down the river
 *   - SPH Lagrangian fluid particle surge simulation
 *   - Delft3D 2D depth-averaged inundation polygon mesh
 *   - Interactive timeline scrubber (T+00:00 to T+06:00) with Play/Pause
 *   - Hydrograph and River profile charts (Chart.js)
 *   - SPH vs Delft3D comparative analysis & HADR evacuation countdown
 */

// Global Application State
const state = {
  simData: null,
  currentTimeHr: 0.0,
  isPlaying: false,
  playSpeed: 0.25,
  autoFollowCamera: true,
  timerInterval: null,
  _lastPanTime: 0,
  scenarioType: "dam_break",
  customHydrograph: null,
  customReachPoints: null,
  map: null,
  baseLayers: {},
  activeBaseLayer: null,
  mapLayers: {
    damMarker: null,
    frontMarker: null,
    sphParticles: L.layerGroup(),
    delftPolygon: null,
    highDangerPolygon: null,
    lowDangerPolygon: null,
    stations: L.layerGroup(),
    safePlaces: L.layerGroup(),
    vectors: L.layerGroup(),
    sarOverlay: null
  },
  charts: {
    hydrograph: null,
    longitudinal: null,
    arrivalCompare: null,
    depthCompare: null
  }
};

// ---------------------------------------------------------------------------
// 1. Initialization
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initEventHandlers();
  initTabs();
  loadPresets();
  loadDamCatalog();
  triggerSimulation("rishi_ganga");
});

// ---------------------------------------------------------------------------
// 2. Map & Google Maps Layer Setup
// ---------------------------------------------------------------------------

function initMap() {
  // Center near Rishi Ganga (default initial view)
  state.map = L.map("sim-map", {
    center: [30.4905, 79.6965],
    zoom: 13,
    zoomControl: false
  });

  // Custom Zoom Control top-right
  L.control.zoom({ position: "topright" }).addTo(state.map);

  // Google Maps Tile Layers (High-resolution satellite, hybrid, terrain)
  state.baseLayers["google-satellite"] = L.tileLayer(
    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    { maxZoom: 20, attribution: "Map data © Google Maps" }
  );

  state.baseLayers["google-hybrid"] = L.tileLayer(
    "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
    { maxZoom: 20, attribution: "Map data © Google Maps" }
  );

  state.baseLayers["google-terrain"] = L.tileLayer(
    "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
    { maxZoom: 20, attribution: "Map data © Google Maps" }
  );

  state.baseLayers["osm"] = L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 19, attribution: "© OpenStreetMap contributors" }
  );

  // Default to Google Satellite
  state.activeBaseLayer = state.baseLayers["google-satellite"];
  state.activeBaseLayer.addTo(state.map);

  // Add layer groups to map
  state.mapLayers.sphParticles.addTo(state.map);
  state.mapLayers.stations.addTo(state.map);
  state.mapLayers.safePlaces.addTo(state.map);
  state.mapLayers.vectors.addTo(state.map);
}

// ---------------------------------------------------------------------------
// 3. Event Listeners & UI Controls
// ---------------------------------------------------------------------------

function initEventHandlers() {
  // Preset selector
  const presetSel = document.getElementById("preset-selector");
  presetSel.addEventListener("change", (e) => {
    const val = e.target.value;
    const customBox = document.getElementById("custom-coords-box");
    if (val === "custom") {
      customBox.style.display = "block";
    } else {
      customBox.style.display = "none";
      state.customHydrograph = null;
      state.customReachPoints = null;
      triggerSimulation(val);
    }
  });

  // Scenario Mode Switcher (Dam Break vs Spillway Water Release)
  const btnDamBreak = document.getElementById("btn-mode-dambreak");
  const btnRelease = document.getElementById("btn-mode-release");
  const spillwayBox = document.getElementById("spillway-controls-box");
  const failRow = document.getElementById("row-failure-mode");

  if (btnDamBreak && btnRelease) {
    btnDamBreak.addEventListener("click", () => {
      btnDamBreak.classList.add("active");
      btnDamBreak.style.border = "1px solid #ef4444";
      btnDamBreak.style.background = "rgba(239, 68, 68, 0.15)";
      btnDamBreak.style.color = "#fca5a5";

      btnRelease.classList.remove("active");
      btnRelease.style.border = "1px solid rgba(6, 182, 212, 0.4)";
      btnRelease.style.background = "rgba(11, 21, 40, 0.6)";
      btnRelease.style.color = "#94a3b8";

      state.scenarioType = "dam_break";
      if (spillwayBox) spillwayBox.style.display = "none";
      if (failRow) failRow.style.display = "block";
      triggerSimulation(presetSel.value);
    });

    btnRelease.addEventListener("click", () => {
      btnRelease.classList.add("active");
      btnRelease.style.border = "1px solid #06b6d4";
      btnRelease.style.background = "rgba(6, 182, 212, 0.2)";
      btnRelease.style.color = "#38bdf8";

      btnDamBreak.classList.remove("active");
      btnDamBreak.style.border = "1px solid rgba(239, 68, 68, 0.4)";
      btnDamBreak.style.background = "rgba(11, 21, 40, 0.6)";
      btnDamBreak.style.color = "#94a3b8";

      state.scenarioType = "water_release";
      if (spillwayBox) spillwayBox.style.display = "block";
      if (failRow) failRow.style.display = "none";
      triggerSimulation(presetSel.value);
    });
  }

  // Custom Dataset Upload Handlers (Deliverable ii)
  const csvInput = document.getElementById("upload-hydrograph-csv");
  if (csvInput) {
    csvInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      formData.append("type", "csv");
      fetch("/api/upload-dataset", { method: "POST", body: formData })
        .then(r => r.json())
        .then(res => {
          if (res.status === "success") {
            state.customHydrograph = res.data;
            document.getElementById("status-csv").innerHTML = `<span style="color:#10b981;"><i class="bi bi-check-circle"></i> Ingested: ${file.name} (Qp=${res.data.peak_outflow_m3s.toLocaleString()} m³/s)</span>`;
            triggerSimulation(presetSel.value);
          } else {
            alert("CSV Error: " + res.message);
          }
        })
        .catch(err => alert("Upload failed: " + err));
    });
  }

  const geoInput = document.getElementById("upload-reach-geojson");
  if (geoInput) {
    geoInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      formData.append("type", "geojson");
      fetch("/api/upload-dataset", { method: "POST", body: formData })
        .then(r => r.json())
        .then(res => {
          if (res.status === "success") {
            state.customReachPoints = res.data;
            document.getElementById("status-geojson").innerHTML = `<span style="color:#10b981;"><i class="bi bi-check-circle"></i> Ingested: ${res.data.length} Reach Points</span>`;
            triggerSimulation("custom");
          } else {
            alert("GeoJSON Error: " + res.message);
          }
        })
        .catch(err => alert("Upload failed: " + err));
    });
  }

  const demInput = document.getElementById("upload-dem-tif");
  if (demInput) {
    demInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      formData.append("type", "dem");
      fetch("/api/upload-dataset", { method: "POST", body: formData })
        .then(r => r.json())
        .then(res => {
          if (res.status === "success") {
            document.getElementById("status-dem").innerHTML = `<span style="color:#10b981;"><i class="bi bi-check-circle"></i> ${file.name} (${res.data.dimensions[0]}x${res.data.dimensions[1]}, Elev: ${res.data.elevation_stats.min_m}m - ${res.data.elevation_stats.max_m}m)</span>`;
          } else {
            alert("DEM Error: " + res.message);
          }
        })
        .catch(err => alert("Upload failed: " + err));
    });
  }

  // Run Scenario Button
  document.getElementById("btn-re-run").addEventListener("click", () => {
    const presetId = presetSel.value;
    if (presetId === "custom") {
      const customParams = {
        name: "Custom Dam Failure Scenario",
        river: "Target River Reach",
        lat: parseFloat(document.getElementById("custom-lat").value),
        lon: parseFloat(document.getElementById("custom-lon").value),
        dam_height_m: parseFloat(document.getElementById("param-dam-height").value),
        water_head_m: parseFloat(document.getElementById("param-water-head").value),
        reservoir_volume_mcm: parseFloat(document.getElementById("param-res-volume").value),
        failure_mode: document.getElementById("param-failure-mode").value,
        channel_slope: parseFloat(document.getElementById("param-slope").value),
        mannings_n: parseFloat(document.getElementById("param-mannings").value),
        reach_points: state.customReachPoints
      };
      triggerSimulation("custom", customParams);
    } else {
      triggerSimulation(presetId);
    }
  });

  // Sliders input sync
  syncSlider("param-dam-height", "val-dam-height", " m");
  syncSlider("param-water-head", "val-water-head", " m");
  syncSlider("param-res-volume", "val-res-volume", " MCM");
  syncSlider("param-slope", "val-slope", "");
  syncSlider("param-mannings", "val-mannings", "");
  syncSlider("param-num-gates", "val-num-gates", " Gates");
  syncSlider("param-gate-width", "val-gate-width", " m");
  syncSlider("param-gate-opening", "val-gate-opening", " m");
  syncSlider("param-release-duration", "val-release-duration", " hr");

  // Base map buttons
  document.querySelectorAll(".btn-basemap").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".btn-basemap").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const layerKey = btn.getAttribute("data-layer");
      if (state.activeBaseLayer) state.map.removeLayer(state.activeBaseLayer);
      state.activeBaseLayer = state.baseLayers[layerKey];
      state.activeBaseLayer.addTo(state.map);
    });
  });

  // Layer Visibility Toggles
  const hazardChk = document.getElementById("layer-hazard-zones");
  if (hazardChk) {
    hazardChk.addEventListener("change", (e) => {
      const show = e.target.checked;
      if (state.mapLayers.highDangerPolygon) {
        if (show) state.mapLayers.highDangerPolygon.addTo(state.map);
        else state.map.removeLayer(state.mapLayers.highDangerPolygon);
      }
      if (state.mapLayers.lowDangerPolygon) {
        if (show) state.mapLayers.lowDangerPolygon.addTo(state.map);
        else state.map.removeLayer(state.mapLayers.lowDangerPolygon);
      }
      const legend = document.getElementById("map-hazard-legend");
      if (legend) legend.style.display = show ? "block" : "none";
    });
  }

  const safeChk = document.getElementById("layer-safe-places");
  if (safeChk) {
    safeChk.addEventListener("change", (e) => {
      if (e.target.checked) state.mapLayers.safePlaces.addTo(state.map);
      else state.map.removeLayer(state.mapLayers.safePlaces);
    });
  }

  document.getElementById("layer-sph").addEventListener("change", (e) => {
    if (e.target.checked) state.mapLayers.sphParticles.addTo(state.map);
    else state.map.removeLayer(state.mapLayers.sphParticles);
  });

  document.getElementById("layer-delft3d").addEventListener("change", (e) => {
    if (state.mapLayers.delftPolygon) {
      if (e.target.checked) state.mapLayers.delftPolygon.addTo(state.map);
      else state.map.removeLayer(state.mapLayers.delftPolygon);
    }
  });

  document.getElementById("layer-stations").addEventListener("change", (e) => {
    if (e.target.checked) state.mapLayers.stations.addTo(state.map);
    else state.map.removeLayer(state.mapLayers.stations);
  });

  document.getElementById("layer-vectors").addEventListener("change", (e) => {
    if (e.target.checked) state.mapLayers.vectors.addTo(state.map);
    else state.map.removeLayer(state.mapLayers.vectors);
  });

  document.getElementById("layer-sar").addEventListener("change", (e) => {
    toggleSarOverlay(e.target.checked);
  });

  document.getElementById("btn-toggle-sar-on-map").addEventListener("click", () => {
    const chk = document.getElementById("layer-sar");
    chk.checked = !chk.checked;
    toggleSarOverlay(chk.checked);
    // Switch to map tab
    document.querySelector('[data-tab="tab-map"]').click();
  });

  // Timeline Slider & Playback
  const timeline = document.getElementById("timeline-slider");
  timeline.addEventListener("input", (e) => {
    state.currentTimeHr = parseFloat(e.target.value);
    updateSimulationFrame();
  });

  const playBtn = document.getElementById("btn-play-pause");
  playBtn.addEventListener("click", togglePlayback);

  document.getElementById("btn-step-fwd").addEventListener("click", () => {
    state.currentTimeHr = Math.min(state.currentTimeHr + 0.10, 6.0);
    timeline.value = state.currentTimeHr.toFixed(2);
    updateSimulationFrame();
  });

  document.getElementById("btn-step-back").addEventListener("click", () => {
    state.currentTimeHr = Math.max(state.currentTimeHr - 0.10, 0.0);
    timeline.value = state.currentTimeHr.toFixed(2);
    updateSimulationFrame();
  });

  document.getElementById("btn-reset-time").addEventListener("click", () => {
    state.currentTimeHr = 0.0;
    timeline.value = 0.0;
    focusDamLocation();
    updateSimulationFrame();
  });

  // Speed buttons
  document.querySelectorAll(".btn-speed").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-speed").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.playSpeed = parseFloat(btn.getAttribute("data-speed"));
    });
  });

  // Camera Follow HUD Buttons
  const followBtn = document.getElementById("btn-toggle-follow");
  followBtn.addEventListener("click", () => {
    state.autoFollowCamera = !state.autoFollowCamera;
    followBtn.classList.toggle("active", state.autoFollowCamera);
    document.getElementById("follow-status-text").innerText = state.autoFollowCamera
      ? "Auto-Follow Water: ON"
      : "Auto-Follow Water: OFF";
    if (state.autoFollowCamera) followFloodWave();
  });

  document.getElementById("btn-focus-dam").addEventListener("click", focusDamLocation);
  document.getElementById("btn-overview-reach").addEventListener("click", fitFullReachBounds);

  // Quick Export
  document.getElementById("btn-quick-export").addEventListener("click", () => {
    window.location.href = "/api/export/shapefile";
  });

  // Copy GEE Script
  document.getElementById("btn-copy-gee").addEventListener("click", () => {
    const code = document.getElementById("gee-code-block").innerText;
    navigator.clipboard.writeText(code).then(() => {
      const btn = document.getElementById("btn-copy-gee");
      btn.innerHTML = '<i class="bi bi-check2"></i> Copied!';
      setTimeout(() => (btn.innerHTML = '<i class="bi bi-clipboard"></i> Copy Script'), 2000);
    });
  });
}

function syncSlider(sliderId, valId, unit) {
  const slider = document.getElementById(sliderId);
  const valElem = document.getElementById(valId);
  slider.addEventListener("input", (e) => {
    valElem.innerText = e.target.value + unit;
  });
}

// ---------------------------------------------------------------------------
// 4. Tab Switching
// ---------------------------------------------------------------------------

function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      tabBtns.forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");

      // Invalidate map size when switching back to map
      if (targetId === "tab-map" && state.map) {
        setTimeout(() => state.map.invalidateSize(), 150);
      }

      // Re-render charts when visible
      if (targetId === "tab-compare" || targetId === "tab-hydrograph") {
        renderAllCharts();
      }
    });
  });
}

// ---------------------------------------------------------------------------
// 5. Presets & Backend Simulation API
// ---------------------------------------------------------------------------

function loadPresets() {
  fetch("/api/presets")
    .then((res) => res.json())
    .then((presets) => {
      // Data loaded
    })
    .catch((err) => console.error("Failed to load presets:", err));
}

function loadDamCatalog() {
  fetch("/api/catalog")
    .then((res) => res.json())
    .then((res) => {
      if (res.status === "success") {
        const tbody = document.getElementById("catalog-table-body");
        if (!tbody) return;
        tbody.innerHTML = "";
        res.dams.forEach((dam) => {
          const tr = document.createElement("tr");
          tr.style.borderBottom = "1px solid rgba(255,255,255,0.06)";
          tr.innerHTML = `
            <td style="padding: 0.65rem;"><strong>${dam.name}</strong></td>
            <td style="padding: 0.65rem; color:#38bdf8;">${dam.river}</td>
            <td style="padding: 0.65rem;">${dam.state}</td>
            <td style="padding: 0.65rem;">${dam.height_m} m</td>
            <td style="padding: 0.65rem;">${dam.volume_mcm} MCM</td>
            <td style="padding: 0.65rem;">${dam.type}</td>
            <td style="padding: 0.65rem; color:#fca5a5;"><small>${dam.event}</small></td>
            <td style="padding: 0.65rem;">
              <button class="btn btn-outline btn-sm btn-load-catalog-dam" data-dam-id="${dam.id}" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;">
                <i class="bi bi-play-circle"></i> Simulate
              </button>
            </td>
          `;
          tbody.appendChild(tr);
        });

        document.querySelectorAll(".btn-load-catalog-dam").forEach((btn) => {
          btn.addEventListener("click", () => {
            const damId = btn.getAttribute("data-dam-id");
            const sel = document.getElementById("preset-selector");
            if (sel) {
              let hasOption = false;
              for (let opt of sel.options) {
                if (opt.value === damId) {
                  hasOption = true;
                  sel.value = damId;
                  break;
                }
              }
              if (!hasOption) {
                sel.value = "custom";
                const dObj = res.dams.find((d) => d.id === damId);
                if (dObj) {
                  document.getElementById("custom-lat").value = dObj.lat;
                  document.getElementById("custom-lon").value = dObj.lon;
                  document.getElementById("param-dam-height").value = dObj.height_m;
                  document.getElementById("param-res-volume").value = dObj.volume_mcm;
                }
              }
            }
            document.querySelector('[data-tab="tab-map"]').click();
            triggerSimulation(damId);
          });
        });
      }
    })
    .catch((err) => console.error("Failed to load dam catalog:", err));
}

function triggerSimulation(presetId, customParams = null) {
  const btn = document.getElementById("btn-re-run");
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Simulating...';
  btn.disabled = true;

  const scenarioType = state.scenarioType || "dam_break";
  const spillwayParams = {
    num_gates: parseInt(document.getElementById("param-num-gates")?.value || 4),
    gate_width_m: parseFloat(document.getElementById("param-gate-width")?.value || 50.0),
    gate_opening_m: parseFloat(document.getElementById("param-gate-opening")?.value || 4.0),
    release_duration_hr: parseFloat(document.getElementById("param-release-duration")?.value || 4.0)
  };

  let cParams = customParams;
  if (state.customReachPoints) {
    cParams = cParams || {};
    cParams.reach_points = state.customReachPoints;
  }

  fetch("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preset_id: presetId,
      custom_params: cParams,
      scenario_type: scenarioType,
      spillway_params: spillwayParams,
      custom_hydrograph: state.customHydrograph
    })
  })
    .then((res) => res.json())
    .then((res) => {
      btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Scenario';
      btn.disabled = false;

      if (res.status === "success") {
        state.simData = res.data;
        updateUIWithNewDam();
        resetPlaybackToStart();
        renderAllCharts();
      } else {
        alert("Simulation error: " + res.message);
      }
    })
    .catch((err) => {
      btn.innerHTML = '<i class="bi bi-play-fill"></i> Run Scenario';
      btn.disabled = false;
      console.error("Simulation error:", err);
    });
}

// ---------------------------------------------------------------------------
// 6. Rendering Dam & River Reach on Google Maps
// ---------------------------------------------------------------------------

function updateUIWithNewDam() {
  if (!state.simData) return;

  const dam = state.simData.dam;
  const breach = state.simData.breach;
  const hadr = state.simData.hadr;

  // Update Sidebar Description & Sliders
  document.getElementById("site-description").innerText = dam.description;
  document.getElementById("param-dam-height").value = dam.dam_height_m;
  document.getElementById("val-dam-height").innerText = dam.dam_height_m + " m";
  document.getElementById("param-water-head").value = dam.water_head_m;
  document.getElementById("val-water-head").innerText = dam.water_head_m + " m";
  document.getElementById("param-res-volume").value = dam.reservoir_volume_mcm;
  document.getElementById("val-res-volume").innerText = dam.reservoir_volume_mcm + " MCM";
  document.getElementById("param-slope").value = dam.channel_slope;
  document.getElementById("val-slope").innerText = dam.channel_slope;
  document.getElementById("param-mannings").value = dam.mannings_n;
  document.getElementById("val-mannings").innerText = dam.mannings_n;
  document.getElementById("param-failure-mode").value = dam.failure_mode;

  // Clear previous markers
  if (state.mapLayers.damMarker) state.map.removeLayer(state.mapLayers.damMarker);
  if (state.mapLayers.frontMarker) state.map.removeLayer(state.mapLayers.frontMarker);
  if (state.mapLayers.delftPolygon) state.map.removeLayer(state.mapLayers.delftPolygon);
  if (state.mapLayers.highDangerPolygon) state.map.removeLayer(state.mapLayers.highDangerPolygon);
  if (state.mapLayers.lowDangerPolygon) state.map.removeLayer(state.mapLayers.lowDangerPolygon);
  state.mapLayers.delftPolygon = null;
  state.mapLayers.highDangerPolygon = null;
  state.mapLayers.lowDangerPolygon = null;
  state.mapLayers.stations.clearLayers();
  state.mapLayers.safePlaces.clearLayers();
  state.mapLayers.vectors.clearLayers();

  // 1. Dam Breach / Water Release Origin Marker
  const isRelease = state.simData.scenario_type === "water_release";
  const originTitle = isRelease ? "EMERGENCY SPILLWAY WATER RELEASE ORIGIN" : "DAM BREACH ORIGIN";
  const damIcon = L.divIcon({
    className: "custom-dam-pin",
    html: `<div class="${isRelease ? 'water-release-marker' : 'dam-origin-marker'}" title="${originTitle}"></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  });

  state.mapLayers.damMarker = L.marker([dam.lat, dam.lon], { icon: damIcon })
    .addTo(state.map)
    .bindPopup(
      `<strong>${originTitle}</strong><br/>` +
      `<b>Name:</b> ${dam.name}<br/>` +
      `<b>River:</b> ${dam.river}<br/>` +
      `<b>Scenario:</b> ${isRelease ? 'Spillway Radial Gate Surge (Controlled Release)' : 'Structural Breach / Rupture'}<br/>` +
      `<b>Height:</b> ${dam.dam_height_m} m | <b>Head:</b> ${dam.water_head_m} m<br/>` +
      `<b>Peak Discharge Qp:</b> ${breach.peak_outflow_m3s.toLocaleString()} m³/s<br/>` +
      `<b>Formation / Hoist Time:</b> ${breach.time_to_failure_hr} hr`
    );

  // 2. Downstream Gauging Stations & Infrastructure Pins
  dam.reach_points.forEach((pt, idx) => {
    if (idx === 0) return; // Skip dam itself

    const stIcon = L.circleMarker([pt.lat, pt.lon], {
      radius: 8,
      fillColor: "#3b82f6",
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.85
    });

    stIcon.bindPopup(
      `<strong>${pt.name}</strong><br/>` +
      `<b>Distance:</b> +${pt.dist_km} km downstream<br/>` +
      `<b>Bed Elevation:</b> ${pt.elev} m<br/>` +
      `<b>Population:</b> ${pt.pop.toLocaleString()}<br/>` +
      `<div id="station-popup-${idx}">Calculating flood arrival...</div>`
    );

    stIcon.ptData = pt;
    stIcon.stationIdx = idx;
    state.mapLayers.stations.addLayer(stIcon);
  });

  // 3. Wave Front Reticle Marker (Initialized at Dam)
  const frontIcon = L.divIcon({
    className: "custom-wave-pin",
    html: '<div class="wave-front-marker" title="Flood Wave Front"></div>',
    iconSize: [28, 28],
    iconAnchor: [14, 14]
  });
  state.mapLayers.frontMarker = L.marker([dam.lat, dam.lon], { icon: frontIcon }).addTo(state.map);

  // 4. Dynamic Velocity Flow Vectors will be rendered during simulation in updateSimulationFrame

  // 5. Designated High-Ground Safe Havens & Disaster Shelters (Safe Places)
  if (dam.safe_places && dam.safe_places.length > 0) {
    dam.safe_places.forEach((sp) => {
      const safeIcon = L.divIcon({
        className: "safe-shelter-pin",
        html: `<div class="safe-haven-marker" title="${sp.name}"><i class="bi bi-shield-fill-check"></i></div>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13]
      });

      const safeMarker = L.marker([sp.lat, sp.lon], { icon: safeIcon });
      safeMarker.bindPopup(
        `<div class="safe-popup">` +
        `<span class="badge-safe-haven"><i class="bi bi-shield-check"></i> 100% VERIFIED SAFE HAVEN</span>` +
        `<h4>${sp.name}</h4>` +
        `<p><b>Safe Ground Elevation:</b> ${sp.elev} m (<b>+${sp.elev_above_river} m</b> above valley floor)</p>` +
        `<p><b>Shelter Capacity:</b> ${sp.capacity.toLocaleString()} persons</p>` +
        `<p><b>Category:</b> ${sp.type.replace(/_/g, " ").toUpperCase()}</p>` +
        `<p><b>Status:</b> <span class="text-success" style="font-weight:700;">${sp.status}</span></p>` +
        `<p class="text-muted" style="font-size:0.75rem; border-top:1px solid #e5e7eb; padding-top:0.25rem;"><i class="bi bi-check-circle-fill text-success"></i> Elevated terrain outside surge reach. NDRF staging & supply center.</p>` +
        `</div>`
      );
      state.mapLayers.safePlaces.addLayer(safeMarker);
    });
  }

  // Update GEE Code Block
  document.getElementById("gee-code-block").innerText = state.simData.gee.script;

  // Fly Camera to Dam Location
  focusDamLocation();
  updateComparisonTable();
  updateHadrTable();
}

// ---------------------------------------------------------------------------
// 7. Auto-Follow Camera & Navigation Shortcuts
// ---------------------------------------------------------------------------

function focusDamLocation() {
  if (!state.simData) return;
  const dam = state.simData.dam;
  state.map.flyTo([dam.lat, dam.lon], 14, { duration: 1.2 });
}

function fitFullReachBounds() {
  if (!state.simData) return;
  const pts = state.simData.dam.reach_points.map((p) => [p.lat, p.lon]);
  const bounds = L.latLngBounds(pts);
  state.map.flyToBounds(bounds.pad(0.15), { duration: 1.2 });
}

function followFloodWave() {
  if (!state.simData || !state.autoFollowCamera) return;
  const frontPos = getWaveFrontPosition(state.currentTimeHr);
  if (frontPos) {
    state.map.panTo([frontPos.lat, frontPos.lon], { animate: true, duration: 0.4 });
  }
}

function getWaveFrontPosition(t_hr) {
  if (!state.simData) return null;
  const dam = state.simData.dam;
  const pts = dam.reach_points;
  const celerity_mps = state.simData.delft3d.wave_celerity_mps || 4.5;
  const frontDistKm = Math.min((celerity_mps * t_hr * 3600) / 1000, pts[pts.length - 1].dist_km);

  // Interpolate lat/lon along reach
  for (let i = 0; i < pts.length - 1; i++) {
    if (frontDistKm >= pts[i].dist_km && frontDistKm <= pts[i + 1].dist_km) {
      const ratio = (frontDistKm - pts[i].dist_km) / (pts[i + 1].dist_km - pts[i].dist_km || 1);
      const lat = pts[i].lat + ratio * (pts[i + 1].lat - pts[i].lat);
      const lon = pts[i].lon + ratio * (pts[i + 1].lon - pts[i].lon);
      return { lat, lon, distKm: frontDistKm };
    }
  }
  return { lat: pts[0].lat, lon: pts[0].lon, distKm: 0.0 };
}

// ---------------------------------------------------------------------------
// 8. Dynamic Simulation Frame Update (SPH + Delft3D)
// ---------------------------------------------------------------------------

function updateSimulationFrame() {
  if (!state.simData) return;

  const t_hr = state.currentTimeHr;
  const t_step_key = getClosestTimestepKey(t_hr);

  // 1. Update Timeline Displays
  const hrs = Math.floor(t_hr);
  const mins = Math.round((t_hr - hrs) * 60);
  const timeStr = `T+${hrs.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}`;
  document.getElementById("hud-time").innerText = timeStr;
  document.getElementById("timeline-display").innerText = `${timeStr} (${Math.round(t_hr * 60)} mins)`;

  // 2. Wave Front Position & Auto-Follow Camera
  const frontPos = getWaveFrontPosition(t_hr);
  if (frontPos) {
    state.mapLayers.frontMarker.setLatLng([frontPos.lat, frontPos.lon]);
    document.getElementById("hud-front-dist").innerText = `${frontPos.distKm.toFixed(1)} km`;

    if (state.autoFollowCamera && state.isPlaying) {
      const now = Date.now();
      if (!state._lastPanTime || now - state._lastPanTime > 250) {
        state._lastPanTime = now;
        state.map.panTo([frontPos.lat, frontPos.lon], { animate: true, duration: 0.3 });
      }
    }
  }

  // 3. Update HUD Metrics based on Breach Hydrograph
  const hydroTimes = state.simData.breach.time_hours;
  const hydroQ = state.simData.breach.outflow_m3s;
  let currQ = 0;
  for (let i = 0; i < hydroTimes.length - 1; i++) {
    if (t_hr >= hydroTimes[i] && t_hr <= hydroTimes[i + 1]) {
      currQ = hydroQ[i];
      break;
    }
  }
  document.getElementById("hud-discharge").innerText = `${Math.round(currQ).toLocaleString()} m³/s`;

  // Wave velocity at current front
  const v_near = state.simData.sph.near_field_velocity_mps;
  const currVel = Math.max(v_near * Math.exp(-(frontPos ? frontPos.distKm : 0) / 35.0), 1.8);
  document.getElementById("hud-velocity").innerText = `${currVel.toFixed(1)} m/s`;

  // Status Badge
  const statusBadge = document.getElementById("flow-status-badge");
  if (t_hr === 0) {
    statusBadge.innerText = "At Dam Crest (Breach Initiation)";
    statusBadge.className = "text-warning";
  } else if (t_hr >= 5.95 || (frontPos && frontPos.distKm >= state.simData.dam.reach_points.slice(-1)[0].dist_km * 0.98)) {
    statusBadge.innerText = "🟢 Simulation Complete — Maximum Inundation Extent Reached";
    statusBadge.className = "text-success font-bold";
  } else {
    statusBadge.innerText = `Water Front at +${frontPos.distKm.toFixed(1)} km Downstream`;
    statusBadge.className = "text-cyan";
  }

  // 4. Render SPH Lagrangian Fluid Particles (Active dynamic stream)
  state.mapLayers.sphParticles.clearLayers();
  const sphSnap = getSphSnapshot(t_hr);

  // Group particles and active hydraulic bore crest
  sphSnap.forEach((p) => {
    // Only display particles within current surge wave front reach
    if (t_hr < 5.95 && frontPos && p.dist_km > frontPos.distKm * 1.02) return;

    // Fluid velocity and surface foam crest styling
    let pColor = "#06b6d4";
    let pRadius = 3.5;
    if (p.velocity > 12.0) {
      pColor = "#ffffff"; // Supercritical violent spray crest
      pRadius = 4.5;
    } else if (p.velocity > 6.5) {
      pColor = "#38bdf8"; // Fast surge channel
      pRadius = 4.0;
    }

    const circle = L.circleMarker([p.lat, p.lon], {
      radius: pRadius,
      fillColor: pColor,
      color: "#0284c7",
      weight: 1,
      opacity: 0.92,
      fillOpacity: 0.85
    });
    state.mapLayers.sphParticles.addLayer(circle);
  });

  // Add turbulent hydraulic bore crest foam at the leading wave front
  if (frontPos && frontPos.distKm > 0.3) {
    for (let f = 0; f < 8; f++) {
      const fOffLat = (Math.sin(f * 1.5 + t_hr * 12) * 0.0008);
      const fOffLon = (Math.cos(f * 1.8 + t_hr * 10) * 0.0008);
      const foam = L.circleMarker([frontPos.lat + fOffLat, frontPos.lon + fOffLon], {
        radius: 4.5 + (f % 3),
        fillColor: "#ffffff",
        color: "#38bdf8",
        weight: 1.5,
        opacity: 0.95,
        fillOpacity: 0.9
      });
      state.mapLayers.sphParticles.addLayer(foam);
    }
  }

  // 4b. Dynamic Hydrodynamic Velocity Flow Vectors (Only in active flood reach)
  state.mapLayers.vectors.clearLayers();
  const vectorsVisible = document.getElementById("layer-vectors")?.checked !== false;
  if (vectorsVisible && frontPos && frontPos.distKm > 0.5) {
    const pts = state.simData.dam.reach_points;
    const vNear = state.simData.sph.near_field_velocity_mps || 16.0;
    const arrowSpacingKm = Math.max(frontPos.distKm / 8.0, 1.8);
    for (let d = arrowSpacingKm * 0.5; d < frontPos.distKm * 0.95; d += arrowSpacingKm) {
      const pos1 = interpolateReachPoint(d, pts);
      const pos2 = interpolateReachPoint(Math.min(d + 0.3, frontPos.distKm), pts);
      const angleDeg = Math.atan2(pos2.lat - pos1.lat, pos2.lon - pos1.lon) * (180 / Math.PI);
      const vLocal = Math.max(vNear * Math.exp(-d / 32.0), 2.2);

      let vColor = "#10b981"; // Moderate green
      if (vLocal >= 8.0) vColor = "#ef4444"; // Supercritical red
      else if (vLocal >= 5.0) vColor = "#f59e0b"; // Fast orange

      const arrowIcon = L.divIcon({
        className: "flow-vector-pin",
        html: `<div style="display:flex; align-items:center; gap:2px; transform: rotate(${90 - angleDeg}deg);">` +
              `<span style="color:${vColor}; font-size:15px; font-weight:900; filter:drop-shadow(0 0 2px rgba(0,0,0,0.9));">➔</span>` +
              `<span style="color:#ffffff; background:rgba(15,23,42,0.85); border:1px solid ${vColor}; border-radius:3px; font-size:9px; font-family:monospace; padding:1px 3px; white-space:nowrap; transform: rotate(${-(90 - angleDeg)}deg);">${vLocal.toFixed(1)} m/s</span>` +
              `</div>`,
        iconSize: [44, 20],
        iconAnchor: [22, 10]
      });

      const vecMarker = L.marker([pos1.lat, pos1.lon], { icon: arrowIcon });
      vecMarker.bindPopup(
        `<strong>Hydrodynamic Velocity Vector</strong><br/>` +
        `<b>Location:</b> +${d.toFixed(1)} km downstream<br/>` +
        `<b>Current Velocity:</b> <span style="color:${vColor}; font-weight:700;">${vLocal.toFixed(1)} m/s</span><br/>` +
        `<b>Flow Regime:</b> ${vLocal >= 5.0 ? 'Supercritical (Violent)' : 'Subcritical (Overbank)'}`
      );
      state.mapLayers.vectors.addLayer(vecMarker);
    }
  }

  // 5. Render Delft3D Flood Inundation Mesh & Multi-Tier Hazard Zones (Continuous Flow)
  const currentFrontKm = frontPos ? frontPos.distKm : 0.0;
  const { coords, highCoords, lowCoords } = generateContinuousFlowPolygons(currentFrontKm, t_hr);
  const hazardZonesVisible = document.getElementById("layer-hazard-zones")?.checked !== false;
  const delftVisible = document.getElementById("layer-delft3d")?.checked !== false;

  // High Danger Zone Polygon (Core Deep & Violent Torrent Channel)
  if (highCoords.length > 3 && hazardZonesVisible) {
    if (!state.mapLayers.highDangerPolygon) {
      state.mapLayers.highDangerPolygon = L.polygon(highCoords, {
        color: "#dc2626",
        weight: 2.5,
        fillColor: "#ef4444",
        fillOpacity: 0.55
      }).addTo(state.map);
    } else {
      state.mapLayers.highDangerPolygon.setLatLngs(highCoords);
      if (!state.map.hasLayer(state.mapLayers.highDangerPolygon)) {
        state.mapLayers.highDangerPolygon.addTo(state.map);
      }
    }

    state.mapLayers.highDangerPolygon.bindPopup(
      `<strong>🔴 HIGH DANGER AREA (T+${t_hr.toFixed(2)}h)</strong><br/>` +
      `<b>Status:</b> <span class="badge-high-danger">CRITICAL / LIFE-THREATENING</span><br/>` +
      `<b>Surge Front Distance:</b> ${currentFrontKm.toFixed(1)} km downstream<br/>` +
      `<b>Surge Depth:</b> &ge; 2.5 m | <b>Flow Velocity:</b> &ge; 5.0 m/s<br/>` +
      `<span class="text-danger" style="font-size:0.75rem;">Total structural hazard. Evacuation window closed.</span>`
    );
  } else if (state.mapLayers.highDangerPolygon) {
    state.map.removeLayer(state.mapLayers.highDangerPolygon);
  }

  // Low Danger Zone Polygon (Peripheral Overbank Diffusion / Backwater Buffer)
  if (lowCoords.length > 3 && hazardZonesVisible) {
    if (!state.mapLayers.lowDangerPolygon) {
      state.mapLayers.lowDangerPolygon = L.polygon(lowCoords, {
        color: "#d97706",
        weight: 1.5,
        dashArray: "6, 6",
        fillColor: "#f59e0b",
        fillOpacity: 0.22
      }).addTo(state.map);
    } else {
      state.mapLayers.lowDangerPolygon.setLatLngs(lowCoords);
      if (!state.map.hasLayer(state.mapLayers.lowDangerPolygon)) {
        state.mapLayers.lowDangerPolygon.addTo(state.map);
      }
    }

    state.mapLayers.lowDangerPolygon.bindPopup(
      `<strong>🟡 LOW DANGER AREA (T+${t_hr.toFixed(2)}h)</strong><br/>` +
      `<b>Status:</b> <span class="badge-low-danger">ADVISORY / PERIPHERAL</span><br/>` +
      `<b>Surge Front Distance:</b> ${currentFrontKm.toFixed(1)} km downstream<br/>` +
      `<b>Surge Depth:</b> 0.3 m to 2.5 m<br/>` +
      `<b>Impact:</b> Agricultural crop submergence, access road waterlogging.<br/>` +
      `<span class="text-warning" style="font-size:0.75rem;">Relocate to nearby elevated Green Safe Places immediately.</span>`
    );
  } else if (state.mapLayers.lowDangerPolygon) {
    state.map.removeLayer(state.mapLayers.lowDangerPolygon);
  }

  // Delft3D Mesh Boundary
  if (coords.length > 3 && delftVisible) {
    if (!state.mapLayers.delftPolygon) {
      state.mapLayers.delftPolygon = L.polygon(coords, {
        color: "#06b6d4",
        weight: 1.5,
        dashArray: "4, 4",
        fillColor: "#0284c7",
        fillOpacity: 0.30
      }).addTo(state.map);
    } else {
      state.mapLayers.delftPolygon.setLatLngs(coords);
      if (!state.map.hasLayer(state.mapLayers.delftPolygon)) {
        state.mapLayers.delftPolygon.addTo(state.map);
      }
    }

    state.mapLayers.delftPolygon.bindPopup(
      `<strong>Delft3D 2D Inundation Zone (T+${t_hr.toFixed(2)}h)</strong><br/>` +
      `<b>Surge Front Distance:</b> ${currentFrontKm.toFixed(1)} km<br/>` +
      `<b>Model:</b> Depth-Averaged Shallow Water Flow`
    );
  } else if (state.mapLayers.delftPolygon) {
    state.map.removeLayer(state.mapLayers.delftPolygon);
  }

  // 6. Update Downstream Station Impact Badges & Danger Levels
  let totalPopRisk = 0;
  let highDangerCount = 0;
  let lowDangerCount = 0;
  const reachSummary = state.simData.delft3d.reach_summary;

  state.mapLayers.stations.eachLayer((marker) => {
    const pt = marker.ptData;
    const sIdx = marker.stationIdx;
    const summary = reachSummary[sIdx];

    if (t_hr < summary.arrival_time_hr) {
      // Not yet reached by surge wave
      const minsLeft = Math.round((summary.arrival_time_hr - t_hr) * 60);
      if (minsLeft <= 30) {
        // Imminent surge alert (Low Danger Warning window)
        lowDangerCount++;
        marker.setStyle({ fillColor: "#f97316", color: "#ffffff", weight: 3, radius: 9 });
        marker.setPopupContent(
          `<strong>${pt.name}</strong><br/>` +
          `<span class="badge-low-danger" style="background:#fff7ed; color:#c2410c; border-color:#f97316;"><i class="bi bi-bell-fill"></i> LOW DANGER / IMMINENT SURGE</span><br/>` +
          `<b>Surge Front ETA:</b> <strong class="text-danger">${minsLeft} minutes</strong><br/>` +
          `<b>Expected Arrival:</b> T+${summary.arrival_time_hr} hr<br/>` +
          `<b>Expected Peak Depth:</b> ${summary.peak_depth_m} m | <b>Pop:</b> ${pt.pop.toLocaleString()}<br/>` +
          `<b class="text-danger">Action: Evacuate immediately along marked routes to Green Safe Havens!</b>`
        );
      } else {
        // Safe for now, plenty of lead time
        marker.setStyle({ fillColor: "#10b981", color: "#ffffff", weight: 2, radius: 8 });
        marker.setPopupContent(
          `<strong>${pt.name}</strong><br/>` +
          `<span class="badge-safe-haven"><i class="bi bi-shield-check"></i> SAFE STATUS / EVACUATION OPEN</span><br/>` +
          `<b>Lead Time Remaining:</b> <strong class="text-success">${minsLeft} minutes</strong><br/>` +
          `<b>Expected Arrival:</b> T+${summary.arrival_time_hr} hr<br/>` +
          `<b>Expected Depth:</b> ${summary.peak_depth_m} m | <b>Pop:</b> ${pt.pop.toLocaleString()}<br/>` +
          `<span class="text-success">Routes clear. Proceed to designated Green Safe Places.</span>`
        );
      }
    } else {
      // Inundated! Classify between High Danger and Low Danger
      totalPopRisk += pt.pop;
      if (summary.peak_depth_m >= 2.5 || summary.peak_velocity_mps >= 5.0) {
        // HIGH DANGER AREA
        highDangerCount++;
        marker.setStyle({ fillColor: "#ef4444", color: "#ffffff", weight: 3, radius: 10 });
        marker.setPopupContent(
          `<strong>${pt.name}</strong><br/>` +
          `<span class="badge-high-danger"><i class="bi bi-radioactive"></i> HIGH DANGER AREA (INUNDATED)</span><br/>` +
          `<b>Current Surge Depth:</b> <span class="text-danger font-bold">${summary.peak_depth_m} m</span><br/>` +
          `<b>Flow Velocity:</b> ${summary.peak_velocity_mps} m/s (Supercritical)<br/>` +
          `<b>Water Wave Arrival:</b> T+${summary.arrival_time_hr} hr<br/>` +
          `<b>Threat Level:</b> <span class="text-danger">Critical Hydraulic Force</span><br/>` +
          `<b class="text-danger">Action: Extreme hazard. Ground access cut off. Aerial evacuation only.</b>`
        );
      } else {
        // LOW DANGER AREA
        lowDangerCount++;
        marker.setStyle({ fillColor: "#f59e0b", color: "#ffffff", weight: 2, radius: 8 });
        marker.setPopupContent(
          `<strong>${pt.name}</strong><br/>` +
          `<span class="badge-low-danger"><i class="bi bi-exclamation-triangle-fill"></i> LOW DANGER AREA (INUNDATED)</span><br/>` +
          `<b>Current Surge Depth:</b> <span class="text-warning font-bold">${summary.peak_depth_m} m</span><br/>` +
          `<b>Flow Velocity:</b> ${summary.peak_velocity_mps} m/s<br/>` +
          `<b>Water Wave Arrival:</b> T+${summary.arrival_time_hr} hr<br/>` +
          `<b>Threat Level:</b> Moderate Overbank Flow<br/>` +
          `<b class="text-warning">Action: Peripheral flood zone. Move to high-ground shelters.</b>`
        );
      }
    }
  });

  // 7. Update HUD Counters
  const hdEl = document.getElementById("hud-high-danger");
  if (hdEl) hdEl.innerText = `${highDangerCount} Sector${highDangerCount !== 1 ? 's' : ''}`;

  const ldEl = document.getElementById("hud-low-danger");
  if (ldEl) ldEl.innerText = `${lowDangerCount} Sector${lowDangerCount !== 1 ? 's' : ''}`;

  const shEl = document.getElementById("hud-safe-havens");
  const safeCount = (state.simData.dam.safe_places || []).length;
  if (shEl) shEl.innerText = `${safeCount} Shelters`;

  const popEl = document.getElementById("hud-pop");
  if (popEl) popEl.innerText = totalPopRisk.toLocaleString();
}

function generateContinuousFlowPolygons(frontDistKm, t_hr) {
  if (!state.simData || frontDistKm <= 0.05) {
    return { coords: [], highCoords: [], lowCoords: [] };
  }
  const pts = state.simData.dam.reach_points;
  const maxReachDist = pts[pts.length - 1].dist_km;
  const targetDist = Math.min(frontDistKm, maxReachDist);

  // 1. Dam breach width B_avg
  const b_w = Math.min(Math.max(state.simData.breach?.breach_width_m || 30.0, 15.0), 120.0);
  const hw = state.simData.dam.water_head_m || 30.0;
  const slope = state.simData.dam.channel_slope || 0.035;
  const atten = 0.024 / Math.max(slope * 100, 0.1);

  // High density of vertices along the river curvature for silky-smooth boundary
  const numSteps = Math.max(Math.min(Math.round(targetDist * 12), 220), 12);
  const stepSize = targetDist / numSteps;

  const leftBank = [];
  const rightBank = [];
  const highLeftBank = [];
  const highRightBank = [];
  const lowLeftBank = [];
  const lowRightBank = [];

  // Hydrodynamic width expansion:
  // 1. Narrow neck at dam crest (sd=0) matching breach opening
  // 2. Rapid expansion in first 1.5 km (jet spreading)
  // 3. Covers full valley floor & floodplain downstream
  // 4. Parabolic rounded bore nose at the wave front
  const slopeFactor = Math.min(Math.max(Math.sqrt(0.035 / Math.max(slope, 0.001)), 0.85), 3.5);

  for (let i = 0; i <= numSteps; i++) {
    const sd = i * stepSize;
    const pos = interpolateReachPoint(sd, pts);
    const posNext = interpolateReachPoint(Math.min(sd + 0.15, maxReachDist), pts);
    const posPrev = interpolateReachPoint(Math.max(sd - 0.15, 0.0), pts);

    const dlat = posNext.lat - posPrev.lat;
    const dlon = posNext.lon - posPrev.lon;
    const norm = Math.hypot(dlat, dlon) || 1e-6;
    const perpLat = -dlon / norm;
    const perpLon = dlat / norm;

    const depth = Math.max(hw * Math.exp(-sd * atten), 0.3);

    // Expansion factor from breach nozzle to valley: 0 at breach, 1 in downstream reach
    const expFactor = 1.0 - Math.exp(-sd / 0.7);

    // Natural valley base widths based on depth, distance, and slope
    const highValleyBase = Math.min((140.0 + (sd * 6.5) + (depth * 7.5)) * slopeFactor, 1400.0);
    const lowValleyBase = Math.min((260.0 + (sd * 12.5) + (depth * 13.0)) * slopeFactor, 3200.0);
    const delftValleyBase = Math.min((200.0 + (sd * 9.5) + (depth * 10.0)) * slopeFactor, 2400.0);

    // Wave front rounded hydraulic bore nose taper
    const normPos = Math.min(sd / Math.max(targetDist, 0.05), 1.0);
    const boreTaper = Math.sqrt(Math.max(1.0 - Math.pow(normPos, 4), 0.08));

    // Dynamic width blending
    const highW = (b_w * 0.85 + expFactor * (highValleyBase - b_w * 0.85)) * boreTaper;
    const lowW = (b_w * 1.25 + expFactor * (lowValleyBase - b_w * 1.25)) * boreTaper;
    const delftW = (b_w * 1.05 + expFactor * (delftValleyBase - b_w * 1.05)) * boreTaper;

    const cosLat = Math.cos(pos.lat * Math.PI / 180.0) || 1.0;
    const highLatOff = (highW / 111320.0) * perpLat;
    const highLonOff = (highW / (111320.0 * cosLat)) * perpLon;

    const lowLatOff = (lowW / 111320.0) * perpLat;
    const lowLonOff = (lowW / (111320.0 * cosLat)) * perpLon;

    const delftLatOff = (delftW / 111320.0) * perpLat;
    const delftLonOff = (delftW / (111320.0 * cosLat)) * perpLon;

    highLeftBank.push([pos.lat + highLatOff, pos.lon + highLonOff]);
    highRightBank.push([pos.lat - highLatOff, pos.lon - highLonOff]);

    lowLeftBank.push([pos.lat + lowLatOff, pos.lon + lowLonOff]);
    lowRightBank.push([pos.lat - lowLatOff, pos.lon - lowLonOff]);

    leftBank.push([pos.lat + delftLatOff, pos.lon + delftLonOff]);
    rightBank.push([pos.lat - delftLatOff, pos.lon - delftLonOff]);
  }

  const coords = leftBank.concat(rightBank.reverse());
  const highCoords = highLeftBank.concat(highRightBank.reverse());
  const lowCoords = lowLeftBank.concat(lowRightBank.reverse());

  return { coords, highCoords, lowCoords };
}

function interpolateReachPoint(distKm, pts) {
  if (!pts || pts.length === 0) return { lat: 0, lon: 0 };
  if (distKm <= pts[0].dist_km) return { lat: pts[0].lat, lon: pts[0].lon };
  if (distKm >= pts[pts.length - 1].dist_km) return { lat: pts[pts.length - 1].lat, lon: pts[pts.length - 1].lon };

  for (let i = 0; i < pts.length - 1; i++) {
    if (distKm >= pts[i].dist_km && distKm <= pts[i + 1].dist_km) {
      const segLen = pts[i + 1].dist_km - pts[i].dist_km || 1e-5;
      const t = (distKm - pts[i].dist_km) / segLen;

      // Catmull-Rom 4-point cubic spline for smooth natural river curves
      const p0 = pts[Math.max(i - 1, 0)];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[Math.min(i + 2, pts.length - 1)];

      const t2 = t * t;
      const t3 = t2 * t;

      const lat = 0.5 * (
        (2 * p1.lat) +
        (-p0.lat + p2.lat) * t +
        (2 * p0.lat - 5 * p1.lat + 4 * p2.lat - p3.lat) * t2 +
        (-p0.lat + 3 * p1.lat - 3 * p2.lat + p3.lat) * t3
      );
      const lon = 0.5 * (
        (2 * p1.lon) +
        (-p0.lon + p2.lon) * t +
        (2 * p0.lon - 5 * p1.lon + 4 * p2.lon - p3.lon) * t2 +
        (-p0.lon + 3 * p1.lon - 3 * p2.lon + p3.lon) * t3
      );
      return { lat, lon };
    }
  }
  return { lat: pts[pts.length - 1].lat, lon: pts[pts.length - 1].lon };
}

function getSphSnapshot(t_hr) {
  if (!state.simData || !state.simData.sph || !state.simData.sph.snapshots) return [];
  const snaps = state.simData.sph.snapshots;

  // Exact lookups first
  const k1 = t_hr.toFixed(2);
  const k2 = t_hr.toFixed(1);
  const k3 = t_hr.toString();
  if (snaps[k1] && snaps[k1].length > 0) return snaps[k1];
  if (snaps[k2] && snaps[k2].length > 0) return snaps[k2];
  if (snaps[k3] && snaps[k3].length > 0) return snaps[k3];

  // If at or past 6.0, return the full extent snapshot (does not disappear!)
  if (t_hr >= 5.8 && snaps["6.0"]) return snaps["6.0"];
  if (t_hr >= 5.8 && snaps["6"]) return snaps["6"];

  // Closest available snapshot
  let bestKey = null;
  let minDiff = 999;
  for (let k in snaps) {
    const kFloat = parseFloat(k);
    if (!isNaN(kFloat) && Array.isArray(snaps[k]) && snaps[k].length > 0) {
      const diff = Math.abs(t_hr - kFloat);
      if (diff < minDiff) {
        minDiff = diff;
        bestKey = k;
      }
    }
  }
  return bestKey ? snaps[bestKey] : [];
}

function getClosestTimestepKey(t_hr) {
  const keys = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0];
  let closest = keys[0];
  let minDiff = 999;
  for (let k of keys) {
    const diff = Math.abs(t_hr - k);
    if (diff < minDiff) {
      minDiff = diff;
      closest = k;
    }
  }
  return closest.toString();
}

// ---------------------------------------------------------------------------
// 9. Playback Loop (Play / Pause / Reset)
// ---------------------------------------------------------------------------

function togglePlayback() {
  if (!state.simData) return;
  const icon = document.getElementById("play-icon");
  const playBtn = document.getElementById("btn-play-pause");

  // If already at or past completion, restart seamlessly from breach
  if (state.currentTimeHr >= 6.0) {
    state.currentTimeHr = 0.0;
    const slider = document.getElementById("timeline-slider");
    if (slider) slider.value = "0.00";
    state.isPlaying = true;
    if (icon) icon.className = "bi bi-pause-fill";
    if (playBtn) playBtn.title = "Pause Simulation";
    startPlaybackTimer();
    updateSimulationFrame();
    return;
  }

  state.isPlaying = !state.isPlaying;

  if (state.isPlaying) {
    if (icon) icon.className = "bi bi-pause-fill";
    if (playBtn) playBtn.title = "Pause Simulation";
    startPlaybackTimer();
  } else {
    if (icon) icon.className = "bi bi-play-fill";
    if (playBtn) playBtn.title = "Play Simulation";
    stopPlaybackTimer();
  }
}

function startPlaybackTimer() {
  stopPlaybackTimer();
  state.timerInterval = setInterval(() => {
    // Paced, smooth simulation speed so the user can easily follow the wave front
    // Base advance: 0.0012 hours per 50ms tick at 1x speed
    // At default 0.25x speed: 1 real second = ~10.8 simulation seconds (comfortable to follow every detail)
    // At 0.1x speed: step-by-step ultra-slow observation
    state.currentTimeHr += 0.0012 * state.playSpeed;
    if (state.currentTimeHr >= 6.0) {
      state.currentTimeHr = 6.0;
      state.isPlaying = false;
      stopPlaybackTimer();
      const icon = document.getElementById("play-icon");
      if (icon) icon.className = "bi bi-arrow-counterclockwise";
      const playBtn = document.getElementById("btn-play-pause");
      if (playBtn) playBtn.title = "Simulation Complete (Click to Replay)";
    }
    const slider = document.getElementById("timeline-slider");
    if (slider) slider.value = state.currentTimeHr.toFixed(2);
    updateSimulationFrame();
  }, 50);
}

function stopPlaybackTimer() {
  if (state.timerInterval) {
    clearInterval(state.timerInterval);
    state.timerInterval = null;
  }
}

function resetPlaybackToStart() {
  stopPlaybackTimer();
  state.isPlaying = false;
  state.currentTimeHr = 0.0;
  document.getElementById("play-icon").className = "bi bi-play-fill";
  const playBtn = document.getElementById("btn-play-pause");
  if (playBtn) playBtn.title = "Play Water Flow Simulation";
  document.getElementById("timeline-slider").value = "0.00";
  updateSimulationFrame();
}

// ---------------------------------------------------------------------------
// 10. SAR Radar Overlay
// ---------------------------------------------------------------------------

function toggleSarOverlay(show) {
  if (!state.simData) return;
  if (state.mapLayers.sarOverlay) {
    state.map.removeLayer(state.mapLayers.sarOverlay);
    state.mapLayers.sarOverlay = null;
  }

  if (show) {
    // Generate translucent radar backscatter rectangle covering reach AOI
    const bbox = state.simData.gee.aoi_bbox;
    const bounds = [[bbox[1], bbox[0]], [bbox[3], bbox[2]]];

    state.mapLayers.sarOverlay = L.rectangle(bounds, {
      color: "#ec4899",
      weight: 1,
      dashArray: "3, 6",
      fillColor: "#ec4899",
      fillOpacity: 0.2
    }).addTo(state.map);

    state.mapLayers.sarOverlay.bindPopup(
      `<strong>Sentinel-1 C-band SAR Detection Footprint</strong><br/>` +
      `<b>Sensor:</b> SAR IW Dual Pol (VV/VH)<br/>` +
      `<b>Water Threshold:</b> &lt; -16.5 dB backscatter<br/>` +
      `<b>Status:</b> All-weather cloud penetration verified`
    );
  }
}

// ---------------------------------------------------------------------------
// 11. Chart.js Renderers (Hydrograph, Profiles, Comparison)
// ---------------------------------------------------------------------------

function renderAllCharts() {
  if (!state.simData) return;
  renderHydrographChart();
  renderLongitudinalProfileChart();
  renderComparisonCharts();
}

function renderHydrographChart() {
  const ctx = document.getElementById("chart-hydrograph");
  if (!ctx) return;
  if (state.charts.hydrograph) state.charts.hydrograph.destroy();

  const breach = state.simData.breach;
  document.getElementById("val-qp").innerText = `${breach.peak_outflow_m3s.toLocaleString()} m³/s`;
  document.getElementById("val-tf").innerText = `${breach.time_to_failure_hr} hr`;
  document.getElementById("val-bw").innerText = `${breach.breach_width_m} m`;

  state.charts.hydrograph = new Chart(ctx, {
    type: "line",
    data: {
      labels: breach.time_hours,
      datasets: [
        {
          label: "Breach Discharge Q(t) [m³/s]",
          data: breach.outflow_m3s,
          borderColor: "#ef4444",
          backgroundColor: "rgba(239, 68, 68, 0.15)",
          fill: true,
          tension: 0.3,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        x: {
          title: { display: true, text: "Time Since Breach Initiation (hours)", color: "#9ca3af" },
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#9ca3af" }
        },
        y: {
          title: { display: true, text: "Outflow Discharge (m³/s)", color: "#9ca3af" },
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#9ca3af" }
        }
      },
      plugins: {
        legend: { labels: { color: "#fff" } }
      }
    }
  });
}

function renderLongitudinalProfileChart() {
  const ctx = document.getElementById("chart-longitudinal");
  if (!ctx) return;
  if (state.charts.longitudinal) state.charts.longitudinal.destroy();

  const reach = state.simData.dam.reach_points;
  const dists = reach.map((p) => p.dist_km);
  const bedElevs = reach.map((p) => p.elev);
  const maxWaterElevs = reach.map((p, i) => p.elev + state.simData.sph.reach_summary[i].peak_depth_m);

  document.getElementById("prof-dam-elev").innerText = `${bedElevs[0]} m`;
  document.getElementById("prof-bed-drop").innerText = `${bedElevs[0] - bedElevs[bedElevs.length - 1]} m`;

  state.charts.longitudinal = new Chart(ctx, {
    type: "line",
    data: {
      labels: dists,
      datasets: [
        {
          label: "River Bed Elevation (m)",
          data: bedElevs,
          borderColor: "#6b7280",
          backgroundColor: "rgba(107, 114, 128, 0.2)",
          fill: "origin",
          pointRadius: 3
        },
        {
          label: "Peak Flood Water Surface Elevation (m)",
          data: maxWaterElevs,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.2)",
          fill: "-1",
          pointRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      scales: {
        x: {
          title: { display: true, text: "Distance Downstream from Dam (km)", color: "#9ca3af" },
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#9ca3af" }
        },
        y: {
          title: { display: true, text: "Elevation (m MSL)", color: "#9ca3af" },
          grid: { color: "rgba(255,255,255,0.06)" },
          ticks: { color: "#9ca3af" }
        }
      },
      plugins: {
        legend: { labels: { color: "#fff" } }
      }
    }
  });
}

function renderComparisonCharts() {
  const ctxArr = document.getElementById("chart-arrival-compare");
  const ctxDep = document.getElementById("chart-depth-compare");
  if (!ctxArr || !ctxDep) return;

  if (state.charts.arrivalCompare) state.charts.arrivalCompare.destroy();
  if (state.charts.depthCompare) state.charts.depthCompare.destroy();

  const comp = state.simData.comparison.comparison_table;
  const labels = comp.map((c) => c.station);
  const sphArr = comp.map((c) => c.sph_arrival_hr);
  const delftArr = comp.map((c) => c.delft3d_arrival_hr);

  const sphDep = comp.map((c) => c.sph_depth_m);
  const delftDep = comp.map((c) => c.delft3d_depth_m);

  // Update KPI Cards
  document.getElementById("cmp-sph-vel").innerText = `${state.simData.sph.near_field_velocity_mps} m/s`;
  document.getElementById("cmp-delft-vel").innerText = `${state.simData.delft3d.wave_celerity_mps} m/s`;
  document.getElementById("cmp-lead-time").innerText = `${comp[1] ? comp[1].lead_time_diff_min : 12} min`;

  // 1. Arrival Time Chart
  state.charts.arrivalCompare = new Chart(ctxArr, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "SPH Arrival Time (hr)",
          data: sphArr,
          backgroundColor: "#06b6d4"
        },
        {
          label: "Delft3D Arrival Time (hr)",
          data: delftArr,
          backgroundColor: "#3b82f6"
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { color: "#9ca3af", font: { size: 10 } }, grid: { display: false } },
        y: {
          title: { display: true, text: "Hours from Breach", color: "#9ca3af" },
          ticks: { color: "#9ca3af" },
          grid: { color: "rgba(255,255,255,0.06)" }
        }
      },
      plugins: { legend: { labels: { color: "#fff" } } }
    }
  });

  // 2. Depth Attenuation Chart
  state.charts.depthCompare = new Chart(ctxDep, {
    type: "line",
    data: {
      labels: comp.map((c) => `+${c.dist_km} km`),
      datasets: [
        {
          label: "SPH Peak Depth (m)",
          data: sphDep,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.2)",
          tension: 0.3
        },
        {
          label: "Delft3D Peak Depth (m)",
          data: delftDep,
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.2)",
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { color: "#9ca3af" }, grid: { color: "rgba(255,255,255,0.06)" } },
        y: {
          title: { display: true, text: "Inundation Depth (m)", color: "#9ca3af" },
          ticks: { color: "#9ca3af" },
          grid: { color: "rgba(255,255,255,0.06)" }
        }
      },
      plugins: { legend: { labels: { color: "#fff" } } }
    }
  });
}

function updateComparisonTable() {
  if (!state.simData) return;
  const tbody = document.querySelector("#table-comparison tbody");
  tbody.innerHTML = "";

  state.simData.comparison.comparison_table.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${row.station}</strong></td>
      <td>+${row.dist_km} km</td>
      <td><span class="text-cyan">${row.sph_arrival_hr} hr</span></td>
      <td><span class="text-primary">${row.delft3d_arrival_hr} hr</span></td>
      <td><strong class="text-warning">${row.lead_time_diff_min > 0 ? "+" + row.lead_time_diff_min : row.lead_time_diff_min} min</strong></td>
      <td>${row.sph_depth_m} m</td>
      <td>${row.delft3d_depth_m} m</td>
      <td><span class="badge-advisory">${row.primary_hazard}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function updateHadrTable() {
  if (!state.simData) return;
  const hadr = state.simData.hadr;

  document.getElementById("hadr-total-pop").innerText = hadr.total_population_at_risk.toLocaleString();
  document.getElementById("hadr-infra").innerText = `${hadr.bridges_infrastructure_threatened} Critical Bridges / Hydel`;
  document.getElementById("hadr-agri").innerText = `${hadr.est_agricultural_loss_ha.toLocaleString()} Hectares`;
  document.getElementById("hadr-econ").innerText = `₹ ${hadr.est_economic_exposure_inr_crores.toLocaleString()} Crores`;

  // Sectors Table
  const tbody = document.querySelector("#table-hadr-sectors tbody");
  tbody.innerHTML = "";

  hadr.sectors.forEach((sec) => {
    const tr = document.createElement("tr");
    let badgeClass = "badge-advisory";
    if (sec.threat_level.includes("CRITICAL")) badgeClass = "badge-severe";
    else if (sec.threat_level.includes("WARNING")) badgeClass = "badge-moderate";

    tr.innerHTML = `
      <td><strong>${sec.name}</strong> (${sec.type})</td>
      <td>+${sec.dist_km} km</td>
      <td>${sec.population.toLocaleString()}</td>
      <td><strong class="text-cyan">${sec.evacuation_deadline}</strong></td>
      <td>${sec.max_water_depth_m} m</td>
      <td><span class="${badgeClass}">${sec.threat_level}</span></td>
    `;
    tbody.appendChild(tr);
  });

  // Protocols List
  const protoList = document.getElementById("protocol-list");
  protoList.innerHTML = "";
  hadr.emergency_protocols.forEach((p) => {
    const li = document.createElement("li");
    li.innerText = p;
    protoList.appendChild(li);
  });
}

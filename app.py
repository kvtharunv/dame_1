"""
app.py
======
Streamlit Dashboard for Dam Break Inundation Modelling.
National Technical Research Organisation (NTRO) - Problem Statement 26161.

Coupled with simulation_engine.py for hydrodynamic calculations:
  - SPH (Smoothed Particle Hydrodynamics)
  - Delft3D 2D Depth-Averaged Inundation
  - Real Indian Dam & River Datasets
  - HADR Loss Assessment & Google Earth Engine (GEE)
"""

import os
import io
import json
import streamlit as st
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

import simulation_engine as se

st.set_page_config(
    page_title="Dam Break Inundation Modelling | NTRO 26161",
    layout="wide",
    page_icon="🌊"
)

# Custom Banner & Links
st.markdown(
    """
    <div style="background: linear-gradient(90deg, #0b1528, #112240); padding: 1.25rem; border-radius: 10px; border-left: 5px solid #06b6d4; margin-bottom: 1.5rem;">
        <h2 style="color: #f3f4f6; margin: 0; font-size: 1.6rem;">🌊 Dam Break Hydrodynamic Inundation Modelling Platform</h2>
        <p style="color: #9ca3af; margin: 0.35rem 0 0.75rem 0; font-size: 0.9rem;">
            NTRO Problem Statement 26161 · Smoothed Particle Hydrodynamics (SPH) & Delft3D Coupled Simulation · Indian River Basins
        </p>
        <a href="http://localhost:5000" target="_blank" style="background: #06b6d4; color: #041018; font-weight: 700; padding: 0.45rem 0.9rem; border-radius: 6px; text-decoration: none; font-size: 0.85rem; display: inline-block;">
            🚀 Open 60-FPS Interactive Web Simulation (Google Maps & Follow Water Flow)
        </a>
    </div>
    """,
    unsafe_allow_html=True
)

# Sidebar: Inputs
st.sidebar.title("Simulation Inputs")

preset_options = {
    "rishi_ganga": "Rishi Ganga (Chamoli 2021 Disaster) - UK",
    "phuktal": "Phuktal River Landslide Dam (Zanskar 2015) - Ladakh",
    "wapriyang": "Wapriyang River Blockage (Nov 2021) - Arunachal",
    "kashmir_jhelum": "Jhelum River / Srinagar (2014 Flood) - J&K",
    "subansiri": "Subansiri Lower Dam - Assam / Arunachal",
    "tehri": "Tehri Dam (Bhagirathi River) - UK",
    "mullaperiyar": "Mullaperiyar Dam (Periyar River) - Kerala/TN",
    "kosi": "Kosi River Embankment (Kusaha) - Bihar",
    "custom": "⚙️ Custom Dam & River Parameters"
}

selected_preset = st.sidebar.selectbox(
    "1. Select Indian River & Dam Site",
    list(preset_options.keys()),
    format_func=lambda k: preset_options[k]
)

# Scenario Mode Selection
scenario_mode = st.sidebar.radio(
    "2. Simulation Scenario Mode",
    ["🔴 Dam Break (Structural Rupture)", "🌊 Spillway Water Release (Radial Gate Surge)"],
    index=0
)
is_release = "Spillway Water Release" in scenario_mode

if selected_preset != "custom":
    site = se.INDIAN_DAM_PRESETS[selected_preset]
    st.sidebar.info(site.description)
    dam_h_default = site.dam_height_m
    hw_default = site.water_head_m
    vol_default = site.reservoir_volume_mcm
    slope_default = site.channel_slope
    n_default = site.mannings_n
    fail_default = site.failure_mode
else:
    dam_h_default = 40.0
    hw_default = 32.0
    vol_default = 25.0
    slope_default = 0.015
    n_default = 0.035
    fail_default = "overtopping"

st.sidebar.subheader("3. Dam & Reservoir Specifications")
dam_height = st.sidebar.slider("Dam Structural Height (m)", 5.0, 270.0, float(dam_h_default), 1.0)
water_head = st.sidebar.slider("Water Head above Breach Invert (m)", 2.0, float(dam_height), float(min(hw_default, dam_height)), 1.0)
res_vol = st.sidebar.slider("Reservoir Storage Volume (MCM)", 1.0, 1200.0, float(vol_default), 1.0)

if not is_release:
    fail_mode = st.sidebar.selectbox("Breach Failure Mode", ["overtopping", "piping", "landslide_breach"], index=0 if fail_default == "overtopping" else (1 if fail_default == "piping" else 2))
    spillway_dict = None
else:
    fail_mode = "overtopping"
    st.sidebar.markdown("##### 🌊 Spillway Radial Gate Controls")
    num_gates = st.sidebar.slider("Number of Gates Hoisted", 1, 12, 4, 1)
    gate_width = st.sidebar.slider("Total Gate Crest Width (m)", 10.0, 200.0, 50.0, 5.0)
    gate_opening = st.sidebar.slider("Gate Opening Height (m)", 0.5, 12.0, 4.0, 0.5)
    rel_duration = st.sidebar.slider("Emergency Release Duration (hr)", 1.0, 8.0, 4.0, 0.5)
    spillway_dict = {
        "num_gates": num_gates,
        "gate_width_m": gate_width,
        "gate_opening_m": gate_opening,
        "release_duration_hr": rel_duration
    }

channel_slope = st.sidebar.slider("River Bed Slope (S₀)", 0.0005, 0.06, float(slope_default), 0.001)
mannings_n = st.sidebar.slider("Manning's Roughness (n)", 0.020, 0.070, float(n_default), 0.002)

run_button = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)

# Run or Load Session Results
if "sim_data" not in st.session_state or run_button:
    with st.spinner("Running Hydrodynamic SPH & Delft3D Coupled Simulation..."):
        custom_dict = None
        if selected_preset == "custom":
            custom_dict = {
                "name": "Custom River Reach",
                "river": "Custom River",
                "dam_height_m": dam_height,
                "water_head_m": water_head,
                "reservoir_volume_mcm": res_vol,
                "failure_mode": fail_mode,
                "channel_slope": channel_slope,
                "mannings_n": mannings_n
            }
        st.session_state["sim_data"] = se.run_master_simulation(
            preset_id=selected_preset,
            custom_params=custom_dict,
            scenario_type="water_release" if is_release else "dam_break",
            spillway_params=spillway_dict
        )

data = st.session_state["sim_data"]
dam = data["dam"]
breach = data["breach"]
sph = data["sph"]
delft = data["delft3d"]
hadr = data["hadr"]
gee = data["gee"]

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Interactive Inundation Map",
    "⚖️ SPH vs Delft3D Comparison",
    "📈 Outflow Hydrograph & Profile",
    "🛡️ HADR Loss & Evacuation Plan",
    "🛰️ Google Earth Engine (SAR)"
])

# ---------------------------------------------------------------------------
# Tab 1: Map
# ---------------------------------------------------------------------------
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Peak Outflow (Qp)", f"{breach['peak_outflow_m3s']:,.0f} m³/s")
    col2.metric("Breach Formation Time", f"{breach['time_to_failure_hr']} hr")
    col3.metric("SPH Near-Field Velocity", f"{sph['near_field_velocity_mps']} m/s")
    col4.metric("Pop. in Hazard Zone", f"{hadr['total_population_at_risk']:,}")

    st.markdown("#### Satellite Inundation & Reach Corridor")
    st.caption("Dam breach origin marked in red. Translucent overlay denotes Delft3D flood inundation extent downstream.")

    # Folium Map
    m = folium.Map(location=[dam["lat"], dam["lon"]], zoom_start=12)
    # Add Google Satellite tiles
    folium.TileLayer(
        tiles="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        attr="Google Maps Satellite",
        name="Google Satellite"
    ).add_to(m)

    # Dam Origin Pin
    folium.Marker(
        [dam["lat"], dam["lon"]],
        popup=f"<b>DAM BREACH: {dam['name']}</b><br>Height: {dam['dam_height_m']}m<br>Qp: {breach['peak_outflow_m3s']:,.0f} m³/s",
        tooltip="Dam Breach Origin",
        icon=folium.Icon(color="red", icon="warning-sign")
    ).add_to(m)

    # Downstream Stations
    for pt in sph["reach_summary"][1:]:
        folium.CircleMarker(
            [pt["lat"], pt["lon"]],
            radius=7,
            color="#ffffff",
            fill_color="#3b82f6",
            fill_opacity=0.9,
            popup=f"<b>{pt['name']}</b> (+{pt['dist_km']} km)<br>Arrival: T+{pt['arrival_time_hr']} hr<br>Depth: {pt['peak_depth_m']} m",
            tooltip=f"{pt['name']} (T+{pt['arrival_time_hr']}h)"
        ).add_to(m)

    # Inundation Polygon
    latest_step = sorted(list(delft["polygons_by_timestep"].keys()), key=lambda x: float(x))[-1]
    poly_data = delft["polygons_by_timestep"].get(latest_step, [])
    if poly_data and len(poly_data[0]["coords"]) > 3:
        folium.Polygon(
            locations=poly_data[0]["coords"],
            color="#06b6d4",
            weight=2,
            fill=True,
            fill_color="#0284c7",
            fill_opacity=0.45,
            tooltip=f"Delft3D Flood Extent (Area: {poly_data[0]['area_km2']} km²)"
        ).add_to(m)

    folium.LayerControl().add_to(m)
    st_folium(m, width=None, height=520)

    st.markdown("---")
    st.subheader("📥 Export Deliverables (GIS Ready)")
    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.markdown(f'<a href="http://localhost:5000/api/export/shapefile" class="btn" style="background:#06b6d4;color:#000;padding:8px 12px;border-radius:5px;text-decoration:none;font-weight:bold;display:block;text-align:center;">Download .SHP (Zip)</a>', unsafe_allow_html=True)
    with d2:
        st.markdown(f'<a href="http://localhost:5000/api/export/kml" class="btn" style="background:#3b82f6;color:#fff;padding:8px 12px;border-radius:5px;text-decoration:none;font-weight:bold;display:block;text-align:center;">Download .KML</a>', unsafe_allow_html=True)
    with d3:
        st.markdown(f'<a href="http://localhost:5000/api/export/geotiff" class="btn" style="background:#10b981;color:#fff;padding:8px 12px;border-radius:5px;text-decoration:none;font-weight:bold;display:block;text-align:center;">Download GeoTIFF (.tif)</a>', unsafe_allow_html=True)
    with d4:
        st.markdown(f'<a href="http://localhost:5000/api/export/hadr" class="btn" style="background:#ef4444;color:#fff;padding:8px 12px;border-radius:5px;text-decoration:none;font-weight:bold;display:block;text-align:center;">Download HADR JSON</a>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tab 2: Comparison
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Hydrodynamic Model Comparison: SPH vs Delft3D")
    st.markdown(
        """
        - **Smoothed Particle Hydrodynamics (SPH):** Lagrangian free-surface particle method. Excels in resolving violent, highly turbulent near-field dam-break jets, wave breaking, and supercritical canyon flow.
        - **Delft3D:** Eulerian 2D depth-averaged shallow water solver. Excels in representing wide-valley floodplains, bed roughness dissipation (Manning's $n$), and long-distance attenuation.
        """
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Wave Arrival Times (Hours from Breach)")
        fig, ax = plt.subplots(figsize=(6, 3.5))
        names = [p["station"] for p in data["comparison"]["comparison_table"]]
        sph_t = [p["sph_arrival_hr"] for p in data["comparison"]["comparison_table"]]
        d3d_t = [p["delft3d_arrival_hr"] for p in data["comparison"]["comparison_table"]]
        x = range(len(names))
        ax.bar([i - 0.2 for i in x], sph_t, width=0.4, label="SPH (Fast surge)", color="#06b6d4")
        ax.bar([i + 0.2 for i in x], d3d_t, width=0.4, label="Delft3D (Gradual)", color="#3b82f6")
        ax.set_xticks(list(x))
        ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("Arrival Time (hr)")
        ax.legend()
        ax.grid(alpha=0.2)
        st.pyplot(fig)

    with c2:
        st.markdown("##### Peak Inundation Depth Attenuation")
        fig2, ax2 = plt.subplots(figsize=(6, 3.5))
        dists = [p["dist_km"] for p in data["comparison"]["comparison_table"]]
        sph_d = [p["sph_depth_m"] for p in data["comparison"]["comparison_table"]]
        d3d_d = [p["delft3d_depth_m"] for p in data["comparison"]["comparison_table"]]
        ax2.plot(dists, sph_d, "o-", label="SPH Depth (m)", color="#06b6d4", linewidth=2)
        ax2.plot(dists, d3d_d, "s-", label="Delft3D Depth (m)", color="#3b82f6", linewidth=2)
        ax2.set_xlabel("Distance Downstream (km)")
        ax2.set_ylabel("Peak Depth (m)")
        ax2.legend()
        ax2.grid(alpha=0.2)
        st.pyplot(fig2)

    st.markdown("##### Station-by-Station Hydrodynamic Discrepancy")
    st.table(data["comparison"]["comparison_table"])

# ---------------------------------------------------------------------------
# Tab 3: Hydrograph
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Breach Outflow Hydrograph & Longitudinal River Profile")
    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"**Froehlich (2008) Hydrograph** (Qp: {breach['peak_outflow_m3s']:,.0f} m³/s | tf: {breach['time_to_failure_hr']} hr)")
        figH, axH = plt.subplots(figsize=(6, 3.5))
        axH.plot(breach["time_hours"], breach["outflow_m3s"], color="#ef4444", linewidth=2)
        axH.fill_between(breach["time_hours"], breach["outflow_m3s"], color="#ef4444", alpha=0.15)
        axH.set_xlabel("Time (hours)")
        axH.set_ylabel("Discharge (m³/s)")
        axH.grid(alpha=0.3)
        st.pyplot(figH)

    with colB:
        st.markdown("**Longitudinal Bed Elevation & Water Profile**")
        reach = dam["reach_points"]
        dists = [p["dist_km"] for p in reach]
        bed = [p["elev"] for p in reach]
        water = [p["elev"] + sph["reach_summary"][i]["peak_depth_m"] for i, p in enumerate(reach)]
        figP, axP = plt.subplots(figsize=(6, 3.5))
        axP.plot(dists, bed, color="#6b7280", label="River Bed Elev (m)", linewidth=2)
        axP.plot(dists, water, color="#06b6d4", label="Peak Water Surface (m)", linewidth=2)
        axP.fill_between(dists, bed, water, color="#06b6d4", alpha=0.25)
        axP.set_xlabel("Distance Downstream (km)")
        axP.set_ylabel("Elevation (m MSL)")
        axP.legend()
        axP.grid(alpha=0.3)
        st.pyplot(figP)

# ---------------------------------------------------------------------------
# Tab 4: HADR
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("HADR Early Warning & Evacuation Lead Times")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Population at Risk", f"{hadr['total_population_at_risk']:,}")
    h2.metric("Critical Infrastructure Threatened", f"{hadr['bridges_infrastructure_threatened']} Bridges/Hydel")
    h3.metric("Agricultural Land Flooded", f"{hadr['est_agricultural_loss_ha']:,} ha")
    h4.metric("Economic Exposure", f"₹ {hadr['est_economic_exposure_inr_crores']:,} Cr")

    st.markdown("##### Sector Evacuation Deadlines")
    st.dataframe(hadr["sectors"], use_container_width=True)

    st.markdown("##### Recommended NDRF Protocols")
    for pr in hadr["emergency_protocols"]:
        st.markdown(f"- **{pr}**")

# ---------------------------------------------------------------------------
# Tab 5: GEE
# ---------------------------------------------------------------------------
with tab5:
    st.subheader("Google Earth Engine Sentinel-1 SAR Integration")
    st.markdown(
        """
        During monsoon flash floods and dam breach crises, optical satellites are obstructed by clouds.
        **Sentinel-1 C-band SAR (Synthetic Aperture Radar)** provides 24/7 all-weather cloud penetration.
        Water causes specular reflection, resulting in very low radar backscatter (< -16.5 dB).
        """
    )
    st.code(gee["script"], language="python")

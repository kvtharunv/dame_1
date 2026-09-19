"""
app.py
======
Streamlit dashboard for the Dam Break Inundation Modelling prototype.

Provides:
  - Input panel: dam/embankment parameters (height, reservoir volume,
    failure mode), DEM source (synthetic demo / uploaded GeoTIFF), breach
    location.
  - Run button that executes the full pipeline:
        DamParameters -> compute_breach() -> BreachResult
        DEM + BreachResult -> simulate_inundation() -> InundationResult
  - Output panel: interactive flood map (folium), breach hydrograph chart,
    key metrics (peak outflow, flooded area, max depth, people/area
    potentially affected), and download buttons for .shp (zipped), .kml,
    and the depth GeoTIFF.
  - A simple "SPH-style vs Delft3D-style" scenario comparison: two runs
    with different breach-formation assumptions (instantaneous/near-field
    vs gradual/far-field), shown side by side, clearly labelled as a
    conceptual stand-in for the two solvers until they are integrated.
  - A minimal "near real-time" panel showing how a Google Earth Engine
    Sentinel-1 water-extent check would slot into the workflow.

Run with:
    streamlit run app.py
"""

import os
import io
import json
import zipfile
import tempfile

import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import rasterio
from rasterio.transform import from_origin

from breach_model import DamParameters, compute_breach
from flood_fill_model import simulate_inundation
from demo import (
    build_synthetic_valley_dem,
    load_real_dem,
    export_depth_geotiff,
    export_flood_extent_shp_kml,
)

st.set_page_config(page_title="Dam Break Inundation Modelling", layout="wide")

# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

if "results" not in st.session_state:
    st.session_state["results"] = None
if "compare_results" not in st.session_state:
    st.session_state["compare_results"] = None


# ---------------------------------------------------------------------------
# Sidebar: inputs
# ---------------------------------------------------------------------------

st.sidebar.title("Simulation Inputs")

st.sidebar.subheader("1. River / Dam site")
site_name = st.sidebar.text_input("Dam / reach name", value="Subansiri_Reach_Assam")

dem_source = st.sidebar.radio(
    "DEM source",
    ["Synthetic demo valley (built-in)", "Upload GeoTIFF DEM"],
    help="Use the built-in synthetic valley DEM for a quick demo, or upload a real "
         "SRTM/ASTER GeoTIFF clipped to your river/dam AOI.",
)

uploaded_dem = None
if dem_source == "Upload GeoTIFF DEM":
    uploaded_dem = st.sidebar.file_uploader("Upload DEM (.tif)", type=["tif", "tiff"])

st.sidebar.subheader("2. Dam / embankment parameters")
dam_height = st.sidebar.slider("Dam height (m)", min_value=5.0, max_value=180.0, value=25.0, step=1.0)
hw_height = st.sidebar.slider(
    "Water head above breach invert at failure (m)",
    min_value=2.0, max_value=float(dam_height), value=min(20.0, dam_height), step=1.0,
)
reservoir_volume_mcm = st.sidebar.slider(
    "Reservoir volume at failure (million m3)",
    min_value=1.0, max_value=1500.0, value=50.0, step=1.0,
)
failure_mode = st.sidebar.selectbox("Failure mode", ["overtopping", "piping"])

st.sidebar.subheader("3. Breach location on DEM")
st.sidebar.caption("Row/col index into the DEM grid (0,0 = top-left / upstream corner).")
breach_row = st.sidebar.number_input("Breach row (upstream position)", min_value=0, value=8, step=1)
breach_col = st.sidebar.number_input("Breach column (across valley)", min_value=0, value=100, step=1)

st.sidebar.subheader("4. Comparison mode")
run_comparison = st.sidebar.checkbox(
    "Run SPH-style vs Delft3D-style comparison",
    value=True,
    help="Runs two scenarios with different breach-formation timing assumptions, "
         "as a conceptual stand-in for a fast near-field (SPH) solve vs a "
         "gradual far-field (Delft3D) solve, until those solvers are integrated.",
)

run_button = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_dem_and_georef(dem_size=200, cell_size_m=30.0):
    if dem_source == "Upload GeoTIFF DEM" and uploaded_dem is not None:
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp.write(uploaded_dem.read())
            tmp_path = tmp.name
        dem, cell_size_m, transform, crs = load_real_dem(tmp_path)
        os.unlink(tmp_path)
        return dem, cell_size_m, transform, crs
    else:
        dem, cell_size_m = build_synthetic_valley_dem(size=dem_size, cell_size_m=cell_size_m)
        origin_lon, origin_lat = 94.10, 27.60
        deg_per_m = 1.0 / 111320.0
        transform = from_origin(origin_lon, origin_lat, cell_size_m * deg_per_m, cell_size_m * deg_per_m)
        crs = "EPSG:4326"
        return dem, cell_size_m, transform, crs


def run_scenario(dam: DamParameters, breach_rc, dem, cell_size_m, transform, crs,
                  tf_scale: float = 1.0):
    """
    Runs breach + inundation. tf_scale multiplies the computed
    time-to-failure to emulate a faster/slower breach formation --
    used to differentiate the "SPH-style" (fast, near-field) vs
    "Delft3D-style" (gradual, far-field) comparison scenarios in this
    prototype, pending real solver integration.
    """
    breach_result = compute_breach(dam)

    if tf_scale != 1.0:
        # Recompute a scaled hydrograph shape while preserving total volume
        # and peak, by simply relabelling the time axis (illustrative only).
        breach_result.time_series_s = breach_result.time_series_s * tf_scale

    inund_result = simulate_inundation(
        dem, breach_rc, volume_m3=breach_result.total_volume_released_m3, cell_size_m=cell_size_m
    )
    return breach_result, inund_result


def depth_grid_to_folium_map(depth_grid, transform, crs, breach_rc):
    """Renders the flood depth raster as an overlay on a folium map."""
    rows, cols = depth_grid.shape

    # Compute lat/lon bounds from the affine transform (assumes crs is geographic
    # or we skip geospatial accuracy for the synthetic demo case)
    top_left = transform * (0, 0)
    bottom_right = transform * (cols, rows)
    bounds = [[top_left[1], top_left[0]], [bottom_right[1], bottom_right[0]]]  # [[lat,lon],[lat,lon]]... note orientation
    lon_min, lat_max = top_left
    lon_max, lat_min = bottom_right
    bounds = [[lat_min, lon_min], [lat_max, lon_max]]

    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

    # Build an RGBA image for the flood depth (blue, alpha scaled by depth)
    depth_norm = np.clip(depth_grid / (depth_grid.max() + 1e-9), 0, 1)
    rgba = np.zeros((rows, cols, 4), dtype=np.uint8)
    rgba[..., 2] = 200  # blue channel
    rgba[..., 0] = 30
    rgba[..., 1] = 90
    rgba[..., 3] = (depth_norm * 200).astype(np.uint8)  # alpha proportional to depth

    folium.raster_layers.ImageOverlay(
        image=rgba,
        bounds=bounds,
        opacity=0.8,
        name="Flood depth",
    ).add_to(m)

    breach_lat_lon = rasterio.transform.xy(transform, breach_rc[0], breach_rc[1])
    folium.Marker(
        location=[breach_lat_lon[1], breach_lat_lon[0]],
        tooltip="Dam / breach location",
        icon=folium.Icon(color="red", icon="warning-sign"),
    ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def build_download_zip(shp_path_base):
    """Zips the multi-file shapefile component set into one downloadable .zip"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
            fp = shp_path_base + ext
            if os.path.exists(fp):
                zf.write(fp, arcname=os.path.basename(fp))
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

st.title("Dam Break Inundation Modelling Dashboard")
st.caption(
    "Hydrodynamic breach + downstream inundation simulation framework · "
    "NTRO Problem Statement 26161 · Prototype build"
)

tab_sim, tab_compare, tab_realtime, tab_about = st.tabs(
    ["Simulation", "SPH vs Delft3D Comparison", "Near Real-Time (GEE)", "About / Architecture"]
)

# --- Run pipeline on button click ---
if run_button:
    with st.spinner("Running breach model and inundation simulation..."):
        dem, cell_size_m, transform, crs = get_dem_and_georef()
        dam = DamParameters(
            name=site_name.replace(" ", "_"),
            dam_height=dam_height,
            hw_height=hw_height,
            reservoir_volume=reservoir_volume_mcm * 1e6,
            failure_mode=failure_mode,
        )
        breach_rc = (int(breach_row), int(breach_col))

        breach_result, inund_result = run_scenario(dam, breach_rc, dem, cell_size_m, transform, crs)

        out_dir = tempfile.mkdtemp(prefix="dbsim_")
        tif_path = os.path.join(out_dir, f"{dam.name}_flood_depth.tif")
        shp_base = os.path.join(out_dir, f"{dam.name}_flood_extent")
        kml_path = os.path.join(out_dir, f"{dam.name}_flood_extent.kml")

        export_depth_geotiff(inund_result.depth_grid, transform, crs, tif_path)
        export_flood_extent_shp_kml(inund_result.flooded_mask, transform, crs, shp_base + ".shp", kml_path)

        st.session_state["results"] = dict(
            dam=dam, breach_rc=breach_rc, dem=dem, cell_size_m=cell_size_m,
            transform=transform, crs=crs, breach_result=breach_result,
            inund_result=inund_result, out_dir=out_dir, tif_path=tif_path,
            shp_base=shp_base, kml_path=kml_path,
        )

        if run_comparison:
            with st.spinner("Running comparison scenarios (SPH-style vs Delft3D-style)..."):
                sph_breach, sph_inund = run_scenario(dam, breach_rc, dem, cell_size_m, transform, crs, tf_scale=0.15)
                d3d_breach, d3d_inund = run_scenario(dam, breach_rc, dem, cell_size_m, transform, crs, tf_scale=1.0)
                st.session_state["compare_results"] = dict(
                    sph=(sph_breach, sph_inund), delft3d=(d3d_breach, d3d_inund)
                )
        else:
            st.session_state["compare_results"] = None


# ---------------------------------------------------------------------------
# Tab 1: Simulation
# ---------------------------------------------------------------------------

with tab_sim:
    res = st.session_state["results"]
    if res is None:
        st.info("Set your dam/embankment parameters in the sidebar and click **Run Simulation**.")
    else:
        breach_result = res["breach_result"]
        inund_result = res["inund_result"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Peak breach outflow", f"{breach_result.peak_outflow_m3s:,.0f} m3/s")
        c2.metric("Time to breach formation", f"{breach_result.time_to_failure_hr:.2f} hr")
        c3.metric("Flooded area", f"{inund_result.flooded_area_m2/1e6:.2f} km2")
        c4.metric("Max flood depth", f"{inund_result.max_depth_m:.1f} m")

        # rough loss/damage proxy: assume a nominal population density (people/km2)
        st.subheader("Loss / damage proxy")
        pop_density = st.slider(
            "Assumed population density in floodplain (people / km2)",
            min_value=0, max_value=2000, value=250, step=10,
            help="Placeholder uniform-density estimate. Production version should overlay "
                 "a real population raster (e.g. WorldPop) on the flood extent.",
        )
        est_affected = (inund_result.flooded_area_m2 / 1e6) * pop_density
        st.write(f"**Estimated population potentially affected:** ~{est_affected:,.0f} people")

        st.subheader("Flood extent map")
        m = depth_grid_to_folium_map(inund_result.depth_grid, res["transform"], res["crs"], res["breach_rc"])
        st_folium(m, width=None, height=500)

        st.subheader("Breach outflow hydrograph")
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.plot(breach_result.time_series_s / 3600.0, breach_result.outflow_series_m3s, color="#1f77b4")
        ax.set_xlabel("Time since breach initiation (hours)")
        ax.set_ylabel("Discharge (m3/s)")
        ax.set_title("Breach outflow hydrograph (Froehlich 2008 empirical model)")
        ax.grid(alpha=0.3)
        st.pyplot(fig)

        st.subheader("Download outputs")
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            zip_buf = build_download_zip(res["shp_base"])
            st.download_button("Download .shp (zipped)", data=zip_buf,
                                file_name=f"{res['dam'].name}_flood_extent_shp.zip",
                                mime="application/zip", use_container_width=True)
        with d2:
            with open(res["kml_path"], "rb") as f:
                st.download_button("Download .kml", data=f.read(),
                                    file_name=f"{res['dam'].name}_flood_extent.kml",
                                    mime="application/vnd.google-earth.kml+xml", use_container_width=True)
        with d3:
            with open(res["tif_path"], "rb") as f:
                st.download_button("Download depth GeoTIFF", data=f.read(),
                                    file_name=f"{res['dam'].name}_flood_depth.tif",
                                    mime="image/tiff", use_container_width=True)
        with d4:
            summary = {
                "dam_name": res["dam"].name,
                "peak_outflow_m3s": breach_result.peak_outflow_m3s,
                "time_to_failure_hr": breach_result.time_to_failure_hr,
                "flooded_area_km2": inund_result.flooded_area_m2 / 1e6,
                "max_depth_m": inund_result.max_depth_m,
                "est_population_affected": est_affected,
            }
            st.download_button("Download summary (.json)", data=json.dumps(summary, indent=2),
                                file_name=f"{res['dam'].name}_summary.json",
                                mime="application/json", use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 2: Comparison
# ---------------------------------------------------------------------------

with tab_compare:
    st.markdown(
        "This panel compares a **fast, near-field breach scenario** (conceptually representing "
        "an SPH-style solve, which resolves violent, high-velocity flow immediately around the "
        "breach) against a **gradual, far-field scenario** (conceptually representing a "
        "Delft3D-style 2D shallow-water solve of floodplain spread). "
        "Both currently use the same empirical breach-volume engine with different breach-"
        "formation timing, as a placeholder until the real SPH and Delft3D solvers are coupled."
    )

    cmp_res = st.session_state["compare_results"]
    if cmp_res is None:
        st.info("Enable **Run SPH-style vs Delft3D-style comparison** in the sidebar and click Run Simulation.")
    else:
        sph_breach, sph_inund = cmp_res["sph"]
        d3d_breach, d3d_inund = cmp_res["delft3d"]

        col_sph, col_d3d = st.columns(2)
        with col_sph:
            st.markdown("### SPH-style (fast, near-field)")
            st.metric("Peak outflow", f"{sph_breach.peak_outflow_m3s:,.0f} m3/s")
            st.metric("Breach formation time", f"{sph_breach.time_to_failure_hr * 0.15:.2f} hr")
            st.metric("Flooded area", f"{sph_inund.flooded_area_m2/1e6:.2f} km2")
            st.metric("Max depth", f"{sph_inund.max_depth_m:.1f} m")
        with col_d3d:
            st.markdown("### Delft3D-style (gradual, far-field)")
            st.metric("Peak outflow", f"{d3d_breach.peak_outflow_m3s:,.0f} m3/s")
            st.metric("Breach formation time", f"{d3d_breach.time_to_failure_hr:.2f} hr")
            st.metric("Flooded area", f"{d3d_inund.flooded_area_m2/1e6:.2f} km2")
            st.metric("Max depth", f"{d3d_inund.max_depth_m:.1f} m")

        st.subheader("Hydrograph comparison")
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(sph_breach.time_series_s / 3600.0, sph_breach.outflow_series_m3s,
                label="SPH-style (fast)", color="#d62728")
        ax.plot(d3d_breach.time_series_s / 3600.0, d3d_breach.outflow_series_m3s,
                label="Delft3D-style (gradual)", color="#1f77b4")
        ax.set_xlabel("Time since breach initiation (hours)")
        ax.set_ylabel("Discharge (m3/s)")
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)


# ---------------------------------------------------------------------------
# Tab 3: Near real-time (GEE) placeholder
# ---------------------------------------------------------------------------

with tab_realtime:
    st.markdown(
        "**Near real-time flood monitoring via Google Earth Engine** (conceptual panel).\n\n"
        "In the full system, this panel would:\n"
        "1. Query the latest available Sentinel-1 SAR scene for the AOI via the GEE Python/JS API "
        "(SAR is preferred over optical since flood events are usually cloud-covered).\n"
        "2. Apply a backscatter threshold to classify open water.\n"
        "3. Overlay the observed water extent against the simulated inundation extent above, "
        "for validation and rapid situational awareness.\n\n"
        "This requires a Google Earth Engine service account and is not wired into this "
        "offline prototype build; the interface point (`get_latest_sar_water_extent(aoi)`) is "
        "left as the integration hook for the next development phase."
    )
    st.code(
        "# Integration hook (not executed in this offline prototype):\n"
        "# import ee\n"
        "# ee.Initialize()\n"
        "# def get_latest_sar_water_extent(aoi_geometry):\n"
        "#     collection = ee.ImageCollection('COPERNICUS/S1_GRD') \\\n"
        "#         .filterBounds(aoi_geometry) \\\n"
        "#         .filter(ee.Filter.eq('instrumentMode', 'IW')) \\\n"
        "#         .sort('system:time_start', False)\n"
        "#     latest = collection.first()\n"
        "#     water_mask = latest.select('VV').lt(-17)  # simple threshold\n"
        "#     return water_mask",
        language="python",
    )


# ---------------------------------------------------------------------------
# Tab 4: About / architecture
# ---------------------------------------------------------------------------

with tab_about:
    st.markdown(
        """
### Framework architecture

```
DamParameters
    |
    v
compute_breach()  --------------->  BreachResult (hydrograph, Qp, breach geometry)
[Froehlich 2008 empirical, swappable for SPH / Delft3D breach-erosion coupling]
    |
    v
simulate_inundation()  ----------->  InundationResult (depth grid, extent, volume)
[DEM-based corridor-constrained volume fill, swappable for Delft3D-FLOW 2D solve /
 SPH near-field solve]
    |
    v
GIS export (.tif, .shp, .kml)  +  Dashboard visualization  +  Loss/damage proxy
    |
    v
(Planned) Near real-time validation via Google Earth Engine Sentinel-1
```

**What's implemented in this prototype:**
- Empirical breach hydrograph generator (Froehlich 2008), volume-conserving
- DEM-based downstream flood-spread simulation with drainage-corridor constraint
- Interactive dashboard with parameter controls, live map, hydrograph chart
- GIS-standard output formats: GeoTIFF, Shapefile, KML
- Conceptual SPH-vs-Delft3D scenario comparison
- GEE near-real-time integration hook (interface defined, not yet live)

**Next engineering phase:**
- Replace `compute_breach()` internals with a coupled SPH breach-erosion solver
- Replace `simulate_inundation()` internals with a Delft3D-FLOW 2D shallow-water solve
- Wire the GEE hook to a live service account for real Sentinel-1 validation
- Replace uniform population-density proxy with a real gridded population overlay (e.g. WorldPop)
        """
    )

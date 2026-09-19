"""
demo.py
=======
End-to-end run of the dam-break inundation prototype:

    DamParameters -> compute_breach() -> BreachResult
                                            |
                                            v
    DEM  ---------------------------> simulate_inundation() -> InundationResult
                                            |
                                            v
                              GeoTIFF depth raster, .shp, .kml, PNG map

This script uses a SYNTHETIC DEM shaped like a river valley so the full
pipeline is runnable immediately, with no external data download required.
To use a REAL DEM (e.g. SRTM/ASTER clipped to your river/dam AOI), replace
`build_synthetic_valley_dem()` with `load_real_dem(path_to_geotiff)` --
the rest of the pipeline (breach -> inundation -> GIS export) is unchanged,
since simulate_inundation() only needs a numpy elevation array + cell size
+ georeferencing transform, not a specific data source.

Swap points for the full-fidelity models (once integrated):
  - compute_breach()      -> replace internals with SPH / Delft3D breach coupling
  - simulate_inundation() -> replace internals with Delft3D-FLOW 2D solve, or
                              SPH near-field solve for the zone close to the breach
"""

import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.features import shapes as rio_shapes
import geopandas as gpd
from shapely.geometry import shape as shapely_shape
import matplotlib.pyplot as plt
import simplekml
import json
import os

from breach_model import DamParameters, compute_breach
from flood_fill_model import simulate_inundation


# ---------------------------------------------------------------------------
# 1. DEM source
# ---------------------------------------------------------------------------

def build_synthetic_valley_dem(size=200, cell_size_m=30.0):
    """
    Generates a synthetic river-valley DEM: a downstream-sloping channel
    with floodplain rising on either side, to stand in for a real SRTM/
    ASTER tile until one is downloaded for the actual AOI (e.g. Subansiri /
    Brahmaputra reach near Lakhimpur/Dhemaji, Assam).

    Row index increases downstream (row 0 = upstream/dam location,
    row size-1 = far downstream).
    """
    y, x = np.mgrid[0:size, 0:size]
    downstream_slope = y * 0.35          # gentle longitudinal drop, m per cell downstream
    valley_shape = np.abs(x - size / 2) ** 1.6 * 0.05   # V-shaped valley cross-section
    noise = np.random.default_rng(42).normal(0, 0.05, size=(size, size))  # micro-relief
    # (kept small relative to the 0.35 m/cell downstream slope so it adds
    # realistic texture without creating spurious local pits that would
    # trap a simple steepest-descent flow trace -- a real DEM would use a
    # proper depression-filling step, e.g. pysheds' fill_depressions,
    # before flow-direction/accumulation is computed.)
    base_elev = 80.0  # metres, arbitrary base elevation for the reach

    dem = base_elev - downstream_slope + valley_shape + noise
    dem = dem.astype(np.float64)
    return dem, cell_size_m


def load_real_dem(path_to_geotiff):
    """
    Loads a real DEM (e.g. clipped SRTM/ASTER GeoTIFF) using rasterio.
    Use this in place of build_synthetic_valley_dem() once real data for
    the chosen river/dam AOI has been downloaded and clipped.
    """
    with rasterio.open(path_to_geotiff) as src:
        dem = src.read(1).astype(np.float64)
        cell_size_m = abs(src.transform.a)  # pixel width in CRS units (metres, if projected)
        transform = src.transform
        crs = src.crs
    return dem, cell_size_m, transform, crs


# ---------------------------------------------------------------------------
# 2. GIS export helpers
# ---------------------------------------------------------------------------

def export_depth_geotiff(depth_grid, transform, crs, out_path):
    height, width = depth_grid.shape
    with rasterio.open(
        out_path, "w", driver="GTiff",
        height=height, width=width, count=1,
        dtype=depth_grid.dtype, crs=crs, transform=transform,
        nodata=0.0,
    ) as dst:
        dst.write(depth_grid, 1)


def export_flood_extent_shp_kml(flooded_mask, transform, crs, shp_path, kml_path):
    """
    Polygonizes the flooded boolean mask into vector geometries and writes
    both a shapefile (.shp) and a KML (.kml), as required by the
    problem-statement deliverables.
    """
    mask_uint8 = flooded_mask.astype(np.uint8)
    polygons = []
    for geom, value in rio_shapes(mask_uint8, mask=mask_uint8.astype(bool), transform=transform):
        if value == 1:
            polygons.append(shapely_shape(geom))

    if not polygons:
        print("Warning: no flooded polygons to export.")
        return None

    gdf = gpd.GeoDataFrame({"flood_id": range(len(polygons))}, geometry=polygons, crs=crs)
    # Dissolve into a single multipolygon for a clean flood-extent layer
    dissolved = gdf.dissolve()
    dissolved.to_file(shp_path)

    # KML export (reproject to WGS84 lat/lon, required for KML)
    dissolved_wgs84 = dissolved.to_crs(epsg=4326)
    kml = simplekml.Kml()
    for _, row in dissolved_wgs84.iterrows():
        geom = row.geometry
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for poly in polys:
            coords = list(poly.exterior.coords)
            kml.newpolygon(name="Flood Extent", outerboundaryis=coords)
    kml.save(kml_path)

    return dissolved


# ---------------------------------------------------------------------------
# 3. Visualization
# ---------------------------------------------------------------------------

def plot_results(dem, depth_grid, breach_rc, out_png_path, dam_name, breach_result, inund_result):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    im0 = ax.imshow(dem, cmap="terrain")
    ax.plot(breach_rc[1], breach_rc[0], "r^", markersize=12, label="Dam / breach location")
    ax.set_title("DEM (elevation, m)")
    ax.legend(loc="upper right")
    plt.colorbar(im0, ax=ax, shrink=0.7, label="Elevation (m)")

    ax2 = axes[1]
    im1 = ax2.imshow(dem, cmap="gray", alpha=0.5)
    depth_masked = np.ma.masked_where(depth_grid <= 0, depth_grid)
    im2 = ax2.imshow(depth_masked, cmap="Blues", vmin=0)
    ax2.plot(breach_rc[1], breach_rc[0], "r^", markersize=12)
    ax2.set_title(f"Simulated Inundation Extent & Depth\n{dam_name}")
    plt.colorbar(im2, ax=ax2, shrink=0.7, label="Flood depth (m)")

    fig.suptitle(
        f"Peak breach outflow: {breach_result.peak_outflow_m3s:,.0f} m3/s   |   "
        f"Flooded area: {inund_result.flooded_area_m2/1e6:.2f} sq km   |   "
        f"Max depth: {inund_result.max_depth_m:.1f} m",
        fontsize=10,
    )
    plt.tight_layout()
    plt.savefig(out_png_path, dpi=150)
    plt.close()


# ---------------------------------------------------------------------------
# 4. Full pipeline run
# ---------------------------------------------------------------------------

def run_pipeline(dam: DamParameters, breach_rc, output_dir,
                  cell_size_m=30.0, dem_size=200, use_real_dem_path=None):
    os.makedirs(output_dir, exist_ok=True)

    # --- DEM ---
    if use_real_dem_path:
        dem, cell_size_m, transform, crs = load_real_dem(use_real_dem_path)
    else:
        dem, cell_size_m = build_synthetic_valley_dem(size=dem_size, cell_size_m=cell_size_m)
        # Arbitrary georeferencing anchored near the Assam/Brahmaputra region
        # (approx. Lakhimpur/Dhemaji area), for demonstration purposes only.
        # Replace with the real DEM's transform/CRS when using actual data.
        origin_lon, origin_lat = 94.10, 27.60
        # Convert cell size in metres to approx degrees at this latitude for a quick demo CRS.
        deg_per_m = 1.0 / 111320.0
        transform = from_origin(origin_lon, origin_lat, cell_size_m * deg_per_m, cell_size_m * deg_per_m)
        crs = "EPSG:4326"

    # --- Breach hydrograph ---
    breach_result = compute_breach(dam)

    # --- Flood spread using peak-equivalent released volume ---
    inund_result = simulate_inundation(
        dem, breach_rc, volume_m3=breach_result.total_volume_released_m3, cell_size_m=cell_size_m
    )

    # --- GIS exports ---
    tif_path = os.path.join(output_dir, f"{dam.name}_flood_depth.tif")
    shp_path = os.path.join(output_dir, f"{dam.name}_flood_extent.shp")
    kml_path = os.path.join(output_dir, f"{dam.name}_flood_extent.kml")
    png_path = os.path.join(output_dir, f"{dam.name}_map.png")
    summary_path = os.path.join(output_dir, f"{dam.name}_summary.json")

    export_depth_geotiff(inund_result.depth_grid, transform, crs, tif_path)
    export_flood_extent_shp_kml(inund_result.flooded_mask, transform, crs, shp_path, kml_path)
    plot_results(dem, inund_result.depth_grid, breach_rc, png_path, dam.name, breach_result, inund_result)

    summary = {
        "dam_name": dam.name,
        "breach": {
            "peak_outflow_m3s": breach_result.peak_outflow_m3s,
            "time_to_failure_hr": breach_result.time_to_failure_hr,
            "breach_width_avg_m": breach_result.breach_width_avg,
            "total_volume_released_m3": breach_result.total_volume_released_m3,
            "engine": breach_result.engine,
        },
        "inundation": {
            "flooded_area_km2": inund_result.flooded_area_m2 / 1e6,
            "max_depth_m": inund_result.max_depth_m,
            "volume_used_m3": inund_result.volume_used_m3,
            "engine": inund_result.engine,
        },
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nOutputs written to: {output_dir}")
    print(f"  - {os.path.basename(tif_path)}  (flood depth raster)")
    print(f"  - {os.path.basename(shp_path)}   (flood extent shapefile)")
    print(f"  - {os.path.basename(kml_path)}   (flood extent KML)")
    print(f"  - {os.path.basename(png_path)}   (map visualization)")
    print(f"  - {os.path.basename(summary_path)} (JSON summary)")

    return breach_result, inund_result, summary


if __name__ == "__main__":
    # Scaled-down illustrative embankment/dam scenario for a clean prototype
    # demo (full Subansiri-scale numbers flood a much larger domain than a
    # small synthetic grid can usefully show at 30 m resolution).
    dam = DamParameters(
        name="Demo_Embankment_Assam_Reach",
        dam_height=25.0,
        hw_height=20.0,
        reservoir_volume=5.0e7,   # 50 million m^3 -- moderate embankment/small reservoir
        failure_mode="overtopping",
    )
    breach_point_rc = (8, 100)  # near top of the synthetic valley, centre column

    run_pipeline(
        dam=dam,
        breach_rc=breach_point_rc,
        output_dir="/home/claude/dam_break_sim/output",
        cell_size_m=30.0,
        dem_size=200,
    )

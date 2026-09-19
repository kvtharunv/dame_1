"""
web_server.py
=============
Flask Web Server for the Dam Break Inundation Modelling Website Simulation.
NTRO Problem Statement 26161.

Endpoints:
  GET  /                     -> Main interactive simulation GUI
  GET  /api/presets          -> List all Indian dam/river presets
  POST /api/simulate         -> Run hydrodynamic simulation (SPH + Delft3D + HADR)
  GET  /api/export/shapefile -> Download ESRI Shapefile (.zip)
  GET  /api/export/kml       -> Download Google Earth KML (.kml)
  GET  /api/export/geotiff   -> Download GeoTIFF depth raster (.tif)
  GET  /api/export/hadr      -> Download HADR Disaster Report (.json)
"""

import os
import json
import io
from flask import Flask, render_template, request, jsonify, send_file, Response
import simulation_engine as se

app = Flask(__name__, template_folder="templates", static_folder="static")

# In-memory cache for latest simulation run
LATEST_SIMULATION = None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/presets", methods=["GET"])
def get_presets():
    presets = []
    for pid, dam in se.INDIAN_DAM_PRESETS.items():
        presets.append({
            "id": dam.id,
            "name": dam.name,
            "river": dam.river,
            "state": dam.state,
            "lat": dam.lat,
            "lon": dam.lon,
            "dam_height_m": dam.dam_height_m,
            "water_head_m": dam.water_head_m,
            "reservoir_volume_mcm": dam.reservoir_volume_mcm,
            "failure_mode": dam.failure_mode,
            "channel_slope": dam.channel_slope,
            "mannings_n": dam.mannings_n,
            "description": dam.description,
            "reach_length_km": dam.reach_points[-1]["dist_km"] if dam.reach_points else 0
        })
    return jsonify(presets)


@app.route("/api/simulate", methods=["POST"])
def run_simulation():
    global LATEST_SIMULATION
    data = request.get_json() or {}
    preset_id = data.get("preset_id", "rishi_ganga")
    custom_params = data.get("custom_params", None)
    scenario_type = data.get("scenario_type", "dam_break")
    spillway_params = data.get("spillway_params", None)
    custom_hydrograph = data.get("custom_hydrograph", None)

    try:
        sim_result = se.run_master_simulation(
            preset_id=preset_id,
            custom_params=custom_params,
            scenario_type=scenario_type,
            spillway_params=spillway_params,
            custom_hydrograph=custom_hydrograph
        )
        LATEST_SIMULATION = sim_result
        return jsonify({
            "status": "success",
            "data": sim_result
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route("/api/catalog", methods=["GET"])
def get_dam_catalog():
    return jsonify({
        "status": "success",
        "count": len(se.INDIA_OPEN_DAM_CATALOG),
        "dams": se.INDIA_OPEN_DAM_CATALOG
    })


@app.route("/api/upload-dataset", methods=["POST"])
def upload_dataset():
    if "file" not in request.files and not request.json:
        return jsonify({"status": "error", "message": "No file or data provided"}), 400

    dataset_type = request.form.get("type", "csv")

    try:
        if dataset_type == "csv":
            file = request.files["file"]
            csv_text = file.read().decode("utf-8")
            parsed_hydro = se.parse_custom_hydrograph_csv(csv_text)
            return jsonify({"status": "success", "type": "hydrograph", "data": parsed_hydro})

        elif dataset_type == "geojson":
            file = request.files["file"]
            geojson_data = json.loads(file.read().decode("utf-8"))
            reach_points = se.parse_custom_river_geojson(geojson_data)
            return jsonify({"status": "success", "type": "reach", "data": reach_points})

        elif dataset_type == "dem":
            file = request.files["file"]
            dem_bytes = file.read()
            dem_info = se.parse_custom_dem_raster(dem_bytes)
            return jsonify({"status": "success", "type": "dem", "data": dem_info})

        else:
            return jsonify({"status": "error", "message": f"Unsupported dataset type: {dataset_type}"}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/export/shapefile", methods=["GET"])
def export_shapefile():
    global LATEST_SIMULATION
    if not LATEST_SIMULATION:
        LATEST_SIMULATION = se.run_master_simulation("rishi_ganga")

    dam_name = LATEST_SIMULATION["dam"]["name"].replace(" ", "_")
    zip_bytes = se.export_simulation_shapefile_zip(
        dam_name=dam_name,
        reach_summary=LATEST_SIMULATION["sph"]["reach_summary"],
        delft_polygons=LATEST_SIMULATION["delft3d"]["polygons_by_timestep"]
    )
    return send_file(
        io.BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{dam_name}_flood_extent_shp.zip"
    )


@app.route("/api/export/kml", methods=["GET"])
def export_kml():
    global LATEST_SIMULATION
    if not LATEST_SIMULATION:
        LATEST_SIMULATION = se.run_master_simulation("rishi_ganga")

    dam_dict = LATEST_SIMULATION["dam"]
    # Recreate DamSite object
    dam = se.DamSite(**dam_dict)
    kml_str = se.export_simulation_kml(
        dam=dam,
        breach=LATEST_SIMULATION["breach"],
        reach_summary=LATEST_SIMULATION["sph"]["reach_summary"],
        delft_polygons=LATEST_SIMULATION["delft3d"]["polygons_by_timestep"]
    )
    return Response(
        kml_str,
        mimetype="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f"attachment; filename={dam.id}_flood_extent.kml"}
    )


@app.route("/api/export/geotiff", methods=["GET"])
def export_geotiff():
    global LATEST_SIMULATION
    if not LATEST_SIMULATION:
        LATEST_SIMULATION = se.run_master_simulation("rishi_ganga")

    dam_dict = LATEST_SIMULATION["dam"]
    dam = se.DamSite(**dam_dict)
    tif_bytes = se.export_simulation_geotiff(
        dam=dam,
        reach_summary=LATEST_SIMULATION["sph"]["reach_summary"],
        delft_polygons=LATEST_SIMULATION["delft3d"]["polygons_by_timestep"]
    )
    return send_file(
        io.BytesIO(tif_bytes),
        mimetype="image/tiff",
        as_attachment=True,
        download_name=f"{dam.id}_flood_depth.tif"
    )


@app.route("/api/export/hadr", methods=["GET"])
def export_hadr():
    global LATEST_SIMULATION
    if not LATEST_SIMULATION:
        LATEST_SIMULATION = se.run_master_simulation("rishi_ganga")

    report = {
        "title": "HADR Dam Break & Flash Flood Disaster Assessment Report",
        "agency": "National Technical Research Organisation (NTRO) / NDMA",
        "dam_name": LATEST_SIMULATION["dam"]["name"],
        "river": LATEST_SIMULATION["dam"]["river"],
        "state": LATEST_SIMULATION["dam"]["state"],
        "breach_metrics": LATEST_SIMULATION["breach"],
        "hadr_assessment": LATEST_SIMULATION["hadr"],
        "model_comparison": LATEST_SIMULATION["comparison"]
    }
    return Response(
        json.dumps(report, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={LATEST_SIMULATION['dam']['id']}_hadr_report.json"}
    )


if __name__ == "__main__":
    # Pre-warm simulation
    LATEST_SIMULATION = se.run_master_simulation("rishi_ganga")
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting Dam Break Simulation Web Server at http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)

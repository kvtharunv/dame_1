# Dam Break Inundation Modelling Using Hydrodynamic Modelling of Any River
### Problem Statement ID: 26161 | National Technical Research Organisation (NTRO) | SIH 2026

---

## 🌟 Overview & Key Features

This platform is an automated hydrodynamic simulation and early warning software tool developed to predict dam break / river blockage inundation for any river basin in India. It satisfies all technical deliverables stipulated in **NTRO Problem Statement 26161**:

1. **Starts at Dam Location on Google Maps**:
   - Simulation automatically initializes directly at the chosen dam crest with a prominent pulsing beacon and structural specifications.
   - Integrated with **Google Maps Satellite**, **Google Hybrid**, **Google Terrain**, and **OpenStreetMap** layers.
2. **Follows the Flow of Water Downstream**:
   - **Auto-Follow Camera Mode**: The map dynamically pans and tracks the surging flood wave front as it rushes down the river valley.
   - **Real-Time HUD**: Displays elapsed time ($T+hh:mm$), wave front distance ($km$), surge velocity ($m/s$), instantaneous discharge ($m^3/s$), and threatened population.
3. **Dual Hydrodynamic Solvers: SPH vs Delft3D**:
   - **Smoothed Particle Hydrodynamics (SPH)**: Lagrangian fluid particles modeling supercritical flow, violent near-field breach jets, and free-surface spray.
   - **Delft3D (2D Depth-Averaged Shallow Water Flow)**: Eulerian numerical solver incorporating bed roughness (Manning's $n$), floodplain lateral storage, and discharge attenuation.
   - **Side-by-Side Comparison**: Live metrics, wave arrival discrepancies, and longitudinal depth profiles.
4. **Dual Scenario Modes: Dam Break vs. Spillway Water Release**:
   - **Dam Break Mode**: Catastrophic structural rupture computed via **Froehlich (2008) ASCE** empirical equations ($Q_p$, $t_f$, $B_{\text{avg}}$).
   - **Emergency Water Release Mode**: Controlled/uncontrolled radial gate discharge surge ($Q = C_d \cdot A \cdot \sqrt{2gH_{\text{eff}}}$) without dam collapse.
5. **Pre-configured Indian Dam & River Basins (NTRO Problem Statement Citations)**:
   - **Rishi Ganga / Dhauliganga (Chamoli 2021 Disaster, Uttarakhand)**
   - **Phuktal River Landslide Dam Burst (Sumdo, Zanskar / Ladakh, 2015 Disaster)**
   - **Wapriyang River Blockage (Siang Basin, Arunachal Pradesh, 2021)**
   - **Jhelum River Valley / Srinagar Reach (Catastrophic 2014 Kashmir Floods)**
   - **Subansiri Lower Hydroelectric Dam (Arunachal / Assam Brahmaputra Reach)**
   - **Tehri Dam (Bhagirathi River, Uttarakhand)**
   - **Mullaperiyar Dam (Periyar River, Kerala / Tamil Nadu)**
   - **Kosi River Embankment (Kusaha Reach, Bihar)**
   - **National Open-Source Dam Catalog (CWC / NRLD)**: 10 major Indian dams pre-indexed with structural attributes.
   - **Custom Dam Locator**: Click anywhere in India or input GPS coordinates to generate dynamic downstream routing.
6. **Multi-Format Input Dataset Ingestion (Deliverable ii)**:
   - **Hydrological Inflow Hydrographs (CSV)**: Upload custom upstream discharge time series.
   - **DEM Elevation Rasters (GeoTIFF / .tif)**: Ingest custom SRTM 30m or CartoDEM grids using windowed chunking for large volume data.
   - **River Reach Geometries (GeoJSON / .kml)**: Custom digitized river thalwegs and valley corridors.
7. **HADR (Humanitarian Assistance & Disaster Relief) Decision Support**:
   - Sector-by-sector evacuation countdown deadlines ($T+hh:mm$).
   - Critical infrastructure risk matrix (bridges, highways, hydel tunnels, settlements).
   - Agricultural damage assessment (hectares) and economic exposure (INR Crores).
   - Official NDRF emergency response standard operating procedures (SOPs).
8. **Near Real-Time Remote Sensing (Google Earth Engine)**:
   - All-weather cloud-penetrating **Sentinel-1 C-band SAR** water classification ($< -16.5$ dB threshold).
   - Interactive SAR radar backscatter overlay and copy-pasteable GEE Python & JavaScript scripts.
9. **GIS Deliverables & Direct Exports**:
   - **ESRI Shapefile Archive (.shp.zip)** with full attribute table.
   - **Google Earth KML (.kml)** with 3D styled translucent inundation polygons and dam pins.
   - **GeoTIFF Depth Grid (.tif)** georeferenced to WGS84 (EPSG:4326).
   - **HADR Operational Report (.json)**.

---

## 🚀 Running the Applications

### 1. Interactive 60-FPS Web Simulation (Primary Platform)
Features the full Google Maps follow-flow camera, animated SPH fluid particles, timeline scrubber, and comparison tabs:
```bash
cd /home/tom/dam_break_sim
source venv/bin/activate
python web_server.py
```
👉 Open your browser at: **`http://localhost:5000`**

### 2. Streamlit Analysis Dashboard
Features parameter tuning, Folium map, and analytical charts:
```bash
cd /home/tom/dam_break_sim
source venv/bin/activate
streamlit run app.py --server.port 8501
```
👉 Open your browser at: **`http://localhost:8501`**

---

## 📁 Repository Structure
```
/home/tom/dam_break_sim/
├── simulation_engine.py       # Core hydrodynamic physics (Froehlich, SPH, Delft3D, GEE, GIS)
├── web_server.py             # Flask REST API backend & static server
├── app.py                    # Streamlit analytical dashboard
├── requirements.txt          # Python dependencies
├── templates/
│   └── index.html            # Mission-control web simulation GUI
├── static/
│   ├── style.css             # NTRO Command Center dark theme
│   └── app.js                # Leaflet + Google Maps, SPH particle system, auto-follow camera
└── venv/                     # Virtual environment with full scientific GIS stack
```

---

## 🔬 Hydrodynamic Governing Equations

### Breach Mechanics: Froehlich (2008)
$$B_{\text{avg}} = 0.27 \cdot k_0 \cdot V_w^{0.32} \cdot h_b^{0.04}$$
$$t_f = 63.2 \cdot \sqrt{\frac{V_w}{g \cdot h_b^2}} \quad [\text{seconds}]$$
$$Q_p = C_d \cdot \left[ B_{\text{avg}} h_b^{1.5} + \frac{8}{15} z \sqrt{2g} h_b^{2.5} \right]$$

### SPH Near-Field Surge Velocity
$$v_{\text{surge}} \approx \sqrt{2 g h_w} \cdot \psi_{\text{canyon}}$$

### Delft3D Shallow Water Wave Celerity
$$c = \frac{5}{3} v_0 = \frac{5}{3} \left( \frac{1}{n} R_h^{2/3} S_0^{1/2} \right)$$

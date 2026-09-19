# Dam Break Inundation Modelling Platform — System Reference Manual
### Problem Statement ID: 26161 | National Technical Research Organisation (NTRO) | SIH 2026
**Document Title:** Comprehensive Technical, Scientific & Operational Guide (`ABOUT.md`)  
**Platform Name:** HYDRO-BREAK 360  
**Project Path:** `/home/tom/dam_break_sim`  
**Web Server Entry Point:** `web_server.py` (`http://localhost:5000`)

---

## 🌟 Quick Project Summary (In Simple Everyday English)

> **What is this project in one simple sentence?**  
> This project is a website that simulates a dam breaking on Google Maps, showing how water rushes down the river valley, which villages are in **🔴 High Danger**, which areas have **🟡 Low Danger** (mild flooding), and where the **🟢 Green Safe Shelters** are located so people can safely run and survive.

### The 3 Indication Levels on the Map:
- **🔴 HIGH DANGER AREA (Red Zone):** Deep water (&ge; 2.5 meters) moving violently at high speed (&ge; 5 m/s). Knocks down buildings and bridges. Extreme life hazard — people must evacuate before water arrives!
- **🟡 LOW DANGER AREA (Yellow Zone):** Shallow water (0.3 to 2.5 meters) spreading into farm fields and roads. People can still safely move away to higher ground.
- **🟢 SAFE PLACES / HAVENS (Green Pins):** Elevated hills and shelters located 25 to 600 meters above the valley floor. The flood water can never reach here.

### Simulation Speed Control:
- The playback speed is set to a calm **0.25x by default** (with an **0.1x ultra-slow mode**) so you can comfortably watch the flood wave pass each village without rushing.
- The map camera automatically and smoothly tracks the moving water wave front down the river.

---

## 1. Executive Summary & Problem Background

In India, catastrophic flash floods triggered by sudden dam failures or the bursting of landslide-dammed lakes (GLOFs/LLOFs) represent severe humanitarian, ecological, and infrastructural threats. Critical historical precedents include:
- **Rishi Ganga / Chamoli Disaster (Feb 2021):** A catastrophic rock and hanging glacier detachment in the Nanda Devi sanctuary formed a temporary blockage that breached violently, sending high-velocity debris torrents down the Rishi Ganga and Dhauliganga rivers, destroying the Raini bridge and burying the Tapovan Vishnugad hydroelectric tunnels.
- **Kosi River Embankment Breach (Aug 2008):** An embankment breach at Kusaha (Indo-Nepal border) shifted the river course by over 100 km eastward across North Bihar flatlands, inundating over 2.7 million people and demonstrating the acute necessity of regional overbank floodplain storage modeling.
- **Assam & Kashmir Valley Floods (2014, 2021):** Intense river overflow requiring immediate Humanitarian Assistance and Disaster Relief (HADR) scenario planning.

### Purpose of the Platform
**HYDRO-BREAK 360** is an automated hydrodynamic simulation, early warning, and scenario-generation software platform built specifically to address **NTRO Problem Statement 26161**. It computes downstream inundation extents, flow velocities, wave arrival deadlines, and socio-economic damages for any dam or river blockage across India. Crucially, it dynamically classifies and visualizes **High Danger Areas**, **Low Danger Areas**, and **High-Ground Safe Places**, providing actionable evacuation intelligence to disaster management authorities.

---

## 2. Programming Languages, Libraries & Scientific Methods (And What Each Is Used For)

The platform employs a modular, full-stack architecture coupling high-performance scientific Python on the backend with responsive, hardware-accelerated mapping on the frontend:

### A. Programming Languages Breakdown

| Language | Layer / Subsystem | Primary Responsibilities & Usage |
| :--- | :--- | :--- |
| **Python 3.10+** | **Backend Server & Numerical Core** | - RESTful API microservices (Flask in `web_server.py`)<br/>- Hydrodynamic governing equations and Froehlich empirical breach regressions<br/>- Geospatial deliverable compilation (Shapefiles, KML, GeoTIFF, JSON)<br/>- Numerical interpolation and Lagrangian particle distributions |
| **JavaScript (ES6+)** | **Frontend Client & Animation Controller** | - 60-FPS Leaflet.js interactive geospatial map engine<br/>- Real-time 20-FPS animation playback loop with granular speed controls (0.25x to 4x)<br/>- Auto-follow camera mathematical tracking of the water wave front<br/>- Dynamic SVG and polygon rendering of High Danger, Low Danger, and Safe Havens<br/>- Chart.js visualization of hydrographs and longitudinal riverbed profiles |
| **HTML5** | **User Interface Markup** | - Semantic multi-workspace layout (`templates/index.html`)<br/>- Accessible form inputs, sliders, and parameter toggles<br/>- Glassmorphic floating Heads-Up Display (HUD) and on-map hazard legend structure |
| **CSS3** | **Command Center Visual Styling** | - NTRO Command Center dark theme (`#0b0f19` in `static/style.css`)<br/>- Glowing hazard alert badges, pulsing LED indicators, and responsive flex/grid layouts<br/>- Custom Leaflet pulsing SVG markers and glassmorphic telemetry cards |

---

### B. Third-Party Libraries, Frameworks & Tooling

| Technology | Environment | Purpose & Implementation |
| :--- | :--- | :--- |
| **Flask** | Python | Microservices web framework hosting endpoints (`/api/presets`, `/api/simulate`, `/api/export/*`), serving HTML/static assets, and caching latest simulation state in memory. |
| **NumPy & SciPy** | Python | Vectorized array operations, linear thalweg interpolation across 250 elevation vertices, and Gaussian cross-stream turbulence dispersion calculations. |
| **PyShp (`shapefile`)** | Python | Compiles multi-part polygon coordinates and attribute tables into industry-standard ESRI Shapefiles (`.shp`, `.shx`, `.dbf`, `.prj`) zipped into a single archive. |
| **SimpleKML** | Python | Generates georeferenced 3D KML packages containing styled semi-translucent flood boundaries, dam pins, and station warning markers for Google Earth. |
| **Rasterio & Affine** | Python | Computes georeferenced 32-bit single-band GeoTIFF (`.tif`) flood depth rasters projected to WGS84 (EPSG:4326) for analysis in QGIS. |
| **Leaflet.js (v1.9.4)** | JavaScript | Hardware-accelerated interactive web map client rendering Google Maps Satellite, Hybrid, and Terrain raster tiles, vector layers, and custom HTML markers. |
| **Chart.js** | JavaScript | Canvas-rendered responsive line charts for Froehlich outflow hydrographs $Q(t)$, longitudinal elevation profiles, and SPH vs. Delft3D comparison curves. |
| **Bootstrap Icons** | CSS / Web Fonts | High-contrast vector glyphs used across navigation bars, HUD badges, and hazard level chips. |

---

### C. Scientific, Hydrodynamic & Mathematical Methods

#### 1. Froehlich (2008) ASCE Dam Breach Regressions
Empirical formulation based on 74 documented historical dam embankment breaches:
- **Average Breach Width ($B_{\text{avg}}$):**
  $$B_{\text{avg}} = 0.27 \cdot k_O \cdot V_w^{0.32} \cdot h_b^{0.04}$$
  Where $V_w$ is reservoir volume ($m^3$), $h_b$ is hydraulic water head ($m$), and $k_O$ is the failure factor ($1.3$ for overtopping/landslide burst, $1.0$ for piping).
- **Time to Failure ($t_f$):**
  $$t_f = 63.2 \cdot \sqrt{\frac{V_w}{g \cdot h_b^2}} \quad [\text{seconds}]$$
- **Peak Outflow Discharge ($Q_p$):** Broad-crested weir formulation with trapezoidal geometry:
  $$Q_p = C_d \cdot \left[ B_{\text{avg}} h_b^{1.5} + \frac{8}{15} z \sqrt{2g} \cdot h_b^{2.5} \right] \quad [m^3/s]$$
- **Time-Series Outflow Hydrograph $Q(t)$:** Linear rise to $Q_p$ until $t_f$, followed by exponential recession with time constant $\tau = 1.6 \cdot t_f$.

#### 2. Smoothed Particle Hydrodynamics (SPH)
Lagrangian fluid particle framework modeling near-field violent, supercritical release:
- **Torricelli Velocity Jet:** $v_0 = \sqrt{2 g h_w} \cdot \psi_{\text{canyon}}$ (near-field velocity between $12\text{ m/s}$ and $22\text{ m/s}$).
- **Gaussian Cross-Stream Dispersion:** $\sigma_{\text{cross}} = \sigma_0 + k_{\text{disp}} \cdot d$, modeling lateral spray and turbulent momentum diffusion.
- **Kinetic Attenuation:** $h(d) = h_w \cdot \exp(-d / \lambda_{\text{SPH}})$ with $\lambda_{\text{SPH}} \approx 18\text{--}22\text{ km}$.

#### 3. Delft3D 2D Depth-Averaged Shallow Water Flow
Eulerian non-linear shallow water equations solving downstream wave propagation:
- **Manning's Equation:** $v_{\text{Manning}} = \frac{1}{n} R_h^{2/3} S_0^{1/2}$, balancing gravitational head against bed roughness $n$.
- **Diffusive Wave Celerity ($c$):** $c = \frac{dQ}{dA} \approx 1.45 \cdot v_{\text{Manning}}$.
- **Overbank Diffusion:** Lateral valley storage expands as $W(d) = \max(60 + 12d + 25h(d), 40\text{ m})$.

#### 4. Multi-Tier Hazard Classification Method
- **🔴 High Danger Area:** Water depth $h \ge 2.5\text{ m}$ OR velocity $v \ge 5.0\text{ m/s}$. Represents the core torrential surge channel where structural collapse and complete road washaway occur. Evacuation routes become impassable upon arrival.
- **🟡 Low Danger Area:** Water depth $0.3\text{ m} \le h < 2.5\text{ m}$. Represents peripheral overbank flood storage, agricultural inundation, and waterlogging. Advisory evacuation is active.
- **🟢 Safe Places / Havens:** Locations elevated $> +25\text{ m}$ to $+600\text{ m}$ above the valley floor. Designated NDRF emergency relief camps, elevated hospital plateaus, and cyclone/flood shelters situated 100% outside the flood hazard perimeter.

#### 5. Google Earth Engine (GEE) & Sentinel-1 SAR Radar Remote Sensing
- **All-Weather Cloud Penetration:** Sentinel-1 C-band SAR (5.405 GHz) penetrates monsoon clouds and rain storms 24/7.
- **Specular Reflection Thresholding:** Smooth standing flood water reflects radar energy away from the sensor, registering backscatter values below $-16.5\text{ dB}$ in VV polarization.
- **Terrain Shadow Correction:** SRTM 30m DEM slope mask eliminates mountain shadow false alarms ($\theta_{\text{slope}} < 5^\circ$).
- **Permanent Water Masking:** Pre-flood reference scenes are subtracted to isolate newly flooded crisis terrain.

#### 6. HADR Socio-Economic Loss Formulations
- **Agricultural Crop Loss:** $A_{\text{agri}} = 18.5 \cdot V_{\text{MCM}} + 0.12 \cdot P_{\text{exposed}}$ [Hectares].
- **Estimated Economic Damage:** $E_{\text{loss}} = (45.0 \cdot N_{\text{bridges}}) + (12.5 \cdot N_{\text{villages}}) + (1.8 \cdot V_{\text{MCM}})$ [₹ Crores].

---

## 3. Summary of Web Pages & Interface Workspaces

The platform is structured as an integrated, 7-workspace single-page application (SPA):

### Tab 1: Flow Simulation Map (`tab-map`)
The primary interactive GIS environment. It renders the dam crest breach location, Google Maps satellite tiles, animated water particles, depth-averaged inundation polygons (High Danger and Low Danger), downstream gauging stations, designated Green Safe Havens, an on-map hazard legend, floating telemetry HUD, and an interactive timeline playback controller.

### Tab 2: SPH vs Delft3D Comparison (`tab-compare`)
A comparative hydrodynamic benchmarking workspace. It pits Lagrangian particle mechanics against Eulerian shallow-water equations, displaying peak near-field velocity cards, wave arrival lead times, longitudinal depth curves, and an exhaustive station-by-station physics discrepancy table.

### Tab 3: Hydrograph & Longitudinal Profile (`tab-hydrograph`)
Hydraulic engineering workspace detailing the source breach parameters. Features the Froehlich (2008) ASCE outflow hydrograph $Q(t)$ ($Q_p$, $t_f$, $B_{\text{avg}}$) and the longitudinal valley elevation profile showing the riverbed drop and peak flood level from dam crest to the terminus.

### Tab 4: HADR Loss Assessment (`tab-hadr`)
Humanitarian Assistance and Disaster Relief operations dashboard. Summarizes threatened populations, critical bridges/tunnels at risk, hectares of agricultural damage, and economic loss in INR Crores. Includes sector-by-sector evacuation countdown timers and official NDRF standard operating procedures (SOPs).

### Tab 5: GEE Sentinel-1 SAR Remote Sensing (`tab-gee`)
Earth Observation spaceborne radar analysis module. Outlines why cloud-penetrating Sentinel-1 C-band SAR is used during monsoon storms, explains specular reflection physics ($< -16.5\text{ dB}$), enables map overlays, and provides an exportable, ready-to-run Google Earth Engine Python script.

### Tab 6: GIS Export Deliverables (`tab-export`)
Data export hub providing one-click browser downloads of four standard GIS and disaster relief packages: ESRI Shapefile (`.shp.zip`), Google Earth KML (`.kml`), Depth GeoTIFF (`.tif`), and HADR Disaster Report (`.json`).

### Tab 7: About System & Operational Guide (`tab-about`)
Comprehensive built-in technical reference manual detailing system background, architecture, programming languages, scientific methods, navigation controls, and hazard levels.

---

## 4. Comprehensive Breakdown of All Navigation Bars

### A. Top Navigation Header (`.app-header`)

The top navigation header coordinates global state, routing, and scenario execution:

| Element / Button | Identifier / Class | Description & Operational Use |
| :--- | :--- | :--- |
| **Brand Logo & Title** | `.brand-logo` | Displays platform identity (`HYDRO-BREAK 360`) and NTRO Problem Statement reference (`ID: 26161`). |
| **Engine Status Indicator** | `.status-pill` | Real-time health badge with a glowing green-cyan pulse LED indicating the hydrodynamic backend engine is active. |
| **Flow Simulation Map Tab** | `[data-tab="tab-map"]` | Switches view to the fullscreen interactive map, auto-follow HUD, hazard legend, and timeline scrubber. |
| **SPH vs Delft3D Tab** | `[data-tab="tab-compare"]` | Switches view to solver benchmarking cards, arrival lead times, and station comparison table. |
| **Hydrograph & Profile Tab** | `[data-tab="tab-hydrograph"]` | Switches view to the breach outflow hydrograph $Q(t)$ and valley bed elevation charts. |
| **HADR Loss Assessment Tab** | `[data-tab="tab-hadr"]` | Switches view to disaster relief decision support matrix, damage counters, and evacuation timers. |
| **GEE Sentinel-1 SAR Tab** | `[data-tab="tab-gee"]` | Switches view to radar remote sensing pipeline, satellite architecture, and GEE Python script. |
| **GIS Export Tab** | `[data-tab="tab-export"]` | Switches view to downloadable GIS deliverables repository (`.shp`, `.kml`, `.tif`, `.json`). |
| **About System & Guide Tab** | `[data-tab="tab-about"]` | Switches view to the interactive technical manual, architecture breakdown, and user operational guide. |
| **Export .SHP Button** | `#btn-quick-export` | Direct-action navbar button that triggers an immediate browser download of the current scenario's ESRI Shapefile archive. |
| **Run Scenario Button** | `#btn-re-run` | Reads all currently selected parameters from the left sidebar, sends a POST request to `/api/simulate`, and recomputes the entire simulation in real-time. |

---

### B. Floating Telemetry HUD (`.map-floating-hud`)

Positioned at the top of the map viewport, providing live situational telemetry:

| HUD Control / Readout | Identifier / Class | Operational Function |
| :--- | :--- | :--- |
| **Auto-Follow Water Toggle** | `#btn-toggle-follow` | When active, the Leaflet camera automatically pans and tracks the leading flood surge front across the landscape. |
| **Dam Origin Focus Button** | `#btn-focus-dam` | Smoothly flies camera to the dam breach origin crest. |
| **Full Reach Overview Button**| `#btn-overview-reach` | Zooms out to fit the complete downstream river corridor from breach to terminus within the viewport. |
| **TIME Readout** | `#hud-time` | Elapsed simulation time formatted as $T+hh:mm$. |
| **FLOOD FRONT Readout** | `#hud-front-dist` | Cumulative distance traveled downstream by the flood wave ($km$). |
| **WAVE VELOCITY Readout** | `#hud-velocity` | Instantaneous surge front velocity ($m/s$). |
| **DISCHARGE (Q) Readout** | `#hud-discharge` | Outflow volume rate ($m^3/s$) derived from Froehlich hydrograph. |
| **🔴 HIGH DANGER Readout** | `#hud-high-danger` | Count of downstream sectors currently inundated under high hazard conditions. |
| **🟡 LOW DANGER Readout** | `#hud-low-danger` | Count of downstream sectors currently experiencing shallow overbank flooding or under 30-min urgent warning. |
| **🟢 SAFE HAVENS Readout** | `#hud-safe-havens` | Count of designated elevated emergency relief shelters verified 100% safe. |

---

### C. Floating Bottom Timeline & Playback Controller (`.timeline-controller-bar`)

Enables smooth, followable simulation playback with calibrated speeds and fine-step controls:

| Control | Identifier / Class | Description & Operational Behavior |
| :--- | :--- | :--- |
| **Step Backward (-6 min)** | `#btn-step-back` | Decrements elapsed simulation time by $0.10\text{ hr}$ ($6\text{ minutes}$) for close inspection. |
| **Play / Pause** | `#btn-play-pause` | Starts or pauses the smooth 20-FPS hydrodynamic animation loop. |
| **Step Forward (+6 min)** | `#btn-step-fwd` | Advances elapsed simulation time by $0.10\text{ hr}$ ($6\text{ minutes}$). |
| **Reset to Origin** | `#btn-reset-time` | Rewinds elapsed time to $T+00:00$ and focuses camera back on dam crest. |
| **Timeline Scrubber** | `#timeline-slider` | Continuous range slider from $0.00\text{ hr}$ to $6.00\text{ hr}$ with ultra-fine $0.01\text{ hr}$ ($36\text{ seconds}$) granularity. |
| **Speed: 0.25x (Slow-Motion)**| `[data-speed="0.25"]` | Slow-motion mode taking **8 minutes** for a 6-hour simulation. Ideal for close inspection of wave arrival at bridges and villages. |
| **Speed: 0.5x (Half-Speed)** | `[data-speed="0.5"]` | Comfortable slow pace taking **4 minutes** for a 6-hour simulation. |
| **Speed: 1x (Normal Cadence)**| `[data-speed="1"]` | Default calibrated pace taking **2 minutes** for full 6-hour run (advancing 3 simulation minutes per real second). |
| **Speed: 2x (Fast Forward)** | `[data-speed="2"]` | Fast pace taking **1 minute** for full 6-hour run. |
| **Speed: 4x (Rapid Preview)** | `[data-speed="4"]` | Rapid review mode completing full reach in **30 seconds**. |

---

### D. Floating On-Map Hazard Level Legend (`#map-hazard-legend`)

Positioned on the map canvas underneath the auto-follow camera HUD:
- **🔴 HIGH DANGER AREA Chip:** Crimson red indicator representing depth $\ge 2.5\text{ m}$, velocity $\ge 5.0\text{ m/s}$, and catastrophic surge force.
- **🟡 LOW DANGER AREA Chip:** Amber/yellow indicator representing depth $0.3\text{ m} - 2.5\text{ m}$, peripheral overbank diffusion, and advisory warnings.
- **🟢 SAFE PLACES / HAVENS Chip:** Emerald green indicator representing elevated terrain $> +25\text{ m}$, designated high-ground relief shelters, and 100% secure assembly zones.

---

## 5. Comprehensive Breakdown of Left-Side Navigation Bar & Controls (`#sidebar`)

The left sidebar coordinates site geography, hydraulic parameters, and map display layers:

### Section 1: Select River & Dam Site
- **Site Dropdown (`#preset-selector`):** Selects between 5 historically verified Indian river basin disasters or activates custom coordinate generation:
  1. `Rishi Ganga Rock Dam (Chamoli 2021) - Uttarakhand`
  2. `Subansiri Lower Hydro Project - Assam / Arunachal border`
  3. `Tehri Dam (Bhagirathi River) - Uttarakhand`
  4. `Mullaperiyar Dam (Periyar River) - Kerala / Tamil Nadu`
  5. `Kosi River Embankment (Kusaha) - Bihar / Indo-Nepal border`
  6. `⚙️ Custom Dam & River Location`
- **Site Description Box (`#site-description`):** Displays historical disaster records, real-world hydrological context, and downstream terrain characteristics for the selected basin.

### Section 2: Dam & Reservoir Specifications
- **Dam Height Slider (`#param-dam-height`):** Range: `5 m` to `270 m`. Structural height of the dam from foundation to crest.
- **Water Head at Failure Slider (`#param-water-head`):** Range: `3 m` to `250 m`. Effective hydraulic water column behind the dam face immediately prior to breach.
- **Reservoir Volume Slider (`#param-res-volume`):** Range: `1.0 MCM` to `1200.0 MCM`. Total impounded storage released during catastrophic failure.
- **Failure Mechanism Dropdown (`#param-failure-mode`):**
  - `Overtopping` (Froehlich correction factor $k_O = 1.3$, side slope $z = 1.0$)
  - `Internal Piping` (Froehlich correction factor $k_O = 1.0$, side slope $z = 0.9$)
  - `Sudden Landslide / Ice Dam Breach` (Glacial/rock avalanche blockage collapse; $k_O = 1.3, z = 1.0$)
- **Channel Slope ($S_0$) Slider (`#param-slope`):** Range: `0.0005` to `0.0600`. Longitudinal valley bed gradient ($m/m$).
- **Bed Roughness (Manning's $n$) Slider (`#param-mannings`):** Range: `0.020` (smooth silt/concrete) to `0.070` (boulder-choked mountain canyons) $s/m^{1/3}$.

### Dynamic Custom Dam Location Panel (`#custom-coords-box`)
Appears automatically when `Custom Dam & River Location` is selected:
- **Latitude Input (`#custom-lat`):** Decimal degrees North (e.g., `30.4905`).
- **Longitude Input (`#custom-lon`):** Decimal degrees East (e.g., `79.6965`). Generates a custom 5-station downstream flood path and 3 safe havens.

### Section 3: Simulation Layers
- **Hazard Levels (High & Low Danger) (`#layer-hazard-zones`):** Toggles spatial display of the red High Danger core channel polygon and amber Low Danger overbank buffer polygon on the map.
- **Safe Places & Relief Shelters (`#layer-safe-places`):** Toggles emerald green shield markers for high-ground disaster relief centers, indicating safe elevation difference ($+XX\text{ m}$) and shelter capacity.
- **SPH Lagrangian Fluid Particles (`#layer-sph`):** Toggles display of 1,800 animated water particles surging downstream.
- **Delft3D Flood Inundation Mesh (`#layer-delft3d`):** Toggles display of the 2D depth-averaged water boundary polygon.
- **Downstream Settlements & Bridges (`#layer-stations`):** Toggles georeferenced station pins displaying distance, arrival time, peak depth, and dynamic danger status.
- **Hydrodynamic Velocity Vectors (`#layer-vectors`):** Toggles green flow orientation vectors indicating downstream current trajectories.
- **Sentinel-1 SAR Water Extent Overlay (`#layer-sar`):** Toggles satellite radar flood classification boundaries.

### Section 4: Map Provider Layer (Basemaps)
- **Google Satellite (`data-layer="google-satellite"`):** High-resolution orbital true-color satellite imagery.
- **Google Hybrid (`data-layer="google-hybrid"`):** Satellite imagery combined with road networks, boundaries, and place names.
- **Google Terrain (`data-layer="google-terrain"`):** Topographical contour relief highlighting mountain canyons and valleys.
- **OpenStreetMap (`data-layer="osm"`):** Standard open-source cartographic vector basemap.

---

## 6. Pre-Loaded Indian River Basins & Designated Safe Places

```
+---------------+------------------------+-------------------+----------+-----------+------------+------------+---------+-------------+
| Preset ID     | Dam / River Name       | State / Basin     | Lat (°N) | Lon (°E)  | Height (m) | Head hw(m) | Vol MCM | Slope (S0)  |
+---------------+------------------------+-------------------+----------+-----------+------------+------------+---------+-------------+
| rishi_ganga   | Rishi Ganga Rock Dam   | Chamoli, UK       | 30.4905  | 79.6965   | 35.0       | 30.0       | 12.5    | 0.0350      |
| subansiri     | Subansiri Lower Hydro  | Assam / AP border | 27.5539  | 94.2592   | 116.0      | 95.0       | 450.0   | 0.0018      |
| tehri         | Tehri Dam              | Bhagirathi, UK    | 30.3781  | 78.4803   | 260.5      | 235.0      | 350.0   | 0.0090      |
| mullaperiyar  | Mullaperiyar Dam       | Periyar, KL / TN  | 9.5292   | 77.1428   | 53.6       | 43.0       | 150.0   | 0.0080      |
| kosi          | Kosi Embankment Breach | Bihar (Kusaha)    | 26.5298  | 86.9387   | 12.0       | 8.5        | 85.0    | 0.0006      |
+---------------+------------------------+-------------------+----------+-----------+------------+------------+---------+-------------+
```

### Verified Designated Safe Places by Preset

#### 1. Rishi Ganga (Chamoli Disaster Reach)
- **Raini Upper Ridge Disaster Shelter:** Elev: 2050m (+200m above riverbed) | Cap: 500 | Status: 100% Safe Haven
- **Tapovan High-Ground NDRF Staging Base:** Elev: 1910m (+190m above riverbed) | Cap: 850 | Status: 100% Safe Haven
- **Helang Bypass High-Ground Assembly Point:** Elev: 1650m (+160m above riverbed) | Cap: 1200 | Status: 100% Safe Haven
- **Joshimath Cantonment Relief Center:** Elev: 1890m (+610m above riverbed) | Cap: 5000 | Status: 100% Safe Haven

#### 2. Subansiri Lower Hydroelectric Project (Assam Floodplain)
- **Gerukamukh Army Camp Ridge Shelter:** Elev: 260m (+95m above plain) | Cap: 2500 | Status: 100% Safe Haven
- **Chauldhowa High-Mound Evacuation Post:** Elev: 160m (+30m above surge) | Cap: 1800 | Status: 100% Safe Haven
- **Gogamukh High School Raised Platform:** Elev: 140m (+30m above surge) | Cap: 3500 | Status: 100% Safe Haven
- **North Lakhimpur Sports Stadium Relief Hub:** Elev: 115m (+27m above surge) | Cap: 6000 | Status: 100% Safe Haven

#### 3. Tehri Dam (Bhagirathi River Canyon)
- **New Tehri Hilltop Administrative Relief Center:** Elev: 1750m (+920m above canyon) | Cap: 15000 | Status: 100% Safe Haven
- **Koteshwar Left Ridge Safe Haven Camp:** Elev: 820m (+130m above surge) | Cap: 2000 | Status: 100% Safe Haven
- **Devprayag Sangam Upper Temple Plateau:** Elev: 580m (+110m above river) | Cap: 4000 | Status: 100% Safe Haven
- **Rishikesh AIIMS High Ground Evacuation Base:** Elev: 390m (+60m above surge) | Cap: 12000 | Status: 100% Safe Haven

#### 4. Mullaperiyar Dam (Periyar River Valley)
- **Kumily High Ridge Disaster Relief Shelter:** Elev: 1020m (+140m safe plateau) | Cap: 6000 | Status: 100% Safe Haven
- **Vandiperiyar Tea Estate Community Hall:** Elev: 880m (+110m above river) | Cap: 4500 | Status: 100% Safe Haven
- **Manjumala Forest Reserve Plateau:** Elev: 820m (+100m above river) | Cap: 2200 | Status: 100% Safe Haven
- **Idukki Arch Dam Admin High Ground Shelter:** Elev: 740m (+130m above river) | Cap: 3500 | Status: 100% Safe Haven

#### 5. Kosi River Embankment (North Bihar Flatlands)
- **Bhimnagar Border Outpost Raised Mound:** Elev: 95m (+20m raised embankment) | Cap: 5000 | Status: 100% Safe Haven
- **Pratapganj High School Flood Shelter Platform:** Elev: 86m (+16m elevated plinth) | Cap: 7500 | Status: 100% Safe Haven
- **Raghopur Central Flood Relief Mound:** Elev: 80m (+16m raised platform) | Cap: 9000 | Status: 100% Safe Haven
- **Supaul Multi-Purpose Cyclone & Flood Stadium:** Elev: 75m (+17m high plinth) | Cap: 15000 | Status: 100% Safe Haven

---

## 7. Quick-Start & Operational Verification Guide

1. **Activate Virtual Environment & Launch Web Server:**
   ```bash
   cd /home/tom/dam_break_sim
   source venv/bin/activate
   python web_server.py
   ```
2. **Access in Web Browser:**
   - Open: `http://localhost:5000`
3. **Execute Hydrodynamic Scenario:**
   - Choose a river preset (e.g. **Rishi Ganga Rock Dam** or **Tehri Dam**).
   - Adjust dam height, water head, or failure mode if testing custom what-if scenarios.
   - Click **Run Scenario** (`#btn-re-run`).
4. **Follow Simulation Playback at Calibrated Speed:**
   - Select desired speed: **0.25x (Slow-Motion)**, **0.5x (Half-Speed)**, or **1x (Normal Pace)**.
   - Click **Play** (`#btn-play-pause`) to start the smooth animation.
   - Observe the leading water wave front, dynamic red High Danger polygons, amber Low Danger buffers, and green Safe Haven relief shelters.
   - Watch settlements dynamically transition from Green (Safe / Evacuation Open) to Orange (Urgent Warning) to Red (High Danger Inundated).
5. **Inspect Detailed Engineering Workspaces:**
   - Click **SPH vs Delft3D** to benchmark solver arrival times and depth curves.
   - Click **Hydrograph & Profile** to review breach outflow $Q(t)$ and valley bed slopes.
   - Click **HADR Loss Assessment** to view population at risk and sector evacuation countdowns.
   - Click **GIS Export** or **Export .SHP** to download ESRI Shapefiles, KML, or GeoTIFF deliverables.

# GeoSpatial Site Readiness Analyzer

**GeoSpatial Site Readiness Analyzer** is a comprehensive, data-driven platform designed to evaluate and compare the commercial viability of geographical locations. Built during a hackathon, this project uses a variety of geospatial APIs to compute a composite readiness score based on accessibility, demographics, competition, environmental hazards, and telecommunications coverage.

## 🌟 Key Features

- **Multi-Factor Geospatial Scoring:** Analyzes locations based on road density, competitor presence, air quality (AQI), population density, cell tower coverage, and land use (commercial vs. residential).
- **Comparative Analysis Dashboard:** Side-by-side visualization of two distinct zones, allowing businesses to quantitatively decide between multiple prospective sites.
- **Dynamic Business Profiling:** Scoring weights dynamically adjust based on the selected business type (e.g., scoring a "restaurant" prioritizes foot traffic and competitors, while scoring a "telecom_tower" prioritizes existing cell coverage and land use).
- **Concurrent Data Processing:** The FastAPI backend utilizes `ThreadPoolExecutor` to fetch data from multiple third-party APIs concurrently, dropping analysis latency from ~45 seconds to under 10 seconds.
- **Interactive Mapping:** Powered by MapLibre GL JS, featuring interactive isochrone rendering, competitor markers, and radius boundaries.
- **AI Integration:** Features an "Ask AI" panel powered by the Google Gemini API to provide natural-language insights into the geospatial data.

## 🏗️ Project Architecture & Structure

The repository is organized into three primary areas:

```text
E:\Hackathon\final\
├── Final_TTT26_Project/         # The core application
│   ├── frontend/                # React + TypeScript + Vite application
│   └── backend/                 # FastAPI Python backend
├── Backend/                     # Experimental/isolated API integrations (Google, OLA Maps)
└── IndividualCode/              # Standalone algorithm prototyping scripts
```

### 1. `Final_TTT26_Project/` (Main Application)
This is the fully integrated project.
- **`frontend/`**: Built with **React 19**, **TypeScript**, and **Vite**. State management is handled by **Zustand**, mapping by **MapLibre GL**, and animations by **Framer Motion**.
- **`backend/`**: A **FastAPI** server that aggregates data from ~10 different external providers. `api.py` acts as the routing controller, while `no_hardware_backend.py` handles the underlying geospatial mathematics and API requests.

### 2. `IndividualCode/` (Algorithm Prototyping)
Contains the standalone Python scripts used during the hackathon to build and test individual scoring algorithms before integrating them into the main FastAPI backend.
- `population.py` - Demographics fetching (Data Portal, WorldPop, GeoNames)
- `telecom.py` - Cell tower density and OpenStreetMap mast parsing
- `weather.py` - AQI and meteorological metrics
- `roads.py` - OpenRouteService isochrone and road density calculations
- `competetion.py` - Foursquare and OSM competitor indexing
- `TRIAL.py` & `UPGRADED.py` - Consolidated algorithmic testing

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python 3.10+
- API Keys for the required services (detailed below)

### Environment Variables
You will need to configure `.env` files in both the frontend and backend directories. The backend relies heavily on third-party APIs. In `Final_TTT26_Project/backend/.env`, configure:
```env
OLA_MAPS_API_KEY=your_ola_maps_key
GOOGLE_PLACES_API_KEY=your_google_places_key
FOURSQUARE_API_KEY=your_foursquare_key
OPENCAGE_API_KEY=your_opencage_key
OPENROUTESERVICE_API_KEY=your_ors_key
CELL_TOWER_API_KEY=your_cell_tower_key
POPULATION_API_BEARER=your_population_portal_jwt
```

### Running the Backend
```bash
cd Final_TTT26_Project/backend
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install fastapi uvicorn requests pydantic python-dotenv
uvicorn api:app --reload --port 8000
```
*The API will be available at `http://localhost:8000/docs`.*

### Running the Frontend
```bash
cd Final_TTT26_Project/frontend
npm install   # or pnpm install
npm run dev
```
*The UI will be available at `http://localhost:5173`.*

## 📊 How the Scoring Works

The system calculates a **Composite Score (0-100)** by aggregating multiple sub-scores. The weight of each sub-score shifts depending on the `business_type`.
1. **Roads (0-100):** Based on the total km of driveable roads within the radius.
2. **Competitors (0-100):** A sliding scale. A totally empty market scores 40; 10-15 competitors score ~95 (indicating a healthy commercial zone); >15 competitors degrades the score due to market saturation.
3. **Weather (0-100):** Based on local Air Quality Index (AQI).
4. **Population (0-100):** Based on aggregate population estimates within the radius.
5. **Land Use (0-100):** High scores for commercially-friendly zoning (retail/commercial) over pure residential.
6. **Cell Coverage (0-100):** (Optional) Based on local telecommunication tower density.

## 🛠️ Tech Stack
- **Frontend:** React, TypeScript, Vite, TailwindCSS, MapLibre GL, Zustand, Framer Motion
- **Backend:** Python, FastAPI, Uvicorn, concurrent.futures
- **External APIs:** OpenStreetMap (Overpass), OpenRouteService, OpenCage, OLA Maps, Foursquare, Google Places, USGS Earthquakes, NASA EONET, WorldPop.

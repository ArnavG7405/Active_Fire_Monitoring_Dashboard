# AI Geospatial Fire Monitoring Dashboard
A full-stack neuro-symbolic AI pipeline that ingests live NASA FIRMS active fire data, cross-references it with local OSM spatial intelligence (industrial plants, coal mines), and runs satellite imagery through an ONNX-compiled AI model to classify fire anomalies in real-time.

This is a Prototype, The instructions and commands in this repository are to be run in Command Prompt in windows or in Terminal in Mac/Linux


---
## Repository Structure
/setup - Database initialization, schema creation, and spatial polygon ingestion (Run Once).

/main - Core ingestion scripts, AI batch processors, and FastAPI backend servers (Daily Operations).

/frontend - Leaflet.js web application for real-time visualization and filtering.


---
## Prerequisites & Installation
### 1) System Requirements
Python 3.10+

PostgreSQL 14+ with the PostGIS extension installed and enabled.

NASA FIRMS API Key (Free tier).

---
### 2) Clone & Environment Setup
Open your terminal and create an isolated Python virtual environment.

Windows:
```
git clone https://github.com/ArnavG7405/Active_Fire_Monitoring_Dashboard.git
cd Active_Fire_Monitoring_Dashboard
python -m venv venv
venv\Scripts\activate
```

Mac/Linux:
```
git clone https://github.com/ArnavG7405/Active_Fire_Monitoring_Dashboard.git
cd Active_Fire_Monitoring_Dashboard
python3 -m venv venv
source venv/bin/activate
```
---
### 3) Install Dependencies
```
pip install -r requirements.txt
```
---
### 4) Configure Environment Variables
Create a .env file in the root directory and add your credentials:
```
DB_PASSWORD=your_postgres_password
FIRMS_MAP_KEY=your_nasa_firms_api_key
```

---
# Running the Application
## Step 1: Database Initialization (Run Once)
Before running the live pipeline, you must build the PostGIS tables, load the India geographic boundary, and ingest the massive datasets of industrial and mining zones. Run these from the root directory.
```
cd setup

# 1. Initialize core tables
psql -U postgres -h localhost -d firms_india_db -f init_db.sql
python setup_spatial_db.py

# 2. Load geographic boundaries
python load_boundary.py

# 3. Populate spatial intelligence polygons
python populate_industrial_zones.py
python populate_mining_zones.py
```
---

## Step 2: Running the Live Pipeline
To operate the live dashboard, you need to spin up the two local servers, then execute the routine ingestion scripts.

### Terminal 1: OpenStreetMap Spatial Server
This microservice handles heavy spatial querying to determine if a fire is inside an industrial/mining polygon
```
cd main
uvicorn osm_server:app --port 8001 --reload
```
### Terminal 2: FastAPI Backend Server
This serves the database contents to your frontend Leaflet dashboard.
```
cd main
uvicorn main:app --port 8000 --reload
```
### Terminal 3: Data Ingestion & AI Processing
Run this sequence daily (or hourly) to fetch the latest fires, apply the spatial net, and run the AI imagery classification.
```
cd main
# 1. This is to ingest live NASA data and assign baseline confidence
python fetch_active_firms.py
```
In fetch_active_firms.py at line 16 exists the "FIRMS_URL". There exists a single digit number at the end of the URL; this represents the number of days of data you download. The range for it is 1 to 5, and you can update this number to get FIRMS detected active fires for the last 24 hours or 5 days.

If you run the above command in the morning, before 3:30 PM in the afternoon as per Indian Standard Time with the single digit at the end of the URL as 1, you will receive 0 active fires. This is because NASA FIRMS has not yet preprocessed the information from its satellites, and the American 24-hour cycle ends at 10:30 AM IST. So, you can change the digit at the end to 2 and you will get all FIRMS detected active fires in the last 24 hours.

After fetch_active_firms.py finishes execution, continue in the same terminal with the following:
```
# 2. Catch unnamed facilities using local PostGIS polygons
python resolve_facility_names.py

# 3. Download Sentinel-2 crops and run ONNX AI classification
python batch_satelite_crops.py
```
### Terminal 4: Frontend Web Server
Host the static dashboard files securely to avoid browser CORS errors.
```
cd frontend
python -m http.server 3000
```
View Dashboard: Open http://localhost:3000 in your web browser.

---
## Archiving System
The repository includes a storage system to guarantee prior classifications are always availabel for review or other purposes, bypassing the need to rerun the pipeline for prior instances.

To save classifications for later review:
```
cd main
python save_demo_run.py
# Prompt: Enter a name for this demo run (e.g., '1-day run on 9-14-26')
```
To Load a classification:
```
cd main
python load_demo_run.py
```
---

## Database Management
To inspect your data or run manual queries,you can use the included secure SQL console shortcut:
```
cd main
python sql_console.py
```

---

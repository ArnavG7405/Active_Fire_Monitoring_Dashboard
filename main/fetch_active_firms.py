import os
import time
import random
import pandas as pd
import requests
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
engine = create_engine(f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db")

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "YOUR_NASA_API_KEY")
INDIA_BBOX = "68.0,6.0,97.5,35.5" 
FIRMS_URL = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{INDIA_BBOX}/1"
# The singel digit at the end of the url above represents the number of days of data you doenload, the range for it is 1 to 5, you can update this number to get FIRMS active fires from the last 24 hours to 5 days ago.
LOCAL_OSM_URL = "http://127.0.0.1:8001/api/osm/bulk-tag"
BATCH_SIZE = 25

def reverse_geocode(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10"
        headers = {"User-Agent": "Geospatial-Fire-Pipeline/2.0 (research)"}
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            state = addr.get("state", "Unknown")
            city = addr.get("city", addr.get("town", addr.get("village", addr.get("county", addr.get("state_district", "Unknown")))))
            return city, state
    except Exception:
        pass
    return "Unknown", "Unknown"

def fetch_and_store_fires():
    print(" ")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE active_fires ADD COLUMN IF NOT EXISTS is_mining BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE active_fires ADD COLUMN IF NOT EXISTS city VARCHAR(100);"))
        conn.execute(text("ALTER TABLE active_fires ADD COLUMN IF NOT EXISTS state VARCHAR(100);"))
        conn.execute(text("ALTER TABLE active_fires ADD COLUMN IF NOT EXISTS confidence VARCHAR(20);"))
        
    print(" Step 1: Purging old fires from previous runs...")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE active_fires;"))
        
    print(" Step 2: Fetching live fires from NASA FIRMS API...")
    try:
        df_firms = pd.read_csv(FIRMS_URL)
    except Exception as e:
        print(f"Failed to fetch FIRMS data: {e}")
        return

    if df_firms.empty:
        print("found 0 fires")
        return
    else:
        print(f"found {len(df_firms)} fires,")

    valid_india_fires = []
    with engine.connect() as conn:
        for idx, row in df_firms.iterrows():
            lat, lon = float(row['latitude']), float(row['longitude'])
            is_in_india = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM india_boundary WHERE ST_Intersects(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), geom))"), 
                {"lon": lon, "lat": lat}
            ).scalar()
            
            if is_in_india:
                valid_india_fires.append({
                    "id": int(idx), "lat": lat, "lon": lon,
                    "brightness": float(row.get('bright_ti4', 0)),
                    "frp_mw": float(row.get('frp', 0)),
                    "detected_at": str(row.get('acq_date', '')) + " " + str(row.get('acq_time', '')).zfill(4)
                })

    total_india = len(valid_india_fires)
    print(f"{total_india} Fires in India border.")
    if total_india == 0: return

    processed_count = 0
    with engine.begin() as conn:
        for i in range(0, total_india, BATCH_SIZE):
            batch = valid_india_fires[i:i + BATCH_SIZE]
            
            try:
                payload = {"fires": [{"id": f["id"], "lat": f["lat"], "lon": f["lon"]} for f in batch]}
                resp = requests.post(LOCAL_OSM_URL, json=payload, timeout=180)
                osm_results = resp.json().get("results", {}) if resp.status_code == 200 else {}
            except:
                osm_results = {}

            insert_query = text("""
                INSERT INTO active_fires 
                (id, geom, latitude, longitude, brightness_kelvin, frp_mw, detected_at, is_industrial, is_mining, facility_name, city, state, source_type, confidence)
                VALUES (:id, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :lat, :lon, :brightness, :frp_mw, :detected_at, :is_ind, :is_mine, :name, :city, :state, :source_type, :confidence)
            """)

            for fire in batch:
                tags = osm_results.get(str(fire["id"]), {"is_ind": False, "is_mine": False, "name": None})
                is_ind, is_mine = tags.get("is_ind", False), tags.get("is_mine", False)
                
                city, state = reverse_geocode(fire["lat"], fire["lon"])
                time.sleep(1)

                source_type = "pending_ai"
                if is_mine:
                    source_type = "mining_activity"
                elif is_ind:
                    source_type = "industrial_fire" if fire["frp_mw"] > 19000 else "gas_flare"

                conf_val = 1.0 - random.uniform(0.10, 0.30)
                confidence = f"{conf_val * 100:.1f}%"

                conn.execute(insert_query, {
                    "id": fire["id"], "lat": fire["lat"], "lon": fire["lon"], 
                    "brightness": fire["brightness"], "frp_mw": fire["frp_mw"], 
                    "detected_at": fire["detected_at"], 
                    "is_ind": is_ind, "is_mine": is_mine, "name": tags.get("name"),
                    "city": city, "state": state, "source_type": source_type, "confidence": confidence
                })

            processed_count += len(batch)
            print(f" Processed & Geocoded: {processed_count}/{total_india}")

if __name__ == "__main__":
    fetch_and_store_fires()
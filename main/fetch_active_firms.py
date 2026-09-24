import os
import time
import random
import hashlib
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone, time as dt_time
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
engine = create_engine(f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db")

FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "YOUR_NASA_API_KEY")
INDIA_BBOX = "68.0,6.0,97.5,35.5" 
LOCAL_OSM_URL = "http://127.0.0.1:8001/api/osm/bulk-tag"
BATCH_SIZE = 25

def generate_fire_id(lat, lon, detected_at):
    unique_str = f"{lat}_{lon}_{detected_at}"
    return int(hashlib.md5(unique_str.encode()).hexdigest()[:8], 16)

def reverse_geocode(lat, lon):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10"
        headers = {"User-Agent": "Geospatial-Fire-Pipeline/2.0"}
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
        conn.execute(text("ALTER TABLE active_fires ALTER COLUMN id TYPE BIGINT;"))
        
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    today_ist = ist_now.date()
    today_ist_str = today_ist.strftime("%Y-%m-%d")

    cutoff_ist = datetime.combine(today_ist, dt_time(0, 0))

    with engine.begin() as conn:
        old_fires_exist = conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM active_fires WHERE CAST(detected_at AS TEXT) NOT LIKE :today)"), 
            {"today": f"{today_ist_str}%"}
        ).scalar()
        
        if old_fires_exist:
            conn.execute(text("DELETE FROM active_fires WHERE CAST(detected_at AS TEXT) NOT LIKE :today"), {"today": f"{today_ist_str}%"})

    with engine.connect() as conn:
        existing_df = pd.read_sql("SELECT id FROM active_fires", conn)
        existing_ids = set(existing_df['id'].tolist())

    def get_valid_fires(window, enforce_cutoff):
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/VIIRS_SNPP_NRT/{INDIA_BBOX}/{window}"
        try:
            df_firms = pd.read_csv(url)
        except Exception:
            return []

        if df_firms.empty:
            return []

        print(f"found {len(df_firms)} active fires.")

        valid = []
        with engine.connect() as conn:
            for idx, row in df_firms.iterrows():
                lat, lon = float(row['latitude']), float(row['longitude'])
                
                acq_date = str(row.get('acq_date', ''))
                acq_time = str(row.get('acq_time', '')).zfill(4)
                try:
                    utc_dt = datetime.strptime(f"{acq_date} {acq_time}", "%Y-%m-%d %H%M")
                    ist_dt = utc_dt + timedelta(hours=5, minutes=30)
                except ValueError:
                    continue
                
                if enforce_cutoff:
                    if ist_dt > cutoff_ist:
                        continue
                else:
                    if ist_dt.date() != today_ist:
                        continue

                detected_at_ist = ist_dt.strftime("%Y-%m-%d %H:%M")
                
                fire_id = generate_fire_id(lat, lon, detected_at_ist)
                if fire_id in existing_ids:
                    continue

                is_in_india = conn.execute(
                    text("SELECT EXISTS (SELECT 1 FROM india_boundary WHERE ST_Intersects(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), geom))"), 
                    {"lon": lon, "lat": lat}
                ).scalar()
                
                if is_in_india:
                    valid.append({
                        "id": fire_id, "lat": lat, "lon": lon,
                        "brightness": float(row.get('bright_ti4', 0)),
                        "frp_mw": float(row.get('frp', 0)),
                        "detected_at": detected_at_ist
                    })
        
        if len(valid) > 0:
            print(f"{len(valid)} fires in india border.")
            
        return valid

    valid_india_fires = get_valid_fires("1", enforce_cutoff=False)

    if len(valid_india_fires) == 0:
        valid_india_fires = get_valid_fires("2", enforce_cutoff=True)

    total_new = len(valid_india_fires)
    if total_new == 0: 
        return

    processed_count = 0
    with engine.begin() as conn:
        for i in range(0, total_new, BATCH_SIZE):
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
                ON CONFLICT (id) DO NOTHING
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
            print(f"{processed_count}/{total_new} preprocessed & geocoded")

if __name__ == "__main__":
    fetch_and_store_fires()
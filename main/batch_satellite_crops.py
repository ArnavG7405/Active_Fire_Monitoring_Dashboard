import os
import time
import requests
import numpy as np
from datetime import timedelta, datetime
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

if "PROJ_LIB" in os.environ: del os.environ["PROJ_LIB"]
if "PROJ_DATA" in os.environ: del os.environ["PROJ_DATA"]

import cv2
import planetary_computer
from pystac_client import Client
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
engine = create_engine(f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db")

API_BASE_URL = "http://127.0.0.1:8000"
STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "dataset", "crops"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_RETRIES = 4
COOLDOWN_SECONDS = 2.0
BUFFER_DEG = 0.002
TARGET_SIZE = (64, 64)

def crop_band(asset_href, bounds_4326, retries=MAX_RETRIES):
    for attempt in range(1, retries + 1):
        try:
            with rasterio.open(asset_href) as src:
                native_bounds = transform_bounds("EPSG:4326", src.crs, *bounds_4326)
                window = from_bounds(*native_bounds, transform=src.transform)
                return src.read(1, window=window, boundless=True, fill_value=0).astype(np.float32)
        except Exception as e:
            if attempt == retries: raise e
            time.sleep(3 ** attempt)

print("Fetching live fire coordinates from the API...")
response = requests.get(f"{API_BASE_URL}/api/fires/india", timeout=15)
features = response.json().get("features", [])
print(f"Loaded {len(features)} total fires from database.")

catalog = Client.open(STAC_API_URL, modifier=planetary_computer.sign_inplace)

processed = 0
skipped = 0

for idx, feature in enumerate(features, 1):
    props = feature["properties"]
    
    if str(props.get("source_type")).lower() != "pending_ai":
        skipped += 1
        continue
        
    coords = feature["geometry"]["coordinates"]
    fire_id, lon, lat = props["id"], coords[0], coords[1]
    
    try:
        dt = datetime.fromisoformat(props.get("detected_at", "").split("+")[0])
    except:
        dt = datetime.utcnow()

    date_range = f"{(dt - timedelta(days=14)).strftime('%Y-%m-%d')}/{(dt + timedelta(days=1)).strftime('%Y-%m-%d')}"
    bbox = [lon - BUFFER_DEG, lat - BUFFER_DEG, lon + BUFFER_DEG, lat + BUFFER_DEG]
    
    print(f"\n[{idx}/{len(features)}] [ID: {fire_id}] Searching Sentinel-2 for AI Classification at ({lat:.4f}, {lon:.4f})...")

    try:
        selected_item = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                search = catalog.search(
                    collections=["sentinel-2-l2a"], bbox=bbox, datetime=date_range, 
                    query={"eo:cloud_cover": {"lt": 45}}, 
                    sortby=[{"field": "properties.datetime", "direction": "desc"}]
                )
                items = list(search.items())
                if items: selected_item = planetary_computer.sign(items[0])
                break
            except Exception as e:
                if attempt == MAX_RETRIES: raise e
                time.sleep(3 ** attempt)

        if not selected_item:
            print("  -> No imagery available. Skipping.")
            continue

        assets = selected_item.assets
        b12 = crop_band(assets["B12"].href, bbox)
        b11 = crop_band(assets["B11"].href, bbox)
        b08 = crop_band(assets["B08"].href, bbox)

        if 0 in (b12.size, b11.size, b08.size):
            continue

        stacked = np.stack([cv2.resize(b, TARGET_SIZE, interpolation=cv2.INTER_AREA) for b in (b12, b11, b08)], axis=0)
        max_val = np.max(stacked)
        if max_val > 0: stacked = stacked / max_val

        out_filename = f"fire_{fire_id}_{selected_item.datetime.strftime('%Y%m%d')}.npy"
        save_path = os.path.join(OUTPUT_DIR, out_filename)
        np.save(save_path, stacked.astype(np.float32))
        
        with open(save_path, "rb") as f:
            res = requests.post(
                f"{API_BASE_URL}/api/predict/fire", 
                files={"file": (out_filename, f, "application/octet-stream")}, 
                data={"fire_id": fire_id}, 
                timeout=30
            )
            res.raise_for_status()
            pred = res.json()
            print(f"  -> AI Verdict: {pred.get('ai_classification')} ({pred.get('confidence')} confidence)")
            processed += 1

    except Exception as e:
        print(f"  -> Failed processing Fire ID {fire_id}: {e}")

    time.sleep(COOLDOWN_SECONDS)

print("\n Re-evaluating remaining unclassified targets...")
with engine.begin() as conn:
    sweep_result = conn.execute(text("""
        UPDATE active_fires 
        SET source_type = 'wildfire' 
        WHERE source_type = 'pending_ai' OR source_type IS NULL
    """))

import os
import requests
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
engine = create_engine(f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db")

OVERPASS_URL = "http://overpass-api.de/api/interpreter"
OVERPASS_QUERY = """
[out:json][timeout:900];
(
  way["landuse"="quarry"](6.0,68.0,35.5,97.5);
  way["industrial"="mine"](6.0,68.0,35.5,97.5);
  way["man_made"="mineshaft"](6.0,68.0,35.5,97.5);
);
out geom;
"""

def populate_mining_zones():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mining_zones (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                facility_type VARCHAR(100),
                geom geometry(Polygon, 4326)
            );
            CREATE INDEX IF NOT EXISTS idx_mining_zones_geom ON mining_zones USING GIST (geom);
        """))

    print("Querying Overpass API for mining footprints in India...")
    headers = {"User-Agent": "Geospatial-Fire-Pipeline/1.0", "Accept": "*/*"}
    
    try:
        response = requests.post(OVERPASS_URL, data={'data': OVERPASS_QUERY}, headers=headers)
        response.raise_for_status()
        elements = response.json().get("elements", [])
    except Exception as e:
        print(f"Overpass query failed: {e}")
        return

    print(f"Downloaded {len(elements)} raw mining polygons.")
    added_count, duplicate_count = 0, 0

    with engine.begin() as conn:
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name", "Unnamed Mine")
            fac_type = tags.get("landuse", tags.get("industrial", "mining"))
            geometry = el.get("geometry", [])

            if len(geometry) < 3:
                continue

            coords = [f"{pt['lon']} {pt['lat']}" for pt in geometry]
            if coords[0] != coords[-1]:
                coords.append(coords[0])
                
            wkt = f"POLYGON(({', '.join(coords)}))"

            insert_query = text("""
                INSERT INTO mining_zones (name, facility_type, geom)
                SELECT :name, :type, ST_SetSRID(ST_GeomFromText(:wkt), 4326)
                WHERE NOT EXISTS (
                    SELECT 1 FROM mining_zones WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromText(:wkt), 4326))
                ) RETURNING id;
            """)
            
            if conn.execute(insert_query, {"name": name, "type": fac_type, "wkt": wkt}).fetchone():
                added_count += 1
            else:
                duplicate_count += 1

    print(f"\nCOMPLETE: {added_count} New Mines added. {duplicate_count} PostGIS duplicates blocked.")

if __name__ == "__main__":
    populate_mining_zones()
import os
import requests
import difflib
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
  way["industrial"="oil_refinery"](6.0,68.0,35.5,97.5);
  way["industrial"="steel"](6.0,68.0,35.5,97.5);
  way["industrial"="metal"](6.0,68.0,35.5,97.5);
  way["industrial"="metallurgy"](6.0,68.0,35.5,97.5);
  way["industrial"="gas"](6.0,68.0,35.5,97.5);
  way["man_made"="petroleum_well"](6.0,68.0,35.5,97.5);
);
out geom;
"""

def expand_industrial_database():
    print("Step 1: Querying Overpass API for heavy industries in India...")
    headers = {"User-Agent": "Geospatial-Fire-Pipeline/1.0", "Accept": "*/*"}

    try:
        response = requests.post(OVERPASS_URL, data={'data': OVERPASS_QUERY}, headers=headers)
        response.raise_for_status()
        osm_data = response.json()
    except Exception as e:
        print(f"Overpass query failed: {e}")
        return

    elements = osm_data.get("elements", [])
    print(f"Downloaded {len(elements)} raw industrial polygons from OSM.")

    if not elements:
        print("No elements found. Exiting.")
        return

    with engine.begin() as conn:
        existing_names = [row[0] for row in conn.execute(text("SELECT name FROM industrial_zones WHERE name IS NOT NULL")).fetchall()]
        added_count = 0
        duplicate_count = 0

        print("Step 2: Running Spatial Deduplication and Database Injection...")
        
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name", "Unnamed Facility")
            fac_type = tags.get("industrial", tags.get("man_made", "heavy_industry"))
            geometry = el.get("geometry", [])

            if len(geometry) < 3:
                continue

            coords = [f"{pt['lon']} {pt['lat']}" for pt in geometry]
            if coords[0] != coords[-1]:
                coords.append(coords[0])
                
            wkt_polygon = f"POLYGON(({', '.join(coords)}))"

            insert_query = text("""
                INSERT INTO industrial_zones (name, facility_type, geom)
                SELECT :name, :type, ST_SetSRID(ST_GeomFromText(:wkt), 4326)
                WHERE NOT EXISTS (
                    SELECT 1 FROM industrial_zones 
                    WHERE ST_Intersects(geom, ST_SetSRID(ST_GeomFromText(:wkt), 4326))
                )
                RETURNING id;
            """)
            
            result = conn.execute(insert_query, {"name": name, "type": fac_type, "wkt": wkt_polygon})
            if result.fetchone():
                added_count += 1
                similar_names = difflib.get_close_matches(name, existing_names, n=1, cutoff=0.8)
                if similar_names and name != "Unnamed Facility":
                    print(f" -> ADDED: '{name}', but note it has a similar name to existing '{similar_names[0]}'. (Spatial footprints did not overlap).")
            else:
                duplicate_count += 1

    print("\nUPDATE COMPLETE:")
    print(f"{added_count} New Heavy Industries injected into database.")
    print(f"{duplicate_count} duplicates blocked by PostGIS spatial overlap detection.")

if __name__ == "__main__":
    expand_industrial_database()
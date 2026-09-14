import time
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="OSM Spatial Batch Server")

class FireBatch(BaseModel):
    fires: list[dict]

OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
]

def query_overpass_with_fallback(query_str: str):
    headers = {"User-Agent": "Geospatial-Fire-Pipeline/1.0", "Accept": "*/*"}
    
    for mirror in OVERPASS_MIRRORS:
        for attempt in range(2):
            try:
                response = requests.post(mirror, data={'data': query_str}, headers=headers, timeout=25)
                if response.status_code == 429:
                    time.sleep(2)
                    continue
                response.raise_for_status()
                return response.json()
            except Exception:
                time.sleep(1)
                continue
    return None

@app.post("/api/osm/bulk-tag")
def bulk_tag_fires(batch: FireBatch):
    if not batch.fires:
        return {"results": {}}

    query_lines = []
    for f in batch.fires:
        lat, lon = f['lat'], f['lon']
        query_lines.append(f'way["landuse"~"farmland|quarry|industrial"](around:600, {lat}, {lon});')
        query_lines.append(f'way["industrial"](around:600, {lat}, {lon});')
        query_lines.append(f'way["man_made"~"mineshaft|petroleum_well"](around:600, {lat}, {lon});')

    overpass_query = "[out:json][timeout:25];\n(\n  " + "\n  ".join(query_lines) + "\n);\nout bb;"
    
    results = {f['id']: {"is_ind": False, "is_mine": False, "name": None} for f in batch.fires}
    data = query_overpass_with_fallback(overpass_query)

    if not data or "elements" not in data:
        print("Overpass mirrors busy or timed out. Defaulting batch to false.")
        return {"results": results}

    for element in data.get('elements', []):
        tags = element.get('tags', {})
        bounds = element.get('bounds', {})
        if not bounds:
            continue

        min_lat = bounds['minlat'] - 0.006
        max_lat = bounds['maxlat'] + 0.006
        min_lon = bounds['minlon'] - 0.006
        max_lon = bounds['maxlon'] + 0.006

        for f in batch.fires:
            f_lat, f_lon = f['lat'], f['lon']
            if min_lat <= f_lat <= max_lat and min_lon <= f_lon <= max_lon:
                facility_name = tags.get('name', 'Unnamed Facility')
                landuse = tags.get('landuse', '')
                man_made = tags.get('man_made', '')

                if tags.get('industrial') in ['gas', 'oil_refinery'] or landuse == 'industrial' or man_made == 'petroleum_well':
                    results[f['id']] = {"is_ind": True, "is_mine": False, "name": facility_name}
                elif landuse == 'quarry' or man_made in ['mineshaft', 'adit']:
                    results[f['id']] = {"is_ind": False, "is_mine": True, "name": facility_name}
                elif landuse == 'farmland':
                    results[f['id']]['name'] = facility_name

    time.sleep(1)
    return {"results": results}
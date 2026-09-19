import os
from urllib.parse import quote_plus
import geopandas as gpd
from shapely.geometry import MultiPolygon
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db"
)

print("Downloading India boundary GeoJSON (this might take a few moments)...")
url = "https://raw.githubusercontent.com/datameet/maps/master/Country/india-composite.geojson"
gdf = gpd.read_file(url)

print("Formatting spatial data...")
gdf = gdf.rename(columns={"geometry": "geom"}).set_geometry("geom")
gdf["geom"] = gdf["geom"].apply(
    lambda x: MultiPolygon([x]) if x.geom_type == "Polygon" else x
)
gdf["name"] = "India"
gdf_final = gdf[["name", "geom"]]

print("Inserting into PostGIS database...")
gdf_final.to_postgis("india_boundary", engine, if_exists="append", index=False)

print("Successfully loaded India's sovereign boundary.")
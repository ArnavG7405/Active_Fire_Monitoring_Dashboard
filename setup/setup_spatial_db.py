import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")

if not db_password:
    print(" Error: DB_PASSWORD not found in .env file.")
    exit()

safe_password = quote_plus(db_password)
engine = create_engine(f"postgresql+psycopg2://postgres:{safe_password}@localhost:5432/firms_india_db")

print(" Connecting to PostgreSQL...")

try:
    with engine.begin() as conn:
        print(" Enabling PostGIS extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        
        print(" Building 'industrial_areas' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS industrial_areas (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                geom GEOMETRY(Polygon, 4326)
            );
        """))
        
        print(" Inserting test industrial geofence...")
        conn.execute(text("""
            INSERT INTO industrial_areas (name, geom)
            SELECT 'Test Industrial Park', ST_GeomFromText('POLYGON((77.0 28.0, 77.5 28.0, 77.5 28.5, 77.0 28.5, 77.0 28.0))', 4326)
            WHERE NOT EXISTS (
                SELECT 1 FROM industrial_areas WHERE name = 'Test Industrial Park'
            );
        """))
        
    print(" Spatial Database Setup Complete! You can now start main.py.")

except Exception as e:
    print(f"\n DATABASE SETUP FAILED: {e}")
    print("Make sure your PostgreSQL server is running and the 'firms_india_db' database exists.")
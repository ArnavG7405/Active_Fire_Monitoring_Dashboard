import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")

if not db_password:
    print("Error: DB_PASSWORD not found in .env file.")
    exit()

safe_password = quote_plus(db_password)
engine = create_engine(f"postgresql+psycopg2://postgres:{safe_password}@localhost:5432/firms_india_db")

print("Connecting to PostgreSQL...")

try:
    with engine.begin() as conn:
        print("Enabling PostGIS extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        
        print("Building 'india_boundary' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS india_boundary (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) DEFAULT 'India',
                geom GEOMETRY(MultiPolygon, 4326) NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_india_boundary_geom ON india_boundary USING GIST (geom);
        """))

        print("Building 'industrial_zones' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS industrial_zones (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                facility_type VARCHAR(100),
                geom GEOMETRY(Geometry, 4326) NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_industrial_zones_geom ON industrial_zones USING GIST (geom);
        """))

        print("Building 'mining_zones' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mining_zones (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                facility_type VARCHAR(100),
                geom GEOMETRY(Polygon, 4326) NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_mining_zones_geom ON mining_zones USING GIST (geom);
        """))

        print("Building 'active_fires' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS active_fires (
                id BIGINT PRIMARY KEY,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                brightness_kelvin DOUBLE PRECISION,
                frp_mw DOUBLE PRECISION,
                confidence VARCHAR(20),
                source_type VARCHAR(50) DEFAULT 'unclassified', 
                is_industrial BOOLEAN DEFAULT FALSE,
                is_mining BOOLEAN DEFAULT FALSE,
                facility_name VARCHAR(255),
                city VARCHAR(100),
                state VARCHAR(100),
                detected_at TIMESTAMP WITH TIME ZONE,
                geom GEOMETRY(Point, 4326) NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_active_fires_geom ON active_fires USING GIST (geom);
        """))

        print("Building 'demo_archives' table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS demo_archives (
                LIKE active_fires INCLUDING ALL,
                run_name VARCHAR(255)
            );
        """))
        
    print("Spatial Database Setup Complete. All 5 tables initialized.")

except Exception as e:
    print(f"DATABASE SETUP FAILED: {e}")
    print("Ensure your PostgreSQL server is running and the 'firms_india_db' database exists.")
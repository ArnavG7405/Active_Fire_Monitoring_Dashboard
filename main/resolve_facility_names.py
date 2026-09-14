import os
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
engine = create_engine(f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db")

def resolve_and_catch_facilities():
    print("Scanning all fires against local PostGIS polygons as a secondary net...")
    
    with engine.begin() as conn:
        # 1. Catch & Resolve Industrial Zones
        ind_query = text("""
            WITH matches AS (
                SELECT f.id AS fire_id, z.name AS zone_name, f.frp_mw
                FROM active_fires f
                JOIN industrial_zones z ON ST_Intersects(f.geom, z.geom)
            )
            UPDATE active_fires f
            SET facility_name = m.zone_name,
                is_industrial = TRUE,
                is_mining = FALSE,
                source_type = CASE WHEN m.frp_mw > 19000 THEN 'industrial_fire' ELSE 'gas_flare' END
            FROM matches m
            WHERE f.id = m.fire_id;
        """)
        ind_result = conn.execute(ind_query)
        
        # 2. Catch & Resolve Mining Zones
        mine_query = text("""
            WITH matches AS (
                SELECT f.id AS fire_id, m.name AS mine_name
                FROM active_fires f
                JOIN mining_zones m ON ST_Intersects(f.geom, m.geom)
            )
            UPDATE active_fires f
            SET facility_name = m.mine_name,
                is_mining = TRUE,
                is_industrial = FALSE,
                source_type = 'mining_activity'
            FROM matches m
            WHERE f.id = m.fire_id;
        """)
        mine_result = conn.execute(mine_query)

    print(f"Local PostGIS Net caught and resolved {ind_result.rowcount} industrial fires and {mine_result.rowcount} mining fires.")

if __name__ == "__main__":
    resolve_and_catch_facilities()
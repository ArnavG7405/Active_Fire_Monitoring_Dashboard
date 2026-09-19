import os
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
engine = create_engine(f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db")

def save_snapshot():
    run_name = input("Enter a name for this demo run (e.g., '1-day run on 9-14-26'): ")
    if not run_name: return
    
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS demo_archives (LIKE active_fires);"))
        conn.execute(text("ALTER TABLE demo_archives ADD COLUMN IF NOT EXISTS run_name VARCHAR(255);"))
        
        conn.execute(text("ALTER TABLE demo_archives DROP CONSTRAINT IF EXISTS demo_archives_pkey;"))
        
        conn.execute(text("DELETE FROM demo_archives WHERE run_name = :name"), {"name": run_name})
        
        result = conn.execute(text("""
            INSERT INTO demo_archives (id, geom, latitude, longitude, brightness_kelvin, frp_mw, detected_at, is_industrial, is_mining, facility_name, city, state, source_type, confidence, run_name)
            SELECT id, geom, latitude, longitude, brightness_kelvin, frp_mw, detected_at, is_industrial, is_mining, facility_name, city, state, source_type, confidence, :name
            FROM active_fires;
        """), {"name": run_name})
        
    print(f" Saved {result.rowcount} fires to archive under '{run_name}'.")

if __name__ == "__main__":
    save_snapshot()
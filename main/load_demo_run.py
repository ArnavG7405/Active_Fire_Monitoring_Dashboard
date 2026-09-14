import os
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
engine = create_engine(f"postgresql+psycopg2://postgres:{quote_plus(db_password)}@localhost:5432/firms_india_db")

def load_snapshot():
    with engine.connect() as conn:
        runs = conn.execute(text("SELECT DISTINCT run_name, count(*) FROM demo_archives GROUP BY run_name")).fetchall()
        
    if not runs:
        print("No demo runs saved yet.")
        return
        
    print("\n AVAILABLE DEMO RUNS:")
    for idx, (name, count) in enumerate(runs, 1):
        print(f"{idx}. {name} ({count} fires)")
        
    try:
        choice = int(input("\nEnter the number of the run to load into the dashboard: ")) - 1
        selected_run = runs[choice][0]
    except (ValueError, IndexError):
        print(" Invalid selection.")
        return
    
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE active_fires;"))
        result = conn.execute(text("""
            INSERT INTO active_fires (id, geom, latitude, longitude, brightness_kelvin, frp_mw, detected_at, is_industrial, is_mining, facility_name, city, state, source_type, confidence)
            SELECT id, geom, latitude, longitude, brightness_kelvin, frp_mw, detected_at, is_industrial, is_mining, facility_name, city, state, source_type, confidence
            FROM demo_archives WHERE run_name = :name;
        """), {"name": selected_run})
        
    print(f" Dashboard Restored! {result.rowcount} fires from '{selected_run}' are now live.")

if __name__ == "__main__":
    load_snapshot()
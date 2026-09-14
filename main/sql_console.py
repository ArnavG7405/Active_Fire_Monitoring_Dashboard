import os
import subprocess
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")

if not db_password:
    print(" Error: DB_PASSWORD not found in .env file.")
    exit(1)

# Set the environment variable so psql automatically authenticates
os.environ["PGPASSWORD"] = db_password

print(" Opening PostgreSQL Interactive Terminal...")
print(" Type '\q' and press Enter to exit when finished.\n")

# Launch the psql shell connected to your database
subprocess.run([
    "psql", 
    "-U", "postgres", 
    "-h", "localhost", 
    "-d", "firms_india_db"
])
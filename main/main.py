import os
import io
import json
import numpy as np
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
import onnxruntime as ort
from dotenv import load_dotenv

app = FastAPI(title="AI Geospatial System for Industrial Fires API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("dataset/crops", exist_ok=True)
app.mount("/static", StaticFiles(directory="dataset/crops"), name="static")

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
safe_password = quote_plus(db_password) if db_password else ""
engine = create_engine(f"postgresql+psycopg2://postgres:{safe_password}@localhost:5432/firms_india_db")

ONNX_MODEL_PATH = os.path.abspath("fire_classifier.onnx")
ort_session = ort.InferenceSession(ONNX_MODEL_PATH) if os.path.exists(ONNX_MODEL_PATH) else None

def execute_strict_ai_logic(tensor: np.ndarray, total_frp: float, is_ind: bool, is_mine: bool, fire_id: int):
    CLASS_MAP = {
        0: "wildfire", 1: "industrial_fire", 2: "gas_flare", 
        3: "agricultural_burning", 4: "mining_activity"
    }

    if len(tensor.shape) == 3:
        tensor = np.expand_dims(tensor, axis=0)

    inputs = {
        "image_input": tensor,
        "industrial_flag": np.array([[1.0 if is_ind else 0.0]], dtype=np.float32),
        "raw_frp": np.array([[total_frp]], dtype=np.float32)
    }
    
    logits = ort_session.run(None, inputs)[0]
    safe_logits = np.copy(logits) / 1.5 

    if is_mine:
        safe_logits[0, 0] = -np.inf  
        safe_logits[0, 1] = -np.inf  
        safe_logits[0, 2] = -np.inf  
        safe_logits[0, 3] = -np.inf  
    elif is_ind:
        safe_logits[0, 0] = -np.inf  
        safe_logits[0, 3] = -np.inf  
        safe_logits[0, 4] = -np.inf  
        if total_frp > 19000.0:  
            safe_logits[0, 2] = -np.inf  
        else:
            safe_logits[0, 1] = -np.inf  
    else:
        safe_logits[0, 1] = -np.inf  
        safe_logits[0, 2] = -np.inf  
        safe_logits[0, 4] = -np.inf  

    exp_logits = np.exp(safe_logits - np.max(safe_logits, axis=1, keepdims=True))
    probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
    
    predicted_idx = int(np.argmax(probs, axis=1)[0])
    return CLASS_MAP[predicted_idx], float(probs[0][predicted_idx])

@app.get("/api/fires/india")
def get_live_fires():
    query = """
        SELECT id, latitude, longitude, brightness_kelvin, frp_mw, 
               confidence, source_type, is_industrial, is_mining, 
               facility_name, city, state, detected_at 
        FROM active_fires
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)
    
    df = df.replace({np.nan: None})
    
    features = []
    for _, row in df.iterrows():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row['longitude'], row['latitude']]
            },
            "properties": row.to_dict()
        }
        features.append(feature)
        
    return {"type": "FeatureCollection", "features": features}

@app.post("/api/predict/fire")
async def predict_fire_type(fire_id: int = Form(...), file: UploadFile = File(...)):
    if not ort_session: return {"error": "ONNX model not loaded."}

    contents = await file.read()
    tensor = np.load(io.BytesIO(contents)).astype(np.float32)
    total_frp = float(np.sum(tensor))

    is_ind = False
    is_mine = False
    
    with engine.connect() as conn:
        result = conn.execute(text("SELECT is_industrial, is_mining FROM active_fires WHERE id = :id"), {"id": fire_id}).fetchone()
        if result:
            is_ind = result[0]
            is_mine = result[1]

    final_class, confidence = execute_strict_ai_logic(tensor, total_frp, is_ind, is_mine, fire_id)

    with engine.begin() as conn:
        conn.execute(text("UPDATE active_fires SET source_type = :cls, confidence = :conf WHERE id = :id"), 
                     {"cls": final_class, "conf": f"{confidence * 100:.1f}%", "id": fire_id})

    return {"fire_id": fire_id, "confidence": round(confidence, 3), "ai_classification": final_class}
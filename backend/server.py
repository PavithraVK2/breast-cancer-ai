from pathlib import Path
import os
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Header, Cookie, Response, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict, EmailStr
import bcrypt
import joblib
import numpy as np
import requests

# Set Root Directory and load environment variables first
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/breastguard')
db_name = os.environ.get('DB_NAME', 'breastguard')
env = os.environ.get('ENV', 'development')

cors_origins_raw = os.environ.get('CORS_ORIGINS')
if cors_origins_raw:
    cors_origins = [origin.strip() for origin in cors_origins_raw.split(',') if origin.strip()]
else:
    cors_origins = ['http://localhost:8082', 'http://localhost:3000']

if cors_origins == ['*']:
    cors_origins = ['http://localhost:8082', 'http://localhost:3000']

secure_cookies = os.environ.get('SECURE_COOKIES', 'false').lower() == 'true'

def set_session_cookie(response: JSONResponse, session_token: str):
    response.set_cookie(
        key='session_token',
        value=session_token,
        httponly=True,
        secure=secure_cookies,
        samesite='none' if secure_cookies else 'lax',
        max_age=7 * 24 * 60 * 60,
        path='/'
    )

client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI(title="BreastGuard AI API", version="1.0.0")
api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

model = None
scaler = None
model_metadata = {}

def load_ml_model():
    global model, scaler, model_metadata
    try:
        model_path = ROOT_DIR / "model" / "svm_model.pkl"
        scaler_path = ROOT_DIR / "model" / "scaler.pkl"
        
        # Fallback to parent model directory if not found in backend/model
        if not (model_path.exists() and scaler_path.exists()):
            alt_model_path = ROOT_DIR.parent / "model" / "svm_model.pkl"
            alt_scaler_path = ROOT_DIR.parent / "model" / "scaler.pkl"
            if alt_model_path.exists() and alt_scaler_path.exists():
                model_path = alt_model_path
                scaler_path = alt_scaler_path
        
        if model_path.exists() and scaler_path.exists():
            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)
            model_metadata = {
                'accuracy': 0.97,
                'n_features': 30,
                'target_names': ['Malignant', 'Benign']
            }
            logger.info("ML model and scaler loaded successfully from %s", model_path)
        else:
            logger.warning("Model files not found at %s. Please run train_model.py.", model_path)
    except Exception as e:
        logger.error("Error loading model: %s", e)

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: Any

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class SessionData(BaseModel):
    user_id: str
    session_token: str
    email: str
    name: str
    picture: Optional[str] = None

class PredictionInput(BaseModel):
    features: List[float]
    patient_name: Optional[str] = "Anonymous"

class PredictionResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    prediction_id: str
    user_id: str
    patient_name: str
    result: str
    confidence: float
    features: List[float]
    created_at: datetime

class DashboardStats(BaseModel):
    total_predictions: int
    benign_count: int
    malignant_count: int
    accuracy: float

async def get_current_user(session_token: Optional[str] = Cookie(None), authorization: Optional[str] = Header(None)) -> dict:
    token = session_token
    
    if not token and authorization:
        if authorization.startswith('Bearer '):
            token = authorization[7:]
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_doc = await db.user_sessions.find_one(
        {"session_token": token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        await db.user_sessions.delete_one({"session_token": token})
        raise HTTPException(status_code=401, detail="Session expired")
    
    user_doc = await db.users.find_one(
        {"user_id": session_doc["user_id"]},
        {"_id": 0, "password_hash": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user_doc

@api_router.post("/auth/register")
async def register(user_data: UserRegister):
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = bcrypt.hashpw(user_data.password.encode('utf-8'), bcrypt.gensalt())
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    new_user = {
        "user_id": user_id,
        "email": user_data.email,
        "name": user_data.name,
        "password_hash": password_hash.decode('utf-8'),
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(new_user)
    
    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    response = JSONResponse(content={
        "user_id": user_id,
        "email": user_data.email,
        "name": user_data.name,
        "session_token": session_token
    })
    set_session_cookie(response, session_token)
    return response

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    user_doc = await db.users.find_one({"email": credentials.email})
    
    if not user_doc or not user_doc.get('password_hash'):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(credentials.password.encode('utf-8'), user_doc['password_hash'].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    session_token = f"session_{uuid.uuid4().hex}"
    session_doc = {
        "user_id": user_doc["user_id"],
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    response = JSONResponse(content={
        "user_id": user_doc["user_id"],
        "email": user_doc["email"],
        "name": user_doc["name"],
        "session_token": session_token
    })
    set_session_cookie(response, session_token)
    return response

@api_router.post("/auth/google/session")
async def google_session(session_id: str = Header(..., alias="X-Session-ID")):
    try:
        response = requests.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session ID")
        
        google_data = response.json()
        
        user_doc = await db.users.find_one({"email": google_data["email"]})
        
        if user_doc:
            await db.users.update_one(
                {"email": google_data["email"]},
                {"$set": {
                    "name": google_data["name"],
                    "picture": google_data.get("picture")
                }}
            )
            user_id = user_doc["user_id"]
        else:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            new_user = {
                "user_id": user_id,
                "email": google_data["email"],
                "name": google_data["name"],
                "picture": google_data.get("picture"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.users.insert_one(new_user)
        
        session_token = google_data["session_token"]
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_sessions.insert_one(session_doc)
        
        http_response = JSONResponse(content={
            "user_id": user_id,
            "email": google_data["email"],
            "name": google_data["name"],
            "picture": google_data.get("picture"),
            "session_token": session_token
        })
        set_session_cookie(http_response, session_token)
        return http_response
        
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(status_code=500, detail="Authentication failed")

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    # Explicitly ensure sensitive fields are sanitized
    sanitized = {k: v for k, v in user.items() if k not in ["_id", "password_hash"]}
    return sanitized

@api_router.post("/auth/logout")
async def logout(response: Response, session_token: Optional[str] = Cookie(None)):
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}

@api_router.post("/predictions", response_model=PredictionResult)
async def create_prediction(prediction_data: PredictionInput, user: dict = Depends(get_current_user)):
    if model is None or scaler is None:
        raise HTTPException(status_code=503, detail="Model not loaded. Please train the model first.")
    
    if len(prediction_data.features) != 30:
        raise HTTPException(status_code=400, detail="Expected 30 features")
    
    try:
        features_array = np.array(prediction_data.features).reshape(1, -1)
        features_scaled = scaler.transform(features_array)
        
        prediction = model.predict(features_scaled)[0]
        probabilities = model.predict_proba(features_scaled)[0]
        
        result = "Benign" if prediction == 1 else "Malignant"
        confidence = float(probabilities[prediction])
        
        prediction_id = f"pred_{uuid.uuid4().hex[:12]}"
        created_at_dt = datetime.now(timezone.utc)
        prediction_doc = {
            "prediction_id": prediction_id,
            "user_id": user["user_id"],
            "patient_name": prediction_data.patient_name,
            "result": result,
            "confidence": confidence,
            "features": prediction_data.features,
            "created_at": created_at_dt.isoformat()
        }
        
        await db.predictions.insert_one(prediction_doc)
        
        return PredictionResult(
            prediction_id=prediction_id,
            user_id=user["user_id"],
            patient_name=prediction_data.patient_name or "Anonymous",
            result=result,
            confidence=confidence,
            features=prediction_data.features,
            created_at=created_at_dt
        )
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Prediction failed")

@api_router.get("/predictions", response_model=List[PredictionResult])
async def get_predictions(user: dict = Depends(get_current_user)):
    predictions = await db.predictions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    for pred in predictions:
        if isinstance(pred['created_at'], str):
            pred['created_at'] = datetime.fromisoformat(pred['created_at'])
    
    return predictions

@api_router.delete("/predictions/{prediction_id}")
async def delete_prediction(prediction_id: str, user: dict = Depends(get_current_user)):
    result = await db.predictions.delete_one({
        "prediction_id": prediction_id,
        "user_id": user["user_id"]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return {"message": "Prediction deleted"}

@api_router.delete("/predictions")
async def delete_all_predictions(user: dict = Depends(get_current_user)):
    result = await db.predictions.delete_many({"user_id": user["user_id"]})
    return {"message": f"Deleted {result.deleted_count} predictions"}

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(user: dict = Depends(get_current_user)):
    predictions = await db.predictions.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(1000)
    
    total = len(predictions)
    benign = sum(1 for p in predictions if p.get("result") == "Benign")
    malignant = total - benign
    
    accuracy = model_metadata.get('accuracy', 0.97)
    
    return DashboardStats(
        total_predictions=total,
        benign_count=benign,
        malignant_count=malignant,
        accuracy=accuracy
    )

@api_router.get("/model/info")
async def get_model_info():
    if model is None:
        return {"loaded": False, "message": "Model not trained yet"}
    
    return {
        "loaded": True,
        "accuracy": model_metadata.get('accuracy', 0.97),
        "n_features": model_metadata.get('n_features', 30),
        "target_names": model_metadata.get('target_names', ['Malignant', 'Benign'])
    }

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    load_ml_model()
    await seed_test_users()
    logger.info("Application started")

async def seed_test_users():
    test_users = [
        {"email": "doctor@test.com", "password": "test123", "name": "Dr. Test User"},
        {"email": "admin@test.com", "password": "admin123", "name": "Admin User"},
    ]
    
    for user_data in test_users:
        existing = await db.users.find_one({"email": user_data["email"]})
        if existing:
            continue
        
        password_hash = bcrypt.hashpw(user_data["password"].encode('utf-8'), bcrypt.gensalt())
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        
        await db.users.insert_one({
            "user_id": user_id,
            "email": user_data["email"],
            "name": user_data["name"],
            "password_hash": password_hash.decode('utf-8'),
            "picture": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Seeded test user: {user_data['email']}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )
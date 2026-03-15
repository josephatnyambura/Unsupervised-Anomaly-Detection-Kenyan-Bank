"""
FastAPI service for Real-Time Anomaly Detection
Kenyan Banking Transaction Monitoring System

Target: < 100ms latency, 50,000+ transactions/day
"""

import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from prometheus_fastapi_instrumentator import Instrumentator

from model_loader import ModelLoader
from anomaly_detector import AnomalyDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

model_loader = ModelLoader(models_dir=os.environ.get("MODELS_DIR", "/app/models"))
anomaly_detector = AnomalyDetector(model_loader)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models at startup, clean up on shutdown."""
    try:
        model_loader.load_all_models()
        logger.info(f"Models loaded successfully: {model_loader.get_loaded_models()}")
    except Exception as e:
        logger.warning(
            f"Models not available at startup: {e}. "
            "API will start in degraded mode. POST to /reload when models are ready."
        )
    yield
    logger.info("Shutting down anomaly detection service.")


app = FastAPI(
    title="Anomaly Detection API",
    description="Real-time unsupervised anomaly detection for Kenyan banking transactions",
    version="2.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ── Pydantic schemas ─────────────────────────────────────────────────────────

class TransactionIn(BaseModel):
    model_config = ConfigDict(extra="allow")  # Allow model features not listed (e.g. has_trigger, lag_balance)

    clientid: str
    transactiondate: str
    inflows: float = 0.0
    outflows: float = 0.0
    balance: float = 0.0
    dailyincome: float = 0.0
    cumulativeincome: float = 0.0
    gross_activity: Optional[float] = None
    zero_activity_freq: Optional[float] = None
    rolling_mean_inflows: Optional[float] = None
    rolling_std_inflows: Optional[float] = None
    # Binary flags (0 or 1) and other model features – optional so request can send only what the model needs
    has_trigger: Optional[float] = None
    balance_error_flag: Optional[float] = None
    is_first_transaction: Optional[float] = None
    lag_balance: Optional[float] = None
    lag_cumulativeincome: Optional[float] = None
    rolling_mean_balance: Optional[float] = None
    rolling_std_balance: Optional[float] = None
    rolling_mean_cumulativeincome: Optional[float] = None
    rolling_std_cumulativeincome: Optional[float] = None
    ratio: Optional[float] = None


class PredictRequest(BaseModel):
    fund_name: str = Field(..., examples=["Money Market Fund"])
    transactions: List[TransactionIn]


class FeatureUsed(BaseModel):
    name: str
    value: float


class PredictionOut(BaseModel):
    transaction_id: int
    is_anomaly: bool
    anomaly_score: float
    risk_tier: str
    fusion_score: float
    processing_time_ms: float
    features_used: Optional[List[Dict[str, Any]]] = None
    feature_contributions: Optional[List[Dict[str, Any]]] = None
    explanation: Optional[str] = None


class PredictResponse(BaseModel):
    predictions: List[PredictionOut]
    total_processing_time_ms: float
    latency_target_met: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes / Docker."""
    models_loaded = model_loader.is_ready()
    status = "healthy" if models_loaded else "degraded"
    return {
        "status": status,
        "models_loaded": model_loader.get_loaded_models(),
        "timestamp": time.time(),
    }


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest):
    """Real-time anomaly detection endpoint."""
    start_time = time.time()

    if not payload.transactions:
        raise HTTPException(status_code=400, detail="No transactions provided")

    if not model_loader.is_ready():
        raise HTTPException(status_code=503, detail="Models not loaded yet")

    try:
        transactions_dicts = [t.model_dump() for t in payload.transactions]
        predictions = anomaly_detector.detect_anomalies(
            fund_name=payload.fund_name,
            transactions=transactions_dicts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    total_time = (time.time() - start_time) * 1000
    if total_time > 100:
        logger.warning(f"Latency target exceeded: {total_time:.2f}ms")

    return PredictResponse(
        predictions=[PredictionOut(
            transaction_id=p["transaction_id"],
            is_anomaly=p["is_anomaly"],
            anomaly_score=p["anomaly_score"],
            risk_tier=p["risk_tier"],
            fusion_score=p["fusion_score"],
            processing_time_ms=p["processing_time_ms"],
            features_used=p.get("features_used"),
            feature_contributions=p.get("feature_contributions"),
            explanation=p.get("explanation"),
        ) for p in predictions],
        total_processing_time_ms=round(total_time, 2),
        latency_target_met=total_time < 100,
    )


@app.get("/models")
async def list_models():
    """List all loaded models and their metadata."""
    models_info = model_loader.get_models_info()
    return {"models": models_info, "count": len(models_info)}


@app.post("/reload")
async def reload_models():
    """Reload all models (for updates without downtime)."""
    try:
        model_loader.reload_models()
        return {
            "status": "success",
            "message": "Models reloaded successfully",
            "models_loaded": model_loader.get_loaded_models(),
        }
    except Exception as e:
        logger.error(f"Error reloading models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")

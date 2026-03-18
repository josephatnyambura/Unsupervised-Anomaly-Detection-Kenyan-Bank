"""
FastAPI service for Real-Time Anomaly Detection (standalone module).
Uses Pydantic for all request/response validation.
Run from project root: uvicorn fastapi_app.main:app --host 0.0.0.0 --port 5000
"""

import os
import sys
import time
import logging
from contextlib import asynccontextmanager
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
_this_dir = Path(__file__).resolve().parent
for p in (str(_project_root), str(_this_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

try:
    from fastapi_app.schemas import (
        PredictRequest,
        PredictResponse,
        PredictionOut,
        HealthResponse,
        ModelsResponse,
        ModelInfo,
        ReloadResponse,
    )
except Exception:
    # Vercel with Root Directory=fastapi_app resolves local modules directly.
    from schemas import (
        PredictRequest,
        PredictResponse,
        PredictionOut,
        HealthResponse,
        ModelsResponse,
        ModelInfo,
        ReloadResponse,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Backend:
# 1) Prefer deployment/app backend when available (local/full repo runtime).
# 2) Fallback to fastapi_app local backend for Vercel/serverless runtime.
try:
    from deployment.app.model_loader import ModelLoader
    from deployment.app.anomaly_detector import AnomalyDetector
    _models_dir = os.environ.get("MODELS_DIR", str(_project_root / "models"))
    model_loader = ModelLoader(models_dir=_models_dir)
    anomaly_detector = AnomalyDetector(model_loader)
except Exception as e:
    logger.warning("Deployment backend unavailable: %s. Trying local fastapi_app backend.", e)
    try:
        try:
            from fastapi_app.model_loader import ModelLoader
            from fastapi_app.anomaly_detector import AnomalyDetector
        except Exception:
            from model_loader import ModelLoader
            from anomaly_detector import AnomalyDetector

        _models_dir = os.environ.get("MODELS_DIR", str(_project_root / "models"))
        model_loader = ModelLoader(models_dir=_models_dir)
        anomaly_detector = AnomalyDetector(model_loader)
        logger.info("Using local fastapi_app backend with models dir: %s", _models_dir)
    except Exception as e2:
        logger.warning("Local backend unavailable: %s. API will run in degraded mode.", e2)
        model_loader = None
        anomaly_detector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models at startup."""
    if model_loader is not None:
        try:
            model_loader.load_all_models()
            logger.info("Models loaded: %s", model_loader.get_loaded_models())
        except Exception as e:
            logger.warning("Models not loaded at startup: %s. Use POST /reload when ready.", e)
    yield
    logger.info("Shutting down FastAPI anomaly detection service.")


app = FastAPI(
    title="Anomaly Detection API",
    description="Real-time unsupervised anomaly detection with Pydantic validation. Kenyan banking transaction monitoring.",
    version="2.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check for Kubernetes/Docker."""
    if model_loader is None or not model_loader.is_ready():
        return HealthResponse(status="degraded", models_loaded=[], timestamp=time.time())
    return HealthResponse(
        status="healthy",
        models_loaded=model_loader.get_loaded_models(),
        timestamp=time.time(),
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(payload: PredictRequest):
    """Real-time anomaly detection. Request/response validated with Pydantic."""
    if model_loader is None or anomaly_detector is None:
        raise HTTPException(status_code=503, detail="Backend not available")
    if not model_loader.is_ready():
        raise HTTPException(status_code=503, detail="Models not loaded yet")

    start = time.time()
    try:
        transactions_dicts = [t.model_dump() for t in payload.transactions]
        predictions = anomaly_detector.detect_anomalies(
            fund_name=payload.fund_name,
            transactions=transactions_dicts,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Prediction error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    total_ms = (time.time() - start) * 1000
    out = PredictResponse(
        predictions=[
            PredictionOut(
                transaction_id=p["transaction_id"],
                is_anomaly=p["is_anomaly"],
                anomaly_score=p["anomaly_score"],
                risk_tier=p["risk_tier"],
                fusion_score=p["fusion_score"],
                processing_time_ms=p["processing_time_ms"],
                features_used=p.get("features_used"),
                explanation=p.get("explanation"),
            )
            for p in predictions
        ],
        total_processing_time_ms=round(total_ms, 2),
        latency_target_met=total_ms < 100,
    )
    return out


@app.get("/models", response_model=ModelsResponse)
async def list_models():
    """List loaded models and metadata."""
    if model_loader is None or not model_loader.is_ready():
        return ModelsResponse(models=[], count=0)
    info = model_loader.get_models_info()
    return ModelsResponse(
        models=[ModelInfo(**m) for m in info],
        count=len(info),
    )


@app.post("/reload", response_model=ReloadResponse)
async def reload_models():
    """Reload all models."""
    if model_loader is None:
        raise HTTPException(status_code=503, detail="Backend not available")
    try:
        model_loader.reload_models()
        return ReloadResponse(
            status="success",
            message="Models reloaded successfully",
            models_loaded=model_loader.get_loaded_models(),
        )
    except Exception as e:
        logger.error("Reload error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="info")

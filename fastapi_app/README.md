# FastAPI Anomaly Detection (standalone)

This folder contains the **FastAPI** service for real-time anomaly detection in a **separate module** from the main deployment app. All request and response bodies are validated with **Pydantic**.

## Features

- **Pydantic validation**: All inputs (`TransactionIn`, `PredictRequest`) and outputs (`PredictResponse`, `HealthResponse`, etc.) use Pydantic models with type hints and constraints (e.g. `ge=0`, `min_length`, `pattern`).
- **Same behaviour as deployment API**: Uses `deployment.app.model_loader` and `deployment.app.anomaly_detector` when run from the project root.
- **Endpoints**: `GET /health`, `POST /predict`, `GET /models`, `POST /reload`, `GET /metrics`.

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt` (FastAPI, Uvicorn, Pydantic, Prometheus instrumentator, sklearn, pandas, joblib).
- Trained models in the project `models/` directory (or set `MODELS_DIR`).

## Run from project root

```bash
# From repository root
pip install -r fastapi_app/requirements.txt
# Ensure deployment app deps are installed if you use it for backend
pip install -r deployment/app/requirements.txt

uvicorn fastapi_app.main:app --host 0.0.0.0 --port 5000
```

Or:

```bash
cd /path/to/project/root
python -m uvicorn fastapi_app.main:app --host 0.0.0.0 --port 5000
```

- **API**: http://localhost:5000  
- **Swagger**: http://localhost:5000/docs  
- **ReDoc**: http://localhost:5000/redoc  

## Pydantic schemas (`schemas.py`)

| Schema            | Purpose                          |
|-------------------|----------------------------------|
| `TransactionIn`   | Single transaction (clientid, date, inflows, etc.; optional features with bounds) |
| `PredictRequest`  | `fund_name` + list of `TransactionIn` (1–10,000) |
| `PredictionOut`   | One prediction (anomaly_score, risk_tier, features_used, explanation) |
| `PredictResponse` | List of predictions + total time + latency flag |
| `HealthResponse`  | status, models_loaded, timestamp |
| `ModelInfo`       | Per-fund model metadata and feature_names |
| `ModelsResponse`  | List of `ModelInfo` + count |
| `ReloadResponse`  | status, message, models_loaded |

Validation includes: non-empty strings, numeric ranges (e.g. `zero_activity_freq` in [0, 1]), `risk_tier` in `Low|Medium|High`, and list length limits.

## Environment

| Variable     | Description        | Default (when run from root) |
|-------------|--------------------|------------------------------|
| `MODELS_DIR`| Path to model dir  | `{project_root}/models`      |

## Docker / production

For production, the Docker image is usually built from `deployment/app/` (see `deployment/README.md`). This `fastapi_app/` module is intended for local development and as the canonical **Pydantic API contract**; the deployment app can be updated to use these schemas by importing from `fastapi_app.schemas` if desired.

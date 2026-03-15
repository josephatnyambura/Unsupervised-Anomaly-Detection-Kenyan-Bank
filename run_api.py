"""
Start the Anomaly Detection API for production (e.g. Render, Railway).
Uses PORT from environment; default 5000 for local.
Run from repo root: python run_api.py
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(
        "fastapi_app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )

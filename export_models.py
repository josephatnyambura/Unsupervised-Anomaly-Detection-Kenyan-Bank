"""
Export the best-performing model artifacts for deployment.

Reads the model artifacts saved by the notebook (under models/<fund>/),
finds the latest version, and copies them into models/<fund>/latest/
so the deployment stack always picks up the best model.

If no notebook-exported artifacts are found, falls back to training
an Isolation Forest from the enhanced transaction CSVs.

Usage:
    python export_models.py
"""

import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "ml" / "anomalies"

FALLBACK_FEATURE_NAMES = [
    "inflows",
    "gross_activity",
    "zero_activity_freq",
    "rolling_mean_inflows",
    "rolling_std_inflows",
]

FUND_KEYS = {
    "money_market_fund": "MONEY MARKET FUND",
    "fixed_income_fund__usd_": "FIXED INCOME FUND (USD)",
}


def _find_latest_notebook_version(fund_key: str) -> Path | None:
    """Return the most recent versioned directory (v_*) for a fund, or None."""
    fund_dir = MODELS_DIR / fund_key
    if not fund_dir.exists():
        return None
    versions = sorted(fund_dir.glob("v_*"), reverse=True)
    for v in versions:
        if (v / "metadata.json").exists():
            return v
    return None


def _copy_notebook_artifacts(fund_key: str, display_name: str) -> dict | None:
    """Copy the notebook's latest versioned artifacts into latest/.

    Uses metadata.json feature_names as the authoritative source because
    the scaler and model were both trained on those exact features.
    """
    version_dir = _find_latest_notebook_version(fund_key)
    if version_dir is None:
        return None

    with open(version_dir / "metadata.json") as f:
        meta = json.load(f)

    latest_dir = MODELS_DIR / fund_key / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)

    import shutil
    for item in version_dir.iterdir():
        shutil.copy2(item, latest_dir / item.name)

    # Always reconcile feature_names.json from metadata (authoritative source)
    meta_features = meta.get("feature_names")
    feature_path = latest_dir / "feature_names.json"
    if meta_features:
        with open(feature_path, "w") as f:
            json.dump(meta_features, f, indent=2)
        print(f"  feature_names.json written from metadata ({len(meta_features)} features)")

    model_name = meta.get("model_name", "Unknown")

    # For neural models: if model.keras exists, remove any stale model.joblib
    # (left over from a previous fallback IsolationForest run)
    keras_path = latest_dir / "model.keras"
    stale_joblib = latest_dir / "model.joblib"
    if keras_path.exists() and stale_joblib.exists():
        stale_joblib.unlink()
        print(f"  Removed stale model.joblib (neural model uses model.keras)")

    print(f"  Using notebook best model: {model_name}")
    print(f"  Copied {version_dir.name} -> latest/")

    return {
        "model_name": model_name,
        "version": version_dir.name,
        "latest_path": str(latest_dir),
        "fund_display_name": display_name,
    }


def _train_fallback_isolation_forest(fund_key: str, display_name: str) -> dict:
    """Train an Isolation Forest from scratch as fallback."""
    csv_path = DATA_DIR / f"enhanced_all_transactions_{fund_key}.csv"
    print(f"  Fallback: training Isolation Forest from {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"  Rows: {len(df):,}")

    X = df[FALLBACK_FEATURE_NAMES].fillna(0).astype(np.float64)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200, max_samples="auto",
        contamination=0.05, random_state=42, n_jobs=-1,
    )
    model.fit(X_scaled)

    y_pred = model.predict(X_scaled)
    scores = -model.score_samples(X_scaled)
    n_anomalies = int((y_pred == -1).sum())
    print(f"  Anomalies detected: {n_anomalies} / {len(df)} ({n_anomalies/len(df)*100:.2f}%)")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for target_dir in [MODELS_DIR / fund_key / f"v_{timestamp}",
                       MODELS_DIR / fund_key / "latest"]:
        target_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, target_dir / "model.joblib")
        joblib.dump(scaler, target_dir / "scaler.joblib")
        with open(target_dir / "feature_names.json", "w") as f:
            json.dump(FALLBACK_FEATURE_NAMES, f, indent=2)
        metadata = {
            "fund_name": display_name,
            "model_name": "Isolation Forest",
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "random_seed": 42,
            "feature_count": len(FALLBACK_FEATURE_NAMES),
            "feature_names": FALLBACK_FEATURE_NAMES,
            "n_estimators": 200,
            "contamination": 0.05,
            "training_samples": len(df),
            "anomalies_detected": n_anomalies,
            "performance_metrics": {
                "contamination_rate": round(n_anomalies / len(df), 4),
                "mean_anomaly_score": round(float(scores.mean()), 6),
                "std_anomaly_score": round(float(scores.std()), 6),
            },
        }
        with open(target_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    return {
        "model_name": "Isolation Forest",
        "version": f"v_{timestamp}",
        "latest_path": str(MODELS_DIR / fund_key / "latest"),
        "fund_display_name": display_name,
    }


def main():
    print("=" * 60)
    print("MODEL EXPORT SCRIPT (dynamic best model)")
    print("=" * 60)

    registry = {
        "created_at": datetime.now().isoformat(),
        "random_seed": 42,
        "models": {},
    }

    for fund_key, display_name in FUND_KEYS.items():
        print(f"\n{'='*60}")
        print(f"Processing: {display_name}")

        result = _copy_notebook_artifacts(fund_key, display_name)
        if result is None:
            csv_path = DATA_DIR / f"enhanced_all_transactions_{fund_key}.csv"
            if csv_path.exists():
                result = _train_fallback_isolation_forest(fund_key, display_name)
            else:
                print(f"  WARNING: No notebook artifacts and no CSV found. Skipping.")
                continue

        registry["models"][fund_key] = result

    registry_path = MODELS_DIR / "model_registry.json"
    with open(registry_path, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Registry written: {registry_path}")
    print(f"Funds exported: {len(registry['models'])}")
    for k, v in registry["models"].items():
        print(f"  {k}: {v['model_name']}")
    print("=" * 60)


if __name__ == "__main__":
    main()

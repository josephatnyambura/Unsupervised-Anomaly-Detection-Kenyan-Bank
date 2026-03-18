"""
Vercel-friendly model loader for fastapi_app.

Loads sklearn/joblib models and avoids heavy TensorFlow dependency so serverless
startup is lighter and more reliable.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

import joblib

logger = logging.getLogger(__name__)


class ModelLoader:
    """Load and cache model artifacts per fund."""

    def __init__(self, models_dir: str):
        self.models_dir = Path(models_dir)
        self.loaded_models: Dict[str, Dict[str, Any]] = {}
        self.scalers: Dict[str, Any] = {}
        self.feature_names: Dict[str, List[str]] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.score_params: Dict[str, Dict[str, Any]] = {}

    def load_all_models(self) -> None:
        logger.info("Loading models from %s", self.models_dir)
        self.loaded_models.clear()
        self.scalers.clear()
        self.feature_names.clear()
        self.metadata.clear()
        self.score_params.clear()

        registry_path = self.models_dir / "model_registry.json"
        if registry_path.exists():
            try:
                with open(registry_path, "r", encoding="utf-8") as f:
                    registry = json.load(f)
                for fund_key, model_info in registry.get("models", {}).items():
                    self._load_fund_model(fund_key, model_info)
            except Exception as e:
                logger.warning("Registry load failed: %s", e)

        # Fallback: discover funds directly from folder structure if registry empty/stale.
        if not self.loaded_models and self.models_dir.exists():
            for fund_dir in self.models_dir.iterdir():
                if fund_dir.is_dir() and fund_dir.name not in {"__pycache__"}:
                    try:
                        self._load_fund_model(fund_dir.name, {})
                    except Exception as e:
                        logger.warning("Skipping %s: %s", fund_dir.name, e)

    def reload_models(self) -> None:
        self.load_all_models()

    def is_ready(self) -> bool:
        return len(self.loaded_models) > 0

    def get_loaded_models(self) -> List[str]:
        return list(self.loaded_models.keys())

    def get_model(self, fund_name: str) -> Dict[str, Any]:
        key = self._resolve_fund_key(fund_name)
        return self.loaded_models[key]

    def get_scaler(self, fund_name: str):
        key = self._resolve_fund_key(fund_name)
        return self.scalers[key]

    def get_feature_names(self, fund_name: str) -> List[str]:
        key = self._resolve_fund_key(fund_name)
        return self.feature_names[key]

    def get_score_params(self, fund_name: str) -> Dict[str, Any]:
        key = self._resolve_fund_key(fund_name)
        return self.score_params.get(key, {})

    def get_models_info(self) -> List[Dict[str, Any]]:
        info: List[Dict[str, Any]] = []
        for fund_key in self.loaded_models:
            meta = self.metadata.get(fund_key, {})
            fnames = self.feature_names.get(fund_key, [])
            info.append(
                {
                    "fund_key": fund_key,
                    "fund_name": meta.get("fund_name", fund_key),
                    "model_name": meta.get("model_name", "sklearn-model"),
                    "created_at": meta.get("created_at"),
                    "feature_count": len(fnames),
                    "feature_names": fnames,
                    "performance": meta.get("performance_metrics", {}),
                }
            )
        return info

    def _load_fund_model(self, fund_key: str, model_info: Dict[str, Any]) -> None:
        fund_root = self.models_dir / fund_key
        latest_dir = fund_root / "latest"
        model_dir = latest_dir if latest_dir.exists() else None

        # Prefer latest/model.joblib. If missing, fallback to newest v_*/model.joblib.
        if model_dir is None or not (model_dir / "model.joblib").exists():
            candidates = sorted(
                [p for p in fund_root.glob("v_*") if p.is_dir()],
                key=lambda p: p.name,
                reverse=True,
            )
            found = next((p for p in candidates if (p / "model.joblib").exists()), None)
            if found is None:
                raise FileNotFoundError(f"No joblib model found for {fund_key}")
            model_dir = found

        metadata_path = model_dir / "metadata.json"
        scaler_path = model_dir / "scaler.joblib"
        features_path = model_dir / "feature_names.json"
        model_path = model_dir / "model.joblib"
        score_params_path = model_dir / "score_params.json"

        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                self.metadata[fund_key] = json.load(f)
        else:
            self.metadata[fund_key] = {
                "fund_name": fund_key,
                "model_name": model_info.get("model_name", "sklearn-model"),
            }

        self.scalers[fund_key] = joblib.load(scaler_path)
        with open(features_path, "r", encoding="utf-8") as f:
            self.feature_names[fund_key] = json.load(f)
        self.loaded_models[fund_key] = {"model": joblib.load(model_path), "type": "sklearn"}

        if score_params_path.exists():
            with open(score_params_path, "r", encoding="utf-8") as f:
                self.score_params[fund_key] = json.load(f)

        logger.info("Loaded %s from %s", fund_key, model_dir)

    def _resolve_fund_key(self, fund_name: str) -> str:
        if fund_name in self.loaded_models:
            return fund_name
        normalized = self._sanitize_filename(fund_name)
        if normalized in self.loaded_models:
            return normalized
        for key, meta in self.metadata.items():
            if str(meta.get("fund_name", "")).lower() == str(fund_name).lower():
                return key
        raise ValueError(f"Unknown fund '{fund_name}'. Available: {list(self.loaded_models.keys())}")

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", str(name).lower().replace(" ", "_"))

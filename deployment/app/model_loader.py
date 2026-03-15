"""
Model Loader - Loads trained models and artifacts for inference

Supports both Keras (.keras) neural models and sklearn (.joblib) models.
"""

import re
import json
import joblib
import logging
from pathlib import Path
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ModelLoader:
    """Manages loading and caching of trained models"""

    def __init__(self, models_dir: str = "/app/models"):
        self.models_dir = Path(models_dir)
        self.loaded_models: Dict[str, Dict] = {}
        self.scalers: Dict[str, Any] = {}
        self.feature_names: Dict[str, List[str]] = {}
        self.metadata: Dict[str, Dict] = {}
        self.score_params: Dict[str, Dict] = {}

    # ── public API ────────────────────────────────────────────────────────

    def load_all_models(self):
        """Load all available models from the models directory."""
        logger.info(f"Loading models from {self.models_dir}")

        registry_path = self.models_dir / "model_registry.json"
        if not registry_path.exists():
            raise FileNotFoundError(f"Model registry not found at {registry_path}")

        with open(registry_path, "r") as f:
            registry = json.load(f)

        if not registry.get("models"):
            logger.warning(
                "Model registry is empty -- no models registered. "
                "Run export_models.py to generate artifacts."
            )
            return

        for fund_key, model_info in registry["models"].items():
            try:
                self._load_fund_model(fund_key, model_info)
                logger.info(f"Loaded model for {fund_key}")
            except Exception as e:
                logger.error(f"Failed to load model for {fund_key}: {e}")
                raise

    def reload_models(self):
        """Reload all models (for hot-swapping)."""
        logger.info("Reloading models...")
        self.loaded_models.clear()
        self.scalers.clear()
        self.feature_names.clear()
        self.metadata.clear()
        self.score_params.clear()
        self.load_all_models()

    def is_ready(self) -> bool:
        return len(self.loaded_models) > 0

    def get_loaded_models(self) -> List[str]:
        return list(self.loaded_models.keys())

    def get_model(self, fund_name: str) -> Dict:
        fund_key = self._resolve_fund_key(fund_name)
        if fund_key not in self.loaded_models:
            raise ValueError(f"Model not loaded for fund: {fund_name}")
        return self.loaded_models[fund_key]

    def get_scaler(self, fund_name: str):
        fund_key = self._resolve_fund_key(fund_name)
        if fund_key not in self.scalers:
            raise ValueError(f"Scaler not loaded for fund: {fund_name}")
        return self.scalers[fund_key]

    def get_feature_names(self, fund_name: str) -> List[str]:
        fund_key = self._resolve_fund_key(fund_name)
        if fund_key not in self.feature_names:
            raise ValueError(f"Feature names not loaded for fund: {fund_name}")
        return self.feature_names[fund_key]

    def get_metadata(self, fund_name: str) -> Dict:
        fund_key = self._resolve_fund_key(fund_name)
        if fund_key not in self.metadata:
            raise ValueError(f"Metadata not loaded for fund: {fund_name}")
        return self.metadata[fund_key]

    def get_score_params(self, fund_name: str) -> Dict:
        fund_key = self._resolve_fund_key(fund_name)
        return self.score_params.get(fund_key, {})

    def get_models_info(self) -> List[Dict]:
        """Return model info including feature_names so clients (e.g. Streamlit) use only the best model's features."""
        info = []
        for fund_key in self.loaded_models:
            meta = self.metadata.get(fund_key, {})
            feature_names = self.feature_names.get(fund_key, [])
            info.append(
                {
                    "fund_key": fund_key,
                    "fund_name": meta.get("fund_name", fund_key),
                    "model_name": meta.get("model_name", "Unknown"),
                    "created_at": meta.get("created_at", "Unknown"),
                    "feature_count": len(feature_names),
                    "feature_names": feature_names,
                    "performance": meta.get("performance_metrics", {}),
                }
            )
        return info

    # ── private helpers ───────────────────────────────────────────────────

    def _load_fund_model(self, fund_key: str, model_info: Dict):
        """Load a specific fund's model and artifacts from the latest/ directory."""
        fund_dir = self.models_dir / fund_key / "latest"

        if not fund_dir.exists():
            raise FileNotFoundError(f"Model directory not found: {fund_dir}")

        with open(fund_dir / "metadata.json", "r") as f:
            self.metadata[fund_key] = json.load(f)

        self.scalers[fund_key] = joblib.load(fund_dir / "scaler.joblib")

        with open(fund_dir / "feature_names.json", "r") as f:
            self.feature_names[fund_key] = json.load(f)

        model_name = self.metadata[fund_key].get("model_name", "Unknown")
        neural_models = {"Autoencoder", "LSTM Autoencoder"}
        model_type = "neural" if model_name in neural_models else "sklearn"

        # Use metadata feature_names as authoritative source
        meta_features = self.metadata[fund_key].get("feature_names")
        if meta_features and len(meta_features) > len(self.feature_names[fund_key]):
            self.feature_names[fund_key] = meta_features
            logger.info(
                "Restored feature_names from metadata (%s features) for %s",
                len(meta_features), fund_key,
            )

        # Load the model: Keras .keras first, then sklearn .joblib
        keras_path = fund_dir / "model.keras"
        joblib_path = fund_dir / "model.joblib"

        if keras_path.exists() and model_type == "neural":
            import tensorflow as tf
            model = tf.keras.models.load_model(keras_path)
            logger.info("Loaded Keras model from %s for %s", keras_path.name, fund_key)
        elif joblib_path.exists():
            model = joblib.load(joblib_path)
            logger.info("Loaded joblib model from %s for %s", joblib_path.name, fund_key)
        else:
            raise FileNotFoundError(
                f"No model file found in {fund_dir}. "
                f"Expected model.keras (for {model_name}) or model.joblib."
            )

        # Load score reference statistics (for normalizing anomaly scores)
        score_params_path = fund_dir / "score_params.json"
        if score_params_path.exists():
            with open(score_params_path, "r") as f:
                self.score_params[fund_key] = json.load(f)
            logger.info("Loaded score_params for %s", fund_key)

        self.loaded_models[fund_key] = {
            "model": model,
            "type": model_type,
            "name": model_name,
        }

    def _resolve_fund_key(self, fund_name: str) -> str:
        """Map a human-readable fund name to its registry key.

        Accepts the registry key directly, the display name from metadata,
        or a sanitised version of either.
        """
        if fund_name in self.loaded_models:
            return fund_name

        sanitised = self._sanitize_filename(fund_name)
        if sanitised in self.loaded_models:
            return sanitised

        for key, meta in self.metadata.items():
            if meta.get("fund_name", "").lower() == fund_name.lower():
                return key

        raise ValueError(
            f"Unknown fund '{fund_name}'. "
            f"Available: {list(self.loaded_models.keys())}"
        )

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_]", "_", str(name).lower().replace(" ", "_"))

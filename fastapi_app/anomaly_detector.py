"""
Vercel-friendly anomaly detector for sklearn-compatible models.
"""

import logging
import time
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(self, model_loader):
        self.model_loader = model_loader

    def detect_anomalies(self, fund_name: str, transactions: List[Dict]) -> List[Dict]:
        start_time = time.time()
        feature_names = list(self.model_loader.get_feature_names(fund_name))
        model_info = self.model_loader.get_model(fund_name)
        score_params = self.model_loader.get_score_params(fund_name)
        scaler = self.model_loader.get_scaler(fund_name)

        x_raw = self._to_feature_matrix(transactions, feature_names)
        x_scaled = scaler.transform(x_raw)

        predictions = self._predict(model_info, x_scaled, score_params)
        is_anomaly = np.array(predictions["is_anomaly"], dtype=int)
        self._apply_business_rules(is_anomaly, transactions)
        risk_tiers = self._classify_risk_tiers(predictions["anomaly_scores"], score_params)

        results = []
        for i, score in enumerate(predictions["anomaly_scores"]):
            row_values = x_raw[i]
            features_used = [
                {"name": fn, "value": float(row_values[j])} for j, fn in enumerate(feature_names)
            ]
            results.append(
                {
                    "transaction_id": i,
                    "is_anomaly": bool(is_anomaly[i]),
                    "anomaly_score": round(float(score), 6),
                    "risk_tier": risk_tiers[i],
                    "fusion_score": round(float(score), 6),
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                    "features_used": features_used,
                    "feature_contributions": [],
                    "explanation": self._explain(risk_tiers[i], bool(is_anomaly[i]), float(score)),
                }
            )
        return results

    @staticmethod
    def _to_feature_matrix(transactions: List[Dict], feature_names: List[str]) -> np.ndarray:
        rows = []
        for txn in transactions:
            row = []
            inflows = float(txn.get("inflows", 0.0))
            outflows = float(txn.get("outflows", 0.0))
            for feature in feature_names:
                if feature == "gross_activity":
                    val = float(txn.get(feature, inflows + outflows))
                else:
                    val = float(txn.get(feature, 0.0))
                row.append(val)
            rows.append(row)
        return np.asarray(rows, dtype=np.float64)

    @staticmethod
    def _predict(model_info: Dict, x_scaled: np.ndarray, score_params: Dict) -> Dict:
        model = model_info["model"]
        y_pred = model.predict(x_scaled)
        is_anomaly = np.where(y_pred == -1, 1, 0)
        if hasattr(model, "score_samples"):
            anomaly_scores = -model.score_samples(x_scaled)
        elif hasattr(model, "decision_function"):
            anomaly_scores = -model.decision_function(x_scaled)
        else:
            anomaly_scores = is_anomaly.astype(float)

        threshold = score_params.get("threshold_95")
        if threshold and threshold > 0:
            anomaly_scores = anomaly_scores / threshold

        return {
            "is_anomaly": is_anomaly.tolist(),
            "anomaly_scores": anomaly_scores.tolist(),
        }

    @staticmethod
    def _apply_business_rules(is_anomaly: np.ndarray, transactions: List[Dict]) -> None:
        for idx, txn in enumerate(transactions):
            if idx >= len(is_anomaly):
                break
            if int(txn.get("is_first_transaction", 0)) == 1:
                is_anomaly[idx] = 0
                continue
            if "has_trigger" in txn and float(txn.get("has_trigger", 0.0)) == 0.0:
                is_anomaly[idx] = 0

    @staticmethod
    def _classify_risk_tiers(scores: List[float], score_params: Dict) -> List[str]:
        arr = np.array(scores, dtype=float)
        if arr.size == 0:
            return []
        threshold = score_params.get("threshold_95")
        if threshold and threshold > 0:
            return np.where(arr < 1.0, "Low", np.where(arr < 2.0, "Medium", "High")).tolist()
        mu = float(arr.mean())
        sigma = float(arr.std())
        if sigma == 0:
            return ["Low"] * len(arr)
        return np.where(arr <= mu + sigma, "Low", np.where(arr <= mu + 2 * sigma, "Medium", "High")).tolist()

    @staticmethod
    def _explain(risk_tier: str, is_anomaly: bool, score: float) -> str:
        if is_anomaly:
            return f"Risk tier **{risk_tier}** (score {score:.4f}): transaction flagged as anomalous."
        return f"Risk tier **{risk_tier}** (score {score:.4f}): transaction appears normal."

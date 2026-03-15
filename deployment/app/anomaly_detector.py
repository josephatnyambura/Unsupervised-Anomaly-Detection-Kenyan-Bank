"""
Anomaly Detector - Core detection logic with preprocessing pipeline

Uses training-set score statistics (score_params.json) to normalize
anomaly scores to a 0-1 range and compute stable risk tiers.
"""

import time
import logging
from typing import List, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Handles anomaly detection for transactions."""

    def __init__(self, model_loader):
        self.model_loader = model_loader

    def detect_anomalies(self, fund_name: str, transactions: List[Dict]) -> List[Dict]:
        start_time = time.time()

        df = pd.DataFrame(transactions)
        feature_names = list(self.model_loader.get_feature_names(fund_name))
        model_info = self.model_loader.get_model(fund_name)
        score_params = self.model_loader.get_score_params(fund_name)

        X = self._preprocess_transactions(df, fund_name, feature_names)
        scaler = self.model_loader.get_scaler(fund_name)

        X_scaled = scaler.transform(X)
        predictions = self._predict(model_info, X_scaled, score_params)

        is_anomaly = np.array(predictions["is_anomaly"])
        self._apply_business_rules(is_anomaly, df)
        predictions["is_anomaly"] = is_anomaly.tolist()

        risk_tiers = self._classify_risk_tiers(
            predictions["anomaly_scores"], score_params
        )

        per_feat = predictions.get("per_feature_errors")

        results = []
        for i, (score, risk) in enumerate(
            zip(predictions["anomaly_scores"], risk_tiers)
        ):
            features_used = [
                {"name": fn, "value": float(X.iloc[i][fn])} for fn in feature_names
            ]

            feature_contributions = []
            if per_feat is not None:
                row_errors = per_feat[i]
                total = float(row_errors.sum()) or 1.0
                for j, fn in enumerate(feature_names):
                    feature_contributions.append({
                        "name": fn,
                        "reconstruction_error": round(float(row_errors[j]), 6),
                        "contribution_pct": round(float(row_errors[j]) / total * 100, 2),
                    })

            explanation = self._explain(
                feature_names,
                X.iloc[i],
                risk,
                bool(predictions["is_anomaly"][i]),
                float(score),
            )
            results.append(
                {
                    "transaction_id": i,
                    "is_anomaly": bool(predictions["is_anomaly"][i]),
                    "anomaly_score": round(float(score), 6),
                    "risk_tier": risk,
                    "fusion_score": round(float(score), 6),
                    "processing_time_ms": round(
                        (time.time() - start_time) * 1000, 2
                    ),
                    "features_used": features_used,
                    "feature_contributions": feature_contributions,
                    "explanation": explanation,
                }
            )

        return results

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _apply_business_rules(is_anomaly: np.ndarray, df: pd.DataFrame) -> None:
        if "is_first_transaction" in df.columns:
            is_anomaly[
                df["is_first_transaction"].astype(bool).values[: len(is_anomaly)]
            ] = 0
        if "has_trigger" in df.columns:
            is_anomaly[(df["has_trigger"].values[: len(is_anomaly)] == 0)] = 0
        elif {"inflows", "outflows"}.issubset(df.columns):
            no_activity = (
                df["inflows"].values[: len(is_anomaly)] == 0
            ) & (df["outflows"].values[: len(is_anomaly)] == 0)
            if "balance_error_flag" in df.columns:
                no_balance_err = (
                    df["balance_error_flag"].values[: len(is_anomaly)] == 0
                )
                is_anomaly[no_activity & no_balance_err] = 0
            else:
                is_anomaly[no_activity] = 0

    def _preprocess_transactions(
        self, df: pd.DataFrame, fund_name: str, feature_names: List[str]
    ) -> pd.DataFrame:
        if "gross_activity" not in df.columns and {"inflows", "outflows"}.issubset(
            df.columns
        ):
            df["gross_activity"] = df["inflows"] + df["outflows"]

        for feature in feature_names:
            if feature not in df.columns:
                df[feature] = 0.0

        return df[feature_names].fillna(0).astype(np.float64)

    @staticmethod
    def _predict(
        model_info: Dict, X_scaled: np.ndarray, score_params: Dict
    ) -> Dict:
        model = model_info["model"]
        model_type = model_info.get("type", "sklearn")

        per_feature_errors = None

        if model_type == "neural":
            if (
                X_scaled.ndim == 2
                and hasattr(model, "input_shape")
                and len(model.input_shape) == 3
            ):
                X_input = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
            else:
                X_input = X_scaled
            reconstructions = model.predict(X_input, verbose=0)
            if reconstructions.ndim == 3:
                reconstructions = reconstructions.reshape(X_scaled.shape)

            sq_errors = np.power(X_scaled - reconstructions, 2)
            per_feature_errors = sq_errors
            raw_mse = np.mean(sq_errors, axis=1)

            ref_threshold = score_params.get("threshold_95")
            ref_mean = score_params.get("mean")
            ref_std = score_params.get("std")

            if ref_threshold and ref_threshold > 0:
                anomaly_scores = raw_mse / ref_threshold
                is_anomaly = (anomaly_scores >= 1.0).astype(int)
            elif ref_mean is not None and ref_std and ref_std > 0:
                anomaly_scores = (raw_mse - ref_mean) / ref_std
                is_anomaly = (anomaly_scores > 2.0).astype(int)
            else:
                threshold = np.percentile(raw_mse, 95) if len(raw_mse) > 1 else 1.0
                anomaly_scores = raw_mse / max(threshold, 1e-10)
                is_anomaly = (anomaly_scores >= 1.0).astype(int)
        else:
            y_pred = model.predict(X_scaled)
            is_anomaly = np.where(y_pred == -1, 1, 0)
            if hasattr(model, "score_samples"):
                anomaly_scores = -model.score_samples(X_scaled)
            elif hasattr(model, "decision_function"):
                anomaly_scores = -model.decision_function(X_scaled)
            else:
                anomaly_scores = is_anomaly.astype(float)

        return {
            "is_anomaly": is_anomaly.tolist(),
            "anomaly_scores": anomaly_scores.tolist(),
            "per_feature_errors": per_feature_errors,
        }

    @staticmethod
    def _explain(
        feature_names: List[str],
        row: pd.Series,
        risk_tier: str,
        is_anomaly: bool,
        anomaly_score: float,
    ) -> str:
        parts = []
        if is_anomaly:
            triggers = []
            if row.get("inflow_spike", 0) == 1:
                triggers.append("unusual inflow spike")
            if row.get("outflow_spike", 0) == 1:
                triggers.append("unusual outflow spike")
            if row.get("balance_error_flag", 0) == 1:
                triggers.append(
                    "balance discrepancy (opening + inflows - outflows != balance)"
                )
            if row.get("has_reversal", 0) > 0:
                triggers.append("reversal detected")
            if row.get("balance_anomaly_flag", 0) == 1:
                triggers.append("balance change exceeds 2 std deviations")
            trigger_str = ", ".join(triggers) if triggers else "elevated anomaly score"
            parts.append(
                "Risk tier **%s** (score %.4f): anomaly triggered by %s."
                % (risk_tier, anomaly_score, trigger_str)
            )
        else:
            if risk_tier == "Low":
                parts.append(
                    "Risk tier **%s** (score %.4f): transaction is within the normal range; "
                    "no unusual inflows, outflows, or balance errors detected."
                    % (risk_tier, anomaly_score)
                )
            else:
                parts.append(
                    "Risk tier **%s** (score %.4f): no specific anomaly triggers "
                    "(unusual inflows, outflows, or balance errors) were detected; "
                    "the score falls in the %s risk range and may warrant review."
                    % (risk_tier, anomaly_score, risk_tier.lower())
                )
        return " ".join(parts)

    @staticmethod
    def _classify_risk_tiers(
        scores: List[float], score_params: Dict
    ) -> List[str]:
        """
        Uses training-set mean/std for stable risk tiers:
            Low    ≤ μ + 1σ   (normalized score ~0-1)
            Medium ≤ μ + 2σ   (normalized score ~1-2)
            High   > μ + 2σ   (normalized score >2)
        Falls back to batch stats if no score_params available.
        """
        arr = np.array(scores)
        if len(arr) == 0:
            return []

        ref_threshold = score_params.get("threshold_95")
        ref_mean = score_params.get("mean")
        ref_std = score_params.get("std")

        if ref_threshold and ref_threshold > 0:
            # Scores are already normalized (mse / threshold_95)
            # <1.0 = below 95th pct = Low; 1-2 = Medium; >2 = High
            return np.where(
                arr < 1.0,
                "Low",
                np.where(arr < 2.0, "Medium", "High"),
            ).tolist()

        mu = ref_mean if ref_mean is not None else float(arr.mean())
        sigma = ref_std if ref_std else float(arr.std())
        if sigma == 0:
            return ["Low"] * len(arr)

        return np.where(
            arr <= mu + sigma,
            "Low",
            np.where(arr <= mu + 2 * sigma, "Medium", "High"),
        ).tolist()

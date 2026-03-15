"""
Pydantic schemas for request/response validation.
All API inputs and outputs are validated with type hints and constraints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ─── Request schemas ─────────────────────────────────────────────────────────

class TransactionIn(BaseModel):
    """Single transaction input; all fields validated."""

    clientid: str = Field(..., min_length=1, max_length=64, description="Client identifier")
    transactiondate: str = Field(..., min_length=8, max_length=32, description="Transaction date (YYYY-MM-DD or ISO)")
    inflows: float = Field(0.0, ge=0.0, description="Inflows amount")
    outflows: float = Field(0.0, ge=0.0, description="Outflows amount")
    balance: float = Field(0.0, ge=0.0, description="Account balance")
    dailyincome: float = Field(0.0, ge=0.0, description="Daily income")
    cumulativeincome: float = Field(0.0, ge=0.0, description="Cumulative income")
    gross_activity: Optional[float] = Field(None, ge=0.0)
    zero_activity_freq: Optional[float] = Field(None, ge=0.0, le=1.0, description="Zero-activity frequency in [0,1]")
    rolling_mean_inflows: Optional[float] = Field(None, ge=0.0)
    rolling_std_inflows: Optional[float] = Field(None, ge=0.0)

    @field_validator("transactiondate")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("transactiondate cannot be empty")
        return v.strip()


class PredictRequest(BaseModel):
    """Request body for POST /predict."""

    fund_name: str = Field(..., min_length=1, max_length=128, examples=["Money Market Fund"])
    transactions: List[TransactionIn] = Field(..., min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def check_transactions_non_empty(self):
        if not self.transactions:
            raise ValueError("At least one transaction is required")
        return self


# ─── Response schemas ───────────────────────────────────────────────────────

class FeatureUsed(BaseModel):
    """Single feature name and value used in a prediction."""

    name: str = Field(..., min_length=1)
    value: float = Field(...)


class PredictionOut(BaseModel):
    """Single prediction result."""

    transaction_id: int = Field(..., ge=0)
    is_anomaly: bool
    anomaly_score: float = Field(..., ge=0.0)
    risk_tier: str = Field(..., pattern="^(Low|Medium|High)$")
    fusion_score: float = Field(..., ge=0.0)
    processing_time_ms: float = Field(..., ge=0.0)
    features_used: Optional[List[Dict[str, Any]]] = None
    explanation: Optional[str] = None


class PredictResponse(BaseModel):
    """Response for POST /predict."""

    predictions: List[PredictionOut] = Field(..., min_length=1)
    total_processing_time_ms: float = Field(..., ge=0.0)
    latency_target_met: bool


# ─── Health & models ─────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str = Field(..., pattern="^(healthy|degraded)$")
    models_loaded: List[str] = Field(default_factory=list)
    timestamp: float = Field(..., ge=0)


class ModelInfo(BaseModel):
    """Per-fund model metadata."""

    fund_key: str
    fund_name: str
    model_name: str
    created_at: Optional[str] = None
    feature_count: int = Field(..., ge=0)
    feature_names: List[str] = Field(default_factory=list)
    performance: Optional[Dict[str, Any]] = None


class ModelsResponse(BaseModel):
    """Response for GET /models."""

    models: List[ModelInfo] = Field(default_factory=list)
    count: int = Field(..., ge=0)


class ReloadResponse(BaseModel):
    """Response for POST /reload."""

    status: str = Field(..., pattern="^(success|error)$")
    message: str
    models_loaded: List[str] = Field(default_factory=list)

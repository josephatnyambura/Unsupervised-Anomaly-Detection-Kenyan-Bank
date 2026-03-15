"""
Streamlit UI for Anomaly Detection API (Production)
Uses only the best model and top features from the deployed API (per fund).
Fetches model name and feature list from GET /models so the UI matches the loaded model.
"""

import json
import os
from pathlib import Path
from datetime import date
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

st.set_page_config(
    page_title="Anomaly Detection",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

FALLBACK_FEATURE_NAMES = [
    "inflows", "gross_activity", "zero_activity_freq",
    "rolling_mean_inflows", "rolling_std_inflows",
]

# Feature UI config: (label, help, min, max, step)
# Derived features are already standardised in the training CSVs (mean≈0).
# Only `balance` is in raw currency.
FEATURE_UI = {
    "inflows": ("Inflows", "Transaction inflows (raw currency).", 0.0, 500_000.0, 1000.0),
    "outflows": ("Outflows", "Transaction outflows (raw currency).", 0.0, 500_000.0, 1000.0),
    "gross_activity": ("Gross activity", "Inflows + outflows.", 0.0, 500_000.0, 1000.0),
    "balance": ("Balance", "Account balance (raw currency).", 0.0, 5_000_000.0, 10000.0),
    "dailyincome": ("Daily income", "Income attributed to the day.", 0.0, 50_000.0, 100.0),
    "cumulativeincome": ("Cumulative income", "Pre-scaled (training mean≈0, std≈1). Typical range: -2 to 55.", -2.0, 60.0, 0.1),
    "zero_activity_freq": ("Zero-activity frequency", "Pre-scaled (training mean≈0). Range: -10 to 0.4.", -10.0, 1.0, 0.05),
    "rolling_mean_inflows": ("Rolling mean inflows", "Recent average inflows.", 0.0, 100_000.0, 500.0),
    "rolling_std_inflows": ("Rolling std inflows", "Recent variability of inflows.", 0.0, 50_000.0, 500.0),
    "lag_balance": ("Lag balance", "Pre-scaled (training mean≈0). Typical range: -0.2 to 24.", -1.0, 25.0, 0.1),
    "lag_cumulativeincome": ("Lag cumulative income", "Pre-scaled (training mean≈0). Typical range: -2 to 55.", -2.0, 55.0, 0.1),
    "rolling_mean_balance": ("Rolling mean balance", "Pre-scaled (training mean≈0). Typical range: -0.2 to 24.", -1.0, 25.0, 0.1),
    "rolling_std_balance": ("Rolling std balance", "Recent balance variability.", 0.0, 100_000.0, 500.0),
    "rolling_mean_cumulativeincome": ("Rolling mean cumul. income", "Pre-scaled (training mean≈0). Typical range: -2 to 48.", -2.0, 50.0, 0.1),
    "rolling_std_cumulativeincome": ("Rolling std cumul. income", "Pre-scaled (training mean≈0). Typical range: 0 to 26.", 0.0, 26.0, 0.1),
    "ratio": ("Ratio", "Transaction ratio (training mean≈0.4). Typical range: -0.1 to 26.", -1.0, 30.0, 0.1),
    "has_trigger": ("Has trigger", "Binary: 1 if anomaly trigger observed, 0 otherwise.", 0.0, 1.0, 1.0),
    "balance_error_flag": ("Balance error flag", "Binary: 1 if balance discrepancy detected, 0 otherwise.", 0.0, 1.0, 1.0),
    "is_first_transaction": ("Is first transaction", "Binary: 1 if first transaction for client, 0 otherwise.", 0.0, 1.0, 1.0),
    "inflow_spike": ("Inflow spike", "Binary: 1 if unusual inflow spike, 0 otherwise.", 0.0, 1.0, 1.0),
    "outflow_spike": ("Outflow spike", "Binary: 1 if unusual outflow spike, 0 otherwise.", 0.0, 1.0, 1.0),
}
BINARY_FEATURES = {"has_trigger", "balance_error_flag", "is_first_transaction", "inflow_spike", "outflow_spike"}

# Default API URL; override with env var API_BASE_URL (e.g. for Streamlit Cloud)
DEFAULT_API_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")
FUND_OPTIONS = {
    "Money Market Fund": "money_market_fund",
    "Fixed Income Fund (USD)": "fixed_income_fund__usd_",
}

# ── Preset values matching ACTUAL training data distributions ─────────────
_MMF_PRESETS = {
    "Normal (typical behaviour)": {
        "clientid": "NORMAL_001", "transactiondate": "2024-07-15",
        "balance": 200_000.0, "zero_activity_freq": 0.0, "cumulativeincome": 0.0,
        "lag_balance": 0.0, "lag_cumulativeincome": 0.0, "rolling_mean_balance": 0.0,
        "rolling_mean_cumulativeincome": 0.0, "rolling_std_cumulativeincome": 0.0,
        "balance_error_flag": 0.0, "has_trigger": 1.0,
    },
    "High value / unusual (suspicious)": {
        "clientid": "SUSPICIOUS_001", "transactiondate": "2024-07-31",
        "balance": 5_000_000.0, "zero_activity_freq": -3.0, "cumulativeincome": 10.0,
        "lag_balance": 8.0, "lag_cumulativeincome": 9.0, "rolling_mean_balance": 7.0,
        "rolling_mean_cumulativeincome": 8.0, "rolling_std_cumulativeincome": 5.0,
        "balance_error_flag": 1.0, "has_trigger": 1.0,
    },
    "Zero activity (dormant pattern)": {
        "clientid": "ZERO_ACT_001", "transactiondate": "2024-08-01",
        "balance": 500.0, "zero_activity_freq": 0.38, "cumulativeincome": -1.0,
        "lag_balance": -0.15, "lag_cumulativeincome": -1.0, "rolling_mean_balance": -0.15,
        "rolling_mean_cumulativeincome": -1.0, "rolling_std_cumulativeincome": 0.0,
        "balance_error_flag": 0.0, "has_trigger": 0.0,
    },
}
_FIF_PRESETS = {
    "Normal (typical behaviour)": {
        "clientid": "NORMAL_001", "transactiondate": "2024-07-15",
        "balance": 45_000.0, "zero_activity_freq": 0.14, "ratio": 0.4,
        "cumulativeincome": -0.13, "lag_balance": -0.15, "lag_cumulativeincome": -0.13,
        "rolling_mean_balance": -0.15, "rolling_mean_cumulativeincome": -0.13,
        "rolling_std_cumulativeincome": 0.001, "has_trigger": 1.0,
    },
    "High value / unusual (suspicious)": {
        "clientid": "SUSPICIOUS_001", "transactiondate": "2024-07-31",
        "balance": 500_000.0, "zero_activity_freq": -3.0, "ratio": 8.0,
        "cumulativeincome": 0.1, "lag_balance": 0.1, "lag_cumulativeincome": 0.1,
        "rolling_mean_balance": 0.1, "rolling_mean_cumulativeincome": 0.1,
        "rolling_std_cumulativeincome": 0.05, "has_trigger": 1.0,
    },
    "Zero activity (dormant pattern)": {
        "clientid": "ZERO_ACT_001", "transactiondate": "2024-08-01",
        "balance": 100.0, "zero_activity_freq": 0.38, "ratio": 0.0,
        "cumulativeincome": -0.14, "lag_balance": -0.16, "lag_cumulativeincome": -0.14,
        "rolling_mean_balance": -0.16, "rolling_mean_cumulativeincome": -0.14,
        "rolling_std_cumulativeincome": 0.0, "has_trigger": 0.0,
    },
}
PRESET_VALUES_BY_FUND = {
    "money_market_fund": _MMF_PRESETS,
    "fixed_income_fund__usd_": _FIF_PRESETS,
}
PRESET_VALUES = _MMF_PRESETS

RISK_COLORS = {"Low": "#2ecc71", "Medium": "#f39c12", "High": "#e74c3c"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_feature_ui(feature_name: str) -> Tuple[str, str, float, float, float]:
    if feature_name in FEATURE_UI:
        return FEATURE_UI[feature_name]
    if any(x in feature_name.lower() for x in ("flag", "trigger", "spike", "is_first")):
        return (feature_name.replace("_", " ").title(), "Binary: 0 or 1 only.", 0.0, 1.0, 1.0)
    return (feature_name.replace("_", " ").title(), "Model feature.", 0.0, 100_000.0, 500.0)


def is_binary_feature(feature_name: str) -> bool:
    if feature_name in BINARY_FEATURES:
        return True
    _, _, mn, mx, step = get_feature_ui(feature_name)
    return step == 1.0 and mx == 1.0


def validate_feature_value(name: str, value: float) -> Tuple[float, str]:
    """Clamp value to valid range. Return (clamped_value, warning_or_empty)."""
    _, _, mn, mx, _ = get_feature_ui(name)
    if is_binary_feature(name):
        clamped = 1.0 if value >= 0.5 else 0.0
        if value not in (0.0, 1.0):
            return clamped, f"**{name}** must be 0 or 1 (was {value}, set to {int(clamped)})."
        return clamped, ""
    if value < mn:
        return mn, f"**{name}** below minimum ({mn}). Clamped."
    if value > mx:
        return mx, f"**{name}** above maximum ({mx}). Clamped."
    return value, ""


def fetch_models_info(base_url: str) -> Tuple[bool, List[Dict], str]:
    try:
        r = requests.get(f"{base_url}/models", timeout=5)
        if r.status_code != 200:
            return False, [], r.text or "HTTP %s" % r.status_code
        return True, r.json().get("models", []), ""
    except requests.exceptions.ConnectionError:
        return False, [], "Cannot connect to API."
    except Exception as e:
        return False, [], str(e)


def get_fund_model_info(api_url: str, fund_key: str) -> Tuple[str, List[str]]:
    ok, models, _ = fetch_models_info(api_url)
    if not ok or not models:
        return "Unknown (API unreachable)", FALLBACK_FEATURE_NAMES
    for m in models:
        if m.get("fund_key") == fund_key:
            return m.get("model_name", "Unknown"), m.get("feature_names", FALLBACK_FEATURE_NAMES)
    return "Unknown", FALLBACK_FEATURE_NAMES


def check_api_connection(base_url: str) -> Tuple[bool, str, Dict[str, Any]]:
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        r.raise_for_status()
        data = r.json()
        status = data.get("status", "unknown")
        models = data.get("models_loaded", [])
        if status == "healthy" and models:
            return True, "API healthy. Models loaded.", data
        if status == "degraded":
            return False, "API up but no models loaded. Run export_models.py and reload.", data
        return True, "API responded.", data
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect. Start API (e.g. docker-compose up -d).", {}
    except Exception as e:
        return False, str(e), {}


def call_predict(base_url: str, fund_key: str, transactions: List[Dict]) -> Tuple[bool, Any]:
    try:
        r = requests.post(
            f"{base_url}/predict",
            json={"fund_name": fund_key, "transactions": transactions},
            timeout=30,
        )
        if r.status_code != 200:
            return False, r.text or "HTTP %s" % r.status_code
        return True, r.json()
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to API."
    except requests.exceptions.Timeout:
        return False, "Request timed out."
    except Exception as e:
        return False, str(e)


def risk_badge(tier: str) -> str:
    return {"Low": "🟢 Low", "Medium": "🟡 Medium"}.get(tier, "🔴 High")


def build_transaction(client_id: str, txn_date: str, feature_values: Dict[str, float]) -> Dict:
    out = {"clientid": client_id, "transactiondate": txn_date}
    out.update(feature_values)
    return out


def build_sample_scenarios(feature_names: List[str], fund_key: str) -> Dict[str, Dict]:
    presets = PRESET_VALUES_BY_FUND.get(fund_key, PRESET_VALUES)
    scenarios = {}
    for name, base in presets.items():
        t = {"clientid": base["clientid"], "transactiondate": base["transactiondate"]}
        for fn in feature_names:
            t[fn] = base.get(fn, 0.0)
        scenarios[name] = t
    return scenarios


def render_contribution_chart(contribs: List[Dict], title: str = ""):
    """Render a horizontal bar chart of per-feature anomaly contribution."""
    if not contribs or not HAS_PLOTLY:
        return
    df_c = pd.DataFrame(contribs)
    if df_c.empty or "contribution_pct" not in df_c.columns:
        return
    df_c = df_c.sort_values("contribution_pct", ascending=True)
    fig = px.bar(
        df_c, x="contribution_pct", y="name", orientation="h",
        color="contribution_pct",
        color_continuous_scale=["#2ecc71", "#f39c12", "#e74c3c"],
        labels={"contribution_pct": "Contribution %", "name": "Feature"},
        text="contribution_pct",
        title=title or None,
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(
        height=max(300, len(df_c) * 40),
        margin=dict(l=10, r=40, t=40 if title else 20, b=20),
        coloraxis_colorbar_title="Contrib %",
        yaxis_title="", xaxis_title="Contribution to anomaly score (%)",
        font=dict(size=12),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_scenario_chart(rows: List[Dict]):
    """Render a risk-colored bar chart for scenario comparison."""
    if not HAS_PLOTLY or not rows:
        st.bar_chart(pd.DataFrame(rows).set_index("Scenario")["Anomaly score"])
        return
    df = pd.DataFrame(rows)
    colors = [RISK_COLORS.get(r, "#95a5a6") for r in df["Risk tier"]]
    fig = go.Figure(go.Bar(
        x=df["Scenario"], y=df["Anomaly score"],
        marker_color=colors,
        text=[f"{s:.4f}" for s in df["Anomaly score"]],
        textposition="outside",
    ))
    fig.add_hline(y=1.0, line_dash="dash", line_color="#e74c3c",
                  annotation_text="Anomaly threshold (score=1.0)",
                  annotation_position="top left")
    fig.update_layout(
        yaxis_title="Anomaly Score (normalized)",
        xaxis_title="", height=400,
        margin=dict(l=10, r=10, t=40, b=10),
        font=dict(size=13),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_prediction_result(pred: Dict, show_contributions: bool = True):
    """Render a single prediction's metrics, explanation, and optional contribution chart."""
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Risk tier", risk_badge(pred["risk_tier"]))
    with c2:
        st.metric("Anomaly score", "%.4f" % pred["anomaly_score"])
    with c3:
        st.metric("Flagged as anomaly", "Yes" if pred["is_anomaly"] else "No")
    if pred.get("explanation"):
        st.info(pred["explanation"])
    if show_contributions and pred.get("feature_contributions"):
        render_contribution_chart(pred["feature_contributions"])


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    api_url = st.text_input("API base URL", value=DEFAULT_API_URL)
    if st.button("Check connection"):
        ok, msg, data = check_api_connection(api_url)
        if ok:
            st.success(msg)
            if data.get("models_loaded"):
                st.caption("Models: " + ", ".join(data["models_loaded"]))
        else:
            st.error(msg)
    st.divider()
    fund_label = st.selectbox("Fund", list(FUND_OPTIONS.keys()))
    fund_key = FUND_OPTIONS[fund_label]
    model_name, feature_names = get_fund_model_info(api_url, fund_key)
    st.caption("Model: **%s** (best from training)." % model_name)
    st.caption("Features (%d): **%s**" % (len(feature_names), ", ".join(feature_names)))

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("🔍 Anomaly Detection")
st.markdown(
    "Production UI for the **FastAPI** anomaly detection service. "
    "The app uses the **best model** and **top features** deployed for each fund (from the API). "
    "These are the same features that influence whether a transaction is an anomaly; "
    "you can see **why** in the explanation."
)
st.divider()

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Single transaction", "Compare scenarios", "Batch (JSON)",
    "Explainability", "Why this result?", "How it works",
])

fund_presets = PRESET_VALUES_BY_FUND.get(fund_key, PRESET_VALUES)
default_values = {fn: fund_presets["Normal (typical behaviour)"].get(fn, 0.0) for fn in feature_names}
sample_scenarios = build_sample_scenarios(feature_names, fund_key)

# ─── Tab 1: Single transaction ───────────────────────────────────────────────
with tab1:
    st.subheader("Score one transaction")
    st.caption(
        "Enter the **%d** features the **%s** model expects. "
        "Values are validated against the training data range." % (len(feature_names), model_name)
    )

    col_meta1, col_meta2 = st.columns(2)
    with col_meta1:
        client_id = st.text_input("Client ID", value="DEMO_001", key="single_client")
    with col_meta2:
        txn_date = st.date_input("Transaction date", value=date(2024, 7, 15), key="single_date")

    st.markdown("**Model features**")
    feature_values = {}
    n_features = len(feature_names)
    n_cols = min(n_features, 5)
    cols = st.columns(n_cols)
    for idx, fkey in enumerate(feature_names):
        label, help_, min_, max_, step = get_feature_ui(fkey)
        default_val = default_values.get(fkey, 0.0)
        default_val = max(min_, min(max_, default_val))

        with cols[idx % n_cols]:
            if is_binary_feature(fkey):
                feature_values[fkey] = float(
                    st.selectbox(label, [0, 1], index=int(default_val), help=help_, key="single_%s" % fkey)
                )
            elif fkey == "zero_activity_freq":
                feature_values[fkey] = st.slider(
                    label, min_, max_, float(default_val), step, help=help_, key="single_%s" % fkey
                )
            else:
                feature_values[fkey] = st.number_input(
                    label, min_value=min_, max_value=max_, value=float(default_val),
                    step=step, help=help_, key="single_%s" % fkey
                )

    if st.button("Get anomaly score", type="primary", key="btn_single"):
        warnings = []
        validated = {}
        for k, v in feature_values.items():
            clamped, warn = validate_feature_value(k, v)
            validated[k] = clamped
            if warn:
                warnings.append(warn)
        if warnings:
            st.warning("Input adjusted: " + " · ".join(warnings))

        txn = build_transaction(client_id, txn_date.isoformat(), validated)
        ok, result = call_predict(api_url, fund_key, [txn])
        if ok:
            pred = result["predictions"][0]
            if pred.get("features_used"):
                st.session_state["last_prediction_features"] = pred["features_used"]
            if pred.get("feature_contributions"):
                st.session_state["last_feature_contributions"] = pred["feature_contributions"]
            st.success("Total time: %.2f ms · Latency target met: %s" % (
                result["total_processing_time_ms"], result["latency_target_met"]))
            render_prediction_result(pred)
            if pred.get("features_used"):
                with st.expander("Features used"):
                    st.dataframe(
                        pd.DataFrame(pred["features_used"]).rename(columns={"name": "Feature", "value": "Value"}),
                        use_container_width=True, hide_index=True,
                    )
            with st.expander("Full API response"):
                st.json(result)
        else:
            st.error(result)

# ─── Tab 2: Compare scenarios ────────────────────────────────────────────────
with tab2:
    st.subheader("Compare preset scenarios")
    st.caption(
        "Presets use the same **%d** features as the **%s** model. "
        "The dashed red line marks the anomaly threshold (score = 1.0)." % (len(feature_names), model_name)
    )
    if st.button("Run all scenarios", type="primary", key="btn_compare"):
        transactions = [sample_scenarios[name] for name in sample_scenarios]
        names = list(sample_scenarios.keys())
        ok, result = call_predict(api_url, fund_key, transactions)
        if ok:
            rows = []
            for i, name in enumerate(names):
                p = result["predictions"][i]
                rows.append({
                    "Scenario": name,
                    "Risk tier": p["risk_tier"],
                    "Anomaly score": round(p["anomaly_score"], 4),
                    "Flagged": "Yes" if p["is_anomaly"] else "No",
                })
            if result["predictions"] and result["predictions"][0].get("feature_contributions"):
                st.session_state["last_feature_contributions"] = result["predictions"][0]["feature_contributions"]

            st.dataframe(
                pd.DataFrame(rows).style.applymap(
                    lambda v: "color: %s" % RISK_COLORS.get(v, ""),
                    subset=["Risk tier"],
                ),
                use_container_width=True, hide_index=True,
            )

            render_scenario_chart(rows)

            for i, name in enumerate(names):
                p = result["predictions"][i]
                with st.expander("%s %s — score %.4f" % (risk_badge(p["risk_tier"]), name, p["anomaly_score"])):
                    if p.get("explanation"):
                        st.info(p["explanation"])
                    if p.get("feature_contributions"):
                        render_contribution_chart(
                            p["feature_contributions"],
                            title="Feature contributions: %s" % name,
                        )
                    if p.get("features_used"):
                        st.dataframe(
                            pd.DataFrame(p["features_used"]).rename(columns={"name": "Feature", "value": "Value"}),
                            use_container_width=True, hide_index=True,
                        )
            with st.expander("Raw API response"):
                st.json(result)
        else:
            st.error(result)

# ─── Tab 3: Batch (JSON) ─────────────────────────────────────────────────────
with tab3:
    st.subheader("Batch prediction from JSON")
    st.caption(
        "Each transaction must include **clientid**, **transactiondate**, and the model features: **%s**."
        % ", ".join(feature_names)
    )
    batch_default = json.dumps(list(sample_scenarios.values()), indent=2)
    json_input = st.text_area("Transactions JSON", value=batch_default, height=220, key="batch_json_%s" % fund_key)
    if st.button("Run batch prediction", type="primary", key="btn_batch"):
        try:
            txns = json.loads(json_input)
            if not isinstance(txns, list):
                txns = [txns]
        except json.JSONDecodeError as e:
            st.error("Invalid JSON: %s" % e)
            txns = None

        if txns is not None:
            # Validate each transaction has required fields
            valid = True
            for idx, t in enumerate(txns):
                if not isinstance(t, dict):
                    st.error("Transaction %d is not a JSON object." % (idx + 1))
                    valid = False
                    break
                missing = [f for f in ("clientid", "transactiondate") if f not in t]
                if missing:
                    st.error("Transaction %d missing required fields: %s" % (idx + 1, ", ".join(missing)))
                    valid = False
                    break
                for fn in feature_names:
                    if fn in t and is_binary_feature(fn) and t[fn] not in (0, 1, 0.0, 1.0):
                        st.warning("Transaction %d: **%s** should be 0 or 1 (got %s)." % (idx + 1, fn, t[fn]))

            if valid:
                ok, result = call_predict(api_url, fund_key, txns)
                if ok:
                    rows = []
                    for i, p in enumerate(result["predictions"]):
                        rows.append({
                            "#": i + 1,
                            "Risk tier": p["risk_tier"],
                            "Anomaly score": round(p["anomaly_score"], 4),
                            "Flagged": "Yes" if p["is_anomaly"] else "No",
                        })
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    st.success("Processed %d transactions in %.2f ms" % (len(rows), result["total_processing_time_ms"]))

                    if HAS_PLOTLY and len(rows) > 1:
                        df_b = pd.DataFrame(rows)
                        colors = [RISK_COLORS.get(r, "#95a5a6") for r in df_b["Risk tier"]]
                        fig = go.Figure(go.Bar(
                            x=[str(r) for r in df_b["#"]], y=df_b["Anomaly score"],
                            marker_color=colors,
                            text=[f"{s:.4f}" for s in df_b["Anomaly score"]],
                            textposition="outside",
                        ))
                        fig.add_hline(y=1.0, line_dash="dash", line_color="#e74c3c",
                                      annotation_text="Threshold")
                        fig.update_layout(
                            xaxis_title="Transaction #", yaxis_title="Anomaly Score",
                            height=350, margin=dict(l=10, r=10, t=30, b=10),
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    for i, p in enumerate(result["predictions"]):
                        with st.expander("%s Transaction %d — score %.4f" % (
                            risk_badge(p["risk_tier"]), i + 1, p["anomaly_score"]
                        )):
                            if p.get("explanation"):
                                st.info(p["explanation"])
                            if p.get("feature_contributions"):
                                render_contribution_chart(p["feature_contributions"])
                    with st.expander("Raw response"):
                        st.json(result)
                else:
                    st.error(result)

# ─── Tab 4: Explainability ───────────────────────────────────────────────────
with tab4:
    st.subheader("Feature contribution to anomaly score")
    st.markdown("""
The autoencoder tries to **reconstruct** each feature from its compressed representation.
Features the model **fails to reconstruct** accurately have higher reconstruction error and
contribute more to the anomaly score.

The chart shows each feature's **percentage contribution** to the total reconstruction error.
A score **≥ 1.0** means the transaction exceeds the 95th percentile threshold from training.

- **Green bars**: low contribution (feature is well-reconstructed, behaving normally)
- **Orange bars**: moderate contribution
- **Red bars**: high contribution (this feature is the main anomaly driver)

Run a prediction in the **Single transaction** or **Compare scenarios** tab first.
    """)

    has_contributions = (
        "last_feature_contributions" in st.session_state
        and st.session_state["last_feature_contributions"]
    )

    if has_contributions:
        contribs = st.session_state["last_feature_contributions"]
        render_contribution_chart(contribs, title="Per-feature anomaly contribution")

        df_detail = pd.DataFrame(contribs).sort_values("contribution_pct", ascending=False)
        df_detail.columns = ["Feature", "Reconstruction Error", "Contribution %"]
        st.markdown("##### Detailed breakdown")
        st.dataframe(df_detail, use_container_width=True, hide_index=True)
    else:
        st.info("Run a prediction in the **Single transaction** or **Compare scenarios** tab to see feature contributions here.")

    st.divider()
    st.markdown("#### SHAP / explainability plots (from notebook)")
    explainability_path = st.text_input(
        "Path to explainability plots",
        value="ml/plots/explainability",
        key="explainability_path",
    )
    if explainability_path:
        base = Path(explainability_path)
        if base.exists():
            patterns = [
                f"*fusion_score*{fund_key}*",
                f"*risk_tier*{fund_key}*",
                f"*shap*{fund_key}*",
            ]
            shown = 0
            for pat in patterns:
                for f in base.glob(pat):
                    if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
                        st.image(str(f), caption=f.name, use_container_width=True)
                        shown += 1
            if shown == 0:
                st.caption("No SHAP plots found for this fund. Run the explainability section in the notebook.")
        else:
            st.caption("Path not found. Run the notebook explainability section first.")

# ─── Tab 5: Why this result? ─────────────────────────────────────────────────
with tab5:
    st.subheader("Understanding the anomaly score")
    st.markdown("""
**How the score works:**

The deployed model is an **autoencoder** (or LSTM autoencoder) that learns the *normal* pattern
of transactions during training. At inference, it tries to reconstruct the input features.
The **reconstruction error** (mean squared error across all features) becomes the anomaly score.

**Score interpretation:**
| Score range | Risk tier | Meaning |
|---|---|---|
| < 1.0 | 🟢 Low | Below the 95th percentile of training errors — normal behaviour |
| 1.0 – 2.0 | 🟡 Medium | Between 95th and ~99th percentile — warrants review |
| > 2.0 | 🔴 High | Significantly above normal — likely anomaly |

**Key features and what they capture:**
| Feature | What it measures |
|---|---|
| **balance** | Account balance in raw currency |
| **cumulativeincome** | Running total of income (pre-scaled) |
| **lag_balance** | Previous period's balance (pre-scaled) |
| **lag_cumulativeincome** | Previous period's cumulative income (pre-scaled) |
| **rolling_mean_balance** | Moving average of balance (pre-scaled) |
| **rolling_mean_cumulativeincome** | Moving average of cumulative income (pre-scaled) |
| **rolling_std_cumulativeincome** | Volatility of cumulative income (pre-scaled) |
| **zero_activity_freq** | Frequency of zero-activity periods (pre-scaled) |
| **balance_error_flag** | 1 if balance doesn't reconcile (opening + inflows − outflows ≠ balance) |
| **has_trigger** | 1 if the transaction has an observable anomaly trigger |
| **ratio** | Outflow/inflow ratio (FIF only, pre-scaled) |

**Business rules applied after scoring:**
- If `has_trigger = 0`, the anomaly flag is suppressed (no observable trigger).
- If `is_first_transaction = 1`, the anomaly flag is suppressed (insufficient history).

**Note on feature scales:** Most derived features (lag_*, rolling_*, cumulativeincome, zero_activity_freq)
are **already standardised** in the training data (mean ≈ 0, std ≈ 1). Only `balance` is in raw
currency units. The preset values in the app match these scales.
    """)

# ─── Tab 6: How it works ─────────────────────────────────────────────────────
with tab6:
    st.subheader("System architecture")
    st.markdown("""
**End-to-end flow:**

1. **Model selection**: The API serves the **best model** identified during training for each fund.
   Money Market Fund uses an **LSTM Autoencoder**; Fixed Income Fund uses an **Autoencoder**.
2. **Feature loading**: This app calls `GET /models` to dynamically fetch the feature list
   for the selected fund. Different funds may use different feature sets.
3. **Input & scaling**: You enter feature values that match the training data's scale.
   The API's `StandardScaler` normalises them before feeding to the model.
4. **Anomaly scoring**: The autoencoder reconstructs the input. The mean squared error (MSE)
   between input and reconstruction is divided by the **95th percentile threshold** from training,
   producing a normalised score where **1.0 = anomaly boundary**.
5. **Risk tiers**: Score < 1.0 → Low, 1.0–2.0 → Medium, > 2.0 → High.
6. **Per-feature contributions**: The squared error for each feature is reported as a percentage
   of the total, showing *which* features drove the anomaly.
7. **Business rules**: Anomaly flags are suppressed when `has_trigger = 0` or
   `is_first_transaction = 1`.

**Deployment stack:**
- **FastAPI** (inference API, < 100ms target latency)
- **Streamlit** (this demo UI)
- **Docker** (containerised deployment)
- **Prometheus** (monitoring via `/metrics`)
    """)
    st.markdown("[Open FastAPI docs (Swagger)](%s/docs)" % api_url)

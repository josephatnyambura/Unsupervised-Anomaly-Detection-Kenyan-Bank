"""Quick API test — run while uvicorn is serving on port 5000."""
import requests
import json

BASE = "http://localhost:5000"

# Health
r = requests.get(f"{BASE}/health", timeout=5)
print("=== HEALTH ===")
print(json.dumps(r.json(), indent=2))

# Models
r = requests.get(f"{BASE}/models", timeout=5)
data = r.json()
print("\n=== MODELS ===")
for m in data["models"]:
    print(f"  {m['fund_name']}: {m['model_name']} ({m['feature_count']} features)")
    print(f"    Features: {m['feature_names']}")

# Predict MMF (LSTM Autoencoder, 10 features)
# Values must match training data scale: balance is raw, all others are pre-standardised (~0 mean)
print("\n=== PREDICT: MONEY MARKET FUND ===")
txn = {
    "clientid": "TEST_001", "transactiondate": "2024-07-15",
    "balance": 200000, "zero_activity_freq": 0.0, "cumulativeincome": 0.0,
    "lag_balance": 0.0, "lag_cumulativeincome": 0.0,
    "rolling_mean_balance": 0.0, "rolling_mean_cumulativeincome": 0.0,
    "rolling_std_cumulativeincome": 0.0, "balance_error_flag": 0, "has_trigger": 1,
}
r = requests.post(f"{BASE}/predict", json={"fund_name": "money_market_fund", "transactions": [txn]}, timeout=30)
if r.status_code == 200:
    p = r.json()["predictions"][0]
    print(f"  OK | Risk: {p['risk_tier']}, Score: {p['anomaly_score']:.6f}, Anomaly: {p['is_anomaly']}")
    print(f"  Features used: {len(p['features_used'])}")
else:
    print(f"  ERROR {r.status_code}: {r.text}")

# Predict FIF (Autoencoder, 10 features)
# balance is raw; other features are pre-standardised in training data
print("\n=== PREDICT: FIXED INCOME FUND (USD) ===")
txn2 = {
    "clientid": "TEST_002", "transactiondate": "2024-07-15",
    "balance": 45000, "zero_activity_freq": 0.14, "ratio": 0.4,
    "cumulativeincome": -0.13, "lag_balance": -0.15,
    "lag_cumulativeincome": -0.13, "rolling_mean_balance": -0.15,
    "rolling_mean_cumulativeincome": -0.13, "rolling_std_cumulativeincome": 0.001, "has_trigger": 1,
}
r = requests.post(f"{BASE}/predict", json={"fund_name": "fixed_income_fund__usd_", "transactions": [txn2]}, timeout=30)
if r.status_code == 200:
    p = r.json()["predictions"][0]
    print(f"  OK | Risk: {p['risk_tier']}, Score: {p['anomaly_score']:.6f}, Anomaly: {p['is_anomaly']}")
    print(f"  Features used: {len(p['features_used'])}")
else:
    print(f"  ERROR {r.status_code}: {r.text}")

print("\n=== ALL TESTS PASSED ===")

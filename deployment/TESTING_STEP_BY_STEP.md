# Step-by-Step: Test Deployment, API, Streamlit, and Grafana

This guide runs **sequentially**: prepare → start services one by one → verify each step → test API → test Streamlit → test Grafana. If Docker keeps returning **500 Internal Server Error** when pulling images, use **Path B (no Docker)** to run the API and Streamlit on your machine and still test everything.

**Project root** = parent folder of `deployment/`. All commands assume you are in the project root unless the step says `cd deployment`.

---

## Overview


| Goal                 | Path A (Docker)                       | Path B (no Docker)        |
| -------------------- | ------------------------------------- | ------------------------- |
| API                  | Docker: postgresql + anomaly-detector | Local: Python + uvicorn   |
| Streamlit            | Run on host (same for both)           | Run on host               |
| Grafana + Prometheus | Docker (optional)                     | Docker (optional) or skip |


Use **Path B** if Docker image pulls fail with 500 errors (postgres, kafka, etc.).

---

## Step 0: Prepare models (both paths)

The API needs a `models/` folder with a registry and per-fund artifacts. Neural models (Autoencoder, LSTM Autoencoder) are saved as `.keras` files; sklearn models as `.joblib`.

### 0a. Re-run the notebook save cell (if `model.keras` files are missing)

Open `Josephat Nyambura - 181247.ipynb` and **re-run all cells** from the training section through the **"MODEL PERSISTENCE WITH JOBLIB"** cell. This creates `model.keras` files containing the trained architecture **and** weights for each fund.

You should see output like:
```
  Saved LSTM Autoencoder trained model to ...\model.keras
  Saved Autoencoder trained model to ...\model.keras
```

### 0b. Export models to `latest/`

```powershell
# From project root
python export_models.py
```

This copies the versioned artifacts (including `model.keras`) into each fund's `latest/` folder and removes any stale `model.keras` left over from previous fallback runs.

**Verify:**
```powershell
dir models\model_registry.json
dir models\money_market_fund\latest\model.keras
dir models\fixed_income_fund__usd_\latest\model.keras
```
Each fund's `latest/` should contain: `model.keras`, `scaler.joblib`, `feature_names.json`, `metadata.json`, `model_architecture.json`.

**Verify:**  
`dir models\model_registry.json` and `dir models\money_market_fund\latest\model.keras` (and same for `fixed_income_fund__usd_`) exist.

---

# Path A: Run with Docker (sequential)

## Step A1: Docker pre-check

If you previously saw **500 Internal Server Error** when pulling images (e.g. `postgres:15-alpine` or `confluentinc/cp-kafka:7.5.0`), do this first.

```powershell
A
docker pull postgres:15-alpine
```

- If `docker pull` returns **500 Internal Server Error**:  
  1. Restart **Docker Desktop** (right-click tray icon → Restart).
  2. Try `docker pull postgres:15-alpine` again.
  3. If it still fails, use **Path B** below to run the API and Streamlit without Docker; you can still test APIs and Streamlit fully.

**Verify:** `docker images` shows `postgres` with tag `15-alpine`.

---

## Step A2: Start PostgreSQL only

```powershell
cd deployment
docker-compose up -d postgresql
```

Wait ~10 seconds, then:

```powershell
docker-compose ps
```

**Verify:** `anomaly-db` (or postgresql) is **Up**.  
Optional: `docker exec anomaly-db pg_isready -U postgres` → output should include “accepting connections”.

---

## Step A3: Build and start the API (anomaly-detector)

```powershell
# Still in deployment/
docker-compose build anomaly-detector
docker-compose up -d anomaly-detector
```

Wait ~30–40 seconds for the healthcheck (models loading).

```powershell
docker-compose ps
curl http://localhost:5000/health
```

**Verify:**  

- Container `anomaly-detector` is **Up**.  
- `curl` returns JSON with `"status": "healthy"` and non-empty `models_loaded`.  
- If `"status": "degraded"` or `models_loaded` is empty: ensure `models/` has both funds’ `latest` with `model.keras`, then:
  ```powershell
  curl -X POST http://localhost:5000/reload
  curl http://localhost:5000/health
  ```

---

## Step A4: Test the API (command line)

From any terminal (API must be running on port 5000).

**Health and models:**

```powershell
curl http://localhost:5000/health
curl http://localhost:5000/models
```

**Predict – Money Market Fund:**

```powershell
curl -X POST http://localhost:5000/predict -H "Content-Type: application/json" -d "{\"fund_name\": \"Money Market Fund\", \"transactions\": [{\"clientid\": \"TEST001\", \"transactiondate\": \"2024-07-15\", \"inflows\": 5000, \"outflows\": 100, \"balance\": 10000, \"dailyincome\": 50, \"cumulativeincome\": 500}]}"
```

**Predict – Fixed Income Fund (USD):**

```powershell
curl -X POST http://localhost:5000/predict -H "Content-Type: application/json" -d "{\"fund_name\": \"Fixed Income Fund (USD)\", \"transactions\": [{\"clientid\": \"TEST002\", \"transactiondate\": \"2024-07-15\", \"inflows\": 1000, \"outflows\": 0, \"balance\": 5000, \"dailyincome\": 25, \"cumulativeincome\": 200}]}"
```

**Verify:** Responses contain `predictions` with `anomaly_score`, `risk_tier`, `features_used`, `explanation`.

**Interactive docs:** Open **[http://localhost:5000/docs](http://localhost:5000/docs)** and try **GET /health**, **GET /models**, **POST /predict**.

---

## Step A5: Run and test Streamlit

Streamlit runs on your host and talks to the API (Docker or local).

```powershell
# From project root (or deployment/)
pip install -r deployment\streamlit_app\requirements.txt
streamlit run deployment/streamlit_app/app.py
```

Browser opens at **[http://localhost:8501](http://localhost:8501)**.

**Verify:**  

1. Sidebar: API URL = `http://localhost:5000` → **Check connection**. You should see the model name and feature list.
2. **Single transaction:** click **Get anomaly score** → risk tier, score, and explanation appear.
3. **Compare scenarios:** **Run all scenarios** and compare Normal / High value / Zero activity.
4. **Batch:** paste a JSON array of transactions (with required fields) → **Run batch prediction**.

---

## Step A6: Start Prometheus and Grafana (optional)

Only after the API is running and you’ve tested it (so Prometheus has something to scrape).

```powershell
cd deployment
docker-compose up -d prometheus grafana
docker-compose ps
```

**Verify Prometheus:**  
Open **[http://localhost:9090](http://localhost:9090)** → **Status** → **Targets**. The `anomaly-detector` target should be **UP**.

**Verify Grafana:**  

1. Open **[http://localhost:3000](http://localhost:3000)**.
2. Log in: **admin** / **admin**.
3. **Dashboards** → open **Anomaly Detection System - Real-Time Monitoring** (or **General** → that dashboard).
4. If it’s missing: **Dashboards** → **New** → **Import** → upload `deployment/monitoring/grafana-dashboard.json`.
5. Generate API traffic (e.g. run the curl predict commands a few times or use Streamlit). Wait 1–2 minutes, refresh the dashboard. You should see request rate, latency percentiles, total requests, etc.

**Verify datasource:** **Connections** → **Data sources** → **Prometheus** → **Save & test** should succeed.

---

# Path B: Run without Docker (when Docker returns 500)

Use this when Docker image pulls keep failing with 500 Internal Server Error. You still get full API + Streamlit testing; Grafana is optional (run Prometheus + Grafana in Docker later if Docker starts working).

## Step B1: Prepare models

Same as Step 0. Ensure `models/model_registry.json` and `models/<fund>/latest/model.keras` (and other artifacts) exist.

---

## Step B2: Run the API locally

```powershell
# From project root
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r deployment\app\requirements.txt
$env:MODELS_DIR = (Get-Location).Path + "\models"
cd deployment\app
python -m uvicorn main:app --host 0.0.0.0 --port 5000
```

Leave this terminal open. In a **new terminal**:

```powershell
curl http://localhost:5000/health
curl http://localhost:5000/models
```

**Verify:** `"status": "healthy"` and non-empty `models_loaded`.

---

## Step B3: Test the API (command line)

Same as Step A4: use the same `curl` commands for health, models, and both predict examples. Open **[http://localhost:5000/docs](http://localhost:5000/docs)** to use Swagger.

---

## Step B4: Run and test Streamlit

Same as Step A5:

```powershell
# New terminal; from project root, with venv activated if you use it
pip install -r deployment\streamlit_app\requirements.txt
streamlit run deployment/streamlit_app/app.py
```

Open **[http://localhost:8501](http://localhost:8501)**, set API URL to `http://localhost:5000`, **Check connection**, then test single transaction, scenarios, and batch.

---

## Step B5: Grafana (optional, if Docker works for Prometheus/Grafana only)

If Docker can pull `prom/prometheus` and `grafana/grafana` but not postgres/kafka:

- Run the API locally (Path B) so it’s on port 5000.
- Prometheus in Docker scrapes `anomaly-detector:5000`; that hostname only works from inside Docker. So you’d need to either:
  - Run the API in Docker (then you’re back to needing postgres image), or  
  - Change Prometheus config to scrape `host.docker.internal:5000` (Windows/Mac) so the container can reach the local API.

So for Path B, the simplest is: **skip Grafana** until Docker is fixed, or run Prometheus + Grafana in Docker and set the scrape target to `host.docker.internal:5000` (see Troubleshooting).

---

# Quick reference


| What                     | Command / URL                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| Prepare models           | `python export_models.py` (from project root)                                                                                  |
| Docker pre-check         | `docker pull postgres:15-alpine`                                                                                               |
| API (Docker, sequential) | `cd deployment` → `docker-compose up -d postgresql` → then `docker-compose up -d anomaly-detector`                             |
| API (local)              | `$env:MODELS_DIR="...\models"; python -m uvicorn main:app --host 0.0.0.0 --port 5000` from `deployment/app`                    |
| Health                   | `curl http://localhost:5000/health`                                                                                            |
| List models              | `curl http://localhost:5000/models`                                                                                            |
| Predict                  | `curl -X POST http://localhost:5000/predict -H "Content-Type: application/json" -d "{...}"`                                    |
| Reload models            | `curl -X POST http://localhost:5000/reload`                                                                                    |
| API docs                 | [http://localhost:5000/docs](http://localhost:5000/docs)                                                                       |
| Streamlit                | `streamlit run deployment/streamlit_app/app.py` → [http://localhost:8501](http://localhost:8501)                               |
| Prometheus               | [http://localhost:9090](http://localhost:9090) (Status → Targets)                                                              |
| Grafana                  | [http://localhost:3000](http://localhost:3000) (admin / admin); dashboard: **Anomaly Detection System - Real-Time Monitoring** |


---

# Troubleshooting

- **Docker: 500 Internal Server Error** when pulling any image (postgres, kafka, etc.)  
Docker Desktop’s daemon is failing. Try: (1) Restart Docker Desktop. (2) In Docker Desktop: Settings → Resources → ensure enough memory/disk. (3) Use **Path B** to run the API and Streamlit without Docker so you can still test APIs and Streamlit fully.
- `**status: degraded` or empty `models_loaded`**  
Ensure `models/<fund>/latest/model.keras` exists for each fund. Run `python export_models.py` or copy a versioned dir to `latest`, then `curl -X POST http://localhost:5000/reload`.
- **Connection refused to localhost:5000**  
Start the API first (Path A or B). On Windows, check that no firewall is blocking port 5000.
- **Streamlit “Check connection” fails**  
Confirm the API is up: `curl http://localhost:5000/health`. Use `http://localhost:5000` in Streamlit (not a Docker hostname).
- **POST /predict returns 400**  
Body must include `fund_name` and `transactions`; each transaction must include at least the fields required by the model (e.g. `clientid`, `transactiondate`, `inflows`, `outflows`, `balance`, `dailyincome`, `cumulativeincome`).
- **Docker: models not found**  
From `deployment/`, docker-compose mounts `../models` (project root). Ensure `models/model_registry.json` and `models/<fund>/latest/`* exist before starting the API container.
- **Grafana: no data or empty dashboard**  
Ensure the API and Prometheus are running. Send traffic to the API (curl or Streamlit), wait 1–2 minutes, refresh the dashboard. Check [http://localhost:9090/targets](http://localhost:9090/targets) — the API target must be UP. In Grafana, **Connections** → **Data sources** → **Prometheus** → **Save & test** must succeed.
- **API running on host, Prometheus in Docker**  
So that Prometheus can scrape the local API, set the scrape target to `host.docker.internal:5000` (Windows/Mac). In `deployment/monitoring/prometheus-config.yaml`, set `targets: ['host.docker.internal:5000']` for the anomaly-detector job (and ensure the job name matches the dashboard’s queries).
- **Kafka image pull error**  
For API and Streamlit testing you do not need Kafka. Use `docker-compose up -d postgresql anomaly-detector` only. If you need Kafka later, restart Docker Desktop and retry, or try another image (e.g. `bitnami/kafka:3`) in `docker-compose.yml`.


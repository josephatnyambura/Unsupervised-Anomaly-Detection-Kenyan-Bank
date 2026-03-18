# Streamlit demo UI for Anomaly Detection API

This app is the **production demo UI** for the anomaly detection API. It uses **only the best model and top features** deployed per fund: it fetches the model name and feature list from the API and shows **why** each transaction was (or wasn't) flagged.

## Prerequisites

- **Python 3.8+**
- **Anomaly detection API running** (e.g. Docker: from `deployment` run `docker-compose up -d` so that http://localhost:5000 is available)

## Install and run

From this folder (`deployment/streamlit_app`):

```bash
pip install -r requirements.txt
streamlit run app.py
```

From the **deployment** folder:

```bash
pip install -r streamlit_app/requirements.txt
streamlit run streamlit_app/app.py
```

Then open the URL shown in the terminal (default **http://localhost:8501**).

## Streamlit Community Cloud deployment

Use these settings in Streamlit Community Cloud:

- **Main file path**: `deployment/streamlit_app/app.py`
- **Requirements file**: `deployment/streamlit_app/requirements.txt` (auto-detected)
- **Python runtime**: from `deployment/streamlit_app/runtime.txt`

Set your API endpoint in app **Secrets**:

```toml
API_BASE_URL = "https://<your-fastapi-public-url>"
```

Important:
- Do **not** leave the API URL as `http://localhost:5000` on Cloud.
- The Streamlit app and FastAPI API must both be publicly reachable over HTTPS.
- After deployment, click **Check connection** in the sidebar. It should show `API healthy. Models loaded.`.

## Using the app

1. **Sidebar**
   - Set **API base URL** (default `http://localhost:5000`) and click **Check connection**.
   - The sidebar shows the **model name** and **feature list** for the selected fund (from **GET /models**). These are the best model and top features for that fund.
   - Choose **Fund** (Money Market Fund or Fixed Income Fund USD).

2. **Single transaction**  
   Set the **model features** (the same ones returned by the API for this fund). Click **Get anomaly score** to see risk tier, anomaly score, **features used**, and **explanation** (why the transaction was or wasn't flagged).

3. **Compare scenarios**  
   Click **Run all scenarios** to score Normal, High-value, and Zero-activity presets (using the best model's features) and compare scores and explanations.

4. **Batch (JSON)**  
   Paste a JSON array of transactions that include the model's **feature names** (plus `clientid`, `transactiondate`) and click **Run batch prediction**. Each prediction includes **features_used** and **explanation**.

5. **Explainability (SHAP/LIME)**  
   View **LIME-style** feature contributions (bar chart from the last prediction's features used) and **SHAP** plots. Optionally set the path to `ml/plots/explainability` (or your notebook output folder) to display SHAP summary, fusion score, and risk tier plots for the selected fund. These plots are produced by the notebook from the **best-performing model** per fund (e.g. Autoencoder).

6. **Why this result? / How it works**  
   Describes how the best model's features drive the score and that the app uses only the deployed model and its top features.

## API behaviour

- **GET /models** returns per fund: `fund_key`, `fund_name`, `model_name`, **`feature_names`** (the top features for that model), and performance info. The Streamlit app uses this to build the form and presets.
- **POST /predict** expects each transaction to include the model's feature names (e.g. `inflows`, `gross_activity`, `zero_activity_freq`, `rolling_mean_inflows`, `rolling_std_inflows`). The response includes per prediction: **`features_used`** (name and value for each feature) and **`explanation`** (short text explaining why the transaction was or wasn't flagged).

## If “Check connection” fails

- Ensure the API is running: `docker ps` and confirm **anomaly-detector** is Up.
- Ensure models are loaded: run `export_models.py` from the project root, then `curl -X POST http://localhost:5000/reload` (or use the API’s reload endpoint).

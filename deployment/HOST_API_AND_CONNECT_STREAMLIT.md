# Step-by-step: Host the API and connect your Streamlit app

This guide has two parts: **Part A** hosts your FastAPI anomaly-detection API on the internet. **Part B** points your Streamlit Cloud app at that API so "Check connection" and predictions work for everyone using your share link.

**Quick overview:**

| Part | What you do |
|------|-------------|
| **A** | Sign up at Render → New Web Service → connect repo → set Build + Start commands → deploy → copy API URL (e.g. `https://anomaly-detection-api.onrender.com`). |
| **B** | In Streamlit Cloud → your app → Settings → Secrets → add `API_BASE_URL = "https://your-api.onrender.com"` → save. No code change. |
| **Done** | Open your Streamlit share link; sidebar shows the API URL; "Check connection" and predictions use the hosted API. |

---

## Prerequisites

- **Your repo:** [github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank](https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank)
- Streamlit app is already deployed on Streamlit Community Cloud (share link works).
- **Models in the repo:** The API needs `models/model_registry.json` and, for each fund, `models/<fund>/latest/model.keras` (or `model.joblib`) and `models/<fund>/latest/scaler.joblib`. If these are in `.gitignore`, the hosted API will start in "degraded" mode (no models). Either push the model files (if under GitHub’s 100 MB limit) or remove the `*.keras` / `*.joblib` ignore for the `models/` folder so they are in the repo.

---

# Part A: Host the API (Render.com free tier)

We use **Render** as a free host. The API will get a URL like `https://your-api-name.onrender.com`. Free services spin down after ~15 minutes of no traffic; the first request after that may take 30–60 seconds to wake up.

---

## A.1 Create a Render account and connect GitHub

1. Go to [render.com](https://render.com) and sign up (e.g. with GitHub).
2. In the dashboard, click **Connect account** / **Link GitHub** and authorize Render for your GitHub user or org.
3. Ensure Render can see the repo **Unsupervised-Anomaly-Detection-Kenyan-Bank** ([link](https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank)).

**Important:** Before or right after creating the Web Service, set **Environment** → **`PYTHON_VERSION`** = **`3.11.11`** so the build uses Python 3.11 and avoids pandas/numpy build errors (see A.5 and Troubleshooting).

---

## A.2 Create a new Web Service

1. On Render, click **New +** → **Web Service**.
2. **Connect a repository:** select **Unsupervised-Anomaly-Detection-Kenyan-Bank** (https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank). If it’s not listed, click **Configure account** and add the repo.
3. Use these settings:

   | Field | Value |
   |--------|--------|
   | **Name** | `anomaly-detection-api` (or any name; it becomes `https://<name>.onrender.com`) |
   | **Region** | Choose one close to you (e.g. Oregon). |
   | **Branch** | `main` |
   | **Runtime** | `Python 3` |
   | **Build Command** | See A.3 below. |
   | **Start Command** | See A.4 below. |

---

## A.3 Build command

The API needs both `fastapi_app` and `deployment.app` (and TensorFlow for .keras models). Use:

```bash
pip install -r deployment/app/requirements.txt && pip install -r fastapi_app/requirements.txt
```

This installs FastAPI, Uvicorn, TensorFlow, scikit-learn, joblib, pandas, etc. If the build fails on a missing module, add that package to `deployment/app/requirements.txt` or run `pip install <package>` in the build command.

---

## A.4 Start command

Use the **repo root** script `run_api.py` (it reads `PORT` from the environment, which Render sets):

```bash
python run_api.py
```

If you prefer not to use `run_api.py`, set **Start Command** to:

```bash
uvicorn fastapi_app.main:app --host 0.0.0.0 --port $PORT
```

(Render sets `$PORT`; if it doesn’t expand, use `python run_api.py`.)

---

## A.5 Environment variables (required and optional)

**Required (avoids build failure):** Render may use a very new Python (e.g. 3.14), which can cause `pandas`/`numpy` to build from source and fail (`_PyLong_AsByteArray` errors). Set a compatible Python version.

In the Render Web Service → **Environment** tab, add:

| Key | Value | Why |
|-----|--------|-----|
| **`PYTHON_VERSION`** | **`3.11.11`** | **Required.** Uses Python 3.11 so `pandas` and `numpy` install from pre-built wheels. Prevents "too few arguments to function '_PyLong_AsByteArray'" and "metadata-generation-failed" errors. |
| `PYTHONPATH` | `.` | So `fastapi_app` and `deployment` can be imported when running from repo root. |
| `MODELS_DIR` | `./models` | Optional; default is repo `models/` (ensure `models/` is in the repo if you want models loaded). |

**If you use the repo's `render.yaml` (Blueprint):** It already sets `PYTHON_VERSION=3.11.11`. If you created the service manually in the dashboard, you **must** add `PYTHON_VERSION` = `3.11.11` in Environment yourself.

---

## A.6 Deploy and get the API URL

1. Click **Create Web Service**. Render will clone the repo, run the build command, then the start command.
2. Wait for the first deploy to finish (logs will show “Listening on 0.0.0.0:XXXX”).
3. Copy the **service URL**, e.g. `https://anomaly-detection-api.onrender.com`. This is your **API base URL** (no trailing slash).

**Check the API:**

- Open `https://<your-api-url>.onrender.com/health` in a browser. You should see JSON with `"status": "healthy"` (or `"degraded"` if models did not load).
- Open `https://<your-api-url>.onrender.com/docs` for the Swagger UI.

If the service is sleeping, the first request may take 30–60 seconds; then it responds normally.

---

# Part B: Point Streamlit app at the hosted API

Your Streamlit app already reads the API URL from the **`API_BASE_URL`** environment variable and uses it as the default in the sidebar. On Streamlit Community Cloud you set this in **Secrets**.

---

## B.1 Open your app on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in.
2. Open the app that uses `deployment/streamlit_app/app.py` (e.g. **Unsupervised-Anomaly-Detection-Kenyan-Bank**).

---

## B.2 Add the API URL as a secret

1. Click the app name → **Settings** (or **Manage app** → **Settings**).
2. Open the **Secrets** tab (or **Streamlit secrets**).
3. In the text box (TOML format), add:

   ```toml
   API_BASE_URL = "https://anomaly-detection-api.onrender.com"
   ```

   Replace `https://anomaly-detection-api.onrender.com` with your **actual** Render API URL from A.6 (no trailing slash).

4. Save. Streamlit will redeploy the app so the new secret is applied.

---

## B.3 Confirm the app uses the secret

- Your app code already has:
  - `DEFAULT_API_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")`
  - Sidebar: `api_url = st.text_input("API base URL", value=DEFAULT_API_URL)`
- So when `API_BASE_URL` is set in Secrets, the sidebar will show the hosted URL by default and all requests (health check, `/models`, `/predict`) will go to that host.

No code change is required; only the secret needs to be set.

---

## B.4 Test the connection

1. Open your **Streamlit share link** (e.g. `https://xxx.streamlit.app`).
2. In the sidebar, you should see **API base URL** = `https://anomaly-detection-api.onrender.com` (or your URL).
3. Click **Check connection**. You should get a success message and, if models are loaded, the list of models.
4. Try **Get anomaly score** or **Run all scenarios**; they should call the hosted API.

If the API was sleeping, the first “Check connection” may take 30–60 seconds; after that it should be fast until the next sleep.

---

# Summary

| Step | What you did |
|------|----------------|
| **A** | Hosted the FastAPI app on Render; got a URL like `https://anomaly-detection-api.onrender.com`. |
| **B** | Set Streamlit secret `API_BASE_URL` to that URL so the Streamlit app uses the hosted API by default. |
| **Result** | Anyone opening your Streamlit share link gets a working “Check connection” and can run predictions against your hosted API. |

---

# Troubleshooting

| Issue | What to do |
|-------|------------|
| **Deploy fails: `can't open file 'run_api.py'` (No such file or directory)** | Render is running the start command from a folder that doesn’t contain `run_api.py`. **Fix:** Dashboard → your service → **Settings** → set **Root Directory** to **blank** (repo root). Save and redeploy. Or use the inline start command in `render.yaml` so the app starts without `run_api.py`. |
| **Build fails: `_PyLong_AsByteArray` / pandas “metadata-generation-failed”** | Render is using a Python (e.g. 3.14) with no pre-built pandas/numpy wheels. **Fix:** Dashboard → your service → **Environment** → add **`PYTHON_VERSION`** = **`3.11.11`** → Save → **Manual Deploy** (or push `render.yaml` and redeploy). |
| Render build fails (e.g. `ModuleNotFoundError: deployment.app`) | Ensure **Root Directory** is blank (build from repo root) and **Start Command** runs from repo root; set **Environment** `PYTHONPATH=.` if needed. |
| Render starts but `/health` returns "degraded" | Models are not loading. Ensure `models/model_registry.json` and each fund’s `models/<fund>/latest/model.keras` (or `.joblib`) and `scaler.joblib` are in the repo (not ignored by `.gitignore`). |
| Streamlit still shows localhost | Confirm Secrets contain `API_BASE_URL = "https://..."` and save; wait for redeploy, then hard-refresh the Streamlit app. |
| "Check connection" times out | Render free tier may be sleeping; try again after 30–60 seconds. For always-on response, use a paid plan or another host. |

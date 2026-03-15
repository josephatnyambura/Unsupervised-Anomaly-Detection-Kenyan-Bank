# Commit and test the whole Render flow

This guide takes you from **committing your Render fixes** through **pushing to GitHub**, **deploying on Render**, and **testing the live API**. Do the steps in order.

**Repo:** [Unsupervised-Anomaly-Detection-Kenyan-Bank](https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank)

---

## Part 1: Commit and push

### Step 1: Open a terminal in the project root

- **Command Prompt:** Win + R → type `cmd` → Enter.  
- **PowerShell:** Right‑click project folder → “Open in Terminal” or open from VS Code/Cursor.

Go to the project root (copy one line, paste, Enter):

**Command Prompt:**
```cmd
cd /d "c:\Users\A257985\OneDrive - Standard Bank\Academics\Notes\Year 1\sem 2\8201 Research Methods for Data Science and Analytics\Project\Python Scripts\Version 2.0 - Cursor"
```

**PowerShell:**
```powershell
cd "c:\Users\A257985\OneDrive - Standard Bank\Academics\Notes\Year 1\sem 2\8201 Research Methods for Data Science and Analytics\Project\Python Scripts\Version 2.0 - Cursor"
```

---

### Step 2: See what changed

```cmd
git status
```

You should see at least:

- `render.yaml` (modified)
- `deployment/HOST_API_AND_CONNECT_STREAMLIT.md` (modified)

If you also changed other files and want to push them, that’s fine — they’ll be included in the next add/commit.

---

### Step 3: Stage and commit

```cmd
git add render.yaml deployment/HOST_API_AND_CONNECT_STREAMLIT.md
```

To stage **everything** that’s changed (respecting `.gitignore`):

```cmd
git add .
```

Then commit:

```cmd
git commit -m "Fix Render deploy: inline start command, Root Directory note, troubleshooting"
```

- If Git says **"Please tell me who you are"**, run once (use your name and email):

```cmd
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Then run the `git commit` command again.

---

### Step 4: Push to GitHub

If you **already added** the GitHub remote earlier:

```cmd
git push origin main
```

If this is the **first push** for this repo (no remote yet):

```cmd
git remote add origin https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank.git
git branch -M main
git push -u origin main
```

- When asked for credentials, use your **GitHub username** and a **Personal Access Token** (not your GitHub password). Create one: GitHub → Settings → Developer settings → Personal access tokens → Generate (scope: `repo`).
- If you get **"updates were rejected"**: run `git pull origin main --rebase`, then `git push origin main` again.

---

### Step 5: Confirm on GitHub

1. Open: **https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank**
2. Check that the latest commit is there and that **`render.yaml`** at the repo root shows the new `startCommand` (the long `python -c "import os; import uvicorn; ..."` line).

---

## Part 2: Render deploy

### Step 6: Fix Root Directory on Render (if you haven’t already)

1. Go to [dashboard.render.com](https://dashboard.render.com) and sign in.
2. Open your **anomaly-detection-api** (or whatever you named the API) service.
3. Go to **Settings** (left sidebar).
4. Find **Root Directory**.
5. Set it to **blank** (empty). That makes Render use the **repo root**, where `run_api.py` and `fastapi_app` live.
6. Click **Save Changes**.

---

### Step 7: Deploy

- **If Render is connected to GitHub:** A new deploy usually starts automatically after your push. Go to the service → **Events** or **Logs** to watch it.
- **If it didn’t start:** Click **Manual Deploy** → **Deploy latest commit**.

Wait for the build and start to finish (often 2–5 minutes). The log should show:

- Build: `pip install -r deployment/app/requirements.txt && pip install -r fastapi_app/requirements.txt`
- Start: the inline `python -c "import os; import uvicorn; ..."` command (no `run_api.py` needed).

If the deploy **fails**, check the **Logs** tab. For “can’t open file run_api.py”, ensure Root Directory is blank (Step 6) and that you pushed the updated `render.yaml`.

---

### Step 8: Copy your API URL

At the top of the service page you’ll see something like:

**https://anomaly-detection-api.onrender.com**

Copy that URL (no trailing slash). You’ll use it for testing and for Streamlit.

---

## Part 3: Test the Render API

Free-tier services **spin down** after ~15 minutes of no traffic. The first request after that can take **30–60 seconds**. If a request times out, wait a bit and try again.

### Step 9: Health check (browser)

Open in your browser (replace with your URL if different):

**https://anomaly-detection-api.onrender.com/health**

You should see JSON, for example:

```json
{"status":"healthy","models_loaded":["money_market_fund", ...]}
```

or, if models didn’t load (e.g. not in repo or too large):

```json
{"status":"degraded","models_loaded":[]}
```

- **`healthy`** = API is up and models are loaded; you can run predictions.
- **`degraded`** = API is up but no models; add model files to the repo or see [HOST_API_AND_CONNECT_STREAMLIT.md](HOST_API_AND_CONNECT_STREAMLIT.md) Troubleshooting.

---

### Step 10: API docs (browser)

Open:

**https://anomaly-detection-api.onrender.com/docs**

You should see **Swagger UI** with endpoints like **GET /health**, **GET /models**, **POST /predict**. You can try **GET /health** and **GET /models** from the page.

---

### Step 11: Optional — test from the command line

**Health:**

```cmd
curl https://anomaly-detection-api.onrender.com/health
```

**List models:**

```cmd
curl https://anomaly-detection-api.onrender.com/models
```

**Predict** (example; replace the URL if yours is different):

```cmd
curl -X POST https://anomaly-detection-api.onrender.com/predict -H "Content-Type: application/json" -d "{\"fund_name\": \"Money Market Fund\", \"transactions\": [{\"clientid\": \"TEST001\", \"transactiondate\": \"2024-07-15\", \"inflows\": 5000, \"outflows\": 100, \"balance\": 10000, \"dailyincome\": 50, \"cumulativeincome\": 500}]}"
```

On **PowerShell**, use backticks to escape the inner quotes or put the JSON in a file and use `curl ... -d "@body.json"`.

If these return JSON (and `/predict` returns scores/result), the Render API is working end‑to‑end.

---

## Part 4: Optional — Connect Streamlit and test

### Step 12: Set Streamlit secret

1. Go to [share.streamlit.io](https://share.streamlit.io) and open your app.
2. **Settings** → **Secrets**.
3. Add (use your real Render URL, no trailing slash):

```toml
API_BASE_URL = "https://anomaly-detection-api.onrender.com"
```

4. Save. Streamlit will redeploy.

### Step 13: Test in the app

1. Open your Streamlit app’s share link.
2. In the sidebar, confirm **API base URL** shows your Render URL.
3. Click **Check connection**. It should say the API is healthy (and show loaded models if applicable).
4. Run a prediction (fund + sample transactions). It should use the Render API.

---

## Quick reference

| What | Where |
|------|--------|
| Commit & push | Part 1 (Steps 1–5) |
| Render Root Directory | Part 2, Step 6 |
| Deploy on Render | Part 2, Steps 7–8 |
| Test API: health & docs | Part 3, Steps 9–10 |
| Test API: curl | Part 3, Step 11 |
| Streamlit → Render | Part 4, Steps 12–13 |

---

## If something goes wrong

| Problem | What to do |
|--------|------------|
| **"can't open file run_api.py"** on Render | Set **Root Directory** to blank (Step 6). Ensure you pushed the updated `render.yaml` with the inline `startCommand`. |
| **Build fails** (e.g. pandas/numpy) | In Render → **Environment**, set **PYTHON_VERSION** = **3.11.11**, save, redeploy. |
| **/health** returns **degraded** | Models aren’t in the repo or are ignored. See [HOST_API_AND_CONNECT_STREAMLIT.md](HOST_API_AND_CONNECT_STREAMLIT.md) Troubleshooting. |
| **Request timeout** | Free tier may be sleeping. Wait 30–60 seconds and try again. |
| **Git push rejected** | Run `git pull origin main --rebase`, then `git push origin main`. |
| **Git "tell me who you are"** | Run the `git config --global user.name` and `user.email` commands in Step 3, then commit again. |

For more detail on hosting the API and connecting Streamlit, see **[HOST_API_AND_CONNECT_STREAMLIT.md](HOST_API_AND_CONNECT_STREAMLIT.md)**.

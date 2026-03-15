# Deploy the Streamlit app to Streamlit Community Cloud (share link)

This guide walks you through pushing your app to **GitHub** and deploying it on **Streamlit Community Cloud** so anyone with your share link can use the UI.

---

## Prerequisites

- **GitHub account** (you have this)
- **Streamlit Community Cloud account** (share.streamlit.io — you have this)
- Your project folder with `deployment/streamlit_app/app.py` and `deployment/streamlit_app/requirements.txt`

---

## Step 1: Prepare the repository for GitHub

### 1.1 Create a `.gitignore` (if you don’t have one)

In the **root** of your project (same level as `deployment`, `article`, `ml`, etc.), create a file named `.gitignore` so large or sensitive files are not pushed:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
venv/
.env
.env.local

# Data and models (optional: exclude if too large for GitHub)
# ml/artifacts/
# models/*.pkl
# *.csv

# IDE and OS
.idea/
.vscode/
.DS_Store
Thumbs.db

# Jupyter
.ipynb_checkpoints/

# Logs and temp
*.log
*.tmp
```

Adjust the commented lines if you want to exclude model files or large data (GitHub has a ~100 MB file limit and repo size recommendations).

### 1.2 Ensure the Streamlit app and requirements are in place

You need at least:

- `deployment/streamlit_app/app.py` — main Streamlit app
- `deployment/streamlit_app/requirements.txt` — dependencies (streamlit, requests, pandas, numpy, plotly)

These are already in your project.

---

## Step 2: Push the project to GitHub

### 2.1 Create a new repository on GitHub

1. Go to [github.com](https://github.com) and sign in.
2. Click **“+”** → **“New repository”**.
3. Set:
   - **Repository name:** e.g. `anomaly-detection-kenyan-bank` (or any name you like).
   - **Visibility:** Public (required for free Streamlit Community Cloud).
   - Do **not** add a README, .gitignore, or license yet if your project already has content.
4. Click **“Create repository”**.

### 2.2 Push your local project to GitHub

Open a terminal in your **project root** (the folder that contains `deployment`, `article`, `ml`, etc.):

```powershell
# Go to project root
cd "c:\Users\A257985\OneDrive - Standard Bank\Academics\Notes\Year 1\sem 2\8201 Research Methods for Data Science and Analytics\Project\Python Scripts\Version 2.0 - Cursor"

# Initialize Git (only if this folder is not already a git repo)
git init

# Add all files (respects .gitignore)
git add .

# First commit
git commit -m "Add anomaly detection Streamlit app and deployment"

# Add GitHub as remote (replace YOUR_USERNAME and YOUR_REPO with your GitHub username and repo name)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Push (main branch; use master if your default branch is master)
git branch -M main
git push -u origin main
```

If the folder is already a Git repo, skip `git init`. Use:

```powershell
git add .
git commit -m "Add Streamlit app for share deployment"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual GitHub username and repository name.

---

## Step 3: Deploy on Streamlit Community Cloud

### 3.1 Open Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io).
2. Sign in with your Streamlit account (or GitHub).

### 3.2 Deploy the app

1. Click **“New app”**.
2. **Connect GitHub** if prompted (authorize Streamlit to see your repositories).
3. Fill in:
   - **Repository:** `YOUR_USERNAME/YOUR_REPO` (e.g. `jnyambura/anomaly-detection-kenyan-bank`).
   - **Branch:** `main` (or the branch you pushed).
   - **Main file path:**  
     `deployment/streamlit_app/app.py`  
     This is the path **from the repo root** to your Streamlit script.
   - **App URL:** optional; you can leave the default, e.g. `anomaly-detection-kenyan-bank` (Streamlit will give you a URL like `https://anomaly-detection-kenyan-bank-xxxxx.streamlit.app`).

4. Click **“Advanced settings”** and set:
   - **Python version:** 3.10 or 3.11 (recommended).
   - **Requirements file (optional):**  
     `deployment/streamlit_app/requirements.txt`  
     So Streamlit installs from this file instead of the repo root.

5. Click **“Deploy!”**.

### 3.3 Wait for the first build

- The first build can take a few minutes (installing dependencies and starting the app).
- If the build fails, open the **logs** in the Streamlit Cloud dashboard and fix any missing dependencies or path errors.

---

## Step 4: Make the app work seamlessly for visitors

### 4.1 App without a backend API (UI only)

- The app will load and show the **sidebar** (Fund, API base URL, “Check connection”, etc.).
- **“Check connection”** will fail unless the API is reachable (see below).
- Visitors can still:
  - Change the fund, read the UI, and use presets/scenarios if you add a “demo mode” that doesn’t call the API, or
  - Use the app in read-only / explanation mode if you later add mock responses.

So the **share link is usable immediately** for showing the UI; for **live predictions**, the API must be reachable.

### 4.2 Optional: Connect the app to a public API

If you later host your **FastAPI** backend somewhere public (e.g. Railway, Render, Fly.io, or a server with a public URL):

1. In the Streamlit Cloud dashboard, open your app → **“Settings”** or **“Manage app”** → **“Secrets”** (or **“Environment variables”**).
2. Add a secret / env var:
   - **Key:** `API_BASE_URL`
   - **Value:** `https://your-public-api-url.com` (no trailing slash).
3. Redeploy or save; the app reads `API_BASE_URL` and uses it as the default in the sidebar, so “Check connection” and predictions will use that URL.

Visitors can still override the API URL in the sidebar if you keep the text input.

### 4.3 Share the link

- In the Streamlit Cloud dashboard, copy the **app URL** (e.g. `https://anomaly-detection-kenyan-bank-xxxxx.streamlit.app`).
- Share this link in your profile or with anyone who should use the app; they open it in a browser and use the UI without installing anything.

---

## Step 5: Updating the app after changes

Whenever you change the app or dependencies:

```powershell
cd "c:\Users\A257985\OneDrive - Standard Bank\Academics\Notes\Year 1\sem 2\8201 Research Methods for Data Science and Analytics\Project\Python Scripts\Version 2.0 - Cursor"

git add .
git commit -m "Update Streamlit app / dependencies"
git push origin main
```

Streamlit Community Cloud will detect the push and **redeploy automatically** (or you can trigger a redeploy from the dashboard). The same share link will show the updated app.

---

## Quick reference

| Item | Value |
|------|--------|
| **Main file path** | `deployment/streamlit_app/app.py` |
| **Requirements path** | `deployment/streamlit_app/requirements.txt` |
| **Optional env var (public API)** | `API_BASE_URL` = your FastAPI base URL |
| **Share link** | From Streamlit Cloud dashboard after deploy |

---

## Troubleshooting

- **Build fails / ModuleNotFoundError:**  
  Ensure `deployment/streamlit_app/requirements.txt` contains all imports used in `app.py` (streamlit, requests, pandas, numpy, plotly). The guide already includes numpy.

- **“Cannot connect to API” in the app:**  
  Expected if no public API is set. Either host the FastAPI backend and set `API_BASE_URL` in Streamlit secrets, or use the share link as a UI-only demo.

- **Wrong branch or file path:**  
  In Streamlit Cloud → app → Settings, set **Branch** and **Main file path** to `deployment/streamlit_app/app.py` (and requirements path to `deployment/streamlit_app/requirements.txt`).

- **Repo private:**  
  Streamlit Community Cloud requires a **public** repo for free tier. Make the repo public or use a different hosting option.

Once deployed, your Streamlit share link can be used from your profile so others can interact with the app seamlessly.

# Step-by-step: Full FastAPI deployment on Vercel (with GitHub push first)

This guide reflects the current project setup for Vercel:

- `vercel.json` at repo root
- `.vercelignore` at repo root
- `fastapi_app/main.py`
- `fastapi_app/requirements.txt`
- `fastapi_app/.python-version`
- model artifacts in `models/*/latest` and `models/*/v_*` (fallback)

It addresses both `AL_NOT_FOUND / NOT_FOUND` and `FUNCTION_INVOCATION_FAILED`.

---

## 1) Push latest changes to GitHub first

From project root:

```cmd
cd /d "c:\Users\A257985\OneDrive - Standard Bank\Academics\Notes\Year 1\sem 2\8201 Research Methods for Data Science and Analytics\Project\Python Scripts\Version 2.0 - Cursor"
```

Check changes:

```cmd
git status
```

Stage Vercel API files:

```cmd
git add vercel.json .vercelignore fastapi_app\main.py fastapi_app\requirements.txt fastapi_app\.python-version fastapi_app\model_loader.py fastapi_app\anomaly_detector.py deployment\DEPLOY_FASTAPI_ON_VERCEL.md
```

Commit:

```cmd
git commit -m "Configure full FastAPI deployment on Vercel"
```

Push:

```cmd
git push origin main
```

If push fails, follow `deployment/GIT_PUSH_STEPS.md`.

---

## 2) Confirm routing config

Root `vercel.json` should route all requests to `fastapi_app/main.py`:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "fastapi_app/main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "fastapi_app/main.py"
    }
  ]
}
```

---

## 3) Create or update Vercel project

1. Go to [vercel.com](https://vercel.com) -> **Add New...** -> **Project**.
2. Import your GitHub repo.
3. In project settings, use:
   - **Framework Preset**: `Other`
   - **Root Directory**: leave empty (repo root)
4. Redeploy after every GitHub push.

Why root repo? You need both `fastapi_app` and `models` in deployment.

---

## 4) Python and dependency behavior

Your logs showed Python defaulting to 3.12. The project now includes:

- `fastapi_app/.python-version` = `3.11`

Keep this committed to reduce runtime incompatibility risk.

Your logs also showed bundle size exceeded and runtime dependency installation was enabled. This can still happen with ML dependencies, but the updated setup reduces failure risk by:

- using a lighter FastAPI backend path in `fastapi_app`
- excluding non-essential folders via `.vercelignore`

---

## 5) Deploy and test endpoints

After deploy, test:

- `https://<your-vercel-domain>/health`
- `https://<your-vercel-domain>/docs`
- `https://<your-vercel-domain>/models`

Then test prediction from Swagger:

- `POST /predict`

Use a small payload first (1 transaction).

---

## 6) Fix `AL_NOT_FOUND` / `NOT_FOUND`

If deployment is "Ready" but page is not found:

1. Confirm root `vercel.json` exists in GitHub main branch.
2. Confirm Vercel project Root Directory is blank (repo root).
3. Redeploy with **Clear Build Cache**.
4. Open `.../health` directly, not only the base page.

---

## 7) Fix `FUNCTION_INVOCATION_FAILED` (500)

If function crashes after deploy:

1. Open Vercel -> Deployment -> **Functions** -> logs.
2. Check for:
   - import errors
   - missing model files
   - memory/timeouts
3. Verify these files are present in repo:
   - `models/model_registry.json`
   - `models/money_market_fund/latest/*`
   - `models/fixed_income_fund__usd_/latest/*`
   - at least one fallback `model.joblib` in:
     - `models/money_market_fund/v_*/model.joblib`
     - `models/fixed_income_fund__usd_/v_*/model.joblib`
4. Redeploy with cache cleared.
5. Start with lightweight endpoint test:
   - `/health` and `/models` first
   - then `/predict` with 1 row

---

## 8) Connect Streamlit to Vercel API

In Streamlit Community Cloud secrets:

```toml
API_BASE_URL = "https://<your-vercel-domain>"
```

Save secrets, let Streamlit redeploy, then click **Check connection** in the app sidebar.

---

## 9) Practical limits and best practice

Vercel can run this API, but serverless limits may still affect heavy ML inference workloads (cold starts, memory/time limits, dependency install at runtime).

For stability on Vercel:

- keep prediction payloads small
- keep model artifacts available for loader fallback (`latest` and at least one `v_*` with `model.joblib`)
- avoid adding heavy unrelated files to deployment

---

## 10) Quick checklist

- [ ] `git push origin main` succeeded
- [ ] root `vercel.json` present in GitHub
- [ ] root `.vercelignore` present in GitHub
- [ ] Root Directory on Vercel is blank (repo root)
- [ ] `/health` works
- [ ] `/models` returns model list
- [ ] `/predict` works with small payload
- [ ] Streamlit `API_BASE_URL` points to Vercel API


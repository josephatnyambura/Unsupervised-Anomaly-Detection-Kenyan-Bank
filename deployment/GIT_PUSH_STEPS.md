# Step-by-step: Push to GitHub using Command Prompt (no errors)

Use **Command Prompt** (cmd), not PowerShell. Run each step in order. Replace `YOUR_USERNAME` and `YOUR_REPO` with your real GitHub username and repository name.

---

## What the .gitignore does (from project scan)

| Include (ignored — not pushed) | Why |
|-------------------------------|-----|
| `__pycache__/`, `*.pyc` | Python bytecode; regenerated |
| `venv/`, `.venv/`, `.env` | Virtual env and secrets; never push |
| `.ipynb_checkpoints/` | Jupyter temp; not needed in repo |
| `*.log`, `*.aux`, `*.nav`, `*.out`, `*.toc` | LaTeX build files in `article/` and Proposal; keep only `.tex` |
| `*.backup.ipynb` | Backup notebooks |
| `.idea/`, `.vscode/`, `.DS_Store`, `Thumbs.db` | IDE and OS junk |

| Keep (pushed) | Why |
|---------------|-----|
| `deployment/streamlit_app/app.py`, `requirements.txt` | Required for Streamlit Share |
| `models/model_registry.json`, `models/*/latest/*.json` | Small config; API uses these |
| `*.tex` (source only) | Your thesis/beamer source |
| `ml/plots/`, `eda/plots/` (PNG) | Needed if Beamer or app references them |
| `*.keras`, `*.joblib` | Currently **not** ignored; push if &lt; 100 MB each. If push fails (file too large), add `*.keras` and `*.joblib` to `.gitignore` and push again. |

---

## Step 1: Open Command Prompt

1. Press **Win + R**, type **cmd**, press Enter.  
   Or: Start menu → type **cmd** → click **Command Prompt**.

---

## Step 2: Go to your project root

Copy and paste this **exactly** (one line), then press Enter:

```cmd
cd /d "c:\Users\A257985\OneDrive - Standard Bank\Academics\Notes\Year 1\sem 2\8201 Research Methods for Data Science and Analytics\Project\Python Scripts\Version 2.0 - Cursor"
```

- `cd /d` changes drive and folder. The quotes are required because of spaces in the path.
- You should see the path in the prompt. If you get "The system cannot find the path specified", check the path (especially OneDrive and folder names).

---

## Step 3: Check if Git is installed

```cmd
git --version
```

- If you see something like `git version 2.x.x`, continue.  
- If you see "git is not recognized", install Git: https://git-scm.com/download/win — then close and reopen Command Prompt and run Step 2 again.

---

## Step 4: Initialize Git (only if this folder is not already a repo)

```cmd
git init
```

- If it says "Reinitialized existing Git repository", that’s fine — the folder was already a repo.  
- If it says "Initialized empty Git repository", that’s fine too.

---

## Step 5: Add the .gitignore and all files

```cmd
git add .gitignore
```

```cmd
git add .
```

- The first command adds the `.gitignore` so it’s used from the start.  
- The second adds everything else; Git will skip files and folders listed in `.gitignore`.

---

## Step 6: Check what will be committed (optional)

```cmd
git status
```

- You should see a list of "new file" / "modified" entries.  
- You should **not** see `__pycache__`, `.env`, `venv`, or `*.log` in the list (they’re ignored).  
- If you see a very large file (e.g. a single file &gt; 100 MB), add that pattern to `.gitignore`, then run again:  
  `git add .gitignore`  
  `git add .`  
  `git status`

---

## Step 7: First commit

```cmd
git commit -m "Add anomaly detection project and Streamlit app"
```

- If you get "nothing to commit, working tree clean", run `git status` again; you might have already committed. You can still add a remote and push.  
- If you get "Please tell me who you are", run these once (use your name and email):

```cmd
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Then run the `git commit` command again.

---

## Step 8: Create the repo on GitHub

1. Go to https://github.com and sign in.  
2. Click **+** (top right) → **New repository**.  
3. **Repository name:** e.g. `anomaly-detection-kenyan-bank`.  
4. **Public**.  
5. Do **not** tick "Add a README" or "Add .gitignore".  
6. Click **Create repository**.

---

## Step 9: Add GitHub as remote and push

**Your repository:** [github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank](https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank)

```cmd
git remote add origin https://github.com/josephatnyambura/Unsupervised-Anomaly-Detection-Kenyan-Bank.git
```

```cmd
git branch -M main
```

```cmd
git push -u origin main
```

- If Git asks for credentials, use your GitHub username and a **Personal Access Token** (not your GitHub password). To create one: GitHub → Settings → Developer settings → Personal access tokens → Generate new token; give it `repo` scope.  
- If you see "failed to push some refs" and "updates were rejected", someone else may have pushed first. Run:  
  `git pull origin main --rebase`  
  then  
  `git push -u origin main`  
  again.

---

## Step 10: Verify on GitHub

- Open `https://github.com/YOUR_USERNAME/YOUR_REPO` in your browser.  
- You should see your files, including `deployment/streamlit_app/app.py` and `.gitignore`.  
- You should **not** see `__pycache__`, `venv`, or `article/*.log` in the file list.

---

## If the Proposal folder or Excel files still appear in `git status`

If you added them to Git before updating `.gitignore`, Git will keep tracking them until you remove them from the index (your files stay on disk; only Git’s tracking is cleared). Run:

```cmd
git rm -r --cached "Unit Trust Anomaly Detection ML Model - Proposal/"
```

Then:

```cmd
git add .gitignore
git add .
git status
```

You should no longer see any files under `Unit Trust Anomaly Detection ML Model - Proposal/`. Then commit as usual.

---

## If "Filename too long" for eda/eda_plots/ or add still fails

Remove the long-path folder from Git’s index, then re-add (files stay on disk):

```cmd
git rm -r --cached eda/eda_plots/
```

Then:

```cmd
git add .gitignore
git add .
```

If you still see an error, run the `git rm` line above first, then `git add .gitignore` and `git add .` again.

---

## If article/ or presentation/ still appear (after adding them to .gitignore)

If those folders were already tracked, remove them from the index (files stay on disk):

```cmd
git rm -r --cached article/
git rm -r --cached presentation/
```

Then:

```cmd
git add .gitignore
git add .
git status
```

---

## If something goes wrong

| Problem | What to do |
|--------|------------|
| "path specified" not found | Check the path in Step 2; ensure quotes and backslashes are correct. |
| "git is not recognized" | Install Git, close and reopen cmd, run Step 2 again. |
| "Please tell me who you are" | Run the two `git config --global` lines in Step 7, then commit again. |
| "remote origin already exists" | Run: `git remote remove origin` then run Step 9 again. |
| "File size exceeds 100MB" | Add that file type to `.gitignore` (e.g. `*.keras` and `*.joblib`), run `git add .gitignore` and `git add .`, then `git commit -m "Update gitignore"` and `git push -u origin main`. |
| "Authentication failed" | Use a Personal Access Token instead of password when Git asks for credentials. |

---

## Next: Deploy on Streamlit Share

After the push works, follow **deployment/STREAMLIT_SHARE_DEPLOY.md** from Step 3 (Deploy on Streamlit Community Cloud). Use:

- **Main file path:** `deployment/streamlit_app/app.py`  
- **Requirements path:** `deployment/streamlit_app/requirements.txt`

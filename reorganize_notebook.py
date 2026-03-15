# Reorganize notebook into sections, smaller chunks, and markdown explanations.
# Run from the notebook directory: python reorganize_notebook.py

import json
import copy
from pathlib import Path

NOTEBOOK_PATH = Path(__file__).resolve().parent / "Josephat Nyambura - 181247.ipynb"
BACKUP_PATH = Path(__file__).resolve().parent / "Josephat Nyambura - 181247.backup.ipynb"

def md_cell(text):
    return {"cell_type": "markdown", "metadata": {}, "source": [t if t.endswith("\n") else t + "\n" for t in text.strip().split("\n")]}

def code_cell(source_lines):
    # source_lines: list of strings (with or without trailing \n)
    out = []
    for i, line in enumerate(source_lines):
        if isinstance(line, str) and not line.endswith("\n"):
            line = line + "\n"
        out.append(line)
    if out and out[-1].endswith("\n\n"):
        out[-1] = out[-1].rstrip("\n") + "\n"
    return {"cell_type": "code", "metadata": {}, "source": out, "outputs": [], "execution_count": None}

def main():
    with open(NOTEBOOK_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)
    Path(BACKUP_PATH).write_text(json.dumps(nb, indent=2), encoding="utf-8")
    print("Backup saved to", BACKUP_PATH)

    cells = nb["cells"]
    new_cells = []

    # --- Title (keep 0, 1, 2) ---
    new_cells.append(cells[0])
    new_cells.append(cells[1])
    new_cells.append(cells[2])

    # --- TOC ---
    new_cells.append(md_cell("""---
## Table of Contents
1. **Environment & Imports** – Reproducibility, libraries, SHAP
2. **Data Loading** – Parquet I/O, inspect, split by fund
3. **Exploratory Data Analysis (EDA)** – Univariate, bivariate, time-series, correlation
4. **Explainability Helpers** – SHAP explainers, fusion score, risk tiers, visualizations
5. **Data Preprocessing & Feature Engineering** – Cleaning, scaling, feature selection
6. **Model Training & Evaluation** – Train/evaluate per fund, select best model
7. **Model Persistence** – Save artifacts and registry for deployment
8. **Explainability & Risk Analysis** – SHAP per fund, fusion, risk tiers, exports
9. **Export & Summary** – Enhanced anomaly CSVs and summary
---"""))

    # --- Section 1: Imports ---
    new_cells.append(md_cell("""## 1. Environment & Imports
Set random seeds for reproducibility and import core libraries (pandas, sklearn, TensorFlow). SHAP is loaded separately for explainability."""))
    new_cells.append(cells[4])
    new_cells.append(cells[5])

    # --- Section 2: Data loading ---
    new_cells.append(md_cell("""## 2. Data Loading
Load transaction data from Parquet (or use the SQL snippet if connected to the database). Helper functions: `store_and_read_parquet`, `read_parquet_file`."""))
    new_cells.append(md_cell("""### 2.1 SQL query (commented out) and Parquet helpers"""))
    new_cells.append(cells[8])
    new_cells.append(cells[9])
    new_cells.append(cells[10])
    new_cells.append(md_cell("""### 2.2 Load data and inspect shape"""))
    new_cells.append(cells[11])
    new_cells.append(cells[12])
    new_cells.append(cells[13])
    new_cells.append(cells[14])
    new_cells.append(cells[15])
    new_cells.append(md_cell("""### 2.3 Fund counts and split by fund"""))
    new_cells.append(cells[16])
    new_cells.append(cells[17])
    new_cells.append(cells[18])

    # --- Section 3: EDA (split cell 19 into 4 cells) ---
    new_cells.append(md_cell("""## 3. Exploratory Data Analysis (EDA)
Generate univariate, bivariate, time-series, and correlation plots per fund. Uses `sanitize_filename` and `save_plot` to write figures under `eda/`."""))
    src19 = cells[19]["source"]
    # Split at lines 130, 424, 526 (indices 130, 424, 526 in source array we need to find)
    # In notebook, source is list of strings; cumulative length or line count per element varies.
    lines19 = "".join(src19).split("\n")
    n19 = len(lines19)
    # Split by line index: 0-130, 130-424, 424-526, 526-end
    def to_source(line_list):
        return [ln + "\n" for ln in line_list]
    idx130 = 130
    idx424 = 424
    idx526 = 526
    new_cells.append(md_cell("""### 3.1 EDA setup: imports, paths, `sanitize_filename`, `save_plot`, `plot_summary`"""))
    new_cells.append(code_cell(to_source(lines19[:idx130])))
    new_cells.append(md_cell("""### 3.2 Univariate and time-series plots"""))
    new_cells.append(code_cell(to_source(lines19[idx130:idx424])))
    new_cells.append(md_cell("""### 3.3 Bivariate analysis (scatter, boxplots, categorical)"""))
    new_cells.append(code_cell(to_source(lines19[idx424:idx526])))
    new_cells.append(md_cell("""### 3.4 Plot summary file"""))
    new_cells.append(code_cell(to_source(lines19[idx526:])))

    # --- Reload SHAP: keep as optional note ---
    new_cells.append(md_cell("""*Optional: If you change SHAP helper code below, re-run the cell above to reload modules before re-running explainability.*"""))
    new_cells.append(cells[20])

    # --- Section 4: Explainability helpers ---
    new_cells.append(md_cell("""## 4. Explainability Helpers
Functions used later for SHAP explanations, fusion scores, risk tiers, and visualizations. Define once, then call from the integration cell."""))
    new_cells.append(cells[21])
    new_cells.append(cells[22])
    new_cells.append(cells[23])
    new_cells.append(cells[24])
    new_cells.append(cells[25])

    # --- Section 5: Preprocessing (cell 26) ---
    new_cells.append(md_cell("""## 5. Data Preprocessing & Feature Engineering
Clean column names, parse dates, clean numerics, create derived features (e.g. balance error, spikes), and define which columns to standardize. Produces `df` and per-fund data used in training."""))
    new_cells.append(cells[26])

    new_cells.append(md_cell("""### 5.1 Quick data checks (shape, counts, head, info)"""))
    new_cells.append(cells[27])
    new_cells.append(cells[28])
    new_cells.append(cells[29])
    new_cells.append(cells[30])
    new_cells.append(cells[31])

    # --- Section 6: Training (split cell 32 into 3 cells) ---
    new_cells.append(md_cell("""## 6. Model Training & Evaluation
Per fund: feature selection, train/test split, train multiple models (Isolation Forest, One-Class SVM, LOF, Autoencoder, LSTM Autoencoder), tune hyperparameters, evaluate with AUC/precision/recall, and select the best model. Results go into `best_models`, `results_dict`, `models`, `scaler_dict`, etc."""))
    src32 = cells[32]["source"]
    lines32 = "".join(src32).split("\n")
    # Split at 267 (preprocess_data), 619 (build_autoencoder)
    idx_267 = 267
    idx_619 = 619
    new_cells.append(md_cell("""### 6.1 Imports, paths, feature selection, and selected features per fund"""))
    new_cells.append(code_cell(to_source(lines32[:idx_267])))
    new_cells.append(md_cell("""### 6.2 Preprocessing function and preprocessing per fund"""))
    new_cells.append(code_cell(to_source(lines32[idx_267:idx_619])))
    new_cells.append(md_cell("""### 6.3 Build autoencoders, train/evaluate all models, select best and save artifacts"""))
    new_cells.append(code_cell(to_source(lines32[idx_619:])))

    # --- Section 7: Model persistence ---
    new_cells.append(md_cell("""## 7. Model Persistence (Save for Deployment)
Save architecture, scaler, feature names, and metadata per fund under `models/<fund>/v_<timestamp>/`. Updates the model registry and optionally a `latest` pointer."""))
    new_cells.append(cells[33])

    # --- Section 8: Explainability integration ---
    new_cells.append(md_cell("""## 8. Explainability & Risk Analysis
Run SHAP for each fund’s best model, compute fusion scores and risk tiers, and generate explainability plots and text summaries."""))
    new_cells.append(cells[34])

    # --- Section 9: Export & summary ---
    new_cells.append(md_cell("""## 9. Export & Summary
Export enhanced anomaly tables (with risk tiers and fusion scores) to CSV and print a short summary of explainability outputs."""))
    new_cells.append(cells[35])
    new_cells.append(cells[36])

    nb["cells"] = new_cells
    with open(NOTEBOOK_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)
    print("Notebook reorganized. Total cells:", len(new_cells))

if __name__ == "__main__":
    main()

"""
Retrain the best Keras models and save them as .keras files.

Rebuilds the exact architectures from the notebook, REFITS the scaler
to avoid sklearn version mismatch, trains on the enhanced CSVs, computes
anomaly-score reference statistics, and saves everything to the versioned
and latest directories.

Usage:
    python retrain_and_save_keras.py
"""

import json
import shutil
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

import tensorflow as tf
from tensorflow.keras.layers import Input, Dense, LSTM, Reshape
from tensorflow.keras.models import Model

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
tf.random.set_seed(RANDOM_SEED)

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "ml" / "anomalies"

FUND_CONFIGS = {
    "money_market_fund": {
        "csv": "enhanced_all_transactions_money_market_fund.csv",
        "display": "MONEY MARKET FUND",
    },
    "fixed_income_fund__usd_": {
        "csv": "enhanced_all_transactions_fixed_income_fund__usd_.csv",
        "display": "FIXED INCOME FUND (USD)",
    },
}


def build_autoencoder(input_dim, encoding_dim=16):
    input_layer = Input(shape=(input_dim,))
    encoded = Dense(encoding_dim * 2, activation="relu")(input_layer)
    encoded = Dense(encoding_dim, activation="relu")(encoded)
    decoded = Dense(encoding_dim * 2, activation="relu")(encoded)
    decoded = Dense(input_dim, activation="sigmoid")(decoded)
    autoencoder = Model(input_layer, decoded)
    autoencoder.compile(optimizer="adam", loss="mse")
    return autoencoder


def build_lstm_autoencoder(input_dim, timesteps=1, lstm_units=16):
    input_layer = Input(shape=(timesteps, input_dim))
    encoded = LSTM(lstm_units, activation="relu", return_sequences=False)(input_layer)
    encoded = Dense(lstm_units // 2, activation="relu")(encoded)
    decoded = Dense(lstm_units, activation="relu")(encoded)
    decoded = Reshape((1, lstm_units))(decoded)
    decoded = LSTM(input_dim, activation="sigmoid", return_sequences=True)(decoded)
    autoencoder = Model(input_layer, decoded)
    autoencoder.compile(optimizer="adam", loss="mse")
    return autoencoder


def compute_score_stats(model, X_scaled, model_name):
    """Compute MSE distribution on scaled data and return reference statistics."""
    if model_name == "LSTM Autoencoder":
        X_input = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
        reconstructions = model.predict(X_input, verbose=0)
        reconstructions = reconstructions.reshape(X_scaled.shape)
    else:
        reconstructions = model.predict(X_scaled, verbose=0)

    mse = np.mean(np.power(X_scaled - reconstructions, 2), axis=1)
    return {
        "threshold_95": float(np.percentile(mse, 95)),
        "threshold_99": float(np.percentile(mse, 99)),
        "mean": float(np.mean(mse)),
        "std": float(np.std(mse)),
        "min": float(np.min(mse)),
        "max": float(np.max(mse)),
        "median": float(np.median(mse)),
    }


def retrain_fund(fund_key: str, config: dict):
    print(f"\n{'='*60}")
    print(f"Retraining: {config['display']}")

    version_dirs = sorted(
        [d for d in (MODELS_DIR / fund_key).glob("v_*") if (d / "metadata.json").exists()],
        reverse=True,
    )
    if not version_dirs:
        print(f"  ERROR: No versioned directory with metadata found for {fund_key}")
        return False

    version_dir = version_dirs[0]

    with open(version_dir / "metadata.json") as f:
        meta = json.load(f)

    with open(version_dir / "feature_names.json") as f:
        feature_names = json.load(f)

    model_name = meta["model_name"]
    params = meta.get("tuned_parameters", {})
    n_features = len(feature_names)

    print(f"  Model: {model_name}")
    print(f"  Features ({n_features}): {', '.join(feature_names)}")
    print(f"  Parameters: {params}")

    csv_path = DATA_DIR / config["csv"]
    if not csv_path.exists():
        print(f"  ERROR: Training data not found at {csv_path}")
        return False

    df = pd.read_csv(csv_path)
    print(f"  Training data: {len(df):,} rows")

    for col in feature_names:
        if col not in df.columns:
            df[col] = 0.0

    X = df[feature_names].fillna(0).astype(np.float64)

    # REFIT the scaler to avoid sklearn version mismatch
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"  Scaler refit: mean range [{X_scaled.mean(axis=0).min():.4f}, {X_scaled.mean(axis=0).max():.4f}]")
    print(f"  Scaled data range: [{X_scaled.min():.2f}, {X_scaled.max():.2f}]")

    X_train, X_test = train_test_split(X_scaled, test_size=0.2, random_state=RANDOM_SEED)

    if model_name == "LSTM Autoencoder":
        lstm_units = params.get("lstm_units", 16)
        epochs = params.get("epochs", 20)
        batch_size = params.get("batch_size", 32)

        model = build_lstm_autoencoder(n_features, lstm_units=lstm_units)
        X_train_lstm = X_train.reshape((X_train.shape[0], 1, X_train.shape[1]))
        X_test_lstm = X_test.reshape((X_test.shape[0], 1, X_test.shape[1]))

        print(f"  Training LSTM Autoencoder ({epochs} epochs, batch_size={batch_size})...")
        model.fit(
            X_train_lstm, X_train_lstm,
            epochs=epochs, batch_size=batch_size,
            shuffle=True, validation_split=0.2, verbose=1,
        )

    elif model_name == "Autoencoder":
        encoding_dim = params.get("encoding_dim", 16)
        epochs = params.get("epochs", 20)
        batch_size = params.get("batch_size", 32)

        model = build_autoencoder(n_features, encoding_dim=encoding_dim)

        print(f"  Training Autoencoder ({epochs} epochs, batch_size={batch_size})...")
        model.fit(
            X_train, X_train,
            epochs=epochs, batch_size=batch_size,
            shuffle=True, validation_split=0.2, verbose=1,
        )
    else:
        print(f"  SKIP: {model_name} is not a Keras model")
        return False

    # Compute score reference statistics on the full scaled dataset
    print("  Computing score reference statistics...")
    stats = compute_score_stats(model, X_scaled, model_name)
    print(f"  Score stats: mean={stats['mean']:.6f}, std={stats['std']:.6f}, "
          f"p95={stats['threshold_95']:.6f}, p99={stats['threshold_99']:.6f}")

    # Save everything to versioned dir
    model.save(version_dir / "model.keras")
    print(f"  Saved model.keras")

    with open(version_dir / "model_architecture.json", "w") as f:
        f.write(model.to_json())

    joblib.dump(scaler, version_dir / "scaler.joblib")
    print(f"  Saved refitted scaler.joblib")

    with open(version_dir / "score_params.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"  Saved score_params.json")

    # Copy everything to latest/
    latest_dir = MODELS_DIR / fund_key / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    for item in version_dir.iterdir():
        shutil.copy2(item, latest_dir / item.name)

    stale_joblib = latest_dir / "model.joblib"
    if stale_joblib.exists():
        stale_joblib.unlink()

    meta_features = meta.get("feature_names")
    if meta_features:
        with open(latest_dir / "feature_names.json", "w") as f:
            json.dump(meta_features, f, indent=2)

    print(f"  Copied to latest/")
    print(f"  Done: {model_name} for {config['display']}")
    return True


def main():
    print("=" * 60)
    print("RETRAIN & SAVE KERAS MODELS (with scaler refit + score stats)")
    print("=" * 60)

    success = 0
    for fund_key, config in FUND_CONFIGS.items():
        if retrain_fund(fund_key, config):
            success += 1

    print(f"\n{'='*60}")
    print(f"Retrained {success}/{len(FUND_CONFIGS)} models")
    if success == len(FUND_CONFIGS):
        print("All model.keras files created. Now run: python export_models.py")
    print("=" * 60)


if __name__ == "__main__":
    main()

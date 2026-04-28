# app/ml/training_pipeline.py — Dask + NVIDIA RAPIDS + XGBoost training pipeline
from __future__ import annotations

"""
NexGen SCM — XGBoost Anomaly Detection Training Pipeline

Data source: BigQuery `nexgen_telemetry.telemetry_raw`
Framework:   Dask (distributed) + NVIDIA RAPIDS (cuDF/cuML) + XGBoost GPU
Output:      model.bst artifact → GCS → Vertex AI (see SKILL.md)

Run locally (CPU):
    python -m app.ml.training_pipeline --mode cpu

Run on GPU cluster (requires CUDA + RAPIDS):
    python -m app.ml.training_pipeline --mode gpu
"""

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Literal

logger = logging.getLogger("nexgen.training")

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "nexgen-scm-2026")
BQ_DATASET = os.getenv("BQ_DATASET", "nexgen_telemetry")
BQ_TABLE = os.getenv("BQ_TABLE", "telemetry_raw")
GCS_MODEL_PATH = os.getenv("GCS_MODEL_PATH", "gs://nexgen-scm-2026-models/xgboost/latest/model.bst")
MODEL_OUTPUT_PATH = Path(os.getenv("MODEL_OUTPUT_PATH", "model.bst"))

FEATURE_COLS = [
    "temperature",
    "humidity",
    "lat",
    "lon",
    "speed_kmh",
    "battery_pct",
    "hours_since_last_checkpoint",
]
LABEL_COL = "anomaly_label"

XGBOOST_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": ["logloss", "auc"],
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 10,
    "scale_pos_weight": 10,  # Anomalies are rare (~10% of data)
    "random_state": 42,
    "verbosity": 1,
}


def load_from_bigquery_dask(mode: Literal["cpu", "gpu"]) -> "dask.dataframe.DataFrame":
    """Load training data from BigQuery using Dask."""
    logger.info(f"Loading data from BigQuery: {PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}")

    if mode == "gpu":
        try:
            import dask_cudf
            from google.cloud import bigquery
            from google.cloud.bigquery import Client as BQClient

            client = BQClient(project=PROJECT_ID)
            query = f"""
                SELECT {', '.join(FEATURE_COLS + [LABEL_COL])}
                FROM `{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
                WHERE {LABEL_COL} IS NOT NULL
                  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
            """
            df_pandas = client.query(query).to_dataframe()
            df = dask_cudf.from_cudf(
                __import__("cudf").from_pandas(df_pandas),
                npartitions=4,
            )
            logger.info(f"Loaded {len(df_pandas):,} rows (GPU/cuDF mode)")
            return df
        except ImportError:
            logger.warning("RAPIDS/cuDF not available — falling back to CPU mode")
            mode = "cpu"

    # CPU mode: use Dask + BigQuery Storage API
    import dask.dataframe as dd
    from google.cloud import bigquery_storage

    # Read via BigQuery Storage Read API for maximum throughput
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT_ID)
    query = f"""
        SELECT {', '.join(FEATURE_COLS + [LABEL_COL])}
        FROM `{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE {LABEL_COL} IS NOT NULL
          AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 90 DAY)
    """
    df_pandas = client.query(query).to_dataframe()
    df = dd.from_pandas(df_pandas, npartitions=4)
    logger.info(f"Loaded {len(df_pandas):,} rows (CPU/Dask mode)")
    return df


def feature_engineering(df) -> tuple:
    """Apply feature engineering and split into train/test."""
    logger.info("Running feature engineering...")

    # Fill nulls with median for numeric features
    df = df.fillna({col: df[col].mean() for col in FEATURE_COLS})

    # Convert to numpy/pandas for XGBoost
    try:
        # GPU path: cuDF → numpy
        X = df[FEATURE_COLS].compute().to_pandas().values
        y = df[LABEL_COL].compute().to_pandas().values
    except AttributeError:
        # CPU path: Dask → pandas
        X = df[FEATURE_COLS].compute().values
        y = df[LABEL_COL].compute().values

    # Time-based split: use last 20% as test set (preserves temporal order)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    logger.info(f"Train: {len(X_train):,} | Test: {len(X_test):,} | "
                f"Anomaly rate (train): {y_train.mean():.2%}")
    return X_train, X_test, y_train, y_test


def train_xgboost(
    X_train, X_test, y_train, y_test, mode: Literal["cpu", "gpu"]
) -> "xgboost.XGBClassifier":
    """Train the XGBoost model with early stopping."""
    import xgboost as xgb

    params = {**XGBOOST_PARAMS}
    if mode == "gpu":
        params["device"] = "cuda"
        params["tree_method"] = "hist"  # GPU-accelerated histogram method
        logger.info("XGBoost training on GPU (CUDA)")
    else:
        params["device"] = "cpu"
        params["tree_method"] = "hist"
        logger.info("XGBoost training on CPU")

    model = xgb.XGBClassifier(**params)

    start = time.monotonic()
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        early_stopping_rounds=20,
        verbose=50,
    )
    elapsed = time.monotonic() - start
    logger.info(f"Training completed in {elapsed:.1f}s | Best iteration: {model.best_iteration}")

    return model


def evaluate_and_save(model, X_test, y_test) -> None:
    """Evaluate the model and save the artifact."""
    from sklearn.metrics import (
        classification_report,
        roc_auc_score,
        average_precision_score,
    )

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.75).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    ap = average_precision_score(y_test, y_pred_proba)

    logger.info(f"Evaluation Results:")
    logger.info(f"  ROC-AUC:          {auc:.4f}")
    logger.info(f"  Avg Precision:    {ap:.4f}")
    logger.info(f"\n{classification_report(y_test, y_pred, target_names=['Normal', 'Anomaly'])}")

    # Save model artifact
    model.save_model(str(MODEL_OUTPUT_PATH))
    logger.info(f"Model saved to: {MODEL_OUTPUT_PATH}")

    # Upload to GCS
    try:
        from google.cloud import storage
        gcs_path = GCS_MODEL_PATH
        bucket_name = gcs_path.split("/")[2]
        blob_path = "/".join(gcs_path.split("/")[3:])
        client = storage.Client(project=PROJECT_ID)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        blob.upload_from_filename(str(MODEL_OUTPUT_PATH))
        logger.info(f"Model uploaded to GCS: {gcs_path}")
    except Exception as exc:
        logger.warning(f"GCS upload failed (artifact still saved locally): {exc}")


def main(mode: Literal["cpu", "gpu"] = "cpu") -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    logger.info(f"🚀 NexGen XGBoost Training Pipeline starting (mode={mode})")

    df = load_from_bigquery_dask(mode)
    X_train, X_test, y_train, y_test = feature_engineering(df)
    model = train_xgboost(X_train, X_test, y_train, y_test, mode)
    evaluate_and_save(model, X_test, y_test)

    logger.info("✅ Training pipeline complete — run deploy-vertex-xgboost skill to deploy")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NexGen XGBoost Training Pipeline")
    parser.add_argument(
        "--mode", choices=["cpu", "gpu"], default="cpu", help="Compute mode"
    )
    args = parser.parse_args()
    main(mode=args.mode)

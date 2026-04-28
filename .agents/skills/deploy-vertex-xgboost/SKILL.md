# Skill: Deploy XGBoost Model to Vertex AI Endpoint

**Skill ID**: `deploy-vertex-xgboost`  
**Trigger**: Run this skill after training a new XGBoost model artifact in the intelligence pipeline.  
**Runtime Requirements**: `gcloud` CLI authenticated, `gsutil`, Python 3.11, `google-cloud-aiplatform`

---

## Overview

This skill automates the full lifecycle of packaging, uploading, registering, and deploying an XGBoost model to a Vertex AI Endpoint, following Google's Model Registry best practices.

---

## Prerequisites

```bash
# Authenticate
gcloud auth application-default login

# Set project and region
gcloud config set project nexgen-scm-2026
gcloud config set ai/region us-central1

# Install Python SDK
pip install google-cloud-aiplatform==1.48.0
```

---

## Step 1 — Save Model Artifact

The training pipeline saves the model in XGBoost BST format. Verify artifact exists:

```python
# In services/intelligence/app/ml/training_pipeline.py
# model.save_model("model.bst") is called at end of training
import os
assert os.path.exists("model.bst"), "Model artifact not found — run training first"
```

---

## Step 2 — Upload Artifact to GCS

```bash
MODEL_VERSION=$(date +%Y%m%d%H%M%S)
GCS_PATH="gs://nexgen-scm-2026-models/xgboost/${MODEL_VERSION}/"

# Create the model directory structure expected by Vertex AI
mkdir -p /tmp/vertex_model/
cp model.bst /tmp/vertex_model/model.bst

# Upload
gsutil -m cp -r /tmp/vertex_model/ "${GCS_PATH}"
echo "Artifact at: ${GCS_PATH}"
```

---

## Step 3 — Register Model in Vertex AI Model Registry

```python
from google.cloud import aiplatform

aiplatform.init(project="nexgen-scm-2026", location="us-central1")

model = aiplatform.Model.upload(
    display_name=f"nexgen-xgboost-anomaly-{MODEL_VERSION}",
    artifact_uri=GCS_PATH,
    serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/xgboost-cpu.1-7:latest",
    serving_container_health_route="/health",
    serving_container_predict_route="/predict",
    serving_container_ports=[8080],
    labels={
        "project": "nexgen-scm",
        "model_type": "anomaly_detection",
        "version": MODEL_VERSION,
    },
)
print(f"Model registered: {model.resource_name}")
```

---

## Step 4 — Deploy to Vertex AI Endpoint

```python
# Get or create the endpoint (Terraform provisions it, we just deploy to it)
endpoint = aiplatform.Endpoint(
    endpoint_name="projects/nexgen-scm-2026/locations/us-central1/endpoints/nexgen-scm-endpoint"
)

deployed_model = endpoint.deploy(
    model=model,
    deployed_model_display_name=f"nexgen-xgboost-{MODEL_VERSION}",
    machine_type="n1-standard-4",
    min_replica_count=1,
    max_replica_count=5,
    accelerator_type=None,          # CPU-only; swap to NVIDIA_TESLA_T4 for GPU
    traffic_split={"0": 100},       # Route 100% traffic to new model
    sync=True,
)
print(f"Deployed: {deployed_model.id}")
```

---

## Step 5 — Smoke Test the Endpoint

```python
import json

test_payload = {
    "instances": [{
        "temperature": 32.5,
        "humidity": 78.2,
        "lat": 28.6139,
        "lon": 77.2090,
        "speed_kmh": 0.0,
        "battery_pct": 45.0,
        "hours_since_last_checkpoint": 6.5,
    }]
}

predictions = endpoint.predict(instances=test_payload["instances"])
print(f"Anomaly score: {predictions.predictions[0]}")
assert 0.0 <= float(predictions.predictions[0]) <= 1.0, "Score out of range"
print("✅ Endpoint smoke test passed")
```

---

## Step 6 — Update FastAPI Environment Variable

After deployment, update the Cloud Run service to point to the new endpoint:

```bash
gcloud run services update nexgen-intelligence \
  --region us-central1 \
  --update-env-vars VERTEX_ENDPOINT_ID=nexgen-scm-endpoint \
  --update-env-vars VERTEX_MODEL_ID=${MODEL_VERSION}
```

---

## Rollback

If the new model causes regression, swap traffic back:

```python
endpoint.undeploy(deployed_model_id=deployed_model.id)
print("Rolled back to previous model")
```

---

## Snyk Security Check

```bash
# Scan the Python environment before deploying
snyk test services/intelligence/ --file=requirements.txt
snyk code test services/intelligence/app/ml/
```

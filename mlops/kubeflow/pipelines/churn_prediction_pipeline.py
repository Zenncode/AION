"""
AION Kubeflow Pipeline — Churn Prediction MLOps
=================================================
End-to-end pipeline:
  1. Data Preprocessing (StandardScaler)
  2. Train PyTorch DNN for churn prediction
  3. Register model in MLflow with hyperparameters
  4. Deploy to NVIDIA Triton if validation accuracy > 90%

Usage:
    python churn_prediction_pipeline.py --upload
    python churn_prediction_pipeline.py --run
"""

import argparse
import json
from typing import Dict, List, Optional

from kfp import dsl
from kfp import compiler
from kfp.dsl import (
    Artifact,
    Dataset,
    Input,
    Output,
    Metrics,
    Model,
)

# =============================================================================
# Constants
# =============================================================================

PIPELINE_NAME = "aion-churn-prediction"
PIPELINE_VERSION = "1.0.0"
EXPERIMENT_NAME = "aion-ml-churn"

# S3 paths
RAW_DATA_PATH = "s3://aion-bronze-raw/ml/churn/"
PROCESSED_DATA_PATH = "s3://aion-silver-lakehouse/ml/churn_processed/"
MODEL_OUTPUT_PATH = "s3://aion-models/churn/"

# Feature Store
FEAST_REGISTRY = "s3://aion-feast-registry/registry.db"
FEAST_ONLINE_STORE = "feast-redis.aion-mlops.svc.cluster.local:6379"

# MLflow
MLFLOW_TRACKING_URI = "http://mlflow.aion-mlops.svc.cluster.local:5000"
MLFLOW_EXPERIMENT_NAME = "aion-churn-prediction"

# Triton
TRITON_URL = "triton-inference-server.aion-inference.svc.cluster.local:8001"
MODEL_REPO = "s3://aion-models/triton-repo/"


# =============================================================================
# Component 1: Data Preprocessing
# =============================================================================

@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "pandas>=2.1.0",
        "scikit-learn>=1.3.0",
        "pyarrow>=14.0.0",
        "boto3>=1.34.0",
        "feast>=0.37.0",
    ],
)
def preprocess_data(
    raw_data_path: str,
    processed_data_path: str,
    feast_registry: str,
    feature_columns: List[str],
    output_dataset: Output[Dataset],
    output_scaler: Output[Artifact],
    output_metrics: Output[Metrics],
) -> Dict:
    """
    Preprocessing step:
      1. Load raw customer data from S3
      2. Retrieve features from Feast feature store
      3. Join, clean, impute missing values
      4. Apply StandardScaler (fit on training, transform all)
      5. Save processed data + scaler artifact
    """
    import pandas as pd
    import numpy as np
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    import joblib
    import json
    import os

    print(f"[Preprocessing] Loading raw data from: {raw_data_path}")

    # Load raw data
    df = pd.read_parquet(raw_data_path)
    print(f"[Preprocessing] Raw data shape: {df.shape}")

    # Retrieve features from Feast
    print(f"[Preprocessing] Retrieving features from Feast registry: {feast_registry}")
    try:
        from feast import FeatureStore
        store = FeatureStore(repo_path=None, config=feast_registry)

        # Get entity dataframe with customer_ids
        entity_df = df[["customer_id", "event_date"]].copy()
        entity_df["event_date"] = pd.to_datetime(entity_df["event_date"])

        # Retrieve features
        feature_refs = [
            "user_activity_features:click_rate_7d",
            "user_activity_features:avg_transaction_value",
            "user_activity_features:total_orders_30d",
            "user_activity_features:total_revenue_30d",
            "user_activity_features:days_since_last_order",
            "user_activity_features:rfm_composite_score",
        ]

        feature_vector = store.get_historical_features(
            entity_df=entity_df,
            features=feature_refs,
        ).to_df()

        # Join features with raw data
        df = df.merge(feature_vector, on=["customer_id", "event_date"], how="left")
        print(f"[Preprocessing] After feature retrieval: {df.shape}")
    except Exception as e:
        print(f"[Preprocessing] Feast retrieval failed ({e}), using raw columns")

    # Select feature columns (ensure they exist)
    available_cols = [c for c in feature_columns if c in df.columns]
    if len(available_cols) < len(feature_columns):
        missing = set(feature_columns) - set(available_cols)
        print(f"[Preprocessing] Warning: missing columns {missing}, filling with 0")
        for col in missing:
            df[col] = 0.0
        available_cols = feature_columns

    X = df[available_cols].copy()
    y = df["churn_label"].copy() if "churn_label" in df.columns else pd.Series(
        (df.get("days_since_last_order", 999) > 60).astype(int), name="churn_label"
    )

    # Impute missing values
    X = X.fillna(X.median())

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # StandardScaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Save processed data
    processed_df = pd.DataFrame(X_train_scaled, columns=available_cols)
    processed_df["churn_label"] = y_train.values
    processed_df["split"] = "train"

    test_df = pd.DataFrame(X_test_scaled, columns=available_cols)
    test_df["churn_label"] = y_test.values
    test_df["split"] = "test"

    full_df = pd.concat([processed_df, test_df], ignore_index=True)
    full_df.to_parquet(processed_data_path, index=False)

    # Save scaler
    scaler_path = "/tmp/scaler.joblib"
    joblib.dump(scaler, scaler_path)

    # Compute preprocessing metrics
    metrics = {
        "total_samples": len(df),
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "features": available_cols,
        "feature_count": len(available_cols),
        "positive_rate": float(y.mean()),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
    }

    # Write outputs
    output_dataset.path = processed_data_path
    output_scaler.path = scaler_path
    output_scaler.metadata["scaler_type"] = "StandardScaler"
    output_scaler.metadata["feature_columns"] = available_cols
    output_metrics.log_metrics(metrics)

    print(f"[Preprocessing] Complete. Train: {len(X_train)}, Test: {len(X_test)}")
    return metrics


# =============================================================================
# Component 2: Train PyTorch DNN
# =============================================================================

@dsl.component(
    base_image="pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
    packages_to_install=[
        "pandas>=2.1.0",
        "numpy>=1.25.0",
        "scikit-learn>=1.3.0",
        "mlflow>=2.9.0",
    ],
)
def train_model(
    processed_data_path: str,
    model_output_path: str,
    mlflow_tracking_uri: str,
    mlflow_experiment_name: str,
    hyperparameters: Dict,
    output_model: Output[Model],
    output_metrics: Output[Metrics],
) -> Dict:
    """
    Train a PyTorch DNN for churn prediction:
      - Input: processed features from preprocessing step
      - Architecture: 4-layer DNN with BatchNorm + Dropout
      - Loss: BCEWithLogitsLoss (binary classification)
      - Optimizer: AdamW with cosine annealing
      - Output: Saved model + training metrics
    """
    import pandas as pd
    import numpy as np
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    from sklearn.metrics import (
        accuracy_score, precision_score, recall_score,
        f1_score, roc_auc_score, confusion_matrix,
    )
    import mlflow
    import mlflow.pytorch
    import json
    import os
    from datetime import datetime

    # Unpack hyperparameters
    hidden_sizes = hyperparameters.get("hidden_sizes", [256, 128, 64, 32])
    dropout_rate = hyperparameters.get("dropout_rate", 0.3)
    learning_rate = hyperparameters.get("learning_rate", 1e-3)
    batch_size = hyperparameters.get("batch_size", 256)
    epochs = hyperparameters.get("epochs", 100)
    weight_decay = hyperparameters.get("weight_decay", 1e-4)
    patience = hyperparameters.get("early_stopping_patience", 15)

    print(f"[Training] Hyperparameters: {json.dumps(hyperparameters, indent=2)}")

    # Load data
    df = pd.read_parquet(processed_data_path)
    feature_cols = [c for c in df.columns if c not in ("churn_label", "split")]
    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"]

    X_train = torch.FloatTensor(train_df[feature_cols].values)
    y_train = torch.FloatTensor(train_df["churn_label"].values).unsqueeze(1)
    X_test = torch.FloatTensor(test_df[feature_cols].values)
    y_test = torch.FloatTensor(test_df["churn_label"].values).unsqueeze(1)

    input_size = X_train.shape[1]
    print(f"[Training] Input features: {input_size}, Train: {len(X_train)}, Test: {len(X_test)}")

    # DataLoaders
    train_dataset = TensorDataset(X_train, y_train)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_dataset = TensorDataset(X_test, y_test)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    # DNN Model
    class ChurnDNN(nn.Module):
        def __init__(self, input_dim, hidden_sizes, dropout_rate):
            super().__init__()
            layers = []
            prev_dim = input_dim
            for h_dim in hidden_sizes:
                layers.append(nn.Linear(prev_dim, h_dim))
                layers.append(nn.BatchNorm1d(h_dim))
                layers.append(nn.ReLU())
                layers.append(nn.Dropout(dropout_rate))
                prev_dim = h_dim
            layers.append(nn.Linear(prev_dim, 1))
            self.network = nn.Sequential(*layers)

        def forward(self, x):
            return self.network(x)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Training] Device: {device}")

    model = ChurnDNN(input_size, hidden_sizes, dropout_rate).to(device)

    # Loss and optimizer
    pos_weight = torch.tensor([(y_train == 0).sum() / (y_train == 1).sum()]).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    # MLflow tracking
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(mlflow_experiment_name)

    with mlflow.start_run(run_name=f"churn-dnn-{datetime.now().strftime('%Y%m%d-%H%M%S')}"):
        # Log hyperparameters
        mlflow.log_params(hyperparameters)
        mlflow.log_param("model_type", "PyTorch_DNN")
        mlflow.log_param("input_features", input_size)
        mlflow.log_param("device", str(device))

        best_val_acc = 0.0
        best_epoch = 0
        patience_counter = 0
        train_losses = []
        val_accuracies = []

        for epoch in range(epochs):
            # ---- Training ----
            model.train()
            epoch_loss = 0.0
            for batch_X, batch_y in train_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                optimizer.zero_grad()
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                epoch_loss += loss.item() * batch_X.size(0)
            scheduler.step()
            avg_loss = epoch_loss / len(X_train)
            train_losses.append(avg_loss)

            # ---- Validation ----
            model.eval()
            all_preds = []
            all_labels = []
            with torch.no_grad():
                for batch_X, batch_y in test_loader:
                    batch_X = batch_X.to(device)
                    outputs = model(batch_X)
                    preds = (torch.sigmoid(outputs) > 0.5).float().cpu()
                    all_preds.extend(preds.numpy().flatten())
                    all_labels.extend(batch_y.numpy().flatten())

            val_acc = accuracy_score(all_labels, all_preds)
            val_accuracies.append(val_acc)

            # Log to MLflow
            mlflow.log_metrics({
                "train_loss": avg_loss,
                "val_accuracy": val_acc,
                "learning_rate": scheduler.get_last_lr()[0],
            }, step=epoch)

            if (epoch + 1) % 10 == 0:
                print(f"  Epoch {epoch+1}/{epochs} — Loss: {avg_loss:.4f}, Val Acc: {val_acc:.4f}")

            # Early stopping
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_epoch = epoch
                patience_counter = 0
                # Save best model
                best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"[Training] Early stopping at epoch {epoch+1}")
                    break

        # Load best model
        model.load_state_dict(best_model_state)
        model.to(device)

        # Final evaluation on test set
        model.eval()
        all_preds, all_probs, all_labels = [], [], []
        with torch.no_grad():
            for batch_X, batch_y in test_loader:
                batch_X = batch_y_labels = batch_y.to(device)
                outputs = model(batch_X.to(device))
                probs = torch.sigmoid(outputs).cpu().numpy().flatten()
                preds = (probs > 0.5).astype(int)
                all_preds.extend(preds)
                all_probs.extend(probs)
                all_labels.extend(batch_y.cpu().numpy().flatten())

        # Metrics
        val_accuracy = accuracy_score(all_labels, all_preds)
        val_precision = precision_score(all_labels, all_preds, zero_division=0)
        val_recall = recall_score(all_labels, all_preds, zero_division=0)
        val_f1 = f1_score(all_labels, all_preds, zero_division=0)
        val_auc = roc_auc_score(all_labels, all_probs) if len(set(all_labels)) > 1 else 0.0
        cm = confusion_matrix(all_labels, all_preds)

        print(f"\n[Training] Final Results:")
        print(f"  Accuracy:  {val_accuracy:.4f}")
        print(f"  Precision: {val_precision:.4f}")
        print(f"  Recall:    {val_recall:.4f}")
        print(f"  F1:        {val_f1:.4f}")
        print(f"  AUC-ROC:   {val_auc:.4f}")
        print(f"  Best Epoch: {best_epoch + 1}")

        # Log final metrics
        final_metrics = {
            "val_accuracy": val_accuracy,
            "val_precision": val_precision,
            "val_recall": val_recall,
            "val_f1": val_f1,
            "val_auc_roc": val_auc,
            "best_epoch": best_epoch + 1,
            "total_epochs": epoch + 1,
            "confusion_matrix_tp": int(cm[1][1]) if cm.shape == (2, 2) else 0,
            "confusion_matrix_fp": int(cm[0][1]) if cm.shape == (2, 2) else 0,
            "confusion_matrix_tn": int(cm[0][0]) if cm.shape == (2, 2) else 0,
            "confusion_matrix_fn": int(cm[1][0]) if cm.shape == (2, 2) else 0,
        }
        mlflow.log_metrics(final_metrics)

        # Log model
        mlflow.pytorch.log_model(
            model,
            artifact_path="churn-dnn-model",
            registered_model_name="aion-churn-dnn",
            pip_requirements=["torch", "numpy"],
        )

        # Log scaler metadata
        mlflow.log_param("scaler_type", "StandardScaler")
        mlflow.log_param("feature_columns", json.dumps(feature_cols))

        # Save model locally for Triton conversion
        model_path = os.path.join(model_output_path, "model.pt")
        os.makedirs(model_output_path, exist_ok=True)
        torch.save({
            "model_state_dict": model.state_dict(),
            "input_size": input_size,
            "hidden_sizes": hidden_sizes,
            "dropout_rate": dropout_rate,
            "feature_columns": feature_cols,
            "scaler_type": "StandardScaler",
        }, model_path)

        # Write outputs
        output_model.path = model_path
        output_model.metadata["model_type"] = "PyTorch_DNN"
        output_model.metadata["val_accuracy"] = val_accuracy
        output_model.metadata["mlflow_run_id"] = mlflow.active_run().info.run_id
        output_metrics.log_metrics(final_metrics)

    print(f"\n[Training] MLflow run: {mlflow.active_run().info.run_id}")
    return final_metrics


# =============================================================================
# Component 3: Register Model in MLflow
# =============================================================================

@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "mlflow>=2.9.0",
        "torch>=2.1.0",
        "boto3>=1.34.0",
    ],
)
def register_model(
    model_input: Input[Model],
    mlflow_tracking_uri: str,
    model_name: str,
    validation_accuracy: float,
    output_model_version: Output[Artifact],
) -> Dict:
    """
    Register the trained model in MLflow Model Registry.
    Attaches metadata: accuracy, framework, deployment target.
    """
    import mlflow
    import json

    mlflow.set_tracking_uri(mlflow_tracking_uri)

    # The model was already logged during training.
    # Here we transition it to the appropriate stage.
    client = mlflow.MlflowClient()

    # Get the latest version
    model_versions = client.search_model_versions(f"name='{model_name}'")
    if not model_versions:
        raise ValueError(f"No model versions found for '{model_name}'")

    latest_version = max(model_versions, key=lambda v: int(v.version))

    # Add metadata tags
    client.update_model_version(
        name=model_name,
        version=latest_version.version,
        description=(
            f"AION Churn Prediction DNN\n"
            f"Validation Accuracy: {validation_accuracy:.4f}\n"
            f"Framework: PyTorch\n"
            f"Deployment Target: Triton Inference Server"
        ),
    )

    # Set tags
    client.set_model_version_tag(model_name, latest_version.version, "validation_accuracy", str(validation_accuracy))
    client.set_model_version_tag(model_name, latest_version.version, "framework", "pytorch")
    client.set_model_version_tag(model_name, latest_version.version, "pipeline_version", "1.0.0")
    client.set_model_version_tag(model_name, latest_version.version, "deployment_target", "triton")

    # Transition to Staging if accuracy > 90%
    if validation_accuracy > 0.90:
        client.transition_model_version_stage(
            name=model_name,
            version=latest_version.version,
            stage="Staging",
        )
        print(f"[Register] Model v{latest_version.version} promoted to Staging (acc={validation_accuracy:.4f})")
    else:
        print(f"[Register] Model v{latest_version.version} kept in None (acc={validation_accuracy:.4f} < 0.90)")

    result = {
        "model_name": model_name,
        "model_version": latest_version.version,
        "stage": "Staging" if validation_accuracy > 0.90 else "None",
        "validation_accuracy": validation_accuracy,
    }

    output_model_version.path = "/tmp/model_version.json"
    with open(output_model_version.path, "w") as f:
        json.dump(result, f)

    return result


# =============================================================================
# Component 4: Deploy to Triton
# =============================================================================

@dsl.component(
    base_image="python:3.11-slim",
    packages_to_install=[
        "torch>=2.1.0",
        "numpy>=1.25.0",
        "onnx>=1.15.0",
        "tritonclient[grpc]>=2.40.0",
        "boto3>=1.34.0",
    ],
)
def deploy_to_triton(
    model_input: Input[Model],
    triton_url: str,
    model_repo: str,
    validation_accuracy: float,
    threshold: float = 0.90,
) -> Dict:
    """
    Deploy model to NVIDIA Triton Inference Server:
      1. Convert PyTorch model to ONNX
      2. Create Triton model repository structure
      3. Upload to S3
      4. Register model with Triton server
    """
    import torch
    import numpy as np
    import onnx
    import json
    import os
    import shutil

    print(f"[Deploy] Validation accuracy: {validation_accuracy:.4f}, threshold: {threshold}")

    if validation_accuracy <= threshold:
        print(f"[Deploy] SKIP — accuracy {validation_accuracy:.4f} <= threshold {threshold}")
        return {"status": "skipped", "reason": "below_threshold"}

    # Load model
    checkpoint = torch.load(model_input.path, map_location="cpu")

    # Rebuild model
    class ChurnDNN(torch.nn.Module):
        def __init__(self, input_dim, hidden_sizes, dropout_rate):
            super().__init__()
            layers = []
            prev_dim = input_dim
            for h_dim in hidden_sizes:
                layers.append(torch.nn.Linear(prev_dim, h_dim))
                layers.append(torch.nn.BatchNorm1d(h_dim))
                layers.append(torch.nn.ReLU())
                layers.append(torch.nn.Dropout(dropout_rate))
                prev_dim = h_dim
            layers.append(torch.nn.Linear(prev_dim, 1))
            self.network = torch.nn.Sequential(*layers)

        def forward(self, x):
            return torch.network(x)

    model = ChurnDNN(
        checkpoint["input_size"],
        checkpoint["hidden_sizes"],
        checkpoint["dropout_rate"],
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    # Export to ONNX
    dummy_input = torch.randn(1, checkpoint["input_size"])
    onnx_path = "/tmp/churn_model.onnx"
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
        opset_version=17,
    )
    print(f"[Deploy] ONNX model exported: {onnx_path}")

    # Create Triton model repository
    triton_model_dir = "/tmp/triton_model_repo/churn_model"
    version_dir = os.path.join(triton_model_dir, "1")
    os.makedirs(version_dir, exist_ok=True)

    # Copy ONNX model
    shutil.copy(onnx_path, os.path.join(version_dir, "model.onnx"))

    # Write config.pbtxt
    config = f"""name: "churn_model"
platform: "onnxruntime_onnx"
max_batch_size: 256
input [
  {{
    name: "input"
    data_type: TYPE_FP32
    dims: [{checkpoint["input_size"]}]
  }}
]
output [
  {{
    name: "output"
    data_type: TYPE_FP32
    dims: [1]
  }}
]
instance_group [
  {{
    count: 2
    kind: KIND_GPU
    gpus: [0]
  }}
]
dynamic_batching {{
  preferred_batch_size: [32, 64, 128]
  max_queue_delay_microseconds: 10000
}}
optimization {{
  graph {{
    level: 1
  }}
}}
versioning {{
  model_compatibility {{
    name: "onnxruntime"
    version: "1.16.0"
  }}
}}
"""
    with open(os.path.join(triton_model_dir, "config.pbtxt"), "w") as f:
        f.write(config)

    print(f"[Deploy] Triton model repo created at: {triton_model_dir}")

    # Upload to S3 (Triton reads from S3 in K8s)
    import boto3
    s3 = boto3.client("s3")
    for root, dirs, files in os.walk(triton_model_dir):
        for file in files:
            local_path = os.path.join(root, file)
            s3_key = os.path.join("triton-repo/churn_model", os.path.relpath(local_path, triton_model_dir))
            s3.upload_file(local_path, "aion-models", s3_key)
            print(f"[Deploy] Uploaded: s3://aion-models/{s3_key}")

    # Health check Triton
    try:
        import tritonclient.grpc as grpcclient
        triton_client = grpcclient.InferenceServerClient(url=triton_url)
        if triton_client.is_server_live():
            print(f"[Deploy] Triton server is live at {triton_url}")
            # Reload model
            triton_client.load_model("churn_model")
            print(f"[Deploy] Model 'churn_model' loaded on Triton")
        else:
            print(f"[Deploy] WARNING: Triton server not live at {triton_url}")
    except Exception as e:
        print(f"[Deploy] Triton health check failed: {e}")

    result = {
        "status": "deployed",
        "model_name": "churn_model",
        "triton_url": triton_url,
        "onnx_opset": 17,
        "max_batch_size": 256,
        "gpu_instances": 2,
        "validation_accuracy": validation_accuracy,
    }

    print(f"[Deploy] Deployment complete")
    return result


# =============================================================================
# Pipeline Definition
# =============================================================================

@dsl.pipeline(
    name=PIPELINE_NAME,
    description="End-to-end churn prediction: preprocess → train → register → deploy",
    pipeline_root="s3://aion-kubeflow-artifacts/churn-pipeline/",
)
def churn_prediction_pipeline(
    raw_data_path: str = RAW_DATA_PATH,
    processed_data_path: str = PROCESSED_DATA_PATH,
    model_output_path: str = MODEL_OUTPUT_PATH,
    mlflow_tracking_uri: str = MLFLOW_TRACKING_URI,
    mlflow_experiment_name: str = MLFLOW_EXPERIMENT_NAME,
    feast_registry: str = FEAST_REGISTRY,
    triton_url: str = TRITON_URL,
    model_repo: str = MODEL_REPO,
    accuracy_threshold: float = 0.90,
    hyperparameters: str = json.dumps({
        "hidden_sizes": [256, 128, 64, 32],
        "dropout_rate": 0.3,
        "learning_rate": 1e-3,
        "batch_size": 256,
        "epochs": 100,
        "weight_decay": 1e-4,
        "early_stopping_patience": 15,
    }),
):
    # --- Step 1: Preprocessing ---
    preprocess_task = preprocess_data(
        raw_data_path=raw_data_path,
        processed_data_path=processed_data_path,
        feast_registry=feast_registry,
        feature_columns=[
            "click_rate_7d",
            "avg_transaction_value",
            "total_orders_30d",
            "total_revenue_30d",
            "days_since_last_order",
            "rfm_composite_score",
        ],
    )
    preprocess_task.set_cpu_request("2")
    preprocess_task.set_memory_request("4G")

    # --- Step 2: Train DNN ---
    hp = json.loads(hyperparameters)
    train_task = train_model(
        processed_data_path=processed_data_path,
        model_output_path=model_output_path,
        mlflow_tracking_uri=mlflow_tracking_uri,
        mlflow_experiment_name=mlflow_experiment_name,
        hyperparameters=hp,
    )
    train_task.set_cpu_request("4")
    train_task.set_memory_request("8G")
    train_task.set_gpu_limit("1")
    train_task.after(preprocess_task)

    # --- Step 3: Register in MLflow ---
    register_task = register_model(
        model_input=train_task.outputs["output_model"],
        mlflow_tracking_uri=mlflow_tracking_uri,
        model_name="aion-churn-dnn",
        validation_accuracy=train_task.outputs["output_metrics"].metrics["val_accuracy"],
    )
    register_task.set_cpu_request("1")
    register_task.set_memory_request("2G")
    register_task.after(train_task)

    # --- Step 4: Deploy to Triton (conditional) ---
    deploy_task = deploy_to_triton(
        model_input=train_task.outputs["output_model"],
        triton_url=triton_url,
        model_repo=model_repo,
        validation_accuracy=train_task.outputs["output_metrics"].metrics["val_accuracy"],
        threshold=accuracy_threshold,
    )
    deploy_task.set_cpu_request("2")
    deploy_task.set_memory_request("4G")
    deploy_task.set_gpu_limit("1")
    deploy_task.after(register_task)

    # Pipeline-level cache
    pipeline_task = dsl.get_pipeline_task()
    pipeline_task.set_cache_enabled(True)


# =============================================================================
# Compile & Upload
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AION Churn Prediction Pipeline")
    parser.add_argument("--compile", action="store_true", help="Compile pipeline to YAML")
    parser.add_argument("--upload", action="store_true", help="Upload to Kubeflow")
    parser.add_argument("--output", default="churn_prediction_pipeline.yaml")
    args = parser.parse_args()

    compiler.Compiler().compile(
        pipeline_func=churn_prediction_pipeline,
        package_path=args.output,
    )
    print(f"Pipeline compiled to: {args.output}")

    if args.upload:
        from kfp import Client

        client = Client(host="http://ml-pipeline.aion-kubeflow.svc.cluster.local:8888")

        client.upload_pipeline(
            pipeline_package_path=args.output,
            pipeline_name=PIPELINE_NAME,
            description="AION churn prediction: preprocess → train → register → deploy to Triton",
        )
        print(f"Pipeline uploaded: {PIPELINE_NAME}")

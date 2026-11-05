from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any


DEFAULT_CHECKPOINT_NAME = "tabpfn-v3-classifier-v3_default.ckpt"
TARGET_COLUMN = "是否为故障杆塔"


def _default_checkpoint_path() -> Path:
    configured = os.getenv("TABPFN_CLASSIFIER_MODEL_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return Path(appdata) / "tabpfn" / DEFAULT_CHECKPOINT_NAME
    return Path.home() / ".cache" / "tabpfn" / DEFAULT_CHECKPOINT_NAME


def runtime_status() -> dict[str, Any]:
    checkpoint = _default_checkpoint_path()
    dependencies = {
        name: importlib.util.find_spec(name) is not None
        for name in ("tabpfn", "torch", "sklearn", "pandas", "openpyxl")
    }
    return {
        "ready": all(dependencies.values()) and checkpoint.is_file(),
        "dependencies": dependencies,
        "checkpoint_path": str(checkpoint),
        "checkpoint_exists": checkpoint.is_file(),
        "default_repeats": 50,
        "default_splits": 5,
        "output_type": "xlsx",
    }


def _classifier_kwargs(params: dict[str, Any]) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    checkpoint = Path(str(params.get("model_path") or _default_checkpoint_path()))
    if checkpoint.is_file():
        kwargs["model_path"] = checkpoint
    device = str(params.get("device") or "").strip()
    if device:
        kwargs["device"] = device
    return kwargs


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import pandas as pd
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )
    from sklearn.model_selection import StratifiedKFold
    from tabpfn import TabPFNClassifier

    task_id = str(input_data.get("task_id") or "tabpfn_task")
    input_file = Path(str(input_data.get("input_file") or "")).resolve()
    output_dir = Path(str(input_data.get("output_dir") or input_file.parent)).resolve()
    params = input_data.get("params") or {}
    n_repeats = int(params.get("n_repeats") or 50)
    n_splits = int(params.get("n_splits") or 5)
    random_seed = int(params.get("random_seed") or 42)
    target_col = str(params.get("target_column") or TARGET_COLUMN)

    if not input_file.is_file():
        raise FileNotFoundError(f"Input weather file does not exist: {input_file}")
    if input_file.suffix.lower() not in {".xlsx", ".xls"}:
        raise ValueError("TabPFN cross-validation requires an Excel .xlsx/.xls file")
    if n_repeats < 1 or n_repeats > 100:
        raise ValueError("n_repeats must be between 1 and 100")
    if n_splits < 2 or n_splits > 10:
        raise ValueError("n_splits must be between 2 and 10")

    df = pd.read_excel(input_file, sheet_name=0, header=1)
    df = df.dropna(how="all")
    df = df.dropna(axis=1, how="all")
    df.columns = df.columns.astype(str).str.strip()
    if target_col not in df.columns:
        raise ValueError(f"Target column not found: {target_col}; columns={df.columns.tolist()}")

    y = df[target_col].astype(str).str.strip().map({
        "Y": 1,
        "N": 0,
        "是": 1,
        "否": 0,
        "1": 1,
        "0": 0,
    })
    valid_idx = y.notna()
    df = df.loc[valid_idx].copy()
    y = y.loc[valid_idx].astype(int)
    X = df.drop(columns=[target_col])
    X = X.apply(pd.to_numeric, errors="coerce")
    X = X.dropna(axis=1, how="all")
    X = X.fillna(X.median())

    if X.empty:
        raise ValueError("No numeric model features remain after cleaning")
    label_counts = y.value_counts().sort_index()
    if len(label_counts) < 2:
        raise ValueError("The target column must contain both fault and non-fault samples")
    if int(label_counts.min()) < n_splits:
        raise ValueError(
            f"The smallest class has {int(label_counts.min())} samples, less than n_splits={n_splits}"
        )

    all_results: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []
    start_time = time.time()
    classifier_kwargs = _classifier_kwargs(params)

    for repeat in range(n_repeats):
        skf = StratifiedKFold(
            n_splits=n_splits,
            shuffle=True,
            random_state=random_seed + repeat,
        )
        for fold, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
            X_train = X.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_train = y.iloc[train_idx]
            y_test = y.iloc[test_idx]

            clf = TabPFNClassifier(**classifier_kwargs)
            clf.fit(X_train, y_train)
            y_pred = clf.predict(X_test)
            y_prob = clf.predict_proba(X_test)[:, 1]

            try:
                auc = roc_auc_score(y_test, y_prob)
            except ValueError:
                auc = np.nan
            tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
            all_results.append({
                "Repeat": repeat + 1,
                "Fold": fold,
                "Accuracy": accuracy_score(y_test, y_pred),
                "Precision": precision_score(y_test, y_pred, zero_division=0),
                "Recall": recall_score(y_test, y_pred, zero_division=0),
                "F1": f1_score(y_test, y_pred, zero_division=0),
                "AUC": auc,
                "TN": int(tn),
                "FP": int(fp),
                "FN": int(fn),
                "TP": int(tp),
            })
            for idx, true_label, pred_label, probability in zip(
                test_idx,
                y_test,
                y_pred,
                y_prob,
            ):
                all_predictions.append({
                    "Repeat": repeat + 1,
                    "Fold": fold,
                    "Sample_Index": int(idx),
                    "True_Label": int(true_label),
                    "Pred_Label": int(pred_label),
                    "Fault_Probability": float(probability),
                })

    result_df = pd.DataFrame(all_results)
    pred_df = pd.DataFrame(all_predictions)
    summary_df = result_df[["Accuracy", "Precision", "Recall", "F1", "AUC"]].agg(
        ["mean", "std", "min", "max"]
    ).T.reset_index()
    summary_df.columns = ["Metric", "Mean", "Std", "Min", "Max"]
    summary_df["CI95_Lower"] = (
        summary_df["Mean"] - 1.96 * summary_df["Std"] / np.sqrt(len(result_df))
    )
    summary_df["CI95_Upper"] = (
        summary_df["Mean"] + 1.96 * summary_df["Std"] / np.sqrt(len(result_df))
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_task_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in task_id)
    output_file = output_dir / f"{safe_task_id}_tabpfn_{n_repeats}x{n_splits}_cv.xlsx"
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        result_df.to_excel(writer, sheet_name="每折结果", index=False)
        summary_df.to_excel(writer, sheet_name="总体统计", index=False)
        pred_df.to_excel(writer, sheet_name="每个样本预测结果", index=False)

    metrics = json.loads(summary_df.to_json(orient="records"))
    return {
        "task_id": task_id,
        "algorithm_id": input_data.get("algorithm_id") or "tabpfn_fault_cv",
        "algorithm_name": "TabPFN故障杆塔交叉验证",
        "status": "success",
        "result_type": "file",
        "output_file": str(output_file),
        "output_filename": output_file.name,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "sheets": ["每折结果", "总体统计", "每个样本预测结果"],
        "summary": {
            "sample_count": int(X.shape[0]),
            "feature_count": int(X.shape[1]),
            "label_distribution": {str(key): int(value) for key, value in label_counts.items()},
            "n_repeats": n_repeats,
            "n_splits": n_splits,
            "total_folds": int(n_repeats * n_splits),
            "duration_seconds": round(time.time() - start_time, 3),
            "metrics": metrics,
        },
    }

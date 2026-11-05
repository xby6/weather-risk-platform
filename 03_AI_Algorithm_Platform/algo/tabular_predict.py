from __future__ import annotations

from typing import Any

from core.model_loader import predict_tabular


def _binary_label(value: Any) -> int | None:
    if value is None or value == "":
        return None
    normalized = str(value).strip().lower()
    if normalized in {"y", "yes", "true", "是", "1", "1.0"}:
        return 1
    if normalized in {"n", "no", "false", "否", "0", "0.0"}:
        return 0
    try:
        return 1 if float(value) >= 0.5 else 0
    except (TypeError, ValueError):
        return None


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    task_id = input_data.get("task_id")
    algorithm_id = input_data.get("algorithm_id") or "tabular_predict"
    model_id = input_data.get("model_id") or algorithm_id
    params = input_data.get("params") or {}
    features = input_data.get("features") or []
    if not features:
        raise ValueError("Tabular task has no weather-file samples")

    rows: list[dict[str, Any]] = []
    model_meta: dict[str, Any] | None = None
    comparable = 0
    correct = 0
    for index, feature in enumerate(features, start=1):
        try:
            output, model_meta = predict_tabular(
                feature,
                model_id=model_id,
                algorithm_id=algorithm_id,
            )
        except Exception as exc:
            source_row = feature.get("source_row") or index
            raise RuntimeError(f"Model execution failed at source row {source_row}: {exc}") from exc

        prediction = output.get("prediction")
        probability = output.get("probability")
        actual_label = feature.get("target_label")
        predicted_binary = _binary_label(prediction)
        actual_binary = _binary_label(actual_label)
        if predicted_binary is not None and actual_binary is not None:
            comparable += 1
            correct += int(predicted_binary == actual_binary)
        rows.append({
            "sample_index": feature.get("sample_index") or index,
            "source_row": feature.get("source_row"),
            "target_label": actual_label,
            "prediction": prediction,
            "predicted_fault": bool(predicted_binary) if predicted_binary is not None else None,
            "fault_probability": probability,
            "used_real_model": True,
        })

    summary = {
        "data_mode": "weather_file_batch",
        "source_file_id": params.get("source_file_id"),
        "source_file_name": params.get("source_file_name"),
        "sample_count": len(rows),
        "feature_count": params.get("source_feature_count"),
        "target_column": params.get("target_column"),
        "target_distribution": params.get("target_distribution") or {},
        "evaluated_sample_count": comparable,
        "accuracy": round(correct / comparable, 6) if comparable else None,
        "used_real_model": bool(rows),
        "model_id": model_meta.get("model_id") if model_meta else model_id,
        "model_name": model_meta.get("algorithm_name") if model_meta else model_id,
        "model_format": model_meta.get("model_format") if model_meta else None,
        "model_error": None,
    }
    return {
        "task_id": task_id,
        "algorithm_id": algorithm_id,
        "model_id": summary["model_id"],
        "algorithm_name": summary["model_name"],
        "status": "success",
        "used_real_model": summary["used_real_model"],
        "summary": summary,
        "result": rows,
    }

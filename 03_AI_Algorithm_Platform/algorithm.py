from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


ALGORITHM_META: dict[str, Any] = {
    "algorithm_id": "standard_algorithm_template",
    "algorithm_name": "Standard Algorithm Template",
    "version": "v1.0.0",
    "algorithm_type": "tabular_forecast",
    "input_type": "file",
    "output_type": "excel_json",
    "entrypoint": "algorithm.py:run",
    "run_api": "/api/tasks/run-file",
    "description": "Unified executable algorithm template for algorithm-server uploads.",
}

RISK_LEVELS = (
    (0.25, "low"),
    (0.50, "medium"),
    (0.75, "high"),
    (1.01, "critical"),
)

NUMERIC_FEATURES = (
    "temperature",
    "humidity",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "pressure",
    "icing_thickness",
    "history_icing_thickness",
)


def _read_table(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        import pandas as pd

        return pd.read_excel(path)
    if suffix == ".csv":
        import pandas as pd

        return pd.read_csv(path)
    raise ValueError("Only .xlsx, .xls and .csv input files are supported.")


def _write_result_file(frame, output_file: Path) -> None:
    suffix = output_file.suffix.lower()
    if suffix == ".csv":
        frame.to_csv(output_file, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
        return
    with __import__("pandas").ExcelWriter(output_file, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="prediction_result", index=False)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _risk_level(probability: float) -> str:
    for limit, label in RISK_LEVELS:
        if probability < limit:
            return label
    return RISK_LEVELS[-1][1]


def _load_model(model_path: str | None) -> Any:
    if not model_path:
        return None
    path = Path(model_path)
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    if suffix in {".pkl", ".joblib"}:
        try:
            import joblib

            return joblib.load(path)
        except Exception:
            import pickle

            with path.open("rb") as source:
                return pickle.load(source)
    return None


def _predict_probability(row: dict[str, Any], model: Any, feature_order: list[str]) -> float:
    if model is not None and hasattr(model, "predict_proba"):
        values = [[_to_float(row.get(feature)) for feature in feature_order]]
        probability = float(model.predict_proba(values)[0][1])
        return max(0.0, min(1.0, probability))

    temperature = _to_float(row.get("temperature"))
    humidity = _to_float(row.get("humidity"))
    wind_speed = _to_float(row.get("wind_speed"))
    precipitation = _to_float(row.get("precipitation"))
    icing = _to_float(row.get("icing_thickness") or row.get("history_icing_thickness"))
    score = 0.18
    score += max(0.0, min(0.22, (humidity - 70.0) / 100.0))
    score += max(0.0, min(0.20, wind_speed / 40.0))
    score += max(0.0, min(0.16, precipitation / 50.0))
    score += max(0.0, min(0.18, icing / 50.0))
    if temperature <= 0:
        score += min(0.18, abs(temperature) / 40.0)
    return round(max(0.0, min(1.0, score)), 6)


def _preview_records(frame, limit: int = 50) -> list[dict[str, Any]]:
    records = frame.head(limit).to_dict(orient="records")
    return json.loads(json.dumps(records, ensure_ascii=False, default=str))


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    task_id = str(input_data.get("task_id") or "TASK_DEMO")
    params = input_data.get("params") or {}
    algorithm_id = str(input_data.get("algorithm_id") or ALGORITHM_META["algorithm_id"])
    model_id = str(input_data.get("model_id") or algorithm_id)
    input_file = Path(str(input_data.get("input_file") or "")).resolve()
    output_dir = Path(str(input_data.get("output_dir") or input_file.parent)).resolve()
    output_format = str(params.get("output_format") or "xlsx").lower()
    output_suffix = ".csv" if output_format == "csv" else ".xlsx"
    output_file = output_dir / f"{task_id}_{algorithm_id}_result{output_suffix}"

    try:
        if not input_file.is_file():
            raise FileNotFoundError(f"Input file does not exist: {input_file}")
        output_dir.mkdir(parents=True, exist_ok=True)

        frame = _read_table(input_file)
        if frame.empty:
            raise ValueError("Input file contains no records.")

        feature_order = params.get("feature_order") or list(NUMERIC_FEATURES)
        if isinstance(feature_order, str):
            feature_order = [item.strip() for item in feature_order.split(",") if item.strip()]
        model = _load_model(input_data.get("model_path") or params.get("model_path"))
        used_real_model = model is not None

        rows = frame.to_dict(orient="records")
        probabilities = [_predict_probability(row, model, list(feature_order)) for row in rows]
        result_frame = frame.copy()
        result_frame["fault_probability"] = probabilities
        result_frame["risk_level"] = [_risk_level(value) for value in probabilities]
        result_frame["used_real_model"] = used_real_model
        result_frame["algorithm_id"] = algorithm_id
        result_frame["model_id"] = model_id

        _write_result_file(result_frame, output_file)
        max_probability = float(max(probabilities))
        avg_probability = float(sum(probabilities) / len(probabilities))
        high_risk_count = sum(1 for value in probabilities if value >= 0.75)

        return {
            "success": True,
            "status": "success",
            "task_id": task_id,
            "algorithm_id": algorithm_id,
            "algorithm_name": ALGORITHM_META["algorithm_name"],
            "model_id": model_id,
            "used_real_model": used_real_model,
            "message": "Algorithm task completed.",
            "result_type": "file",
            "output_file": str(output_file),
            "output_filename": output_file.name,
            "content_type": (
                "text/csv"
                if output_suffix == ".csv"
                else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            "result": _preview_records(result_frame),
            "charts": [],
            "summary": {
                "total_records": int(len(result_frame)),
                "feature_count": int(len(feature_order)),
                "max_fault_probability": max_probability,
                "average_fault_probability": avg_probability,
                "high_risk_count": int(high_risk_count),
                "risk_distribution": {
                    label: int(sum(1 for value in probabilities if _risk_level(value) == label))
                    for _, label in RISK_LEVELS
                },
                "output_file": output_file.name,
            },
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "status": "failed",
            "task_id": task_id,
            "algorithm_id": algorithm_id,
            "algorithm_name": ALGORITHM_META["algorithm_name"],
            "model_id": model_id,
            "used_real_model": False,
            "message": "Algorithm task failed.",
            "result_type": "json",
            "output_file": "",
            "output_filename": "",
            "result": [],
            "charts": [],
            "summary": {},
            "error": str(exc),
        }

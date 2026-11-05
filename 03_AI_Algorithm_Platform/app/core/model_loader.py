from __future__ import annotations

import importlib
import json
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.model_registry import DEFAULT_FEATURE_ORDER, get_active_model_for_algorithm, get_model


def normalize_feature(row: dict[str, Any] | None) -> dict[str, float]:
    row = row or {}
    alias = {
        "temperature": ["temperature", "temp", "T", "温度"],
        "humidity": ["humidity", "rh", "RH", "相对湿度", "湿度"],
        "wind_speed": ["wind_speed", "windSpeed", "ws", "风速"],
        "wind_direction": ["wind_direction", "windDirection", "wd", "风向"],
        "precipitation": ["precipitation", "rain", "rainfall", "降水", "降水量"],
        "history_icing_thickness": [
            "history_icing_thickness",
            "historyIcingThickness",
            "icing_thickness",
            "icingThickness",
            "history_icing",
            "ice",
            "历史覆冰厚度",
            "覆冰厚度",
        ],
    }
    out: dict[str, float] = {}
    for key, names in alias.items():
        value = None
        for name in names:
            if name in row and row.get(name) not in (None, ""):
                value = row.get(name)
                break
        try:
            out[key] = float(value) if value not in (None, "") else 0.0
        except Exception:
            out[key] = 0.0
    out["icing_thickness"] = out["history_icing_thickness"]
    return out


def feature_vector(row: dict[str, Any], feature_order: list[str] | None = None) -> list[float]:
    order = feature_order or DEFAULT_FEATURE_ORDER
    if order == ["__file_columns__"]:
        values = row.get("tabular_values")
        if not isinstance(values, list) or not values:
            raise ValueError("The model expects weather-file columns, but tabular_values is empty")
        try:
            return [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise ValueError("tabular_values contains a non-numeric feature") from exc
    normalized = normalize_feature(row)
    return [float(normalized.get(name, 0.0)) for name in order]


def _load_joblib_or_pickle(path: Path) -> Any:
    try:
        joblib = importlib.import_module("joblib")
        return joblib.load(path)
    except Exception:
        with path.open("rb") as file:
            return pickle.load(file)


@lru_cache(maxsize=32)
def load_model_cached(model_path: str, model_format: str = "") -> Any:
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"模型文件不存在：{path}")
    fmt = (model_format or path.suffix.lower().lstrip(".")).lower()

    if fmt == "json":
        return json.loads(path.read_text(encoding="utf-8"))
    if fmt in {"pkl", "pickle", "joblib"}:
        return _load_joblib_or_pickle(path)
    if fmt in {"pt", "pth"}:
        torch = importlib.import_module("torch")
        try:
            return torch.jit.load(str(path), map_location="cpu")
        except Exception:
            return torch.load(str(path), map_location="cpu")
    raise ValueError(f"暂不支持的模型格式：{fmt}。当前支持 json、pkl、joblib、pt、pth")


def _weight_for(weights: dict[str, Any], name: str) -> float:
    if name in weights:
        return float(weights.get(name) or 0.0)
    if name == "history_icing_thickness" and "icing_thickness" in weights:
        return float(weights.get("icing_thickness") or 0.0)
    if name == "icing_thickness" and "history_icing_thickness" in weights:
        return float(weights.get("history_icing_thickness") or 0.0)
    return 0.0


def _predict_json_linear(model: dict[str, Any], features: dict[str, Any], order: list[str]) -> float:
    model_type = str(model.get("model_type") or model.get("type") or "linear_icing")
    if model_type not in {"linear_icing", "linear", "formula"}:
        raise ValueError(f"JSON 模型 model_type={model_type} 不支持，请使用 linear_icing")
    weights = model.get("weights") or model.get("coef") or model.get("coefficients") or {}
    if not isinstance(weights, dict):
        raise ValueError("JSON 线性模型 weights 必须是对象")
    intercept = float(model.get("intercept") or model.get("bias") or 0.0)
    xmap = normalize_feature(features)
    value = intercept
    for name in order:
        value += _weight_for(weights, name) * float(xmap.get(name, 0.0))
    if model.get("output_transform") in ("clip_nonnegative", "nonnegative", None):
        value = max(0.0, value)
    return float(value)


def _predict_estimator(model: Any, vector: list[float]) -> float:
    if hasattr(model, "predict"):
        pred = model.predict([vector])
        if hasattr(pred, "tolist"):
            pred = pred.tolist()
        if isinstance(pred, list):
            first = pred[0]
            if isinstance(first, (list, tuple)):
                first = first[0]
            return float(first)
        return float(pred)

    if callable(model):
        torch = importlib.import_module("torch")
        if hasattr(model, "eval"):
            model.eval()
        with torch.no_grad():
            tensor = torch.tensor([vector], dtype=torch.float32)
            pred = model(tensor)
            if hasattr(pred, "detach"):
                pred = pred.detach().cpu().numpy().tolist()
        if isinstance(pred, list):
            first = pred[0]
            if isinstance(first, (list, tuple)):
                first = first[0]
            return float(first)
        return float(pred)

    raise ValueError("模型对象缺少 predict 方法，也不是可调用 PyTorch 模型")


def _scalar(value: Any) -> Any:
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, (list, tuple)):
        return _scalar(value[0]) if value else None
    return value


def _predict_tabular_estimator(model: Any, vector: list[float]) -> tuple[Any, float | None]:
    if not hasattr(model, "predict"):
        raise ValueError("Tabular model object does not provide predict")
    prediction = _scalar(model.predict([vector]))
    probability = None
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba([vector])
        if hasattr(probabilities, "tolist"):
            probabilities = probabilities.tolist()
        first_row = probabilities[0] if isinstance(probabilities, list) and probabilities else probabilities
        if isinstance(first_row, (list, tuple)) and first_row:
            probability = float(first_row[-1])
    return prediction, probability


def resolve_icing_model(model_id: str | None = None, algorithm_id: str | None = None) -> dict[str, Any] | None:
    model = get_model(model_id=model_id, algorithm_id=algorithm_id)
    if model and str(model.get("status") or "enabled") == "enabled":
        return model
    return get_active_model_for_algorithm(algorithm_id=algorithm_id, algorithm_type="icing")


def predict_icing(
    features: dict[str, Any],
    model_id: str | None = None,
    algorithm_id: str | None = None,
) -> tuple[float, dict[str, Any]]:
    model_meta = resolve_icing_model(model_id=model_id, algorithm_id=algorithm_id)
    if not model_meta:
        raise RuntimeError("未找到可用的覆冰预测模型，请先在算力平台上传 algorithm_type=icing 的模型")

    order = model_meta.get("feature_order") or DEFAULT_FEATURE_ORDER
    if isinstance(order, str):
        order = [item.strip() for item in order.split(",") if item.strip()]
    if not order:
        order = DEFAULT_FEATURE_ORDER

    model_path = str(model_meta.get("model_path") or "")
    model_format = str(model_meta.get("model_format") or "")
    loaded = load_model_cached(model_path, model_format)
    if isinstance(loaded, dict):
        value = _predict_json_linear(loaded, features, order)
    else:
        value = _predict_estimator(loaded, feature_vector(features, order))
    return max(0.0, float(value)), model_meta


def predict_tabular(
    features: dict[str, Any],
    model_id: str | None = None,
    algorithm_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    model_meta = get_model(model_id=model_id, algorithm_id=algorithm_id)
    if not model_meta or str(model_meta.get("status") or "enabled") != "enabled":
        raise RuntimeError("No enabled uploaded tabular model was found")

    order = model_meta.get("feature_order") or ["__file_columns__"]
    if isinstance(order, str):
        order = [item.strip() for item in order.split(",") if item.strip()]
    model_path = str(model_meta.get("model_path") or "")
    model_format = str(model_meta.get("model_format") or "")
    loaded = load_model_cached(model_path, model_format)
    if isinstance(loaded, dict):
        prediction = _predict_json_linear(loaded, features, order)
        probability = None
    else:
        prediction, probability = _predict_tabular_estimator(loaded, feature_vector(features, order))
    return {"prediction": prediction, "probability": probability}, model_meta

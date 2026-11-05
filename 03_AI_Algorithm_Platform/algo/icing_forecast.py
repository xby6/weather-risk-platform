from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

try:
    from core.model_loader import normalize_feature, predict_icing
except Exception:
    normalize_feature = None
    predict_icing = None


def _risk_level(icing: float) -> str:
    if icing < 10:
        return "蓝色"
    if icing < 20:
        return "黄色"
    if icing < 30:
        return "橙色"
    return "红色"


def _fallback_rule_predict(feature: dict[str, Any], step: int) -> float:
    temp = float(feature.get("temperature") or 0)
    humidity = float(feature.get("humidity") or 0)
    wind_speed = float(feature.get("wind_speed") or 0)
    precipitation = float(feature.get("precipitation") or 0)
    ice = float(feature.get("history_icing_thickness") or feature.get("icing_thickness") or 0)

    growth = 0.0
    if temp < 0 and humidity >= 85:
        growth += min(1.2, abs(temp) * 0.08 + (humidity - 85) * 0.02)
    if precipitation > 0:
        growth += min(1.0, precipitation * 0.2)
    if wind_speed > 3:
        growth += min(0.4, (wind_speed - 3) * 0.05)
    return max(0.0, ice + growth + step * 0.02)


def _parse_start_time(features: list[dict[str, Any]]) -> datetime:
    if features and features[0].get("time"):
        raw = str(features[0]["time"])
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(raw[:19], fmt)
            except Exception:
                pass
    return datetime.now()


def _feature_from_params(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": params.get("temperature"),
        "humidity": params.get("humidity"),
        "wind_speed": params.get("wind_speed") or params.get("windSpeed"),
        "wind_direction": params.get("wind_direction") or params.get("windDirection"),
        "precipitation": params.get("precipitation"),
        "history_icing_thickness": (
            params.get("history_icing_thickness")
            if params.get("history_icing_thickness") not in (None, "")
            else params.get("historyIcingThickness")
            if params.get("historyIcingThickness") not in (None, "")
            else params.get("icingThickness")
            if params.get("icingThickness") not in (None, "")
            else params.get("icing_thickness")
        ),
    }


def _run_batch(
    input_data: dict[str, Any],
    features: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    task_id = input_data.get("task_id")
    algorithm_id = input_data.get("algorithm_id") or "icing_forecast"
    model_id = input_data.get("model_id") or algorithm_id
    region = input_data.get("region") or ""
    line_code = input_data.get("line_code") or ""
    rows: list[dict[str, Any]] = []
    model_meta: dict[str, Any] | None = None

    if predict_icing is None:
        raise RuntimeError("Model loader is unavailable")

    for index, feature in enumerate(features, start=1):
        try:
            prediction, model_meta = predict_icing(
                feature,
                model_id=model_id,
                algorithm_id=algorithm_id,
            )
        except Exception as exc:
            source_row = feature.get("source_row") or index
            raise RuntimeError(f"Model execution failed at source row {source_row}: {exc}") from exc

        prediction = round(float(prediction), 6)
        risk = _risk_level(prediction)
        rows.append({
            "sample_index": feature.get("sample_index") or index,
            "source_row": feature.get("source_row"),
            "target_label": feature.get("target_label"),
            "prediction": prediction,
            "future_icing_thickness": prediction,
            "risk_level": risk,
            "region": region,
            "line_code": line_code,
            "used_real_model": True,
        })

    predictions = [row["prediction"] for row in rows]
    summary = {
        "data_mode": "weather_file_batch",
        "source_file_id": params.get("source_file_id"),
        "source_file_name": params.get("source_file_name"),
        "sample_count": len(rows),
        "feature_count": params.get("source_feature_count"),
        "target_column": params.get("target_column"),
        "target_distribution": params.get("target_distribution") or {},
        "prediction_min": min(predictions) if predictions else None,
        "prediction_max": max(predictions) if predictions else None,
        "prediction_mean": round(sum(predictions) / len(predictions), 6) if predictions else None,
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
        "algorithm_name": model_meta.get("algorithm_name") if model_meta else algorithm_id,
        "status": "success",
        "used_real_model": summary["used_real_model"],
        "summary": summary,
        "result": rows,
    }


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    task_id = input_data.get("task_id")
    algorithm_id = input_data.get("algorithm_id") or "icing_forecast"
    model_id = input_data.get("model_id") or algorithm_id
    line_code = input_data.get("line_code") or ""
    region = input_data.get("region") or ""
    forecast_hours = int(input_data.get("forecast_hours") or 24)
    features = input_data.get("features") or []
    params = input_data.get("params") or {}

    if not features:
        features = [_feature_from_params(params)]
    if params.get("batch_mode"):
        return _run_batch(input_data, features, params)

    start_time = _parse_start_time(features)
    latest = dict(features[-1] if features else {})
    if latest.get("history_icing_thickness") in (None, "") and latest.get("icing_thickness") not in (None, ""):
        latest["history_icing_thickness"] = latest.get("icing_thickness")

    used_real_model = False
    model_meta: dict[str, Any] | None = None
    model_error = None
    series: list[dict[str, Any]] = []
    current_feature = dict(latest)

    for step in range(forecast_hours):
        try:
            if predict_icing is None:
                raise RuntimeError("模型加载器不可用")
            pred, model_meta = predict_icing(current_feature, model_id=model_id, algorithm_id=algorithm_id)
            used_real_model = True
        except Exception as exc:
            if not used_real_model:
                model_error = str(exc)
            if normalize_feature:
                current_feature = normalize_feature(current_feature)
            pred = _fallback_rule_predict(current_feature, step)

        time_point = start_time + timedelta(hours=step + 1)
        pred = round(float(pred), 3)
        risk = _risk_level(pred)
        series.append({
            "time": time_point.strftime("%Y-%m-%d %H:%M:%S"),
            "region": region,
            "line_code": line_code,
            "future_icing_thickness": pred,
            "icing_thickness": pred,
            "risk_level": risk,
            "risk_label": risk,
            "used_real_model": used_real_model,
        })
        current_feature = dict(current_feature)
        current_feature["history_icing_thickness"] = pred
        current_feature["icing_thickness"] = pred

    max_item = max(series, key=lambda item: item["future_icing_thickness"]) if series else None
    final_item = series[-1] if series else None
    summary = {
        "region": region,
        "line_code": line_code,
        "forecast_hours": forecast_hours,
        "future_icing_thickness": final_item["future_icing_thickness"] if final_item else 0,
        "max_icing_thickness": max_item["future_icing_thickness"] if max_item else 0,
        "risk_level": max_item["risk_level"] if max_item else "蓝色",
        "max_risk_level": max_item["risk_level"] if max_item else "蓝色",
        "used_real_model": used_real_model,
        "model_id": model_meta.get("model_id") if model_meta else model_id,
        "model_name": model_meta.get("algorithm_name") if model_meta else "规则兜底",
        "model_format": model_meta.get("model_format") if model_meta else "rule_fallback",
        "model_error": None if used_real_model else model_error,
    }

    return {
        "task_id": task_id,
        "algorithm_id": algorithm_id,
        "model_id": summary["model_id"],
        "algorithm_name": "输电线路覆冰厚度预测模型",
        "status": "success",
        "future_icing_thickness": summary["future_icing_thickness"],
        "risk_level": summary["risk_level"],
        "used_real_model": used_real_model,
        "summary": summary,
        "result": series,
    }

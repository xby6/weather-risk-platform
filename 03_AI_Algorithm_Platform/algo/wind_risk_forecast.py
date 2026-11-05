from __future__ import annotations

from datetime import datetime, timedelta
import random
from typing import Any


def _risk_level(wind_speed: float) -> str:
    if wind_speed < 8:
        return "蓝色"
    if wind_speed < 12:
        return "黄色"
    if wind_speed < 17:
        return "橙色"
    return "红色"


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    task_id = input_data.get("task_id")
    line_code = input_data.get("line_code") or "90-91"
    region = input_data.get("region") or "辽宁"
    forecast_hours = int(input_data.get("forecast_hours") or 24)
    features = input_data.get("features") or []
    start_time = datetime.now()
    base_wind = 6.0
    if features:
        latest = features[-1]
        base_wind = float(latest.get("wind_speed") or 6.0)
        if latest.get("time"):
            try:
                start_time = datetime.strptime(latest["time"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

    result = []
    for i in range(forecast_hours):
        t = start_time + timedelta(hours=i + 1)
        wind = max(0, base_wind + random.uniform(-1.5, 3.0))
        result.append({
            "time": t.strftime("%Y-%m-%d %H:%M:%S"),
            "region": region,
            "line_code": line_code,
            "wind_speed": round(wind, 2),
            "risk_level": _risk_level(wind),
        })
    max_item = max(result, key=lambda x: x["wind_speed"]) if result else None
    return {
        "task_id": task_id,
        "algorithm_id": "wind_risk_forecast",
        "algorithm_name": "大风风险预测模型",
        "status": "success",
        "summary": {
            "region": region,
            "line_code": line_code,
            "max_wind_speed": max_item["wind_speed"] if max_item else 0,
            "max_risk_level": max_item["risk_level"] if max_item else "蓝色",
        },
        "result": result,
    }

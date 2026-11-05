from __future__ import annotations

from datetime import datetime, timedelta
import random
from typing import Any

LEVELS = ["蓝色", "黄色", "橙色", "红色"]


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    task_id = input_data.get("task_id")
    line_code = input_data.get("line_code") or "90-91"
    region = input_data.get("region") or "辽宁"
    forecast_hours = int(input_data.get("forecast_hours") or 24)
    start_time = datetime.now()
    result = []
    for i in range(forecast_hours):
        risk_score = min(100, max(0, 35 + i * 1.2 + random.uniform(-8, 12)))
        if risk_score < 40:
            level = "蓝色"
        elif risk_score < 60:
            level = "黄色"
        elif risk_score < 80:
            level = "橙色"
        else:
            level = "红色"
        result.append({
            "time": (start_time + timedelta(hours=i + 1)).strftime("%Y-%m-%d %H:%M:%S"),
            "region": region,
            "line_code": line_code,
            "risk_score": round(risk_score, 2),
            "risk_level": level,
        })
    max_item = max(result, key=lambda x: x["risk_score"]) if result else None
    return {
        "task_id": task_id,
        "algorithm_id": "comprehensive_risk",
        "algorithm_name": "综合电力气象风险评估模型",
        "status": "success",
        "summary": {
            "region": region,
            "line_code": line_code,
            "max_risk_score": max_item["risk_score"] if max_item else 0,
            "max_risk_level": max_item["risk_level"] if max_item else "蓝色",
        },
        "result": result,
    }

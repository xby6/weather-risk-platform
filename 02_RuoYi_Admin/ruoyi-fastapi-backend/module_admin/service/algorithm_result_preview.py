from __future__ import annotations

from pathlib import Path
from typing import Any


PREDICTION_SHEET = '未来故障预测'
RISK_SHEET = '概率等级统计'
FOLD_SHEET = '每折结果'
SUMMARY_SHEET = '总体统计'
RISK_LEVELS = ('低', '一般', '较高', '高')
MAX_PREVIEW_ROWS = 5000


def _number(value: Any, digits: int | None = None) -> float | None:
    if value in (None, ''):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float('inf'), float('-inf')):
        return None
    return round(number, digits) if digits is not None else number


def _integer(value: Any) -> int:
    number = _number(value)
    return int(number) if number is not None else 0


def _text(value: Any) -> str:
    if value in (None, ''):
        return ''
    try:
        if value != value:
            return ''
    except Exception:
        pass
    if hasattr(value, 'strftime'):
        try:
            return value.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    return str(value).strip()


def _prediction_rows(frame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in frame.head(MAX_PREVIEW_ROWS).to_dict(orient='records'):
        probability = _number(record.get('故障概率'))
        probability_percent = _number(record.get('故障概率(%)'), 3)
        if probability is None and probability_percent is not None:
            probability = probability_percent / 100
        if probability_percent is None and probability is not None:
            probability_percent = round(probability * 100, 3)
        rows.append(
            {
                'point_index': _integer(record.get('点位序号')),
                'city': _text(record.get('运行单位')),
                'line_name': _text(record.get('线路名称')),
                'tower_code': _text(record.get('杆塔编号')),
                'forecast_hour': _integer(record.get('预测时效(h)')),
                'forecast_time': _text(record.get('预测时间')),
                'temperature': _number(record.get('温度'), 3),
                'humidity': _number(record.get('湿度'), 3),
                'wind_speed': _number(record.get('风速'), 3),
                'precipitation': _number(record.get('小时降水'), 3),
                'predicted_fault': _text(record.get('预测是否故障')),
                'fault_probability': _number(probability, 6),
                'probability_percent': probability_percent,
                'risk_level': _text(record.get('概率等级')),
            }
        )
    return rows


def _risk_rows(frame, predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[str, tuple[int, float]] = {}
    if frame is not None:
        for record in frame.to_dict(orient='records'):
            level = _text(record.get('概率等级'))
            if not level:
                continue
            values[level] = (
                _integer(record.get('记录数')),
                _number(record.get('占比'), 6) or 0.0,
            )
    if not values:
        total = len(predictions)
        for level in RISK_LEVELS:
            count = sum(1 for row in predictions if row.get('risk_level') == level)
            values[level] = (count, count / total if total else 0.0)
    return [
        {'risk_level': level, 'count': values.get(level, (0, 0.0))[0], 'ratio': values.get(level, (0, 0.0))[1]}
        for level in RISK_LEVELS
    ]


def _hourly_chart(predictions: list[dict[str, Any]]) -> dict[str, list[Any]]:
    grouped: dict[int, list[float]] = {}
    for row in predictions:
        hour = int(row.get('forecast_hour') or 0)
        probability = _number(row.get('fault_probability'))
        if hour > 0 and probability is not None:
            grouped.setdefault(hour, []).append(probability)
    hours = sorted(grouped)
    return {
        'hours': hours,
        'average': [round(sum(grouped[hour]) / len(grouped[hour]) * 100, 3) for hour in hours],
        'maximum': [round(max(grouped[hour]) * 100, 3) for hour in hours],
    }


def _metric_chart(frame) -> list[dict[str, Any]]:
    if frame is None:
        return []
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient='records'):
        name = _text(record.get('Metric'))
        value = _number(record.get('Mean'), 6)
        if name and value is not None:
            rows.append({'name': name, 'value': value})
    return rows


def _confusion_chart(frame) -> dict[str, int]:
    if frame is None:
        return {'tn': 0, 'fp': 0, 'fn': 0, 'tp': 0}
    return {
        key.lower(): int(frame[key].fillna(0).sum()) if key in frame.columns else 0
        for key in ('TN', 'FP', 'FN', 'TP')
    }


def build_algorithm_result_preview(path: Path) -> dict[str, Any]:
    import pandas as pd

    result_path = path.resolve()
    if not result_path.is_file() or result_path.suffix.lower() not in {'.xlsx', '.xls'}:
        return {'available': False, 'message': '算法结果文件不存在或不是 Excel 文件'}

    with pd.ExcelFile(result_path) as workbook:
        sheet_names = set(workbook.sheet_names)
        if PREDICTION_SHEET not in sheet_names:
            return {'available': False, 'message': '结果文件中没有“未来故障预测”工作表'}

        prediction_frame = pd.read_excel(workbook, sheet_name=PREDICTION_SHEET)
        risk_frame = pd.read_excel(workbook, sheet_name=RISK_SHEET) if RISK_SHEET in sheet_names else None
        fold_frame = pd.read_excel(workbook, sheet_name=FOLD_SHEET) if FOLD_SHEET in sheet_names else None
        summary_frame = pd.read_excel(workbook, sheet_name=SUMMARY_SHEET) if SUMMARY_SHEET in sheet_names else None

    predictions = _prediction_rows(prediction_frame)
    risks = _risk_rows(risk_frame, predictions)
    return {
        'available': True,
        'prediction_total': int(len(prediction_frame)),
        'prediction_truncated': len(prediction_frame) > len(predictions),
        'predictions': predictions,
        'risk_statistics': risks,
        'charts': {
            'hourly_probability': _hourly_chart(predictions),
            'risk_distribution': [
                {'name': row['risk_level'], 'value': row['count']} for row in risks
            ],
            'validation_metrics': _metric_chart(summary_frame),
            'confusion_matrix': _confusion_chart(fold_frame),
        },
    }

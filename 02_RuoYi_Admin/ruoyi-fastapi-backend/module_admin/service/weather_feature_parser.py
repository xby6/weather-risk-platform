from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd


MAX_SAMPLE_COUNT = 5000
MAX_FEATURE_COUNT = 1000
TARGET_ALIASES = {"是否为故障杆塔", "target", "label", "fault", "is_fault"}


def _clean_name(value: Any, index: int) -> str:
    name = str(value or "").strip()
    if not name or name.lower().startswith("unnamed:"):
        return f"field_{index + 1}"
    return name


def _read_csv(path: Path, header: int | None, nrows: int | None = None) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return pd.read_csv(path, header=header, nrows=nrows, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError("CSV file could not be read")


def _read_table(path: Path, header: int | None, nrows: int | None = None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path, header=header, nrows=nrows)
    if suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=0, header=header, nrows=nrows, engine="openpyxl")
    raise ValueError(f"Unsupported weather file type: {suffix or 'unknown'}; use .xlsx or .csv")


def _detect_header_row(path: Path) -> int:
    preview = _read_table(path, header=None, nrows=5)
    if preview.empty:
        raise ValueError("Weather file is empty")

    best_index = 0
    best_score = -1
    for row_index, row in preview.iterrows():
        values = [str(value).strip() for value in row.tolist() if pd.notna(value) and str(value).strip()]
        if any(value in TARGET_ALIASES for value in values):
            return int(row_index)
        text_count = sum(1 for value in values if not _is_number(value))
        score = len(values) + text_count * 2
        if score > best_score:
            best_index = int(row_index)
            best_score = score
    return best_index


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _find_column(columns: list[str], *aliases: str) -> str | None:
    lowered = [(column, column.strip().lower()) for column in columns]
    for alias in aliases:
        target = alias.lower()
        for column, normalized in lowered:
            if normalized == target:
                return column
    for alias in aliases:
        target = alias.lower()
        for column, normalized in lowered:
            if target in normalized:
                return column
    return None


def _number(row: pd.Series, column: str | None, default: float = 0.0) -> float:
    if not column:
        return default
    value = row.get(column)
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _wind_direction(u_wind: float, v_wind: float) -> float:
    if u_wind == 0 and v_wind == 0:
        return 0.0
    return round((270.0 - math.degrees(math.atan2(v_wind, u_wind))) % 360.0, 3)


def _target_distribution(values: pd.Series | None) -> dict[str, int]:
    if values is None:
        return {}
    counts = values.dropna().astype(str).str.strip().value_counts()
    return {str(key): int(value) for key, value in counts.items()}


def parse_weather_dataset(
    file_path: str | Path,
    *,
    include_samples: bool = True,
    max_samples: int = MAX_SAMPLE_COUNT,
) -> dict[str, Any]:
    path = Path(file_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Weather file does not exist: {path}")

    header_row = _detect_header_row(path)
    frame = _read_table(path, header=header_row)
    frame = frame.dropna(how="all").dropna(axis=1, how="all")
    frame.columns = [_clean_name(value, index) for index, value in enumerate(frame.columns)]
    if frame.empty:
        raise ValueError("Weather file has no data rows")

    target_column = next((column for column in frame.columns if column.strip().lower() in TARGET_ALIASES), None)
    target_values = frame[target_column] if target_column else None
    feature_columns = [column for column in frame.columns if column != target_column]
    numeric = frame[feature_columns].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(axis=1, how="all")
    if numeric.shape[1] == 0:
        raise ValueError("Weather file has no numeric model features")
    if numeric.shape[1] > MAX_FEATURE_COUNT:
        raise ValueError(f"Feature count {numeric.shape[1]} exceeds limit {MAX_FEATURE_COUNT}")
    if len(numeric) > max_samples:
        raise ValueError(f"Sample count {len(numeric)} exceeds limit {max_samples}")

    numeric = numeric.fillna(numeric.median(numeric_only=True)).fillna(0.0)
    columns = [str(column) for column in numeric.columns]
    temperature_col = _find_column(columns, "温度", "temperature", "temp")
    humidity_col = _find_column(columns, "湿度", "humidity", "relative_humidity", "rh")
    precipitation_col = _find_column(columns, "小时降水", "降水", "precipitation", "rainfall")
    wind_speed_col = _find_column(columns, "风速", "wind_speed", "windspeed")
    wind_direction_col = _find_column(columns, "风向", "wind_direction", "winddirection")
    u_wind_col = _find_column(columns, "u风", "u_wind")
    v_wind_col = _find_column(columns, "v风", "v_wind")
    icing_col = _find_column(columns, "历史覆冰厚度", "覆冰厚度", "history_icing_thickness", "icing_thickness")

    samples: list[dict[str, Any]] = []
    if include_samples:
        for position, (_, row) in enumerate(numeric.iterrows()):
            u_wind = _number(row, u_wind_col)
            v_wind = _number(row, v_wind_col)
            label = None
            if target_values is not None:
                raw_label = target_values.iloc[position]
                if pd.notna(raw_label):
                    label = str(raw_label).strip()
            samples.append({
                "sample_index": position + 1,
                "source_row": header_row + position + 2,
                "temperature": _number(row, temperature_col),
                "humidity": _number(row, humidity_col),
                "wind_speed": _number(row, wind_speed_col),
                "wind_direction": _number(row, wind_direction_col, _wind_direction(u_wind, v_wind)),
                "precipitation": _number(row, precipitation_col),
                "history_icing_thickness": _number(row, icing_col),
                "icing_thickness": _number(row, icing_col),
                "target_label": label,
                "tabular_values": [float(value) for value in row.tolist()],
            })

    return {
        "file_path": str(path),
        "file_name": path.name,
        "header_row": header_row + 1,
        "record_count": int(len(numeric)),
        "field_count": int(len(columns) + (1 if target_column else 0)),
        "feature_count": int(len(columns)),
        "fields": ([target_column] if target_column else []) + columns,
        "feature_names": columns,
        "target_column": target_column,
        "target_distribution": _target_distribution(target_values),
        "samples": samples,
    }

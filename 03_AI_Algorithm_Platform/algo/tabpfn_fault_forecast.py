from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from algo.tabpfn_fault_cv import TARGET_COLUMN, _classifier_kwargs, runtime_status as cv_runtime_status


ALGORITHM_ID = "tabpfn_fault_forecast"
ALGORITHM_NAME = "TabPFN杆塔故障概率预测"
HORIZON_COLUMNS = (
    "预测时效(h)",
    "预测时效（h）",
    "预测时效",
    "时效(h)",
    "时效（h）",
    "时效",
    "forecast_hour",
    "forecast_hours",
)
RISK_LABELS = ("低", "一般", "较高", "高")
WEATHER_FEATURE_PAIRS = (
    ("温度", "温度（℃）"),
    ("湿度", "湿度（%）"),
    ("比湿", "比湿（g/kg）"),
    ("小时降水", "小时降水（mm）"),
    ("风速", "风速（m/s）"),
    ("U风", "U风（m/s）"),
    ("V风", "V风（m/s）"),
)
CURRENT_TO_SEQUENCE = dict(WEATHER_FEATURE_PAIRS)
SEQUENCE_TO_CURRENT = {sequence: current for current, sequence in WEATHER_FEATURE_PAIRS}


def runtime_status() -> dict[str, Any]:
    import importlib.util

    status = cv_runtime_status()
    status["dependencies"] = {
        **status.get("dependencies", {}),
        "matplotlib": importlib.util.find_spec("matplotlib") is not None,
    }
    status["ready"] = bool(status.get("checkpoint_exists")) and all(status["dependencies"].values())
    status["output_type"] = "xlsx_with_charts"
    return status


def _read_excel(path: Path, header_row: int):
    import pandas as pd

    frame = pd.read_excel(path, sheet_name=0, header=header_row - 1)
    frame = frame.dropna(how="all").dropna(axis=1, how="all")
    frame.columns = frame.columns.astype(str).str.strip()
    return frame


def _read_training_excel(path: Path, target_col: str, preferred_header_row: int):
    candidates = [preferred_header_row, *[row for row in range(1, 6) if row != preferred_header_row]]
    for header_row in candidates:
        frame = _read_excel(path, header_row)
        if target_col in frame.columns:
            return frame, header_row
    raise ValueError(f"训练文件前 5 行中未找到目标列：{target_col}")


def _read_prediction_excel(path: Path, feature_columns: list[str], preferred_header_row: int):
    candidates = [preferred_header_row, *[row for row in range(1, 6) if row != preferred_header_row]]
    best_frame = None
    best_header_row = preferred_header_row
    best_score = -1
    feature_set = set(feature_columns)
    for header_row in candidates:
        frame = _read_excel(path, header_row)
        score = len(feature_set.intersection(frame.columns))
        if score > best_score:
            best_frame = frame
            best_header_row = header_row
            best_score = score
        if score == len(feature_columns):
            break
    if best_frame is None:
        raise ValueError("无法读取待预测 Excel 文件")
    return best_frame, best_header_row


def _target_values(series):
    return series.astype(str).str.strip().map({
        "Y": 1,
        "N": 0,
        "是": 1,
        "否": 0,
        "1": 1,
        "0": 0,
        "1.0": 1,
        "0.0": 0,
    })


def _prepare_training(frame, target_col: str):
    import pandas as pd

    if target_col not in frame.columns:
        raise ValueError(f"训练文件缺少目标列：{target_col}")
    labels = _target_values(frame[target_col])
    valid_rows = labels.notna()
    if not valid_rows.any():
        raise ValueError(f"训练文件目标列 {target_col} 没有可识别的 Y/N、是/否或 1/0 标签")

    labels = labels.loc[valid_rows].astype(int)
    raw_features = frame.loc[valid_rows].drop(columns=[target_col])
    numeric_features = raw_features.apply(pd.to_numeric, errors="coerce")
    numeric_features = numeric_features.dropna(axis=1, how="all")
    if numeric_features.empty:
        raise ValueError("训练文件清洗后没有可用数值特征")

    medians = numeric_features.median().fillna(0.0)
    numeric_features = numeric_features.fillna(medians).astype(float)
    label_counts = labels.value_counts().sort_index()
    if len(label_counts) < 2:
        raise ValueError("训练文件必须同时包含故障和非故障样本")
    return numeric_features, labels, medians, label_counts


def _filter_forecast_horizon(frame, forecast_hours: int):
    import pandas as pd

    for column in HORIZON_COLUMNS:
        if column not in frame.columns:
            continue
        horizon = pd.to_numeric(frame[column], errors="coerce")
        mask = horizon.gt(0) & horizon.le(forecast_hours)
        if mask.any():
            return frame.loc[mask].copy(), column
    return frame.copy(), None


def _prepare_prediction(frame, feature_columns: list[str], medians):
    import pandas as pd

    missing = [column for column in feature_columns if column not in frame.columns]
    if missing:
        preview = "、".join(missing[:12])
        suffix = "……" if len(missing) > 12 else ""
        raise ValueError(f"待预测文件缺少 {len(missing)} 个训练特征：{preview}{suffix}")
    numeric = frame.reindex(columns=feature_columns).apply(pd.to_numeric, errors="coerce")
    numeric = numeric.fillna(medians).astype(float)
    if numeric.empty:
        raise ValueError("待预测文件没有可预测记录")
    return numeric


def _sequence_feature(column: str) -> tuple[str, int] | None:
    for base in SEQUENCE_TO_CURRENT:
        if column == base:
            return base, 1
        match = re.fullmatch(rf"{re.escape(base)}\.(\d+)", column)
        if match:
            return base, int(match.group(1)) + 1
    return None


def _sequence_columns(columns) -> dict[tuple[str, int], str]:
    result: dict[tuple[str, int], str] = {}
    for column in columns:
        parsed = _sequence_feature(str(column))
        if parsed:
            result[parsed] = str(column)
    return result


def _forecast_time(start_value, horizon: int):
    import pandas as pd

    timestamp = pd.to_datetime(start_value, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp + pd.Timedelta(hours=horizon - 1)


def _expand_wide_hourly_prediction(frame, feature_columns: list[str], medians, forecast_hours: int):
    import pandas as pd

    sequence_columns = _sequence_columns(frame.columns)
    available_hours = sorted({hour for base, hour in sequence_columns if base == "温度（℃）"})
    current_features = [current for current, _ in WEATHER_FEATURE_PAIRS if current in frame.columns]
    if len(available_hours) < 2 or not current_features:
        return None

    max_available_hour = max(available_hours)
    hours = min(forecast_hours, max_available_hour)
    feature_set = set(feature_columns)
    weather_columns = {
        column
        for column in frame.columns
        if column in CURRENT_TO_SEQUENCE or _sequence_feature(str(column)) is not None
    }
    metadata_columns = [
        column
        for column in frame.columns
        if column not in weather_columns and column not in HORIZON_COLUMNS
    ]
    lag_hours = [parsed[1] for column in feature_columns if (parsed := _sequence_feature(column))]
    max_lag = max(lag_hours, default=0)
    model_rows: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []

    for _, source_row in frame.iterrows():
        for horizon in range(1, hours + 1):
            model_row: dict[str, Any] = {}
            for feature in feature_columns:
                if feature in CURRENT_TO_SEQUENCE:
                    source_column = sequence_columns.get((CURRENT_TO_SEQUENCE[feature], horizon))
                    model_row[feature] = source_row.get(source_column, source_row.get(feature))
                    continue
                sequence = _sequence_feature(feature)
                if sequence:
                    sequence_base, lag = sequence
                    previous_hour = horizon - lag
                    if previous_hour >= 1:
                        source_column = sequence_columns.get((sequence_base, previous_hour))
                        model_row[feature] = source_row.get(source_column)
                    else:
                        current_column = SEQUENCE_TO_CURRENT[sequence_base]
                        model_row[feature] = source_row.get(current_column)
                    continue
                model_row[feature] = source_row.get(feature)
            model_rows.append(model_row)

            output_row = {column: source_row.get(column) for column in metadata_columns}
            output_row["预测时效(h)"] = horizon
            if "预测起始时间" in source_row.index:
                output_row["预测时间"] = _forecast_time(source_row.get("预测起始时间"), horizon)
            for current, _ in WEATHER_FEATURE_PAIRS:
                if current in model_row:
                    output_row[current] = model_row[current]
            output_row["历史补齐小时数"] = max(0, max_lag - horizon + 1)
            output_rows.append(output_row)

    model_frame = pd.DataFrame(model_rows, columns=feature_columns)
    model_frame = _prepare_prediction(model_frame, feature_columns, medians)
    output_frame = pd.DataFrame(output_rows)
    return output_frame, model_frame, "预测时效(h)", {
        "mode": "wide_hourly_expansion",
        "source_point_count": int(len(frame)),
        "hour_count": int(hours),
        "max_lag_hours": int(max_lag),
    }


def _prepare_forecast_prediction(frame, feature_columns: list[str], medians, forecast_hours: int):
    expanded = _expand_wide_hourly_prediction(frame, feature_columns, medians, forecast_hours)
    if expanded is not None:
        return expanded
    filtered_frame, horizon_column = _filter_forecast_horizon(frame, forecast_hours)
    return filtered_frame, _prepare_prediction(filtered_frame, feature_columns, medians), horizon_column, {
        "mode": "row_per_horizon",
        "source_point_count": int(len(frame)),
        "hour_count": None,
        "max_lag_hours": None,
    }


def _risk_level(probability: float, thresholds: tuple[float, float, float]) -> str:
    if probability < thresholds[0]:
        return RISK_LABELS[0]
    if probability < thresholds[1]:
        return RISK_LABELS[1]
    if probability < thresholds[2]:
        return RISK_LABELS[2]
    return RISK_LABELS[3]


def _cross_validate(X, y, params: dict[str, Any]):
    import numpy as np
    import pandas as pd
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from tabpfn import TabPFNClassifier

    n_repeats = int(params.get("n_repeats") or 1)
    n_splits = int(params.get("n_splits") or 5)
    random_seed = int(params.get("random_seed") or 42)
    if n_repeats < 1 or n_repeats > 100:
        raise ValueError("重复次数必须在 1 到 100 之间")
    if n_splits < 2 or n_splits > 10:
        raise ValueError("交叉验证折数必须在 2 到 10 之间")
    if int(y.value_counts().min()) < n_splits:
        raise ValueError(f"最少类别样本数小于交叉验证折数 {n_splits}")

    fold_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    classifier_kwargs = _classifier_kwargs(params)
    for repeat in range(n_repeats):
        splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_seed + repeat)
        for fold, (train_idx, test_idx) in enumerate(splitter.split(X, y), start=1):
            classifier = TabPFNClassifier(**classifier_kwargs)
            classifier.fit(X.iloc[train_idx], y.iloc[train_idx])
            predicted = classifier.predict(X.iloc[test_idx])
            probabilities = classifier.predict_proba(X.iloc[test_idx])[:, 1]
            actual = y.iloc[test_idx]
            try:
                auc = roc_auc_score(actual, probabilities)
            except ValueError:
                auc = np.nan
            tn, fp, fn, tp = confusion_matrix(actual, predicted, labels=[0, 1]).ravel()
            fold_rows.append({
                "Repeat": repeat + 1,
                "Fold": fold,
                "Accuracy": accuracy_score(actual, predicted),
                "Precision": precision_score(actual, predicted, zero_division=0),
                "Recall": recall_score(actual, predicted, zero_division=0),
                "F1": f1_score(actual, predicted, zero_division=0),
                "AUC": auc,
                "TN": int(tn),
                "FP": int(fp),
                "FN": int(fn),
                "TP": int(tp),
            })
            for index, true_label, pred_label, probability in zip(test_idx, actual, predicted, probabilities):
                prediction_rows.append({
                    "Repeat": repeat + 1,
                    "Fold": fold,
                    "Sample_Index": int(index),
                    "True_Label": int(true_label),
                    "Pred_Label": int(pred_label),
                    "Fault_Probability": float(probability),
                })

    fold_frame = pd.DataFrame(fold_rows)
    validation_frame = pd.DataFrame(prediction_rows)
    summary_frame = fold_frame[["Accuracy", "Precision", "Recall", "F1", "AUC"]].agg(
        ["mean", "std", "min", "max"]
    ).T.reset_index()
    summary_frame.columns = ["Metric", "Mean", "Std", "Min", "Max"]
    summary_frame["CI95_Lower"] = summary_frame["Mean"] - 1.96 * summary_frame["Std"] / np.sqrt(len(fold_frame))
    summary_frame["CI95_Upper"] = summary_frame["Mean"] + 1.96 * summary_frame["Std"] / np.sqrt(len(fold_frame))
    return fold_frame, summary_frame, validation_frame


def _create_charts(output_dir: Path, summary_frame, prediction_frame, fold_frame) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    chart_paths: list[Path] = []

    metrics_path = output_dir / "evaluation_metrics.png"
    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    axis.bar(summary_frame["Metric"], summary_frame["Mean"], color="#3b82f6")
    axis.set_ylim(0, 1)
    axis.set_title("交叉验证指标均值")
    axis.set_ylabel("得分")
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(metrics_path, dpi=150)
    plt.close(fig)
    chart_paths.append(metrics_path)

    confusion_path = output_dir / "confusion_matrix.png"
    confusion = np.array([
        [fold_frame["TN"].sum(), fold_frame["FP"].sum()],
        [fold_frame["FN"].sum(), fold_frame["TP"].sum()],
    ])
    fig, axis = plt.subplots(figsize=(5.4, 4.4))
    image = axis.imshow(confusion, cmap="Blues")
    for row in range(2):
        for column in range(2):
            axis.text(column, row, int(confusion[row, column]), ha="center", va="center", color="#111827")
    axis.set_xticks([0, 1], ["预测正常", "预测故障"])
    axis.set_yticks([0, 1], ["实际正常", "实际故障"])
    axis.set_title("交叉验证混淆矩阵")
    fig.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(confusion_path, dpi=150)
    plt.close(fig)
    chart_paths.append(confusion_path)

    probability_path = output_dir / "hourly_fault_probability_trend.png"
    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    if "预测时效(h)" in prediction_frame.columns:
        hourly = prediction_frame.groupby("预测时效(h)")["故障概率"].agg(["mean", "max"]).reset_index()
        axis.plot(hourly["预测时效(h)"], hourly["mean"], marker="o", label="平均概率", color="#3b82f6")
        axis.plot(hourly["预测时效(h)"], hourly["max"], marker="o", label="最高概率", color="#ef4444")
        axis.set_xlim(hourly["预测时效(h)"].min(), hourly["预测时效(h)"].max())
        axis.set_title("逐小时故障概率趋势")
        axis.set_xlabel("预测时效（小时）")
        axis.set_ylabel("故障概率")
        axis.legend()
    else:
        axis.hist(prediction_frame["故障概率"], bins=10, range=(0, 1), color="#f59e0b", edgecolor="#ffffff")
        axis.set_xlim(0, 1)
        axis.set_title("预测故障概率分布")
        axis.set_xlabel("故障概率")
        axis.set_ylabel("记录数")
    axis.set_ylim(0, 1)
    axis.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(probability_path, dpi=150)
    plt.close(fig)
    chart_paths.append(probability_path)

    risk_path = output_dir / "risk_level_distribution.png"
    counts = prediction_frame["概率等级"].value_counts().reindex(RISK_LABELS, fill_value=0)
    fig, axis = plt.subplots(figsize=(7.2, 4.2))
    axis.bar(counts.index, counts.values, color=["#22c55e", "#eab308", "#f97316", "#ef4444"])
    axis.set_title("预测概率等级分布")
    axis.set_xlabel("概率等级")
    axis.set_ylabel("记录数")
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(risk_path, dpi=150)
    plt.close(fig)
    chart_paths.append(risk_path)
    return chart_paths


def _write_workbook(
    output_file: Path,
    prediction_frame,
    risk_frame,
    fold_frame,
    summary_frame,
    validation_frame,
    task_info_frame,
    chart_paths: list[Path],
) -> None:
    import pandas as pd
    from openpyxl import load_workbook
    from openpyxl.drawing.image import Image
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        prediction_frame.to_excel(writer, sheet_name="未来故障预测", index=False)
        risk_frame.to_excel(writer, sheet_name="概率等级统计", index=False)
        fold_frame.to_excel(writer, sheet_name="每折结果", index=False)
        summary_frame.to_excel(writer, sheet_name="总体统计", index=False)
        validation_frame.to_excel(writer, sheet_name="历史样本验证", index=False)
        task_info_frame.to_excel(writer, sheet_name="任务说明", index=False)

    workbook = load_workbook(output_file)
    header_fill = PatternFill("solid", fgColor="1D4ED8")
    header_font = Font(color="FFFFFF", bold=True)
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for column_index in range(1, min(sheet.max_column, 40) + 1):
            values = [str(sheet.cell(row, column_index).value or "") for row in range(1, min(sheet.max_row, 100) + 1)]
            sheet.column_dimensions[get_column_letter(column_index)].width = min(max(max(map(len, values), default=8) + 2, 10), 24)

    prediction_sheet = workbook["未来故障预测"]
    headers = {cell.value: cell.column for cell in prediction_sheet[1]}
    probability_column = headers.get("故障概率")
    if probability_column and prediction_sheet.max_row > 1:
        letter = get_column_letter(probability_column)
        prediction_sheet.conditional_formatting.add(
            f"{letter}2:{letter}{prediction_sheet.max_row}",
            ColorScaleRule(start_type="num", start_value=0, start_color="63BE7B", mid_type="num", mid_value=0.5, mid_color="FFEB84", end_type="num", end_value=1, end_color="F8696B"),
        )
        for cell in prediction_sheet[letter][1:]:
            cell.number_format = "0.00%"

    chart_sheet = workbook.create_sheet("可视化图表")
    chart_sheet.sheet_view.showGridLines = False
    positions = ("A1", "L1", "A25", "L25")
    for chart_path, position in zip(chart_paths, positions):
        image = Image(str(chart_path))
        image.width = 620
        image.height = 360
        chart_sheet.add_image(image, position)
    workbook.save(output_file)


def run(input_data: dict[str, Any]) -> dict[str, Any]:
    import pandas as pd
    from tabpfn import TabPFNClassifier

    start_time = time.time()
    task_id = str(input_data.get("task_id") or "tabpfn_forecast_task")
    training_file = Path(str(input_data.get("training_file") or "")).resolve()
    prediction_file = Path(str(input_data.get("input_file") or "")).resolve()
    output_dir = Path(str(input_data.get("output_dir") or prediction_file.parent)).resolve()
    params = input_data.get("params") or {}
    header_row = int(params.get("header_row") or 2)
    target_col = str(params.get("target_column") or TARGET_COLUMN)
    forecast_hours = int(params.get("forecast_hours") or 24)
    fault_threshold = float(params.get("fault_threshold") or 0.5)
    risk_threshold_values = params.get("risk_thresholds") or (0.25, 0.5, 0.75)
    risk_thresholds = tuple(float(value) for value in risk_threshold_values)

    if not training_file.is_file():
        raise FileNotFoundError("未收到历史训练 Excel 文件")
    if not prediction_file.is_file():
        raise FileNotFoundError("未收到待预测 Excel 文件")
    if training_file.suffix.lower() not in {".xlsx", ".xls"} or prediction_file.suffix.lower() not in {".xlsx", ".xls"}:
        raise ValueError("TabPFN 杆塔故障预测仅支持 Excel .xlsx/.xls 文件")
    if forecast_hours < 1 or forecast_hours > 168:
        raise ValueError("预测时长必须在 1 到 168 小时之间")
    if not 0 < fault_threshold < 1:
        raise ValueError("故障判定阈值必须在 0 到 1 之间")
    if len(risk_thresholds) != 3 or sorted(risk_thresholds) != list(risk_thresholds) or risk_thresholds[0] <= 0 or risk_thresholds[-1] >= 1:
        raise ValueError("概率等级阈值必须是 0 到 1 之间的三个递增数字")

    training_frame, training_header_row = _read_training_excel(training_file, target_col, header_row)
    X_train, y_train, medians, label_counts = _prepare_training(training_frame, target_col)
    prediction_source, prediction_header_row = _read_prediction_excel(prediction_file, list(X_train.columns), header_row)
    prediction_source, X_predict, horizon_column, forecast_layout = _prepare_forecast_prediction(
        prediction_source,
        list(X_train.columns),
        medians,
        forecast_hours,
    )

    fold_frame, summary_frame, validation_frame = _cross_validate(X_train, y_train, params)
    classifier = TabPFNClassifier(**_classifier_kwargs(params))
    classifier.fit(X_train, y_train)
    probabilities = classifier.predict_proba(X_predict)[:, 1]
    predicted_labels = (probabilities >= fault_threshold).astype(int)

    prediction_frame = prediction_source.copy()
    prediction_frame["预测是否故障"] = ["是" if int(value) == 1 else "否" for value in predicted_labels]
    prediction_frame["故障概率"] = probabilities
    prediction_frame["故障概率(%)"] = probabilities * 100
    prediction_frame["概率等级"] = [_risk_level(float(value), risk_thresholds) for value in probabilities]
    prediction_frame["故障判定阈值"] = fault_threshold
    prediction_frame["预测时长(h)"] = forecast_hours

    risk_counts = prediction_frame["概率等级"].value_counts().reindex(RISK_LABELS, fill_value=0)
    risk_frame = pd.DataFrame({
        "概率等级": list(RISK_LABELS),
        "记录数": [int(risk_counts[label]) for label in RISK_LABELS],
        "占比": [float(risk_counts[label] / len(prediction_frame)) for label in RISK_LABELS],
    })
    task_info_frame = pd.DataFrame([
        {"项目": "算法", "内容": ALGORITHM_NAME},
        {"项目": "历史训练文件", "内容": params.get("training_file_name") or training_file.name},
        {"项目": "待预测文件", "内容": params.get("source_file_name") or prediction_file.name},
        {"项目": "预测时长", "内容": f"{forecast_hours} 小时"},
        {"项目": "故障判定阈值", "内容": fault_threshold},
        {"项目": "概率等级阈值", "内容": json.dumps(risk_thresholds, ensure_ascii=False)},
        {"项目": "时效筛选列", "内容": horizon_column or "未发现时效列，已预测文件全部记录"},
        {"项目": "训练文件表头行", "内容": training_header_row},
        {"项目": "预测文件表头行", "内容": prediction_header_row},
        {"项目": "预测展开方式", "内容": "逐点位逐小时" if forecast_layout["mode"] == "wide_hourly_expansion" else "每行一个预测时效"},
        {"项目": "源点位数", "内容": forecast_layout["source_point_count"]},
        {"项目": "逐小时预测数", "内容": len(prediction_frame)},
        {"项目": "历史不足处理", "内容": "早期时效缺少的历史小时使用起报时刻气象补齐" if forecast_layout["mode"] == "wide_hourly_expansion" else "不适用"},
    ])

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_task_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in task_id)
    output_file = output_dir / f"{safe_task_id}_tabpfn_fault_forecast.xlsx"
    chart_paths = _create_charts(output_dir, summary_frame, prediction_frame, fold_frame)
    _write_workbook(
        output_file,
        prediction_frame,
        risk_frame,
        fold_frame,
        summary_frame,
        validation_frame,
        task_info_frame,
        chart_paths,
    )

    metrics = json.loads(summary_frame.to_json(orient="records"))
    risk_distribution = {label: int(risk_counts[label]) for label in RISK_LABELS}
    return {
        "task_id": task_id,
        "algorithm_id": ALGORITHM_ID,
        "algorithm_name": ALGORITHM_NAME,
        "status": "success",
        "result_type": "file",
        "output_file": str(output_file),
        "output_filename": output_file.name,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "sheets": ["未来故障预测", "概率等级统计", "每折结果", "总体统计", "历史样本验证", "任务说明", "可视化图表"],
        "chart_files": [path.name for path in chart_paths],
        "summary": {
            "used_real_model": True,
            "mode": "train_and_forecast",
            "training_file_name": params.get("training_file_name") or training_file.name,
            "prediction_file_name": params.get("source_file_name") or prediction_file.name,
            "sample_count": int(X_train.shape[0]),
            "feature_count": int(X_train.shape[1]),
            "prediction_count": int(len(prediction_frame)),
            "source_point_count": forecast_layout["source_point_count"],
            "prediction_mode": forecast_layout["mode"],
            "hour_count": forecast_layout["hour_count"],
            "predicted_fault_count": int(sum(int(value) for value in predicted_labels)),
            "average_fault_probability": float(probabilities.mean()),
            "max_fault_probability": float(probabilities.max()),
            "fault_threshold": fault_threshold,
            "risk_distribution": risk_distribution,
            "forecast_hours": forecast_hours,
            "horizon_column": horizon_column,
            "training_header_row": training_header_row,
            "prediction_header_row": prediction_header_row,
            "label_distribution": {str(key): int(value) for key, value in label_counts.items()},
            "n_repeats": int(params.get("n_repeats") or 1),
            "n_splits": int(params.get("n_splits") or 5),
            "total_folds": int((params.get("n_repeats") or 1) * (params.get("n_splits") or 5)),
            "duration_seconds": round(time.time() - start_time, 3),
            "metrics": metrics,
        },
    }

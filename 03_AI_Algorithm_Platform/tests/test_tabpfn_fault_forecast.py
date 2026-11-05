from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from openpyxl import load_workbook


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from algo.tabpfn_fault_forecast import run


class FakeTabPFNClassifier:
    def __init__(self, **_kwargs):
        pass

    def fit(self, features, labels):
        self.center = float(features.iloc[:, 0].median())
        return self

    def predict_proba(self, features):
        values = features.iloc[:, 0].to_numpy(dtype=float)
        probability = 1.0 / (1.0 + np.exp(-(values - self.center)))
        return np.column_stack([1.0 - probability, probability])

    def predict(self, features):
        return (self.predict_proba(features)[:, 1] >= 0.5).astype(int)


def write_double_header_excel(path: Path, columns: list[str], rows: list[list[object]]) -> None:
    content = [["气象数据", *([None] * (len(columns) - 1))], columns, *rows]
    pd.DataFrame(content).to_excel(path, index=False, header=False)


class TabPfnFaultForecastTest(unittest.TestCase):
    def test_generates_prediction_workbook_and_embedded_charts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            training_file = root / "training.xlsx"
            prediction_file = root / "prediction.xlsx"
            output_dir = root / "output"
            write_double_header_excel(
                training_file,
                ["是否为故障杆塔", "温度", "湿度"],
                [
                    ["N", -4, 30],
                    ["N", -3, 35],
                    ["N", -2, 40],
                    ["N", -1, 45],
                    ["Y", 1, 70],
                    ["Y", 2, 75],
                    ["Y", 3, 80],
                    ["Y", 4, 85],
                ],
            )
            write_double_header_excel(
                prediction_file,
                ["杆塔编号", "预测时效(h)", "温度", "湿度"],
                [
                    ["T001", 1, -2, 50],
                    ["T002", 3, 1, 70],
                    ["T003", 6, 3, 80],
                    ["T004", 12, 4, 90],
                ],
            )

            with patch("tabpfn.TabPFNClassifier", FakeTabPFNClassifier):
                result = run({
                    "task_id": "TEST_FORECAST",
                    "algorithm_id": "tabpfn_fault_forecast",
                    "training_file": str(training_file),
                    "input_file": str(prediction_file),
                    "output_dir": str(output_dir),
                    "params": {
                        "n_repeats": 1,
                        "n_splits": 2,
                        "random_seed": 42,
                        "forecast_hours": 6,
                        "fault_threshold": 0.5,
                    },
                })

            output_file = Path(result["output_file"])
            self.assertTrue(output_file.is_file())
            self.assertEqual(result["summary"]["prediction_count"], 3)
            self.assertTrue(result["summary"]["used_real_model"])
            self.assertEqual(len(result["chart_files"]), 4)

            workbook = load_workbook(output_file)
            self.assertEqual(
                workbook.sheetnames,
                ["未来故障预测", "概率等级统计", "每折结果", "总体统计", "历史样本验证", "任务说明", "可视化图表"],
            )
            self.assertEqual(len(workbook["可视化图表"]._images), 4)
            headers = [cell.value for cell in workbook["未来故障预测"][1]]
            self.assertIn("故障概率", headers)
            self.assertIn("概率等级", headers)

    def test_expands_wide_weather_sequence_to_hourly_predictions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            training_file = root / "training.xlsx"
            prediction_file = root / "prediction.xlsx"
            output_dir = root / "output"
            sequence_headers = ["温度（℃）", "湿度（%）"] * 3
            write_double_header_excel(
                training_file,
                ["是否为故障杆塔", "温度", "湿度", *sequence_headers],
                [
                    ["N", -4, 30, -5, 28, -6, 26, -7, 24],
                    ["N", -3, 35, -4, 33, -5, 31, -6, 29],
                    ["N", -2, 40, -3, 38, -4, 36, -5, 34],
                    ["N", -1, 45, -2, 43, -3, 41, -4, 39],
                    ["Y", 1, 70, 0, 68, -1, 66, -2, 64],
                    ["Y", 2, 75, 1, 73, 0, 71, -1, 69],
                    ["Y", 3, 80, 2, 78, 1, 76, 0, 74],
                    ["Y", 4, 85, 3, 83, 2, 81, 1, 79],
                ],
            )
            write_double_header_excel(
                prediction_file,
                ["杆塔编号", "预测起始时间", "预测时效(h)", "温度", "湿度", *sequence_headers],
                [["T001", "2026-07-05 00:00:00", 3, -1, 50, 0, 55, 2, 65, 4, 75]],
            )

            with patch("tabpfn.TabPFNClassifier", FakeTabPFNClassifier):
                result = run({
                    "task_id": "TEST_HOURLY_FORECAST",
                    "algorithm_id": "tabpfn_fault_forecast",
                    "training_file": str(training_file),
                    "input_file": str(prediction_file),
                    "output_dir": str(output_dir),
                    "params": {
                        "n_repeats": 1,
                        "n_splits": 2,
                        "random_seed": 42,
                        "forecast_hours": 3,
                        "fault_threshold": 0.5,
                    },
                })

            self.assertEqual(result["summary"]["prediction_mode"], "wide_hourly_expansion")
            self.assertEqual(result["summary"]["source_point_count"], 1)
            self.assertEqual(result["summary"]["prediction_count"], 3)
            output = pd.read_excel(result["output_file"], sheet_name="未来故障预测")
            self.assertEqual(output["预测时效(h)"].tolist(), [1, 2, 3])
            self.assertEqual(output["温度"].tolist(), [0, 2, 4])
            self.assertEqual(output["历史补齐小时数"].tolist(), [3, 2, 1])
            self.assertEqual(
                pd.to_datetime(output["预测时间"]).dt.strftime("%Y-%m-%d %H:%M:%S").tolist(),
                ["2026-07-05 00:00:00", "2026-07-05 01:00:00", "2026-07-05 02:00:00"],
            )
            self.assertTrue(output["概率等级"].notna().all())


if __name__ == "__main__":
    unittest.main()

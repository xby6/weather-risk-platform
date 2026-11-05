from __future__ import annotations

import unittest
import sys
from pathlib import Path
from unittest.mock import patch

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from algo import tabular_predict


class TabularPredictTest(unittest.TestCase):
    def test_returns_classification_result_and_accuracy(self) -> None:
        model_meta = {
            "model_id": "tabular-test-model",
            "algorithm_name": "Tabular test model",
            "model_format": "pkl",
        }
        input_data = {
            "task_id": "tabular-test-001",
            "algorithm_id": "tabular-test-model",
            "features": [
                {"sample_index": 1, "source_row": 3, "target_label": "N", "tabular_values": [1.0]},
                {"sample_index": 2, "source_row": 4, "target_label": "Y", "tabular_values": [2.0]},
            ],
            "params": {"source_file_name": "weather.xlsx", "source_feature_count": 1},
        }

        with patch.object(
            tabular_predict,
            "predict_tabular",
            side_effect=[
                ({"prediction": 0, "probability": 0.1}, model_meta),
                ({"prediction": 1, "probability": 0.9}, model_meta),
            ],
        ):
            result = tabular_predict.run(input_data)

        self.assertTrue(result["used_real_model"])
        self.assertEqual(result["summary"]["sample_count"], 2)
        self.assertEqual(result["summary"]["accuracy"], 1.0)
        self.assertFalse(result["result"][0]["predicted_fault"])
        self.assertEqual(result["result"][1]["fault_probability"], 0.9)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from unittest.mock import patch

from algo import icing_forecast


class IcingForecastBatchTest(unittest.TestCase):
    def test_weather_file_batch_executes_every_sample(self) -> None:
        model_meta = {
            "model_id": "batch-test-model",
            "algorithm_name": "Batch test model",
            "model_format": "pkl",
        }
        input_data = {
            "task_id": "batch-test-001",
            "algorithm_id": "batch-test-model",
            "model_id": "batch-test-model",
            "features": [
                {"sample_index": 1, "source_row": 3, "temperature": 1.0, "target_label": "N"},
                {"sample_index": 2, "source_row": 4, "temperature": 2.0, "target_label": "Y"},
            ],
            "params": {
                "batch_mode": True,
                "source_file_name": "weather.xlsx",
                "source_feature_count": 168,
            },
        }

        with patch.object(
            icing_forecast,
            "predict_icing",
            side_effect=[(1.25, model_meta), (2.5, model_meta)],
        ) as predictor:
            result = icing_forecast.run(input_data)

        self.assertEqual(predictor.call_count, 2)
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["used_real_model"])
        self.assertEqual(result["summary"]["sample_count"], 2)
        self.assertEqual(result["summary"]["feature_count"], 168)
        self.assertEqual(result["result"][1]["target_label"], "Y")
        self.assertEqual(result["result"][1]["prediction"], 2.5)


if __name__ == "__main__":
    unittest.main()

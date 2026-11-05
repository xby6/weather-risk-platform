from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from module_admin.service.weather_feature_parser import parse_weather_dataset


class WeatherFeatureParserTest(unittest.TestCase):
    def test_parse_weather_csv_for_batch_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "weather.csv"
            source.write_text(
                "是否为故障杆塔,温度,湿度,比湿,小时降水,风速,U风,V风\n"
                "N,-5,90,2.1,0.5,4,-1,-3\n"
                "Y,-8,95,2.4,1.2,6,-2,-4\n",
                encoding="utf-8",
            )

            parsed = parse_weather_dataset(source)

        self.assertEqual(parsed["header_row"], 1)
        self.assertEqual(parsed["record_count"], 2)
        self.assertEqual(parsed["feature_count"], 7)
        self.assertEqual(parsed["target_distribution"], {"N": 1, "Y": 1})
        self.assertEqual(parsed["samples"][0]["temperature"], -5.0)
        self.assertEqual(parsed["samples"][1]["target_label"], "Y")
        self.assertEqual(len(parsed["samples"][0]["tabular_values"]), 7)


if __name__ == "__main__":
    unittest.main()

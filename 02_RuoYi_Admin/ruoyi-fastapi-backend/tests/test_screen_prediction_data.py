from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from module_admin.controller.screen_controller import (
    _prediction_hourly_trend,
    _prediction_risk_distribution_by_region,
    _prediction_warning_list,
    _read_prediction_result_file,
)


class ScreenPredictionDataTest(unittest.TestCase):
    def test_prediction_result_is_aggregated_for_screen(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result_file = Path(temp) / 'forecast.xlsx'
            frame = pd.DataFrame(
                [
                    {'运行单位': '沈阳', '线路名称': '沈阳线', '杆塔编号': 'S1', '预测时效(h)': 1, '预测时间': '2026-07-05 01:00:00', '故障概率': 0.2, '故障概率(%)': 20, '概率等级': '低', '预测是否故障': '否', '经度': 123.1, '纬度': 41.8},
                    {'运行单位': '沈阳', '线路名称': '沈阳线', '杆塔编号': 'S1', '预测时效(h)': 2, '预测时间': '2026-07-05 02:00:00', '故障概率': 0.6, '故障概率(%)': 60, '概率等级': '较高', '预测是否故障': '是', '经度': 123.1, '纬度': 41.8},
                    {'运行单位': '大连', '线路名称': '大连线', '杆塔编号': 'D1', '预测时效(h)': 1, '预测时间': '2026-07-05 01:00:00', '故障概率': 0.4, '故障概率(%)': 40, '概率等级': '一般', '预测是否故障': '否', '经度': 121.6, '纬度': 38.9},
                    {'运行单位': '大连', '线路名称': '大连线', '杆塔编号': 'D1', '预测时效(h)': 2, '预测时间': '2026-07-05 02:00:00', '故障概率': 0.8, '故障概率(%)': 80, '概率等级': '高', '预测是否故障': '是', '经度': 121.6, '纬度': 38.9},
                ]
            )
            with pd.ExcelWriter(result_file, engine='openpyxl') as writer:
                frame.to_excel(writer, sheet_name='未来故障预测', index=False)

            rows = _read_prediction_result_file(result_file)
            self.assertEqual(len(rows), 4)
            warnings = _prediction_warning_list({'taskCode': 'TASK-1', 'taskName': '预测任务'}, rows)
            self.assertEqual(warnings[0]['tower_code'], 'D1')
            self.assertEqual(warnings[0]['probability_percent'], 80)

            distribution = _prediction_risk_distribution_by_region(rows)
            self.assertEqual(distribution['cities'], ['沈阳市', '大连市'])
            self.assertEqual(distribution['level1'], [0, 1])
            self.assertEqual(distribution['level2'], [1, 0])
            self.assertEqual(distribution['level3'], [0, 1])
            self.assertEqual(distribution['level4'], [1, 0])

            trend = _prediction_hourly_trend(rows)
            self.assertEqual(trend['hours'], [1, 2])
            self.assertEqual(trend['series'][0]['name'], '沈阳市')
            self.assertEqual(trend['series'][0]['data'], [20.0, 60.0])
            self.assertEqual(trend['series'][1]['data'], [40.0, 80.0])


if __name__ == '__main__':
    unittest.main()

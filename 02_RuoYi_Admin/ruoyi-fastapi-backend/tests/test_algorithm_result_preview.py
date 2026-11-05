from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from module_admin.service.algorithm_result_preview import build_algorithm_result_preview


class AlgorithmResultPreviewTest(unittest.TestCase):
    def test_forecast_workbook_is_converted_to_browser_preview(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result_file = Path(temp) / 'forecast.xlsx'
            predictions = pd.DataFrame(
                [
                    {'点位序号': 1, '运行单位': '沈阳', '线路名称': '沈阳线', '杆塔编号': 'S1', '预测时效(h)': 1, '预测时间': '2026-07-05 01:00:00', '温度': -5, '湿度': 80, '风速': 3, '小时降水': 0.1, '预测是否故障': '否', '故障概率': 0.2, '故障概率(%)': 20, '概率等级': '低'},
                    {'点位序号': 1, '运行单位': '沈阳', '线路名称': '沈阳线', '杆塔编号': 'S1', '预测时效(h)': 2, '预测时间': '2026-07-05 02:00:00', '温度': -6, '湿度': 82, '风速': 4, '小时降水': 0.2, '预测是否故障': '是', '故障概率': 0.6, '故障概率(%)': 60, '概率等级': '较高'},
                    {'点位序号': 2, '运行单位': '大连', '线路名称': '大连线', '杆塔编号': 'D1', '预测时效(h)': 1, '预测时间': '2026-07-05 01:00:00', '温度': 1, '湿度': 70, '风速': 5, '小时降水': 0, '预测是否故障': '否', '故障概率': 0.4, '故障概率(%)': 40, '概率等级': '一般'},
                    {'点位序号': 2, '运行单位': '大连', '线路名称': '大连线', '杆塔编号': 'D1', '预测时效(h)': 2, '预测时间': '2026-07-05 02:00:00', '温度': 0, '湿度': 75, '风速': 6, '小时降水': 0, '预测是否故障': '是', '故障概率': 0.8, '故障概率(%)': 80, '概率等级': '高'},
                ]
            )
            risks = pd.DataFrame(
                [
                    {'概率等级': '低', '记录数': 1, '占比': 0.25},
                    {'概率等级': '一般', '记录数': 1, '占比': 0.25},
                    {'概率等级': '较高', '记录数': 1, '占比': 0.25},
                    {'概率等级': '高', '记录数': 1, '占比': 0.25},
                ]
            )
            folds = pd.DataFrame([{'TN': 5, 'FP': 1, 'FN': 2, 'TP': 4}, {'TN': 6, 'FP': 2, 'FN': 1, 'TP': 5}])
            summary = pd.DataFrame([{'Metric': 'Accuracy', 'Mean': 0.8}, {'Metric': 'AUC', 'Mean': 0.9}])
            with pd.ExcelWriter(result_file, engine='openpyxl') as writer:
                predictions.to_excel(writer, sheet_name='未来故障预测', index=False)
                risks.to_excel(writer, sheet_name='概率等级统计', index=False)
                folds.to_excel(writer, sheet_name='每折结果', index=False)
                summary.to_excel(writer, sheet_name='总体统计', index=False)

            preview = build_algorithm_result_preview(result_file)

            self.assertTrue(preview['available'])
            self.assertEqual(preview['prediction_total'], 4)
            self.assertEqual(preview['predictions'][0]['tower_code'], 'S1')
            self.assertEqual(preview['risk_statistics'][3]['count'], 1)
            self.assertEqual(preview['charts']['hourly_probability']['average'], [30.0, 70.0])
            self.assertEqual(preview['charts']['hourly_probability']['maximum'], [40.0, 80.0])
            self.assertEqual(preview['charts']['confusion_matrix'], {'tn': 11, 'fp': 3, 'fn': 3, 'tp': 9})
            self.assertEqual(preview['charts']['validation_metrics'][1], {'name': 'AUC', 'value': 0.9})


if __name__ == '__main__':
    unittest.main()

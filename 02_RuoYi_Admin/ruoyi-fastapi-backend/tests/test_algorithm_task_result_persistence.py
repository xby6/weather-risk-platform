from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from module_admin.controller import algorithm_link_controller


class AlgorithmTaskResultPersistenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_database_file_result_is_cached_without_remote_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "algorithm-output.xlsx"
            source.write_bytes(b"real-result-file")
            cache_root = root / "ruoyi-results"
            task = {
                "taskCode": "TASK-001",
                "resultPath": "/algorithm/task/result-file/TASK-001",
            }
            result = {
                "result_type": "file",
                "output_file": str(source),
                "output_filename": "model-result.xlsx",
            }

            with patch.object(algorithm_link_controller, "TASK_RESULT_DIR", cache_root):
                cached_path = await algorithm_link_controller._cache_result_file(task, result)

            cached = Path(cached_path)
            self.assertTrue(cached.is_file())
            self.assertEqual(cached.read_bytes(), b"real-result-file")
            self.assertEqual(cached.name, "model-result.xlsx")

    def test_empty_result_is_not_treated_as_persisted(self) -> None:
        self.assertFalse(algorithm_link_controller._has_persisted_result({"result": None}))
        self.assertFalse(algorithm_link_controller._has_persisted_result({"result": {}}))
        self.assertTrue(algorithm_link_controller._has_persisted_result({"result": {"status": "success"}}))


if __name__ == "__main__":
    unittest.main()

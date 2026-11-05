from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import task_store


class TaskStorePersistenceTest(unittest.TestCase):
    def test_completed_task_is_restored_after_store_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store_path = Path(temp) / "task_store.json"
            with patch.object(task_store, "TASK_STORE_PATH", store_path):
                first_store = task_store.TaskStore()
                first_store.create("task-001", "algorithm-001", {"input_file": "input.xlsx"})
                first_store.update(
                    "task-001",
                    status="success",
                    progress=100,
                    result={"result_type": "file", "output_file": "result.xlsx"},
                )

                restarted_store = task_store.TaskStore()
                restored = restarted_store.get("task-001")

            self.assertIsNotNone(restored)
            self.assertEqual(restored["status"], "success")
            self.assertEqual(restored["progress"], 100)
            self.assertEqual(restored["result"]["output_file"], "result.xlsx")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import algorithm_runtime


class AlgorithmRuntimeTest(unittest.TestCase):
    def test_executes_registered_entrypoint_and_returns_its_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package_dir = root / "package"
            output_dir = root / "output"
            package_dir.mkdir()
            output_dir.mkdir()
            input_file = root / "input.txt"
            input_file.write_text("weather-data", encoding="utf-8")
            (package_dir / "runner.py").write_text(
                "from pathlib import Path\n"
                "def run(input_data):\n"
                "    target = Path(input_data['output_dir']) / 'result.csv'\n"
                "    value = input_data['params']['threshold']\n"
                "    target.write_text(f'threshold\\n{value}\\n', encoding='utf-8')\n"
                "    return {'output_file': str(target), 'summary': {'threshold': value}}\n",
                encoding="utf-8",
            )
            model = {
                "status": "enabled",
                "package_path": str(package_dir),
                "entrypoint": "runner.py:run",
            }
            input_data = {
                "input_file": str(input_file),
                "output_dir": str(output_dir),
                "params": {"threshold": 0.73},
            }

            with patch.object(algorithm_runtime, "get_model", return_value=model):
                result = algorithm_runtime.run_registered_algorithm("custom", input_data)

            self.assertEqual(result["result_type"], "file")
            self.assertEqual(result["output_filename"], "result.csv")
            self.assertEqual(result["summary"]["threshold"], 0.73)
            self.assertTrue(Path(result["output_file"]).is_file())


if __name__ == "__main__":
    unittest.main()

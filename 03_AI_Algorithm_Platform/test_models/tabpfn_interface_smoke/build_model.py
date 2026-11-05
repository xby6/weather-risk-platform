from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
MODEL_PATH = PACKAGE_DIR / "tabpfn_interface_smoke_v1.pkl"
INFO_PATH = PACKAGE_DIR / "upload_fields.json"


def build_model() -> dict[str, object]:
    # This dependency-free model is only for upload and task API smoke tests.
    return {
        "model_type": "linear_icing",
        "intercept": 0.5,
        "weights": {
            "temperature": -0.05,
            "humidity": 0.02,
            "wind_speed": 0.10,
            "wind_direction": 0.0,
            "precipitation": 0.30,
            "history_icing_thickness": 0.80,
        },
        "output_transform": "clip_nonnegative",
        "metadata": {
            "source_project": "TabPFN-main.zip",
            "execution_mode": "interface_smoke_test",
            "used_real_tabpfn": False,
            "notice": "API smoke-test artifact; not a trained TabPFN checkpoint.",
        },
    }


def main() -> None:
    model = build_model()
    MODEL_PATH.write_bytes(pickle.dumps(model, protocol=4))
    digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()

    upload_fields = json.loads(INFO_PATH.read_text(encoding="utf-8"))
    upload_fields["file"] = MODEL_PATH.name
    upload_fields["sha256"] = digest
    info_content = json.dumps(upload_fields, ensure_ascii=False, indent=2) + "\n"
    INFO_PATH.write_bytes(info_content.encode("utf-8"))
    print(f"created={MODEL_PATH}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()

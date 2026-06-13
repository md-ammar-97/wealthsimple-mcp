from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml


def load_config(
    pipeline_yaml: str = "config/pipeline.yaml",
    delivery_yaml: str = "config/delivery.yaml",
) -> SimpleNamespace:
    with open(pipeline_yaml, encoding="utf-8") as f:
        pipeline = yaml.safe_load(f)
    with open(delivery_yaml, encoding="utf-8") as f:
        delivery = yaml.safe_load(f)
    cfg = {**pipeline, **delivery}
    return SimpleNamespace(**cfg)

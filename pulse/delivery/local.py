from __future__ import annotations

from pathlib import Path

from pulse.utils.logging import log


def write_artifact(content: str, output_path: str, run_id: str = "dry-run") -> None:
    """Write a string artifact to the given path, creating parent dirs as needed."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log(run_id, "delivery", "artifact_written", path=str(path))

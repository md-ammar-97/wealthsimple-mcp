from __future__ import annotations

import subprocess
import sys


def test_python_module_entrypoint_runs_click_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pulse.cli", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "run" in result.stdout

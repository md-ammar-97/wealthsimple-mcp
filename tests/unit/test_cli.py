from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch

from click.testing import CliRunner

from pulse.cli import main


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


def test_run_help_includes_skip_delivery_option() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pulse.cli", "run", "--help"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0
    assert "--skip-delivery" in result.stdout


def test_run_forwards_skip_delivery_to_pipeline() -> None:
    runner = CliRunner()
    with patch("pulse.cli.load_config", return_value=object()):
        with patch(
            "pulse.cli.run_pipeline",
            return_value={"run_id": "test-run", "status": "success"},
        ) as run_pipeline:
            result = runner.invoke(
                main,
                ["run", "--input", "reviews.csv", "--skip-delivery"],
            )

    assert result.exit_code == 0
    assert run_pipeline.call_args.kwargs["skip_delivery"] is True

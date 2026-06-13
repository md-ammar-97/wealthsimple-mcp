import json
import sys
from datetime import datetime, timezone


def log(run_id: str, stage: str, event: str, **kwargs) -> None:
    """Emit a structured JSON log line to stdout. Never include raw review text or PII."""
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_id": run_id,
        "stage": stage,
        "event": event,
    }
    record.update(kwargs)
    print(json.dumps(record), flush=True)

"""Thread-safe append-only JSON-lines logger.

Every record gets a physical UTC timestamp for human readability, but
per the assignment, physical time must never be used to decide
causality -- only the Lamport/vector values matter for that.
"""

import json
import threading
from datetime import datetime, timezone


class JsonlLogger:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()

    def log(self, event_type, fields):
        record = {
            "physical_time_utc": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
        }
        record.update(fields)
        line = json.dumps(record)
        with self._lock:
            with open(self.path, "a") as f:
                f.write(line + "\n")

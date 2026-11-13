from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from desktop.runtime_paths import resolve_runtime_paths
from desktop.service_manager import stop_services


if __name__ == "__main__":
    stop_services(resolve_runtime_paths())

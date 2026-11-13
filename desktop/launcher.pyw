from __future__ import annotations

import ctypes
import sys
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from desktop.bootstrap import ensure_database
from desktop.runtime_paths import WEB_PORT, resolve_runtime_paths
from desktop.service_manager import start_services


def _message(title: str, text: str) -> None:
    if hasattr(ctypes, "windll"):
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)


def main() -> None:
    paths = resolve_runtime_paths()
    paths.logs.mkdir(parents=True, exist_ok=True)
    try:
        ensure_database(paths)
        result = start_services(paths)
        webbrowser.open(result["web_url"] or f"http://127.0.0.1:{WEB_PORT}/")
    except Exception as error:
        log_path = paths.logs / "launcher.log"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{datetime.now().isoformat()}] {error}\n")
            traceback.print_exc(file=log)
        _message(
            "高二英语智能练习",
            f"启动失败：{error}\n\n日志：{log_path}",
        )


if __name__ == "__main__":
    main()

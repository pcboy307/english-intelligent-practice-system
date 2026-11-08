#!/usr/bin/env python3
"""Complete one 29-question M2 session in the real Expo web UI."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION = "m2-805a5871183b"
EVIDENCE = ROOT / "qa" / "evidence" / "m2"
EVIDENCE.mkdir(parents=True, exist_ok=True)
AGENT_BROWSER = shutil.which("agent-browser")
if not AGENT_BROWSER:
    raise RuntimeError("AGENT_BROWSER_NOT_FOUND")


def command(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [AGENT_BROWSER, "--session", SESSION, *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


choose_first = """
Array.from(document.querySelectorAll('[role="button"]'))
  .find((node) => node.textContent.trim().startsWith('A'))
  .click();
'selected'
""".strip()
encoded_choice = base64.b64encode(choose_first.encode("utf-8")).decode("ascii")

has_submit = (
    "Array.from(document.querySelectorAll('[role=\"button\"]'))"
    ".some((node) => node.textContent.trim() === '交卷')"
)
encoded_has_submit = base64.b64encode(has_submit.encode("utf-8")).decode("ascii")

for question in range(1, 41):
    selected = command("eval", "-b", encoded_choice)
    if selected.returncode:
        raise RuntimeError(f"SELECT_FAILED:{question}:{selected.stderr}")
    time.sleep(0.12)
    submit_visible = command("eval", "-b", encoded_has_submit)
    if submit_visible.stdout.strip().endswith("true"):
        break
    advanced = command(
        "find",
        "role",
        "button",
        "click",
        "--name",
        "下一题",
        "--exact",
    )
    if advanced.returncode:
        raise RuntimeError(f"NEXT_FAILED:{question}:{advanced.stderr}")
    time.sleep(0.18)
else:
    raise RuntimeError("SUBMIT_BUTTON_NOT_FOUND")

for name in ("交卷", "确认交卷", "查看报告"):
    clicked = command(
        "find",
        "role",
        "button",
        "click",
        "--name",
        name,
        "--exact",
    )
    if clicked.returncode:
        raise RuntimeError(f"CLICK_FAILED:{name}:{clicked.stderr}")
    time.sleep(0.5)

waited = command(
    "wait",
    "--text",
    "薄弱知识点分析",
    "--timeout",
    "30000",
)
if waited.returncode:
    raise RuntimeError(f"REPORT_WAIT_FAILED:{waited.stderr}")

subprocess.run(
    [
        AGENT_BROWSER,
        "--session",
        SESSION,
        "screenshot",
        "--full",
        str(EVIDENCE / "browser-report.png"),
    ],
    check=True,
)
snapshot = command("snapshot", "-i")
(EVIDENCE / "browser-report-snapshot.txt").write_text(
    snapshot.stdout,
    encoding="utf-8",
)
dom = command("read")
(EVIDENCE / "browser-report-dom.txt").write_text(dom.stdout, encoding="utf-8")
print(
    json.dumps(
        {
            "status": "passed",
            "screenshot": str(EVIDENCE / "browser-report.png"),
            "snapshot": str(EVIDENCE / "browser-report-snapshot.txt"),
            "dom": str(EVIDENCE / "browser-report-dom.txt"),
        },
        ensure_ascii=False,
        indent=2,
    )
)

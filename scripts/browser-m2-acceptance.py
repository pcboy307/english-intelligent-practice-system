#!/usr/bin/env python3
"""Drive one complete M2 student flow through the real web UI."""

from __future__ import annotations

import json
import base64
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION = "m2-805a5871183b"
EVIDENCE = ROOT / "qa" / "evidence" / "m2" / "browser-acceptance"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    executable = shutil.which("agent-browser")
    if not executable:
        raise RuntimeError("AGENT_BROWSER_NOT_FOUND")
    return subprocess.run(
        [executable, "--session", SESSION, *args],
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )


choose_a = (
    'Array.from(document.querySelectorAll("[role=button]"))'
    '.find((node) => node.textContent.trim().startsWith("A")).click();'
    '"answered"'
)
choose_a_b64 = base64.b64encode(choose_a.encode("utf-8")).decode("ascii")

for index in range(1, 30):
    response = run("eval", "-b", choose_a_b64)
    if response.returncode:
        raise RuntimeError(f"ANSWER_CLICK_FAILED {index}: {response.stderr}")
    time.sleep(0.18)
    if index < 29:
        response = run(
            "find",
            "role",
            "button",
            "click",
            "--name",
            "下一题",
        )
        if response.returncode:
            raise RuntimeError(f"NEXT_CLICK_FAILED {index}: {response.stderr}")
        time.sleep(0.22)

response = run("find", "role", "button", "click", "--name", "交卷")
if response.returncode:
    raise RuntimeError(f"SUBMIT_CLICK_FAILED: {response.stderr}")
time.sleep(0.25)
response = run(
    "find",
    "role",
    "button",
    "click",
    "--name",
    "确认交卷",
)
if response.returncode:
    raise RuntimeError(f"CONFIRM_CLICK_FAILED: {response.stderr}")

response = run("wait", "--text", "薄弱点分析", "--timeout", "30000")
if response.returncode:
    raise RuntimeError(f"REPORT_WAIT_FAILED: {response.stderr}")
run("screenshot", "--full", str(EVIDENCE / "report.png"))
snapshot = run("snapshot", "-i")
(EVIDENCE / "report-snapshot.txt").write_text(
    snapshot.stdout,
    encoding="utf-8",
)
dom = run("read")
(EVIDENCE / "report-dom.txt").write_text(dom.stdout, encoding="utf-8")
print(
    json.dumps(
        {
            "status": "passed",
            "screenshot": str(EVIDENCE / "report.png"),
            "snapshot": str(EVIDENCE / "report-snapshot.txt"),
        },
        ensure_ascii=False,
        indent=2,
    )
)

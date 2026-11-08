#!/usr/bin/env python3
"""Final browser acceptance run against the current M2 Bank #2."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION = "m2final-805a5871183b"
OUT = ROOT / "qa" / "evidence" / "m2" / "browser-acceptance"
OUT.mkdir(parents=True, exist_ok=True)
TOOL = shutil.which("agent-browser")
if not TOOL:
    raise RuntimeError("AGENT_BROWSER_NOT_FOUND")


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        [TOOL, "--session", SESSION, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode:
        raise RuntimeError(
            f"AGENT_BROWSER_FAILED {args}: {completed.stderr}"
        )
    return completed


def click_role(name: str) -> None:
    run(
        "find",
        "role",
        "button",
        "click",
        "--name",
        name,
        "--exact",
    )
    time.sleep(0.25)


choose_a = (
    "Array.from(document.querySelectorAll('[role=\"button\"]'))"
    ".find((node) => node.textContent.trim().startsWith('A')).click();"
    "'selected'"
)
choice = base64.b64encode(choose_a.encode("utf-8")).decode("ascii")

run("open", "http://127.0.0.1:8081")
run("wait", "--text", "开始 30 分钟练习")
run("eval", "localStorage.removeItem('device_student_id'); 'cleared'")
run("open", "http://127.0.0.1:8081")
run("wait", "--text", "开始 30 分钟练习")
click_role("开始 30 分钟练习")
run("wait", "--text", "第 1 题")

for index in range(1, 30):
    run("eval", "-b", choice)
    time.sleep(0.12)
    if index < 29:
        click_role("下一题")

click_role("交卷")
click_role("确认交卷")
click_role("查看报告")
run("wait", "--text", "薄弱知识点分析", "--timeout", "30000")

run(
    "screenshot",
    "--full",
    str(OUT / "report.png"),
)
snapshot = run("snapshot", "-i")
(OUT / "report-snapshot.txt").write_text(snapshot.stdout, encoding="utf-8")
dom = run("read")
(OUT / "report-dom.txt").write_text(dom.stdout, encoding="utf-8")
print(
    json.dumps(
        {
            "status": "passed",
            "session": SESSION,
            "screenshot": str(OUT / "report.png"),
            "snapshot": str(OUT / "report-snapshot.txt"),
            "dom": str(OUT / "report-dom.txt"),
        },
        ensure_ascii=False,
        indent=2,
    )
)

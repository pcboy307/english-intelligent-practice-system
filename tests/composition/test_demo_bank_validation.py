from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_demo_bank_has_80_questions_and_all_passages_pass_quality_gates(tmp_path: Path) -> None:
    output = tmp_path / "demo-bank-validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate-demo-bank.py",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["question_count"] == 80
    assert result["passage_count"] == 11
    assert result["question_type_counts"] == {
        "cloze": 30,
        "grammar_fill": 20,
        "reading": 20,
        "gap_fill": 10,
    }
    assert len(result["passages"]) == 11
    assert result["passes"] is True
    assert all(passage["passes"] for passage in result["passages"])

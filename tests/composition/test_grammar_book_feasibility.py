from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_grammar_coverage_and_book_distribution_are_jointly_reachable(
    tmp_path: Path,
) -> None:
    output = ROOT / "qa" / "evidence" / "m0" / "grammar-book-feasibility.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "scripts/check-m0-grammar-book-feasibility.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["conclusion"] == "可达"
    assert result["required_coverage_occurrences"] == 252
    assert len(result["pair_intersections"]) == 210
    assert result["incompatible_pair_count"] == 34
    assert result["compatible_pair_count"] == 176
    assert result["unit_book_consistency"] == {
        "checked_rows": 25,
        "mismatch_count": 0,
        "mismatches": [],
        "passes": True,
    }
    assert result["distribution_targets"] == {
        "必修": 80,
        "选必一": 120,
        "选必二": 180,
        "跨册": 20,
    }
    assert all(row["passes"] for row in result["rows"])
    assert sum(
        item["covered_id_occurrences"]
        for item in result["group_compatible_witnesses"]
    ) == 252

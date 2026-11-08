"""Create a small bank-v1 package for browser import verification."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "qa" / "evidence" / "m26" / "stage-a" / "stage-a-generated.json"
OUTPUT = ROOT / "qa" / "evidence" / "m26" / "browser" / "ui-import-test-package.json"


def main() -> None:
    records = json.loads(SOURCE.read_text(encoding="utf-8"))
    reading = next(record for record in records if record["type"] == "reading")
    package = {
        "format_version": "bank-v1",
        "name": "UI Import Test 20261108",
        "target_size": 4,
        "difficulty_profile": "advanced",
        "generated_at": "2026-11-08",
        "composition": {
            "cloze": 0,
            "grammar_fill": 0,
            "reading": 1,
            "gap_fill": 0,
        },
        "passages": [reading],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()

"""Create a small bank-v1 package for browser import verification."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "qa" / "evidence" / "m26" / "stage-a" / "stage-a-generated.json"
OUTPUT = ROOT / "qa" / "evidence" / "m26" / "browser" / "ui-import-test-package.json"
QUALITY_OUTPUT = (
    ROOT
    / "qa"
    / "evidence"
    / "m26"
    / "browser"
    / "ui-import-no-validation-package.json"
)
EMPTY_NAME_OUTPUT = (
    ROOT
    / "qa"
    / "evidence"
    / "m26"
    / "browser"
    / "ui-import-empty-name-package.json"
)
DUPLICATE_OUTPUT = (
    ROOT
    / "qa"
    / "evidence"
    / "m26"
    / "browser"
    / "ui-import-duplicate-name-package.json"
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
    write_json(OUTPUT, package)

    quality_package = json.loads(json.dumps(package))
    quality_package["name"] = "Direct Import No Validation 20261109"
    quality_package["passages"][0]["questions"][0]["explanation"] = ""
    write_json(QUALITY_OUTPUT, quality_package)

    empty_name_package = json.loads(json.dumps(package))
    empty_name_package["name"] = "   "
    write_json(EMPTY_NAME_OUTPUT, empty_name_package)

    duplicate_package = json.loads(json.dumps(package))
    duplicate_package["name"] = "M2 Bank #2"
    write_json(DUPLICATE_OUTPUT, duplicate_package)

    print(OUTPUT)
    print(QUALITY_OUTPUT)
    print(EMPTY_NAME_OUTPUT)
    print(DUPLICATE_OUTPUT)


if __name__ == "__main__":
    main()

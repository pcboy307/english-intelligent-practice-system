from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from backend.app.composer import assemble_demo_paper
from backend.app.demo_bank import DemoQuestion


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "qa"
    / "question-banks"
    / "20261109_500-batch-01-rev-02.json"
)


def _questions() -> list[DemoQuestion]:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    questions = []
    for passage in package["passages"]:
        for item in passage["questions"]:
            questions.append(
                DemoQuestion(
                    id=f"{passage['passage_group_id']}-Q{item['number']:02d}",
                    bank_id="new-batch",
                    type=passage["type"],
                    passage_group_id=passage["passage_group_id"],
                    passage=passage["passage"],
                    stem=item["stem"],
                    options=item["options"],
                    answer=item["answer"],
                    explanation=item["explanation"],
                    knowledge_points=item["knowledge_points"],
                    grammar_tags=item["grammar_tags"],
                    book_source=item["book_source"],
                    difficulty=item["difficulty"],
                    topic_value=passage["topic"],
                )
            )
    return questions


def test_new_batch_can_assemble_both_practice_modes() -> None:
    questions = _questions()
    weights = {
        item.id: {
            "weight": 1.0,
            "base_weight": 1.0,
            "recent_three_penalty": 0.0,
            "i_err": 0.0,
        }
        for item in questions
    }

    for paper_number, expected_size in ((1, 29), (2, 30)):
        selected, log = assemble_demo_paper(
            questions,
            paper_number,
            weights,
            set(),
            set(),
            set(),
            {
                "选必二": 0.45,
                "选必一": 0.30,
                "必修": 0.20,
                "跨册": 0.05,
            },
            ["选必二", "选必一", "必修", "跨册"],
        )

        assert len(selected) == expected_size
        assert max(
            Counter(
                tag for question in selected for tag in question.grammar_tags
            ).values()
        ) <= 3
        assert len(log["topics"]) >= 3


def test_revision_applies_quality_fixes() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    passages = {
        passage["passage_group_id"]: passage
        for passage in package["passages"]
    }

    grammar = passages["M26-NEW-GRAMMAR-01"]
    assert grammar["questions"][1]["answer"] == "in which people can rest"
    assert grammar["questions"][3]["answer"] == "be reviewed"
    assert grammar["questions"][8]["answer"] == "has planted"

    transport = passages["M26-NEW-CLOZE-02"]
    assert "provisional" not in transport["questions"][1]["options"]
    assert transport["questions"][6]["options"] == [
        "modest",
        "sharp",
        "frequent",
        "absent",
    ]
    assert "could not walk far" not in transport["passage"].split(
        "so the town introduced", 1
    )[1]

    repair = passages["M26-NEW-READING-02"]
    assert "咖啡馆" not in repair["questions"][2]["explanation"]
    assert "（千克）" not in repair["passage"]

    gap_options = passages["M26-NEW-GAP-01"]["options"]
    assert gap_options["B"].startswith("Over time")
    assert gap_options["C"].startswith("However")
    assert gap_options["G"].startswith("For example")

    assert package["difficulty_profile"] == "advanced"

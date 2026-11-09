from __future__ import annotations

import json
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
    for paper_number in (1, 2):
        selected, log = assemble_demo_paper(
            questions,
            paper_number,
            {},
        )

        assert len(selected) == log["question_count"]
        assert set(log["question_type_counts"]) == {
            "cloze",
            "grammar_fill",
            log["paper_mode"],
        }
        assert log["selected_passage_groups"] == list(
            dict.fromkeys(
                question.passage_group_id for question in selected
            )
        )
        assert log["selected_unseen_passage_count"] == 3
        assert log["selected_total_passage_coverage_count"] == 0
        assert log["selected_distinct_topic_count"] == len(log["topics"])
        assert log["selection_basis"] == (
            "lowest_passage_coverage_then_distinct_topics"
        )


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

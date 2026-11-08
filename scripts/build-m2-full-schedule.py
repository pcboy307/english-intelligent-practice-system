#!/usr/bin/env python3
"""Build a deterministic 47-passage schedule for M2."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "config" / "m2-full-schedule.json"

TYPE_COUNTS = {
    "cloze": (6, 15),
    "grammar_fill": (6, 10),
    "reading": (25, 4),
    "gap_fill": (10, 5),
}
DIFFICULTY_BY_TYPE = {
    "cloze": {1: 14, 2: 27, 3: 32, 4: 14, 5: 3},
    "grammar_fill": {1: 9, 2: 18, 3: 21, 4: 9, 5: 3},
    "reading": {1: 15, 2: 30, 3: 35, 4: 15, 5: 5},
    "gap_fill": {1: 7, 2: 15, 3: 17, 4: 7, 5: 4},
}
BOOK_COUNTS_CLOZE = {"选必二": 49, "选必一": 35, "必修": 2, "跨册": 4}
READING_TYPES = [
    "main_idea",
    "detail",
    "inference",
    "vocabulary_in_context",
    "purpose_or_attitude",
]
COHESION_TYPES = (
    ["pronoun_reference"] * 13
    + ["logical_connector"] * 13
    + ["lexical_repetition"] * 12
    + ["semantic_contrast"] * 12
)
TOPICS = {
    "cloze": [
        "青春成长与自我认识",
        "团队合作与责任",
        "健康生活与自律",
        "数字学习与选择",
        "环境保护与行动",
        "生涯规划与目标",
    ],
    "grammar_fill": [
        "科学探究",
        "校园运动",
        "社区服务",
        "旅行与交通",
        "艺术与文化",
        "未来职业",
    ],
    "reading": [
        "饮食文化",
        "气候变化行动",
        "人工智能与学习",
        "睡眠科学",
        "志愿服务",
        "传统节日",
        "城市花园",
        "体育精神",
        "音乐学习",
        "数字隐私",
        "海洋塑料",
        "博物馆教育",
        "公共图书馆",
        "可再生能源",
        "友谊与信任",
        "时间管理",
        "野生动物保护",
        "在线学习",
        "可持续旅游",
        "改变生活的发明",
        "学习压力",
        "循环经济",
        "太空探索",
        "地方历史",
        "自动化与工作",
    ],
    "gap_fill": [
        "高效学习习惯",
        "校园科学展",
        "健康作息",
        "户外活动",
        "面对失败",
        "博物馆参观",
        "环保社团",
        "沟通技巧",
        "旅行准备",
        "阅读习惯",
    ],
}
UNIT_BY_TAG = {
    "选必二": [f"选必二 U{i}" for i in range(1, 6)],
    "选必一": [f"选必一 U{i}" for i in range(1, 6)],
    "必修": [f"必修{i} U{u}" for i in range(1, 4) for u in range(1, 4)],
    "跨册": ["跨册综合"],
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def book_tag(book_source: str) -> str:
    compact = re.sub(r"\s+", "", book_source)
    if compact.startswith("选必二"):
        return "选必二"
    if compact.startswith("选必一"):
        return "选必一"
    if compact.startswith("跨册"):
        return "跨册"
    if compact.startswith("必修"):
        return "必修"
    return ""


def grammar_allowed() -> dict[str, list[str]]:
    curriculum = load_json(ROOT / "contracts" / "curriculum.json")
    return {
        item["id"]: list(item["allowed_book_tags"])
        for item in curriculum["grammar_whitelist"]
    }


def grammar_tag_plan() -> list[str]:
    quota = load_json(ROOT / "config" / "m2-quota-allocation.json")
    return [
        tag
        for tag, count in quota["grammar_tag_targets"].items()
        for _ in range(count)
    ]


GRAMMAR_BOOK_PLANS = {
    "relative_clauses_defining": ["必修"] * 3,
    "relative_clauses_non_defining": ["选必一", "选必一", "跨册"],
    "passive_voice_tenses": ["选必二"] * 3,
    "past_participle_nonfinite": ["必修"] * 3,
    "v_ing_nonfinite": ["选必一", "选必一", "跨册"],
    "noun_clauses": ["选必二", "选必二", "选必二"],
    "adverbial_clauses": ["必修"] * 3,
    "subjunctive_basic_if": ["选必二", "选必二", "选必二"],
    "subjunctive_basic_should": ["选必二", "选必二", "选必一"],
    "partial_inversion_basic": ["选必二"] * 3,
    "cleft_basic": ["选必一", "选必一", "跨册"],
    "tense_system": ["选必二", "选必二", "选必二"],
    "subject_verb_agreement": ["必修"] * 3,
    "articles": ["必修"] * 3,
    "prepositions": ["必修"] * 3,
    "pronouns": ["必修"] * 3,
    "conjunctions": ["必修"] * 3,
    "word_formation": ["选必一", "选必二", "选必二"],
    "comparatives_superlatives": ["必修"] * 2,
    "with_compound": ["选必一"] * 2,
    "infinitive_nonfinite": ["必修"] * 2,
}


def grammar_assignments() -> list[tuple[str, str]]:
    used = Counter()
    result = []
    for tag in grammar_tag_plan():
        result.append((tag, GRAMMAR_BOOK_PLANS[tag][used[tag]]))
        used[tag] += 1
    return result


def distribute_sequence(counts: dict[int, int]) -> list[int]:
    values = [level for level in range(1, 6) for _ in range(counts[level])]
    result = []
    while values:
        for level in (3, 2, 4, 1, 5):
            if level in values:
                result.append(level)
                values.remove(level)
    return result


def book_sequence(target_counts: dict[str, int]) -> list[str]:
    books = []
    while sum(target_counts.values()):
        for book in ("选必二", "选必一", "必修", "跨册"):
            if target_counts[book]:
                books.append(book)
                target_counts[book] -= 1
    return books


def choose_tag_for_book(book: str, offset: int) -> str:
    allowed = grammar_allowed()
    candidates = sorted(
        tag for tag, values in allowed.items() if book in values
    )
    return candidates[offset % len(candidates)]


def build_schedule() -> dict:
    words = [
        item["word"]
        for item in load_json(
            ROOT / "contracts" / "high-frequency-cloze-words.json"
        )["words"]
    ]
    grammar_plan = grammar_assignments()
    if len(grammar_plan) != 60:
        raise RuntimeError("GRAMMAR_BOOK_ASSIGNMENT_COUNT_MISMATCH")
    cloze_books = book_sequence(dict(BOOK_COUNTS_CLOZE))
    book_offsets = Counter()
    passages = []

    for passage_index in range(6):
        target_slice = words[passage_index % 3 * 15 : passage_index % 3 * 15 + 15]
        difficulty_values = distribute_sequence(DIFFICULTY_BY_TYPE["cloze"])[
            passage_index * 15 : (passage_index + 1) * 15
        ]
        questions = []
        for question_index, (target, level) in enumerate(
            zip(target_slice, difficulty_values, strict=True),
            start=1,
        ):
            book = cloze_books[passage_index * 15 + question_index - 1]
            offset = book_offsets[book]
            book_offsets[book] += 1
            questions.append(
                {
                    "question_index": question_index,
                    "book_source": UNIT_BY_TAG[book][
                        passage_index % len(UNIT_BY_TAG[book])
                    ],
                    "difficulty": level,
                    "grammar_tags": [choose_tag_for_book(book, offset)],
                    "cloze_target": target,
                }
            )
        passages.append(
            {
                "type": "cloze",
                "passage_group_id": f"M2-FULL-CLOZE-{passage_index + 1:02d}",
                "topic": TOPICS["cloze"][passage_index],
                "book_source": questions[0]["book_source"],
                "difficulty": 3,
                "questions": questions,
            }
        )

    grammar_difficulty = distribute_sequence(DIFFICULTY_BY_TYPE["grammar_fill"])
    for passage_index in range(6):
        questions = []
        for question_index in range(10):
            overall = passage_index * 10 + question_index
            tag, book = grammar_plan[overall]
            questions.append(
                {
                    "question_index": question_index + 1,
                    "book_source": UNIT_BY_TAG[book][
                        passage_index % len(UNIT_BY_TAG[book])
                    ],
                    "difficulty": grammar_difficulty[overall],
                    "grammar_tags": [tag],
                }
            )
        passages.append(
            {
                "type": "grammar_fill",
                "passage_group_id": f"M2-FULL-GRAMMAR-{passage_index + 1:02d}",
                "topic": TOPICS["grammar_fill"][passage_index],
                "book_source": questions[0]["book_source"],
                "difficulty": 3,
                "questions": questions,
            }
        )

    reading_difficulty = distribute_sequence(DIFFICULTY_BY_TYPE["reading"])
    reading_types = READING_TYPES * 20
    for passage_index in range(25):
        questions = []
        for question_index in range(4):
            overall = passage_index * 4 + question_index
            book = (
                "选必二"
                if overall % 5 in {0, 1}
                else "选必一"
                if overall % 5 == 2
                else "必修"
            )
            questions.append(
                {
                    "question_index": question_index + 1,
                    "book_source": UNIT_BY_TAG[book][
                        passage_index % len(UNIT_BY_TAG[book])
                    ],
                    "difficulty": reading_difficulty[overall],
                    "grammar_tags": [
                        choose_tag_for_book(book, overall)
                    ],
                    "reading_type": reading_types[overall],
                }
            )
        passages.append(
            {
                "type": "reading",
                "passage_group_id": f"M2-FULL-READING-{passage_index + 1:02d}",
                "topic": TOPICS["reading"][passage_index],
                "book_source": questions[0]["book_source"],
                "difficulty": 3,
                "questions": questions,
            }
        )

    gap_difficulty = distribute_sequence(DIFFICULTY_BY_TYPE["gap_fill"])
    cohesion_types = COHESION_TYPES[:]
    for passage_index in range(10):
        questions = []
        for question_index in range(5):
            overall = passage_index * 5 + question_index
            book = (
                "选必二"
                if overall % 2 == 0
                else "选必一"
                if overall % 3 == 0
                else "必修"
            )
            questions.append(
                {
                    "question_index": question_index + 1,
                    "book_source": UNIT_BY_TAG[book][
                        passage_index % len(UNIT_BY_TAG[book])
                    ],
                    "difficulty": gap_difficulty[overall],
                    "grammar_tags": [
                        choose_tag_for_book(book, overall)
                    ],
                    "cohesion_type": cohesion_types[overall],
                }
            )
        passages.append(
            {
                "type": "gap_fill",
                "passage_group_id": f"M2-FULL-GAP-{passage_index + 1:02d}",
                "topic": TOPICS["gap_fill"][passage_index],
                "book_source": questions[0]["book_source"],
                "difficulty": 3,
                "questions": questions,
            }
        )

    return {
        "schema_version": "1.0.0",
        "bank_name": "M2 Bank #2",
        "target_questions": 300,
        "passages": passages,
    }


def main() -> None:
    schedule = build_schedule()
    OUTPUT.write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "passages": len(schedule["passages"]),
                "questions": sum(
                    len(item["questions"]) for item in schedule["passages"]
                ),
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

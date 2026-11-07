"""Deterministic 30-question half-day demo bank.

This fixture deliberately contains one cloze, one grammar-fill and one gap-fill
passage. It is temporary sprint content, not Bank#1 production content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

BANK_ID = "00000000-0000-4000-8000-000000000001"


@dataclass(frozen=True)
class DemoQuestion:
    id: str
    bank_id: str
    type: str
    passage_group_id: str
    passage: str
    stem: str
    options: list[str] | None
    answer: str
    explanation: str
    knowledge_points: list[str]
    grammar_tags: list[str]
    book_source: str
    difficulty: int

    @property
    def question_order(self) -> int:
        match = re.search(r"(\d+)$", self.id)
        if not match:
            raise ValueError(f"Question ID has no ordinal: {self.id}")
        return int(match.group(1))

    @property
    def passage_order(self) -> int:
        prefix = self.passage_group_id.rsplit("-", 2)[-2]
        return {"CLOZE": 1, "GRAMMAR": 2, "GAP": 3}[prefix]

    @property
    def blank_label(self) -> str:
        if self.type == "grammar_fill":
            return chr(0x2460 + self.question_order - 1)
        return f"({self.question_order})"

    @property
    def presentation_mode(self) -> str:
        return {
            "cloze": "cloze_single_choice",
            "grammar_fill": "passage_single_choice",
            "gap_fill": "seven_choice",
        }[self.type]


CLOZE_TEXT = (
    "Last April, our class joined a cleanup at the local beach. We met early in "
    "the morning and divided into small (1) so that every area could be checked. "
    "We collected bottles, paper and pieces of (2) from the sand. Everyone worked "
    "(3) because broken glass could hurt someone. (4) the work was tiring, nobody "
    "complained. Our teacher (5) that each group should record what it found. The "
    "result showed that most waste came from food packaging. We made a (6) to "
    "reduce this waste at school. Near noon, we (7) a group of birds beside the "
    "water. We moved away quietly to (8) disturbing them. Some volunteers had "
    "(9) worked at the beach before, so they knew the safest route. We finished "
    "the task (10) using any plastic bags. The local officer said our (11) was "
    "valuable, and asked us to share the data with the community. We also agreed "
    "that the message should (12) beyond our classroom. A week later, more "
    "families joined the next cleanup. Although the beach looked cleaner, we felt "
    "(13) about the work we had done. Protecting the coast requires steady action, "
    "and every small step is part of a larger (14). We left with a clear sense of "
    "(15)."
)

CLOZE_QA = [
    ("teams", ["groups", "teams", "pieces", "signs"], "team", "team"),
    ("plastic", ["plastic", "music", "weather", "silence"], "noun_context", "noun_phrase"),
    ("carefully", ["carefully", "loudly", "suddenly", "rarely"], "adverb", "word_formation"),
    ("Although", ["Because", "Although", "Unless", "So"], "concession", "adverbial_clauses"),
    ("suggested", ["suggested", "refused", "forgot", "divided"], "verb_meaning", "conjunctions"),
    ("decision", ["decision", "distance", "direction", "difficulty"], "noun_choice", "word_formation"),
    ("noticed", ["noticed", "covered", "borrowed", "replaced"], "context_verb", "tense_system"),
    ("avoid", ["avoid", "finish", "invite", "prepare"], "verb_pattern", "v_ing_nonfinite"),
    ("already", ["already", "instead", "hardly", "perhaps"], "adverb_context", "adverbs"),
    ("without", ["without", "against", "between", "during"], "preposition", "prepositions"),
    ("effort", ["effort", "habit", "product", "promise"], "noun_context", "noun_phrases"),
    ("reach", ["reach", "hide", "divide", "remain"], "verb_meaning", "conjunctions"),
    ("proud", ["proud", "tired", "afraid", "silent"], "adjective_context", "comparatives"),
    ("project", ["project", "journey", "lesson", "surface"], "noun_context", "reading_detail"),
    ("achievement", ["achievement", "attention", "argument", "adventure"], "noun_context", "word_formation"),
]

GRAMMAR_TEXT = (
    "Community gardens ① popular in many cities for many years. They give people "
    "a chance to grow their own food and meet their neighbours. A garden ② on "
    "unused land last year is now used by more than fifty families. People work "
    "together because the space ③ by everyone. Before planting, they must decide "
    "what ④ and where each plant should go. Some volunteers ⑤ in the garden for "
    "two years and know its soil well. They explain that young plants ⑥ protection "
    "from strong wind. Everyone is asked to keep the paths clear so that all "
    "visitors can move ⑦. The garden is not only beautiful ⑧ also useful. It teaches "
    "children where food comes from, and it reminds adults ⑨ about waste. If more "
    "residents join next season, the project ⑩ even stronger."
)

GRAMMAR_QA = [
    ("have become", ["have become", "had become", "will become", "are becoming"], "tense_system", "for many years 表示动作持续到现在，应使用现在完成时。", "现在完成时"),
    ("built", ["build", "building", "built", "to build"], "past_participle_nonfinite", "garden 与 build 是被动关系，过去分词 built 作后置定语。", "过去分词作定语"),
    ("is shared", ["shares", "shared", "is shared", "will share"], "passive_voice_tenses", "space 与 share 是被动关系，整句为一般现在时，因此使用 is shared。", "一般现在时被动语态"),
    ("to grow", ["grow", "growing", "to grow", "grown"], "infinitive_nonfinite", "what 后使用不定式表示需要种植的内容，to grow 符合结构。", "不定式作宾语"),
    ("have worked", ["work", "worked", "have worked", "will work"], "tense_system", "for two years 表示从过去持续到现在，应使用现在完成时。", "现在完成时"),
    ("need", ["need", "needs", "needed", "needing"], "subject_verb_agreement", "主语 young plants 为复数，一般现在时谓语使用 need。", "主谓一致"),
    ("safely", ["safe", "safety", "safely", "unsafe"], "word_formation", "move 是动词，需要用副词 safely 修饰。", "副词化"),
    ("but", ["and", "but", "or", "so"], "conjunctions", "not only ... but also ... 是固定并列结构。", "并列连词"),
    ("to think", ["think", "thinking", "to think", "thought"], "infinitive_nonfinite", "remind sb to do sth 是固定结构，因此使用 to think。", "不定式作宾补"),
    ("will become", ["becomes", "became", "will become", "would have become"], "subjunctive_basic_if", "条件句描述将来可能发生的结果，主句使用一般将来时 will become。", "条件句中的将来表达"),
]

GAP_TEXT = (
    "A school wants to start a weekend reading club. The plan explains how "
    "students can join and what they should bring. First, interested students "
    "should write their names on the notice board. (1) The club will then arrange "
    "a short meeting. At the meeting, members will choose books together. "
    "(2) Group leaders will help younger students find books that are right for "
    "them. The club will meet every Saturday morning in the library. (3) Students "
    "are expected to return the books they borrow. At the end of each month, the "
    "group will discuss what they have read. (4) Everyone can speak for two "
    "minutes about a favourite part. New members are always welcome. (5) The "
    "school hopes the club will help students enjoy reading and share ideas."
)

GAP_OPTIONS = [
    "A. This gives everyone time to prepare.",
    "B. The books should be returned on time.",
    "C. It also gives them a chance to make new friends.",
    "D. They can ask questions when they are unsure.",
    "E. A favourite story may be shared at the meeting.",
    "F. This simple step helps the organizers plan.",
    "G. The club has already become popular.",
]

GAP_QA = [
    ("F", "transition", "前文要求学生在公告板上写名字，下一步自然是帮助组织者安排活动。", "该句承接报名后的活动安排。"),
    ("C", "addition", "该段在补充小组长帮助学生的另一项好处。", "所补句子应与前一句形成递进关系。"),
    ("D", "support", "学生借书前可能需要向小组长寻求帮助。", "该句提供借书前的实际指导。"),
    ("A", "sequence", "限制每人发言两分钟，可以为下一位成员留下准备时间。", "该句体现了发言时间安排带来的结果。"),
    ("B", "closing", "最后应落到学校希望学生享受阅读并分享想法这一目的。", "该句总结阅读俱乐部的预期成果。"),
]


CLOZE_REASONS = {
    "team": "small groups 表示把学生分成小组。",
    "noun_context": "该词与所在句子的名词语境一致。",
    "adverb": "此处需要副词修饰 worked。",
    "concession": "前后句是让步关系，Although 符合逻辑。",
    "verb_meaning": "该动词与教师记录结果这一语境一致。",
    "noun_choice": "该名词与 make a decision 的固定搭配一致。",
    "context_verb": "该动词表示在水边注意到一群鸟。",
    "verb_pattern": "avoid doing 表示避免做某事。",
    "adverb_context": "already 与该句完成时语境一致。",
    "preposition": "without 表示没有使用塑料袋。",
    "adjective_context": "proud 与完成清理后的感受一致。",
    "reading_detail": "该名词与前文的清理活动相呼应。",
}


def _explanation(answer: str, point: str) -> str:
    reason = CLOZE_REASONS.get(point, "该选项与句子结构和上下文最为匹配。")
    return f"正确答案是 {answer}。{reason}其余选项在语境或语法上不合适。"


def build_demo_questions() -> list[DemoQuestion]:
    questions: list[DemoQuestion] = []
    for number, (answer, options, point, tag) in enumerate(CLOZE_QA, start=1):
        questions.append(
            DemoQuestion(
                id=f"DEMO-C{number:02d}",
                bank_id=BANK_ID,
                type="cloze",
                passage_group_id="DEMO-CLOZE-01",
                passage=CLOZE_TEXT,
                stem=f"选择第 {number} 空最合适的选项。",
                options=options,
                answer=answer,
                explanation=_explanation(answer, point),
                knowledge_points=[point],
                grammar_tags=[tag],
                book_source="选必二 U3",
                difficulty=3 if number < 12 else 4,
            )
        )
    for number, (answer, options, tag, explanation, point) in enumerate(GRAMMAR_QA, start=1):
        questions.append(
            DemoQuestion(
                id=f"DEMO-G{number:02d}",
                bank_id=BANK_ID,
                type="grammar_fill",
                passage_group_id="DEMO-GRAMMAR-01",
                passage=GRAMMAR_TEXT,
                stem=f"选择 {chr(0x2460 + number - 1)} 处最合适的选项。",
                options=options,
                answer=answer,
                explanation=f"正确答案是 {answer}。{explanation}",
                knowledge_points=[point],
                grammar_tags=[tag],
                book_source="选必一 U3",
                difficulty=3,
            )
        )
    for number, (answer, link_type, fit, point) in enumerate(GAP_QA, start=1):
        questions.append(
            DemoQuestion(
                id=f"DEMO-P{number:02d}",
                bank_id=BANK_ID,
                type="gap_fill",
                passage_group_id="DEMO-GAP-01",
                passage=GAP_TEXT,
                stem=f"选择最适合第 {number} 空的句子。",
                options=GAP_OPTIONS,
                answer=answer,
                explanation=f"正确答案是 {answer}。{fit}{point}",
                knowledge_points=[f"gap_fill_{link_type}"],
                grammar_tags=["conjunctions"],
                book_source="必修二 U1",
                difficulty=3,
            )
        )
    return questions


def demo_bank() -> dict:
    return {
        "bank_id": BANK_ID,
        "name": "Demo Bank",
        "version": "1",
        "status": "active",
        "target_size": 30,
        "difficulty_profile": "standard",
        "created_at": datetime(2026, 11, 7, tzinfo=timezone.utc).isoformat(),
        "questions": build_demo_questions(),
    }

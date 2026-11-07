"""Deterministic 30-question half-day demo bank.

This fixture deliberately contains one cloze, one grammar-fill and one gap-fill
passage. It is temporary sprint content, not Bank#1 production content.
"""

from __future__ import annotations

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
    "Community gardens (1) [become] popular in many cities. They give people a "
    "chance to grow their own food and meet their neighbours. A garden (2) [build] "
    "on unused land last year is now used by more than fifty families. People work "
    "together because the space (3) [share] by everyone. Before planting, they must "
    "decide what (4) [grow] and where each plant should go. Some volunteers "
    "(5) [work] in the garden for two years and know its soil well. They explain "
    "that young plants (6) [need] protection from strong wind. Everyone is asked "
    "to keep the paths clear so that all visitors can move (7) [safe]. The garden "
    "is not only beautiful (8) also useful. It teaches children where food comes "
    "from, and it reminds adults (9) [think] about waste. If more residents joined "
    "next season, the project (10) [become] even stronger."
)

GRAMMAR_QA = [
    ("have become", "tense_system", "Present perfect describes a state that started in the past and continues now.", "现在完成时"),
    ("built", "past_participle_nonfinite", "The past participle modifies the noun garden.", "过去分词作定语"),
    ("is shared", "passive_voice_tenses", "The space receives the action and the sentence is present passive.", "一般现在时被动"),
    ("to grow", "infinitive_nonfinite", "What is followed by an infinitive and to grow expresses the purpose.", "不定式作宾语"),
    ("have worked", "tense_system", "For two years signals present perfect.", "现在完成时"),
    ("need", "subject_verb_agreement", "The plural subject young plants takes need.", "主谓一致"),
    ("safely", "word_formation", "The adverb safely modifies the verb move.", "副词化"),
    ("but", "conjunctions", "Not only is paired with but also.", "并列连词"),
    ("to think", "infinitive_nonfinite", "Remind can be followed by an object and an infinitive.", "不定式作宾补"),
    ("will become", "subjunctive_basic_if", "The if clause uses a present form and the main clause describes a likely future result.", "第一类条件句"),
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
    ("F", "transition", "After asking students to put names on the board, the next logical step is planning.", "The sentence explains the result of collecting names."),
    ("C", "addition", "The paragraph is adding another benefit of group leaders helping students.", "The added benefit follows the previous sentence."),
    ("D", "support", "Before returning books, students may need help from club leaders.", "The sentence offers practical guidance to members."),
    ("A", "sequence", "The discussion length gives the next member time to prepare.", "The sentence shows the result of limiting each talk to two minutes."),
    ("B", "closing", "A closing sentence about the school's hope follows the club's practical purpose.", "The final sentence summarizes the desired outcome."),
]


def _explanation(answer: str, point: str) -> str:
    return (
        f"The correct answer is {answer}. "
        f"It matches the grammatical and semantic context for {point}. "
        "The other choices do not fit the local meaning or structure."
    )


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
                stem=f"Choose the best word for blank ({number}).",
                options=options,
                answer=answer,
                explanation=_explanation(answer, point),
                knowledge_points=[point],
                grammar_tags=[tag],
                book_source="选必二 U3",
                difficulty=3 if number < 12 else 4,
            )
        )
    for number, (answer, tag, fit, point) in enumerate(GRAMMAR_QA, start=1):
        questions.append(
            DemoQuestion(
                id=f"DEMO-G{number:02d}",
                bank_id=BANK_ID,
                type="grammar_fill",
                passage_group_id="DEMO-GRAMMAR-01",
                passage=GRAMMAR_TEXT,
                stem=f"Fill in blank ({number}) with the correct form. Prompt: {GRAMMAR_TEXT.split(f'({number}) ')[1].split()[0]}",
                options=None,
                answer=answer,
                explanation=f"The correct answer is {answer}. {fit} The form fits the complete sentence and its grammatical context.",
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
                stem=f"Choose the sentence that best fits blank ({number}).",
                options=GAP_OPTIONS,
                answer=answer,
                explanation=f"The correct answer is {answer}. {fit} The link type is {link_type}; {point}",
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

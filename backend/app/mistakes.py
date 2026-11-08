from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


QUESTION_TYPE = {
    "cloze": "cloze",
    "grammar_fill": "grammar",
    "reading": "reading",
    "gap_fill": "seven",
}


def mistake_key(question_type: str, question_id: str, passage_id: str) -> str:
    return f"seven:{passage_id}" if question_type == "gap_fill" else question_id


def question_label(question_type: str, question_id: str) -> str:
    if question_type == "gap_fill":
        return "七选五全篇"
    match = re.search(r"(\d+)$", question_id)
    number = str(int(match.group(1))) if match else "?"
    if question_type in {"cloze", "grammar_fill"}:
        return f"第{number}空"
    return f"第{number}题"


def record_session_results(
    connection: Connection,
    *,
    student_id: str,
    session_id: str,
    bank_id: str,
    attempt_kind: str,
    results: list[dict],
    now: datetime,
) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        db_type = result["type"]
        mapped_type = QUESTION_TYPE[db_type]
        passage_id = result["passage_group_id"]
        key = mistake_key(db_type, result["question_id"], passage_id)
        grouped[key].append(result)
        connection.execute(
            """
            INSERT INTO question_attempts
                (student_id, session_id, bank_id, question_id, passage_id,
                 question_type, chosen_option, correct_option, is_correct,
                 attempt_kind, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                student_id,
                session_id,
                bank_id,
                result["question_id"],
                passage_id,
                mapped_type,
                str(result["user_answer"]),
                str(result["correct_answer"]),
                result["correct"],
                attempt_kind,
                now,
            ),
        )

    for key, unit_results in grouped.items():
        first = unit_results[0]
        db_type = first["type"]
        mapped_type = QUESTION_TYPE[db_type]
        passage_id = first["passage_group_id"]
        is_wrong = (
            not all(result["correct"] for result in unit_results)
            if db_type == "gap_fill"
            else not first["correct"]
        )
        if is_wrong:
            connection.execute(
                """
                INSERT INTO mistake_items
                    (student_id, bank_id, question_id, passage_id, question_type,
                     first_wrong_at, last_wrong_at, wrong_count, correct_streak,
                     status, mastered_at, last_review_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 0, 'open', NULL,
                        CASE WHEN %s='review' THEN %s ELSE NULL END)
                ON CONFLICT (student_id, bank_id, question_id)
                DO UPDATE SET
                    passage_id=EXCLUDED.passage_id,
                    question_type=EXCLUDED.question_type,
                    last_wrong_at=EXCLUDED.last_wrong_at,
                    wrong_count=mistake_items.wrong_count + 1,
                    correct_streak=0,
                    status='open',
                    mastered_at=NULL,
                    last_review_at=CASE
                        WHEN %s='review' THEN EXCLUDED.last_review_at
                        ELSE mistake_items.last_review_at
                    END
                """,
                (
                    student_id,
                    bank_id,
                    key,
                    passage_id,
                    mapped_type,
                    now,
                    now,
                    attempt_kind,
                    now,
                    attempt_kind,
                ),
            )
        elif attempt_kind == "review":
            connection.execute(
                """
                UPDATE mistake_items
                SET correct_streak=LEAST(2, correct_streak + 1),
                    status=CASE
                        WHEN correct_streak + 1 >= 2 THEN 'mastered'
                        ELSE 'open'
                    END,
                    mastered_at=CASE
                        WHEN correct_streak + 1 >= 2 THEN %s
                        ELSE mastered_at
                    END,
                    last_review_at=%s
                WHERE student_id=%s AND bank_id=%s AND question_id=%s
                """,
                (now, now, student_id, bank_id, key),
            )


def list_open_mistakes(
    connection: Connection,
    *,
    student_id: str,
    active_bank_id: str,
) -> dict:
    active_bank = connection.execute(
        "SELECT id::text AS id, name FROM question_banks WHERE id=%s",
        (active_bank_id,),
    ).fetchone()
    active_question_ids = {
        row["id"]
        for row in connection.execute(
            """
            SELECT id
            FROM questions
            WHERE bank_id=%s AND status='published'
            """,
            (active_bank_id,),
        ).fetchall()
    }
    active_passage_ids = {
        row["passage_group_id"]
        for row in connection.execute(
            """
            SELECT DISTINCT passage_group_id
            FROM questions
            WHERE bank_id=%s AND status='published'
            """,
            (active_bank_id,),
        ).fetchall()
    }
    rows = connection.execute(
        """
        SELECT student_id, bank_id, question_id, passage_id, question_type,
               first_wrong_at, last_wrong_at, wrong_count, correct_streak,
               status, mastered_at, last_review_at
        FROM mistake_items
        WHERE student_id=%s AND status='open'
        ORDER BY last_wrong_at DESC, passage_id, question_id
        """,
        (student_id,),
    ).fetchall()
    bank_names = {
        str(row["id"]): row["name"]
        for row in connection.execute(
            "SELECT id, name FROM question_banks"
        ).fetchall()
    }

    current_items: list[dict] = []
    historical_by_bank: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        item = {
            "question_id": row["question_id"],
            "passage_id": row["passage_id"],
            "question_type": row["question_type"],
            "label": (
                "七选五全篇"
                if row["question_type"] == "seven"
                else _label_from_key(row["question_id"])
            ),
            "wrong_count": row["wrong_count"],
            "correct_streak": row["correct_streak"],
            "status": row["status"],
        }
        row_bank_id = str(row["bank_id"])
        current = row_bank_id == active_bank_id
        if not current:
            if row["question_type"] == "seven" and row["passage_id"] in active_passage_ids:
                current = True
            elif row["question_id"] in active_question_ids:
                current = True
        if current:
            current_items.append(item)
        else:
            historical_by_bank[row_bank_id].append(item)

    def group(bank_id: str, bank_name: str, items: list[dict]) -> dict:
        by_passage: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            by_passage[item["passage_id"]].append(item)
        passages = []
        for passage_id, passage_items in sorted(by_passage.items()):
            passages.append(
                {
                    "passage_id": passage_id,
                    "question_type": passage_items[0]["question_type"],
                    "items": sorted(
                        passage_items,
                        key=lambda value: value["question_id"],
                    ),
                }
            )
        return {
            "bank_id": bank_id,
            "bank_name": bank_name,
            "count": len(items),
            "passages": passages,
        }

    return {
        "current_bank": group(
            active_bank_id,
            active_bank["name"],
            current_items,
        ),
        "history_banks": [
            group(bank_id, bank_names.get(bank_id, "历史题库"), items)
            for bank_id, items in sorted(historical_by_bank.items())
        ],
        "total_open": len(rows),
    }


def get_passage_mistake_detail(
    connection: Connection,
    *,
    student_id: str,
    passage_id: str,
    active_bank_id: str,
) -> dict:
    rows = connection.execute(
        """
        SELECT student_id, bank_id, question_id, passage_id, question_type,
               first_wrong_at, last_wrong_at, wrong_count, correct_streak,
               status, mastered_at, last_review_at
        FROM mistake_items
        WHERE student_id=%s AND passage_id=%s AND status='open'
        ORDER BY last_wrong_at DESC
        """,
        (student_id, passage_id),
    ).fetchall()
    if not rows:
        raise KeyError("MISTAKES_NOT_FOUND")
    active_has_passage = connection.execute(
        """
        SELECT 1
        FROM questions
        WHERE bank_id=%s AND passage_group_id=%s AND status='published'
        LIMIT 1
        """,
        (active_bank_id, passage_id),
    ).fetchone()
    bank_id = (
        active_bank_id
        if active_has_passage
        else str(rows[0]["bank_id"])
    )
    passage = connection.execute(
        """
        SELECT p.id::text AS passage_row_id, p.passage_group_id, p.type,
               p.content, qb.name AS bank_name
        FROM passages p
        JOIN question_banks qb ON qb.id=p.bank_id
        WHERE p.bank_id=%s AND p.passage_group_id=%s
        """,
        (bank_id, passage_id),
    ).fetchone()
    if not passage:
        raise KeyError("PASSAGE_NOT_FOUND")
    questions = connection.execute(
        """
        SELECT id, type, passage_group_id, stem, options, answer
        FROM questions
        WHERE bank_id=%s AND passage_group_id=%s AND status='published'
        ORDER BY id
        """,
        (bank_id, passage_id),
    ).fetchall()
    bank_rows = [
        row for row in rows if str(row["bank_id"]) == bank_id
    ]
    mapped_type = QUESTION_TYPE[passage["type"]]
    if mapped_type == "seven":
        target_items = [
            {
                "question_id": f"seven:{passage_id}",
                "passage_id": passage_id,
                "question_type": "seven",
                "label": "七选五全篇",
                "wrong_count": sum(row["wrong_count"] for row in bank_rows),
                "correct_streak": min(
                    row["correct_streak"] for row in bank_rows
                ),
                "status": "open",
            }
        ]
        target_question_ids = {row["id"] for row in questions}
    else:
        target_items = [
            {
                "question_id": row["question_id"],
                "passage_id": row["passage_id"],
                "question_type": row["question_type"],
                "label": question_label(row["question_type"], row["question_id"]),
                "wrong_count": row["wrong_count"],
                "correct_streak": row["correct_streak"],
                "status": row["status"],
            }
            for row in bank_rows
        ]
        target_question_ids = {
            item["question_id"] for item in target_items
        }
    question_payload = []
    for row in questions:
        question_payload.append(
            {
                "question_id": row["id"],
                "type": row["type"],
                "passage_group_id": row["passage_group_id"],
                "stem": row["stem"],
                "options": row["options"] or [],
                "answer": row["answer"],
                "label": question_label(row["type"], row["id"]),
                "locked": row["id"] not in target_question_ids,
            }
        )
    return {
        "bank_id": bank_id,
        "bank_name": passage["bank_name"],
        "passage_id": passage_id,
        "question_type": mapped_type,
        "passage": passage["content"],
        "questions": question_payload,
        "target_items": target_items,
        "target_question_ids": sorted(target_question_ids),
    }


def _label_from_key(question_id: str) -> str:
    match = re.search(r"(\d+)$", question_id)
    return f"第{int(match.group(1))}题" if match else question_id


def create_review_composition(
    *,
    bank_id: str,
    bank_name: str,
    passage_id: str,
    target_question_ids: list[str],
) -> dict:
    return {
        "bank_name": bank_name,
        "session_kind": "review",
        "review_passage_id": passage_id,
        "target_question_ids": target_question_ids,
        "question_type_counts": {"review": len(target_question_ids)},
        "review_context": True,
    }


def session_attempt_kind(session_kind: str) -> str:
    return "review" if session_kind == "review" else "practice"


def coverage_statistics(
    connection: Connection,
    *,
    student_id: str,
    active_bank_id: str,
) -> dict:
    bank = connection.execute(
        "SELECT name FROM question_banks WHERE id=%s",
        (active_bank_id,),
    ).fetchone()
    if not bank:
        raise KeyError("ACTIVE_BANK_NOT_FOUND")
    question_ids = [
        row["id"]
        for row in connection.execute(
            """
            SELECT id
            FROM questions
            WHERE bank_id=%s AND status='published'
            """,
            (active_bank_id,),
        ).fetchall()
    ]
    appearances = {
        row["question_id"]: row["session_count"]
        for row in connection.execute(
            """
            SELECT qa.question_id, count(DISTINCT qa.session_id) AS session_count
            FROM question_attempts qa
            JOIN practice_sessions ps ON ps.id=qa.session_id
            WHERE qa.student_id=%s
              AND qa.question_id=ANY(%s)
              AND ps.status='submitted'
            GROUP BY qa.question_id
            """,
            (student_id, question_ids),
        ).fetchall()
    }
    twice_plus = sum(appearances.get(question_id, 0) >= 2 for question_id in question_ids)
    once = sum(appearances.get(question_id, 0) == 1 for question_id in question_ids)
    none = len(question_ids) - once - twice_plus
    total = len(question_ids)
    assert none + once + twice_plus == total
    return {
        "total": total,
        "none": none,
        "once": once,
        "twice_plus": twice_plus,
        "bank_name": bank["name"],
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


def clear_mistakes_preview(
    connection: Connection,
    *,
    student_id: str,
    active_bank_id: str,
) -> dict:
    bank = connection.execute(
        "SELECT name FROM question_banks WHERE id=%s",
        (active_bank_id,),
    ).fetchone()
    if not bank:
        raise KeyError("ACTIVE_BANK_NOT_FOUND")
    counts = connection.execute(
        """
        SELECT
          count(*) FILTER (WHERE bank_id=%s) AS current_count,
          count(*) FILTER (WHERE bank_id<>%s) AS history_count
        FROM mistake_items
        WHERE student_id=%s
        """,
        (active_bank_id, active_bank_id, student_id),
    ).fetchone()
    return {
        "count": counts["current_count"],
        "bank_name": bank["name"],
        "history_count": counts["history_count"],
    }


def clear_current_mistakes(
    connection: Connection,
    *,
    student_id: str,
    active_bank_id: str,
) -> int:
    rows = connection.execute(
        """
        DELETE FROM mistake_items
        WHERE student_id=%s AND bank_id=%s
        RETURNING question_id
        """,
        (student_id, active_bank_id),
    ).fetchall()
    return len(rows)


def active_question_ids(
    connection: Connection,
    *,
    active_bank_id: str,
) -> list[str]:
    return [
        row["id"]
        for row in connection.execute(
            """
            SELECT id
            FROM questions
            WHERE bank_id=%s AND status='published'
            """,
            (active_bank_id,),
        ).fetchall()
    ]


def reset_coverage_preview(
    connection: Connection,
    *,
    student_id: str,
    active_bank_id: str,
) -> dict:
    bank = connection.execute(
        "SELECT name FROM question_banks WHERE id=%s",
        (active_bank_id,),
    ).fetchone()
    if not bank:
        raise KeyError("ACTIVE_BANK_NOT_FOUND")
    question_ids = active_question_ids(
        connection,
        active_bank_id=active_bank_id,
    )
    count = connection.execute(
        """
        SELECT count(*) AS count
        FROM question_attempts
        WHERE student_id=%s AND question_id=ANY(%s)
        """,
        (student_id, question_ids),
    ).fetchone()["count"]
    return {
        "count": count,
        "bank_name": bank["name"],
        "question_total": len(question_ids),
    }


def reset_coverage_attempts(
    connection: Connection,
    *,
    student_id: str,
    active_bank_id: str,
) -> int:
    question_ids = active_question_ids(
        connection,
        active_bank_id=active_bank_id,
    )
    rows = connection.execute(
        """
        DELETE FROM question_attempts
        WHERE student_id=%s AND question_id=ANY(%s)
        RETURNING id
        """,
        (student_id, question_ids),
    ).fetchall()
    return len(rows)


def switchable_banks(
    connection: Connection,
    *,
    student_id: str,
    active_bank_id: str,
) -> dict:
    rows = connection.execute(
        """
        SELECT qb.id::text AS id, qb.name, qb.status, qb.target_size,
               count(q.id) FILTER (WHERE q.status='published') AS question_count
        FROM question_banks qb
        LEFT JOIN questions q ON q.bank_id=qb.id
        WHERE qb.status IN ('active', 'ready', 'archived')
          AND COALESCE((qb.coverage_snapshot->>'switchable')::boolean, TRUE)
        GROUP BY qb.id, qb.name, qb.status, qb.target_size, qb.created_at
        ORDER BY (qb.id=%s) DESC, qb.created_at DESC
        """,
        (active_bank_id,),
    ).fetchall()
    in_progress = connection.execute(
        """
        SELECT count(*) AS count
        FROM practice_sessions
        WHERE student_id=%s
          AND bank_id=%s
          AND status='in_progress'
          AND deadline > now()
        """,
        (student_id, active_bank_id),
    ).fetchone()["count"]
    return {
        "current_bank_id": active_bank_id,
        "in_progress_count": in_progress,
        "banks": [
            {
                "bank_id": row["id"],
                "name": row["name"],
                "version": 1,
                "question_count": row["question_count"],
                "status": row["status"],
                "is_current": row["id"] == active_bank_id,
            }
            for row in rows
        ],
    }

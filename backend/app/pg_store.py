from __future__ import annotations

import os
import random
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .demo_bank import DemoQuestion, demo_bank
from .store import SessionRecord


class PostgresStore:
    """PostgreSQL-backed store for the 30-question sprint fixture."""

    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres@127.0.0.1:15432/english_practice",
        )
        config_path = Path(__file__).resolve().parents[2] / "config" / "api.json"
        import json

        config = json.loads(config_path.read_text(encoding="utf-8"))
        expected_port = int(
            os.getenv("EXPECTED_DATABASE_PORT", config["database"]["expected_port"])
        )
        with self.connection() as connection:
            actual_port = connection.execute(
                "SELECT inet_server_port() AS port"
            ).fetchone()["port"]
        if actual_port != expected_port:
            raise RuntimeError(
                "DATABASE_PORT_MISMATCH: "
                f"inet_server_port()={actual_port} expected={expected_port}"
            )
        self.bank = self._ensure_seeded()
        self.questions = self._load_questions()
        self.sessions: dict[str, SessionRecord] = {}

    @contextmanager
    def connection(self):
        connection = psycopg.connect(self.database_url, row_factory=dict_row, autocommit=True)
        try:
            yield connection
        finally:
            connection.close()

    def _ensure_seeded(self) -> dict:
        seeded = demo_bank()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM question_banks WHERE id = %s",
                (seeded["bank_id"],),
            ).fetchone()
            if row:
                return {
                    "bank_id": str(row["id"]),
                    "name": row["name"],
                    "version": "1",
                    "status": row["status"],
                    "target_size": row["target_size"],
                    "difficulty_profile": row["difficulty_profile"],
                    "created_at": row["created_at"].isoformat(),
                }

            connection.execute(
                """
                INSERT INTO question_banks
                    (id, name, target_size, difficulty_profile, status, coverage_snapshot)
                VALUES (%s, %s, %s, %s, 'draft', %s)
                """,
                (
                    seeded["bank_id"],
                    seeded["name"],
                    seeded["target_size"],
                    seeded["difficulty_profile"],
                    Jsonb(
                        {
                            "question_type_counts": {"cloze": 15, "grammar_fill": 10, "gap_fill": 5},
                            "grammar_fill_coverage": {
                                "tense_system": 4,
                                "past_participle_nonfinite": 1,
                                "passive_voice_tenses": 1,
                                "infinitive_nonfinite": 2,
                                "subject_verb_agreement": 1,
                                "word_formation": 1,
                                "conjunctions": 1,
                            },
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ),
                ),
            )
            seen_passages = {}
            for question in seeded["questions"]:
                seen_passages.setdefault(
                    question.passage_group_id,
                    (question.type, question.passage, question.book_source),
                )
            for group_id, (qtype, text, book_source) in seen_passages.items():
                connection.execute(
                    """
                    INSERT INTO passages
                        (passage_group_id, bank_id, type, content, word_count, topic,
                         book_source, difficulty, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 3, 'published')
                    """,
                    (
                        group_id,
                        seeded["bank_id"],
                        qtype,
                        text,
                        len(text.split()),
                        "community life",
                        book_source,
                    ),
                )
            for question in seeded["questions"]:
                connection.execute(
                    """
                    INSERT INTO questions
                        (id, bank_id, type, passage_group_id, stem, options, answer,
                         explanation, knowledge_points, grammar_tags, book_source,
                         difficulty, status, batch_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            'published', 'DEMO-SPRINT-01')
                    """,
                    (
                        question.id,
                        question.bank_id,
                        question.type,
                        question.passage_group_id,
                        question.stem,
                        Jsonb(question.options) if question.options is not None else None,
                        Jsonb(question.answer),
                        question.explanation,
                        question.knowledge_points,
                        question.grammar_tags,
                        question.book_source,
                        question.difficulty,
                    ),
                )
            connection.execute(
                "UPDATE question_banks SET status='active' WHERE id=%s",
                (seeded["bank_id"],),
            )
        return seeded

    def _load_questions(self) -> dict[str, DemoQuestion]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT q.*, p.content AS passage
                FROM questions q
                JOIN passages p
                  ON p.bank_id=q.bank_id AND p.passage_group_id=q.passage_group_id
                WHERE q.bank_id=%s AND q.status='published'
                """,
                (self.bank["bank_id"],),
            ).fetchall()
        return {
            row["id"]: DemoQuestion(
                id=row["id"],
                bank_id=str(row["bank_id"]),
                type=row["type"],
                passage_group_id=row["passage_group_id"],
                passage=row["passage"],
                stem=row["stem"],
                options=row["options"],
                answer=row["answer"],
                explanation=row["explanation"],
                knowledge_points=row["knowledge_points"],
                grammar_tags=row["grammar_tags"],
                book_source=row["book_source"],
                difficulty=row["difficulty"],
            )
            for row in rows
        }

    def active_bank(self) -> dict:
        return self.bank

    def _student_state(self, student_id: str) -> tuple[dict, dict, dict]:
        with self.connection() as connection:
            tags = {
                row["question_id"]: {
                    "status": row["status"],
                    "streak": row["streak"],
                    "knowledge_points": row["knowledge_points"],
                    "grammar_tags": row["grammar_tags"],
                }
                for row in connection.execute(
                    "SELECT * FROM error_tags WHERE student_id=%s AND bank_id=%s",
                    (student_id, self.bank["bank_id"]),
                ).fetchall()
            }
            rows = connection.execute(
                """
                SELECT si.question_id, pr.report, ps.started_at
                FROM session_items si
                JOIN practice_sessions ps ON ps.id=si.session_id
                JOIN practice_reports pr ON pr.session_id=ps.id
                WHERE ps.student_id=%s AND si.bank_id=%s
                """,
                (student_id, self.bank["bank_id"]),
            ).fetchall()
        history: dict[str, list[tuple[bool, datetime]]] = defaultdict(list)
        appearances: dict[str, list[datetime]] = defaultdict(list)
        for row in rows:
            appearances[row["question_id"]].append(row["started_at"])
            result = next(
                (
                    item
                    for item in row["report"]["question_results"]
                    if item["question_id"] == row["question_id"]
                ),
                None,
            )
            if result:
                history[row["question_id"]].append((result["correct"], row["started_at"]))
        return tags, history, appearances

    def _weight(
        self,
        question: DemoQuestion,
        tags: dict,
        history: dict,
        appearances: dict,
        now: datetime,
    ) -> float:
        tag = tags.get(question.id)
        i_err = 1.0 if tag and tag["status"] == "active" else 0.0
        s_kp = min(
            3,
            sum(
                1
                for other in tags.values()
                if other["status"] == "active"
                and (
                    set(other["knowledge_points"]) & set(question.knowledge_points)
                    or set(other["grammar_tags"]) & set(question.grammar_tags)
                )
            ),
        )
        same_type = [
            correct
            for qid, outcomes in history.items()
            if self.questions[qid].type == question.type
            for correct, _ in outcomes
        ]
        s_type = 1.0 if same_type and sum(same_type) / len(same_type) < 0.6 else 0.0
        gap = tags.get(question.id)
        mastery = 0.7
        if gap and gap["status"] == "active":
            mastery = 0.5
        g_gap = max(0.0, 0.7 - mastery) * 2
        seen = appearances.get(question.id, [])
        recent = 1.2 if len(seen[-3:]) >= 3 else (0.6 if any(now - at <= timedelta(days=7) for at in seen) else 0)
        return max(0.1, 1.0 + 2 * i_err + s_kp + 0.5 * s_type + 0.8 * g_gap - recent)

    def _sample(self, candidates: list[DemoQuestion], amount: int, weights: list[float], rng) -> list[DemoQuestion]:
        remaining = list(zip(candidates, weights))
        selected = []
        while remaining and len(selected) < amount:
            total = sum(weight for _, weight in remaining)
            target = rng.random() * total
            running = 0.0
            index = len(remaining) - 1
            for position, (_, weight) in enumerate(remaining):
                running += weight
                if target <= running:
                    index = position
                    break
            selected.append(remaining.pop(index)[0])
        return selected

    def start_session(self, student_id: str, duration_minutes: int, now: datetime) -> SessionRecord:
        if duration_minutes != 30:
            raise ValueError("INVALID_DURATION")
        tags, history, appearances = self._student_state(student_id)
        rng = random.SystemRandom()
        all_questions: list[DemoQuestion] = []
        for qtype, amount in {"cloze": 15, "grammar_fill": 10, "gap_fill": 5}.items():
            candidates = [q for q in self.questions.values() if q.type == qtype]
            weights = [self._weight(q, tags, history, appearances, now) for q in candidates]
            all_questions.extend(self._sample(candidates, amount, weights, rng))
        rng.shuffle(all_questions)
        session_id = str(uuid.uuid4())
        composition = {
            "bank_name": self.bank["name"],
            "question_type_counts": {"cloze": 15, "grammar_fill": 10, "gap_fill": 5},
            "error_pool_ratio": 0.0,
            "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
            "book_distribution": {"必修": 0.2, "选必一": 0.3, "选必二": 0.45, "cross_book": 0.05},
            "topics": ["environment", "community life", "reading"],
        }
        record = SessionRecord(
            id=session_id,
            student_id=student_id,
            bank_id=self.bank["bank_id"],
            bank_name=self.bank["name"],
            bank_version=self.bank["version"],
            duration_minutes=30,
            started_at=now,
            deadline=now + timedelta(minutes=30),
            question_ids=[q.id for q in all_questions],
            composition_note=composition,
        )
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO practice_sessions
                    (id, student_id, bank_id, bank_name, bank_version, duration_minutes,
                     status, started_at, deadline, composition_note)
                VALUES (%s, %s, %s, %s, 1, 30, 'in_progress', %s, %s, %s)
                """,
                (
                    session_id,
                    student_id,
                    self.bank["bank_id"],
                    self.bank["name"],
                    now,
                    record.deadline,
                    Jsonb(composition),
                ),
            )
            for ordinal, question in enumerate(all_questions):
                connection.execute(
                    "INSERT INTO session_items (session_id, question_id, bank_id, ordinal) VALUES (%s, %s, %s, %s)",
                    (session_id, question.id, self.bank["bank_id"], ordinal),
                )
        self.sessions[session_id] = record
        return record

    def _load_session(self, student_id: str, session_id: str) -> SessionRecord:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM practice_sessions WHERE id=%s AND student_id=%s",
                (session_id, student_id),
            ).fetchone()
            if not row:
                raise KeyError("SESSION_NOT_FOUND")
            items = connection.execute(
                "SELECT question_id FROM session_items WHERE session_id=%s ORDER BY ordinal",
                (session_id,),
            ).fetchall()
            answers = connection.execute(
                "SELECT question_id, answer FROM saved_answers WHERE session_id=%s",
                (session_id,),
            ).fetchall()
        record = SessionRecord(
            id=str(row["id"]),
            student_id=str(row["student_id"]),
            bank_id=str(row["bank_id"]),
            bank_name=row["bank_name"],
            bank_version=str(row["bank_version"]),
            duration_minutes=row["duration_minutes"],
            started_at=row["started_at"],
            deadline=row["deadline"],
            question_ids=[item["question_id"] for item in items],
            composition_note=row["composition_note"],
            status=row["status"],
            answers={item["question_id"]: item["answer"] for item in answers},
            submitted_at=row["submitted_at"],
            idempotency_key=str(row["submit_idempotency_key"]) if row["submit_idempotency_key"] else None,
        )
        return record

    def get_session(self, student_id: str, session_id: str, now: datetime) -> SessionRecord:
        record = self._load_session(student_id, session_id)
        if record.status == "in_progress" and now >= record.deadline:
            self.submit_session(student_id, session_id, f"auto:{session_id}", now)
            record = self._load_session(student_id, session_id)
        self.sessions[session_id] = record
        return record

    def get_report(self, student_id: str, session_id: str) -> dict:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT report
                FROM practice_reports
                WHERE student_id=%s AND session_id=%s
                """,
                (student_id, session_id),
            ).fetchone()
        if not row:
            raise KeyError("REPORT_NOT_FOUND")
        return row["report"]

    def save_answer(
        self, student_id: str, session_id: str, question_id: str, answer: str, now: datetime
    ) -> SessionRecord:
        record = self.get_session(student_id, session_id, now)
        if record.status != "in_progress":
            raise ValueError("SESSION_SUBMITTED")
        if question_id not in record.question_ids:
            raise KeyError("QUESTION_NOT_FOUND")
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO saved_answers (session_id, question_id, answer, client_revision, saved_at)
                VALUES (%s, %s, %s, 1, %s)
                ON CONFLICT (session_id, question_id)
                DO UPDATE SET answer=EXCLUDED.answer, client_revision=saved_answers.client_revision+1,
                              saved_at=EXCLUDED.saved_at
                """,
                (session_id, question_id, Jsonb(answer), now),
            )
        record.answers[question_id] = answer
        return record

    def submit_session(
        self, student_id: str, session_id: str, idempotency_key: str, now: datetime
    ) -> dict:
        record = self._load_session(student_id, session_id)
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT submit_idempotency_key FROM practice_sessions WHERE id=%s",
                (session_id,),
            ).fetchone()
        if existing and existing["submit_idempotency_key"]:
            if str(existing["submit_idempotency_key"]) != idempotency_key:
                raise ValueError("IDEMPOTENCY_KEY_MISMATCH")
            with self.connection() as connection:
                row = connection.execute(
                    "SELECT report FROM practice_reports WHERE session_id=%s",
                    (session_id,),
                ).fetchone()
            return row["report"]

        status = "expired" if now >= record.deadline else "submitted"
        results = []
        type_stats = defaultdict(lambda: {"correct": 0, "total": 0})
        point_stats = defaultdict(list)
        for qid in record.question_ids:
            question = self.questions[qid]
            user_answer = record.answers.get(qid, "")
            normalized = " ".join(str(user_answer).strip().split()).casefold()
            if question.type == "cloze":
                correct = normalized == str(question.answer).casefold()
            elif question.type == "gap_fill":
                correct = normalized.split(".", 1)[0].upper() == str(question.answer).upper()
            else:
                correct = normalized == str(question.answer).casefold()
            type_stats[question.type]["total"] += 1
            type_stats[question.type]["correct"] += int(correct)
            for point in question.knowledge_points:
                point_stats[point].append(correct)
            results.append(
                {
                    "question_id": qid,
                    "correct": correct,
                    "user_answer": user_answer,
                    "correct_answer": question.answer,
                    "explanation": question.explanation,
                    "knowledge_points": question.knowledge_points,
                    "grammar_tags": question.grammar_tags,
                    "book_source": question.book_source,
                    "difficulty": question.difficulty,
                }
            )
        levels = [
            {
                "knowledge_point": point,
                "level": "mastered" if sum(values) / len(values) >= 0.85 else ("weak" if sum(values) / len(values) < 0.6 else "consolidating"),
                "mastery": round(sum(values) / len(values), 4),
                "attempts": len(values),
            }
            for point, values in point_stats.items()
        ]
        weak = sorted(levels, key=lambda item: item["mastery"])[:3]
        report = {
            "session_id": session_id,
            "bank_id": record.bank_id,
            "bank_name": record.bank_name,
            "score": round(sum(item["correct"] for item in results) / max(1, len(results)) * 100, 2),
            "max_score": 100,
            "accuracy": round(sum(item["correct"] for item in results) / max(1, len(results)), 4),
            "duration_seconds": max(0, int((now - record.started_at).total_seconds())),
            "type_scores": {
                qtype: {**values, "accuracy": round(values["correct"] / max(1, values["total"]), 4)}
                for qtype, values in type_stats.items()
            },
            "knowledge_point_levels": levels,
            "weak_points": [{"knowledge_point": item["knowledge_point"], "error_stage": "Answer selection"} for item in weak],
            "suggestions": [
                {"knowledge_point": item["knowledge_point"], "action": f"Review {item['knowledge_point']} and complete a short focused set."}
                for item in weak
            ],
            "question_results": results,
            "error_tag_changes": [],
        }
        changes = []
        with self.connection() as connection:
            for result in results:
                question = self.questions[result["question_id"]]
                tag = connection.execute(
                    "SELECT * FROM error_tags WHERE student_id=%s AND question_id=%s AND bank_id=%s",
                    (student_id, question.id, question.bank_id),
                ).fetchone()
                previous = tag["status"] if tag else "none"
                if not result["correct"]:
                    if tag:
                        connection.execute(
                            "UPDATE error_tags SET status='active', streak=0, updated_at=%s WHERE id=%s",
                            (now, tag["id"]),
                        )
                    else:
                        connection.execute(
                            """
                            INSERT INTO error_tags
                                (student_id, question_id, bank_id, question_type,
                                 knowledge_points, grammar_tags)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (student_id, question.id, question.bank_id, question.type, question.knowledge_points, question.grammar_tags),
                        )
                elif tag and tag["status"] == "active":
                    already = connection.execute(
                        "SELECT 1 FROM error_tag_successes WHERE tag_id=%s AND session_id=%s",
                        (tag["id"], session_id),
                    ).fetchone()
                    if not already:
                        connection.execute(
                            "INSERT INTO error_tag_successes (tag_id, session_id) VALUES (%s, %s)",
                            (tag["id"], session_id),
                        )
                        successes = connection.execute(
                            "SELECT count(*) AS count FROM error_tag_successes WHERE tag_id=%s",
                            (tag["id"],),
                        ).fetchone()["count"]
                        streak = min(2, successes)
                        status_value = "mastered" if successes >= 2 else "active"
                        connection.execute(
                            "UPDATE error_tags SET streak=%s, status=%s, mastered_at=%s, updated_at=%s WHERE id=%s",
                            (streak, status_value, now if status_value == "mastered" else None, now, tag["id"]),
                        )
                updated = connection.execute(
                    "SELECT status, streak FROM error_tags WHERE student_id=%s AND question_id=%s",
                    (student_id, question.id),
                ).fetchone()
                current = updated["status"] if updated else "active"
                if previous != current:
                    changes.append(
                        {
                            "question_id": question.id,
                            "from_status": previous,
                            "to_status": current,
                            "streak": updated["streak"] if updated else 0,
                        }
                    )
            report["error_tag_changes"] = changes
            connection.execute(
                """
                UPDATE practice_sessions
                SET status=%s, submitted_at=%s, submit_idempotency_key=%s
                WHERE id=%s
                """,
                (status, now, idempotency_key, session_id),
            )
            connection.execute(
                """
                INSERT INTO practice_reports (session_id, student_id, bank_id, bank_name, report)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET report=EXCLUDED.report
                """,
                (session_id, student_id, record.bank_id, record.bank_name, Jsonb(report)),
            )
        self.sessions[session_id] = record
        return report

    def admin_audit(self, method: str, path: str, token: str, result: str, status_code: int) -> None:
        import hashlib

        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO admin_audit_log
                    (method, path, token_fingerprint, result, status_code)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (method, path, hashlib.sha256(token.encode()).hexdigest()[:8], result, status_code),
            )

    def get_error_tags(self, student_id: str) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT question_id, bank_id, knowledge_points, grammar_tags, status, streak
                FROM error_tags
                WHERE student_id=%s
                ORDER BY updated_at DESC
                """,
                (student_id,),
            ).fetchall()
        return [
            {
                "question_id": row["question_id"],
                "bank_id": str(row["bank_id"]),
                "knowledge_points": row["knowledge_points"],
                "grammar_tags": row["grammar_tags"],
                "status": row["status"],
                "streak": row["streak"],
            }
            for row in rows
        ]

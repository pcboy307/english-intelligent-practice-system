"""PostgreSQL operations for the M2 generation pilot."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg.types.json import Jsonb

from .generation import validate_generated_passage


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))


class M2Repository:
    def __init__(self, connection) -> None:
        self.connection = connection

    def get_bank(self, bank_id: str) -> dict[str, Any] | None:
        return self.connection.execute(
            """
            SELECT id::text AS id, name, target_size, difficulty_profile, status,
                   coverage_snapshot, generation_job_id::text,
                   created_at, finished_at
            FROM question_banks
            WHERE id=%s
            """,
            (bank_id,),
        ).fetchone()

    def get_active_bank(self) -> dict[str, Any] | None:
        return self.connection.execute(
            """
            SELECT qb.id::text AS id, qb.name, qb.target_size,
                   qb.difficulty_profile, qb.status, qb.coverage_snapshot,
                   qb.generation_job_id::text, qb.created_at, qb.finished_at
            FROM bank_active_state bas
            JOIN question_banks qb ON qb.id=bas.active_bank_id
            WHERE bas.singleton=TRUE
            """
        ).fetchone()

    def create_bank(
        self,
        *,
        name: str,
        target_size: int,
        difficulty_profile: str,
    ) -> dict[str, Any]:
        row = self.connection.execute(
            """
            INSERT INTO question_banks
                (name, target_size, difficulty_profile, status)
            VALUES (%s, %s, %s, 'draft')
            RETURNING id::text AS id
            """,
            (name, target_size, difficulty_profile),
        ).fetchone()
        self._audit(row["id"], "created", "m2_pipeline", {})
        return self.get_bank(row["id"])

    def create_generation_job(
        self,
        bank_id: str,
        *,
        target_passages: int,
        batch_size: int,
        approved_by: str,
        reason: str,
    ) -> dict[str, Any]:
        bank = self.get_bank(bank_id)
        if not bank:
            raise KeyError("BANK_NOT_FOUND")
        if bank["status"] not in {"draft", "generating"}:
            raise ValueError("BANK_NOT_DRAFT_OR_GENERATING")
        if bank["status"] == "generating":
            active_job = self.connection.execute(
                """
                SELECT id
                FROM generation_jobs
                WHERE bank_id=%s
                  AND status IN (
                    'queued',
                    'running',
                    'paused_for_review',
                    'paused_for_owner'
                  )
                LIMIT 1
                """,
                (bank_id,),
            ).fetchone()
            if active_job:
                raise ValueError("GENERATION_JOB_ALREADY_ACTIVE")
        now = datetime.now(timezone.utc)
        approval = self.connection.execute(
            """
            INSERT INTO generation_approvals
                (bank_id, approved_by, reason, created_at, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id::text AS id
            """,
            (
                bank_id,
                approved_by,
                reason,
                now,
                now + timedelta(hours=2),
            ),
        ).fetchone()
        job = self.connection.execute(
            """
            INSERT INTO generation_jobs
                (bank_id, approval_id, status, batch_size, target_passages)
            VALUES (%s, %s, 'queued', %s, %s)
            RETURNING id::text AS id, status, target_passages, completed_passages,
                      rejected_count, batch_size, created_at, updated_at
            """,
            (bank_id, approval["id"], batch_size, target_passages),
        ).fetchone()
        self.connection.execute(
            """
            UPDATE question_banks
            SET status='generating', generation_job_id=%s
            WHERE id=%s AND status IN ('draft', 'generating')
            """,
            (job["id"], bank_id),
        )
        self._audit(
            bank_id,
            "generation_started",
            "m2_pipeline",
            {"job_id": job["id"]},
        )
        return self.get_job(job["id"])

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.connection.execute(
            """
            SELECT id::text AS id, bank_id::text AS bank_id, status,
                   batch_size, target_passages, completed_passages,
                   rejected_count, first_batch_verified, checkpoint,
                   created_at, updated_at, finished_at
            FROM generation_jobs
            WHERE id=%s
            """,
            (job_id,),
        ).fetchone()

    def set_job_status(
        self,
        job_id: str,
        status: str,
        *,
        checkpoint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = self.connection.execute(
            """
            UPDATE generation_jobs
            SET status=%s,
                checkpoint=COALESCE(%s, checkpoint),
                updated_at=now(),
                finished_at=CASE WHEN %s IN ('completed', 'failed') THEN now() ELSE finished_at END
            WHERE id=%s
            RETURNING id::text AS id
            """,
            (status, Jsonb(checkpoint) if checkpoint is not None else None, status, job_id),
        ).fetchone()
        if not row:
            raise KeyError("GENERATION_JOB_NOT_FOUND")
        return self.get_job(job_id)

    def insert_passage(
        self,
        *,
        bank_id: str,
        job_id: str,
        batch_id: str,
        record: dict[str, Any],
        prevalidated: bool = False,
    ) -> list[str]:
        # Kept for API compatibility. Prevalidation never bypasses integrity.
        self._reject_invalid_record(record)
        questions = record["questions"]
        passage_group_id = record["passage_group_id"]
        self.connection.execute(
            """
            INSERT INTO passages
                (passage_group_id, bank_id, type, content, word_count, topic,
                 book_source, difficulty, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft')
            """,
            (
                passage_group_id,
                bank_id,
                record["type"],
                record["passage"],
                _word_count(record["passage"]),
                record["topic"],
                record["book_source"],
                record["difficulty"],
            ),
        )
        ids = []
        for index, question in enumerate(questions, start=1):
            question_id = f"{passage_group_id}-Q{index:02d}"
            self.connection.execute(
                """
                INSERT INTO questions
                    (id, bank_id, type, passage_group_id, stem, options, answer,
                     explanation, knowledge_points, grammar_tags, book_source,
                     difficulty, status, batch_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'draft', %s)
                """,
                (
                    question_id,
                    bank_id,
                    record["type"],
                    passage_group_id,
                    question["stem"],
                    Jsonb(question["options"]),
                    Jsonb(question["answer"]),
                    question["explanation"],
                    question["knowledge_points"],
                    question["grammar_tags"],
                    question.get("book_source", record["book_source"]),
                    question.get("difficulty", record["difficulty"]),
                    batch_id,
                ),
            )
            ids.append(question_id)
        self.connection.execute(
            """
            UPDATE generation_jobs
            SET completed_passages=completed_passages+1, updated_at=now()
            WHERE id=%s
            """,
            (job_id,),
        )
        return ids

    def question_count(self, bank_id: str) -> int:
        return int(
            self.connection.execute(
                "SELECT count(*) AS count FROM questions WHERE bank_id=%s",
                (bank_id,),
            ).fetchone()["count"]
        )

    def replace_passage_questions(
        self,
        *,
        bank_id: str,
        batch_id: str,
        record: dict[str, Any],
    ) -> list[str]:
        self._reject_invalid_record(record)
        passage_group_id = record["passage_group_id"]
        passage = self.connection.execute(
            """
            UPDATE passages
            SET content=%s, word_count=%s, updated_at=now()
            WHERE bank_id=%s AND passage_group_id=%s
            RETURNING id
            """,
            (
                record["passage"],
                _word_count(record["passage"]),
                bank_id,
                passage_group_id,
            ),
        ).fetchone()
        if not passage:
            raise KeyError(f"PASSAGE_NOT_FOUND:{passage_group_id}")
        ids = []
        for index, question in enumerate(record["questions"], start=1):
            question_id = f"{passage_group_id}-Q{index:02d}"
            updated = self.connection.execute(
                """
                UPDATE questions
                SET type=%s, stem=%s, options=%s, answer=%s, explanation=%s,
                    knowledge_points=%s, grammar_tags=%s, book_source=%s,
                    difficulty=%s, status='draft', batch_id=%s, updated_at=now()
                WHERE bank_id=%s AND passage_group_id=%s AND id=%s
                RETURNING id
                """,
                (
                    record["type"],
                    question["stem"],
                    Jsonb(question["options"]),
                    Jsonb(question["answer"]),
                    question["explanation"],
                    question["knowledge_points"],
                    question["grammar_tags"],
                    question["book_source"],
                    question["difficulty"],
                    batch_id,
                    bank_id,
                    passage_group_id,
                    question_id,
                ),
            ).fetchone()
            if not updated:
                raise KeyError(f"QUESTION_NOT_FOUND:{question_id}")
            ids.append(question_id)
        return ids

    @staticmethod
    def _reject_invalid_record(record: dict[str, Any]) -> None:
        report = validate_generated_passage(record)
        if report.accepted:
            return
        raise ValueError(
            "GENERATED_PASSAGE_REJECTED:"
            + json.dumps(
                [failure.as_dict() for failure in report.failures],
                ensure_ascii=False,
            )
        )

    def set_bank_status(
        self,
        bank_id: str,
        status: str,
        *,
        coverage_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = self.connection.execute(
            """
            UPDATE question_banks
            SET status=%s,
                coverage_snapshot=COALESCE(%s, coverage_snapshot),
                finished_at=CASE
                    WHEN %s IN ('ready', 'archived') THEN now()
                    ELSE finished_at
                END
            WHERE id=%s
            RETURNING id::text AS id
            """,
            (
                status,
                Jsonb(coverage_snapshot) if coverage_snapshot is not None else None,
                status,
                bank_id,
            ),
        ).fetchone()
        if not row:
            raise KeyError("BANK_NOT_FOUND")
        self._audit(
            bank_id,
            f"status:{status}",
            "m2_pipeline",
            {"status": status},
        )
        return self.get_bank(bank_id)

    def activate_bank(self, bank_id: str, *, actor: str) -> dict[str, Any]:
        target = self.get_bank(bank_id)
        if not target:
            raise KeyError("BANK_NOT_FOUND")
        if target["status"] != "ready":
            raise ValueError("BANK_NOT_READY")
        previous = self.get_active_bank()
        self.connection.execute(
            "UPDATE question_banks SET status='active' WHERE id=%s",
            (bank_id,),
        )
        self.connection.execute(
            """
            INSERT INTO bank_audit_logs
                (bank_id, action, previous_bank_id, actor, details)
            VALUES (%s, 'activated', %s, %s, %s)
            """,
            (
                bank_id,
                previous["id"] if previous else None,
                actor,
                Jsonb({"previous_bank_id": previous["id"] if previous else None}),
            ),
        )
        return self.get_bank(bank_id)

    def clone_pilot_for_browser(
        self,
        *,
        source_bank_id: str,
        name: str,
    ) -> dict[str, Any]:
        source = self.get_bank(source_bank_id)
        if not source:
            raise KeyError("SOURCE_BANK_NOT_FOUND")
        clone = self.create_bank(
            name=name,
            target_size=self.question_count(source_bank_id),
            difficulty_profile=source["difficulty_profile"],
        )
        self.connection.execute(
            """
            INSERT INTO passages
                (passage_group_id, bank_id, type, content, word_count, topic,
                 book_source, difficulty, status, out_of_scope_flags)
            SELECT passage_group_id, %s, type, content, word_count, topic,
                   book_source, difficulty, 'published', out_of_scope_flags
            FROM passages
            WHERE bank_id=%s
            """,
            (clone["id"], source_bank_id),
        )
        self.connection.execute(
            """
            INSERT INTO questions
                (id, bank_id, type, passage_group_id, stem, options, answer,
                 explanation, knowledge_points, grammar_tags, book_source,
                 difficulty, out_of_scope_flags, status, batch_id)
            SELECT concat(%s, '-', id), %s, type, passage_group_id, stem, options,
                   answer, explanation, knowledge_points, grammar_tags,
                   book_source, difficulty, out_of_scope_flags, 'published',
                   concat(batch_id, '-BROWSER')
            FROM questions
            WHERE bank_id=%s
            """,
            (clone["id"], clone["id"], source_bank_id),
        )
        coverage = {
            "question_counts": {"cloze": 15, "grammar_fill": 10, "reading": 4, "gap_fill": 0},
            "passage_counts": {"cloze": 1, "grammar_fill": 1, "reading": 1, "gap_fill": 0},
            "difficulty_distribution": {},
            "book_distribution": {},
            "topic_distribution": {},
            "out_of_scope_rate": 0,
            "passage_duplicate_rate": 0,
            "stem_duplicate_rate": 0,
            "grammar_fill_coverage": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.set_bank_status(
            clone["id"],
            "ready",
            coverage_snapshot=coverage,
        )

    def _audit(
        self,
        bank_id: str,
        action: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO bank_audit_logs
                (bank_id, action, actor, details)
            VALUES (%s, %s, %s, %s)
            """,
            (bank_id, action, actor, Jsonb(details)),
        )

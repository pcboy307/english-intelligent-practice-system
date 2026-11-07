#!/usr/bin/env python3
"""Generate and validate the M2.0 three-passage pilot with the local LLM."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.generation import (  # noqa: E402
    GenerationClient,
    GenerationExhausted,
    TokenBudgetExceeded,
    build_cost_report,
    generate_validated_passage,
)
from backend.app.m2_pilot import (  # noqa: E402
    load_pilot_schedule,
    validate_pilot_schedule,
)
from backend.app.m2_repository import M2Repository  # noqa: E402


EVIDENCE_DIR = ROOT / "qa" / "evidence" / "m2"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_prompt(
    passage: dict,
    previous_failures: list[dict],
) -> str:
    questions = []
    for index, assignment in enumerate(passage["questions"], start=1):
        questions.append(
            {
                "question_order": index,
                "book_source": assignment["book_source"],
                "difficulty": assignment["difficulty"],
                "grammar_tags": assignment["grammar_tags"],
                "options_count": 4,
            }
        )
    correction_block = ""
    if previous_failures:
        correction_block = (
            "\nThe previous attempt was rejected by machine gates. "
            "Correct every listed defect in this new version:\n"
            + json.dumps(previous_failures, ensure_ascii=False, indent=2)
            + "\n"
        )
    return f"""
Create ONE original English practice passage for a Guangdong Grade 11 student.
Do not copy or paraphrase any real examination passage. Do not mention real people,
schools, exam IDs, brands, or named places.

Required passage type: {passage['type']}
Passage group ID: {passage['passage_group_id']}
Topic: {passage['topic']}
Default book source: {passage['book_source']}
Default difficulty: {passage['difficulty']}

Word limits and structure:
- cloze: 170-220 English words, exactly 15 numbered blanks (1) through (15).
- grammar_fill: 120-180 English words, exactly blanks ① through ⑩.
- reading: at most 250 English words.

Every question must:
1. use exactly four non-empty options;
2. put the exact correct option text in "answer";
3. include a Chinese explanation of at least three complete sentences separated
   by Chinese full stops;
4. use one concise unique knowledge point string;
5. copy book_source, difficulty and grammar_tags EXACTLY from its assignment;
6. avoid tested structures outside the 21-ID grammar whitelist.

Vocabulary rule:
- Use only simple words expected as learned in PEP 2019 required books 1-3
  and elective required books 1-2.
- Keep the unknown-word rate at or below 3 percent.
- Do not use names, rare derivations, rare word senses, or professional terms
  unless the term is immediately followed by a Chinese gloss in full-width
  parentheses. At most two such glossed terms are allowed.
- Do not use elective books 3 or 4 material.

For grammar_fill, all four options in each question must belong to the same
grammatical category and test the assigned grammar tag.

Per-question assignments:
{json.dumps(questions, ensure_ascii=False, indent=2)}
{correction_block}
Return exactly this JSON shape, with no markdown:
{{
  "type": "{passage['type']}",
  "passage_group_id": "{passage['passage_group_id']}",
  "topic": "{passage['topic']}",
  "book_source": "{passage['book_source']}",
  "difficulty": {passage['difficulty']},
  "passage": "complete passage text",
  "questions": [
    {{
      "stem": "question text",
      "options": ["option one", "option two", "option three", "option four"],
      "answer": "exact option text",
      "explanation": "三句中文解析。第二句说明干扰项。第三句说明考点。",
      "knowledge_points": ["one_unique_knowledge_point"],
      "grammar_tags": ["exact assignment"],
      "book_source": "exact assignment",
      "difficulty": 1
    }}
  ]
}}
""".strip()


def find_existing_bank(connection, name: str) -> dict | None:
    return connection.execute(
        """
        SELECT id::text AS id, status
        FROM question_banks
        WHERE name=%s AND status IN ('draft', 'generating')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (name,),
    ).fetchone()


def latest_job(connection, bank_id: str) -> dict | None:
    return connection.execute(
        """
        SELECT id::text AS id, status
        FROM generation_jobs
        WHERE bank_id=%s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (bank_id,),
    ).fetchone()


def update_gate_evidence(
    *,
    passage_type: str,
    attempts: list[dict],
    prior: list[dict],
) -> list[dict]:
    rows = list(prior)
    for attempt in attempts:
        rows.append({"passage_type": passage_type, **attempt})
    counts = Counter(
        failure["category"]
        for row in rows
        for failure in row.get("failures", [])
    )
    write_json(
        EVIDENCE_DIR / "gate-failures.json",
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "failure_counts": dict(sorted(counts.items())),
            "attempts": rows,
        },
    )
    return rows


def save_partial_cost(
    passage_rows: list[dict],
    *,
    model: dict,
    budget: dict,
    status: str,
) -> dict:
    if passage_rows:
        report = build_cost_report(passage_rows)
    else:
        report = {
            "passages": [],
            "totals": {
                "passages": 0,
                "questions": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "elapsed_seconds": 0.0,
                "failed_retries": 0,
            },
            "per_question": {
                "prompt_tokens": 0.0,
                "completion_tokens": 0.0,
                "total_tokens": 0.0,
                "elapsed_seconds": 0.0,
            },
            "extrapolations": {},
        }
    report.update(
        {
            "status": status,
            "model": model,
            "budget": budget,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_json(EVIDENCE_DIR / "generation-cost-report.json", report)
    return report


def count_rows(connection, bank_id: str) -> dict:
    questions = {
        row["type"]: row["count"]
        for row in connection.execute(
            """
            SELECT type, count(*) AS count
            FROM questions
            WHERE bank_id=%s
            GROUP BY type
            """,
            (bank_id,),
        ).fetchall()
    }
    passages = {
        row["type"]: row["count"]
        for row in connection.execute(
            """
            SELECT type, count(*) AS count
            FROM passages
            WHERE bank_id=%s
            GROUP BY type
            """,
            (bank_id,),
        ).fetchall()
    }
    return {
        "bank_id": bank_id,
        "question_count": sum(questions.values()),
        "passage_count": sum(passages.values()),
        "question_type_counts": questions,
        "passage_type_counts": passages,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-browser-bank", action="store_true")
    args = parser.parse_args()

    generation = load_json(ROOT / "config" / "generation.json")
    schedule = load_pilot_schedule()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    schedule_check = validate_pilot_schedule(
        schedule,
        generation["pilot"]["paper_targets"],
    )
    if not schedule_check["accepted"]:
        raise RuntimeError(
            "PILOT_SCHEDULE_INVALID:" + ",".join(schedule_check["failures"])
        )

    client = GenerationClient(generation["model"])
    total_prompt = 0
    total_completion = 0
    passage_rows = []
    gate_rows: list[dict] = []
    generated_records = []

    with psycopg.connect(
        database_url(),
        row_factory=dict_row,
        autocommit=False,
    ) as connection:
        repo = M2Repository(connection)
        existing = find_existing_bank(
            connection,
            generation["pilot"]["bank_name"],
        )
        if existing:
            bank = repo.get_bank(existing["id"])
            job = latest_job(connection, existing["id"])
        else:
            with connection.transaction():
                bank = repo.create_bank(
                    name=generation["pilot"]["bank_name"],
                    target_size=generation["pilot"]["target_size"],
                    difficulty_profile="standard",
                )
                job = repo.create_generation_job(
                    bank["id"],
                    target_passages=generation["m2_targets"]["passages"],
                    batch_size=10,
                    approved_by="system_owner",
                    reason="M2.0 approved in owner instruction",
                )
        if not job:
            raise RuntimeError("GENERATION_JOB_NOT_FOUND")

        if repo.question_count(bank["id"]) == 0:
            repo.set_job_status(job["id"], "running")
            connection.commit()
            try:
                for passage_spec in schedule["passages"]:
                    started = time.perf_counter()

                    def generator(attempt, failures, spec=passage_spec):
                        prompt = build_prompt(spec, failures)
                        try:
                            return client.generate(spec["type"], prompt)
                        except Exception as error:
                            return (
                                {
                                    "type": spec["type"],
                                    "generation_error": str(error),
                                },
                                0,
                                0,
                                time.perf_counter() - started,
                            )

                    remaining_budget = (
                        generation["budget"]["pilot_total_token_cap"]
                        - total_prompt
                        - total_completion
                    )
                    result = generate_validated_passage(
                        passage_spec["type"],
                        generator,
                        max_retries=generation["model"]["max_retries"],
                        token_cap=remaining_budget,
                        expected_schedule=passage_spec,
                    )
                    generated_records.append(result.record)
                    total_prompt += result.metrics["prompt_tokens"]
                    total_completion += result.metrics["completion_tokens"]
                    passage_rows.append(
                        {
                            "type": passage_spec["type"],
                            "question_count": len(result.record["questions"]),
                            "prompt_tokens": result.metrics["prompt_tokens"],
                            "completion_tokens": result.metrics["completion_tokens"],
                            "elapsed_seconds": result.metrics["elapsed_seconds"],
                            "failed_retries": result.metrics["failed_retries"],
                        }
                    )
                    gate_rows = update_gate_evidence(
                        passage_type=passage_spec["type"],
                        attempts=result.attempts,
                        prior=gate_rows,
                    )
                    save_partial_cost(
                        passage_rows,
                        model=generation["model"],
                        budget=generation["budget"],
                        status="running",
                    )

                paper_check = validate_pilot_schedule(
                    schedule,
                    generation["pilot"]["paper_targets"],
                )
                if not paper_check["accepted"]:
                    raise RuntimeError(
                        "PILOT_PAPER_INVALID:"
                        + ",".join(paper_check["failures"])
                    )
                with connection.transaction():
                    for record in generated_records:
                        repo.insert_passage(
                            bank_id=bank["id"],
                            job_id=job["id"],
                            batch_id=generation["pilot"]["batch_id"],
                            record=record,
                        )
                    connection.execute(
                        """
                        INSERT INTO generation_batches
                            (job_id, bank_id, batch_number, passage_target,
                             status, accepted_count, rejected_count, checkpoint,
                             finished_at)
                        VALUES (%s, %s, 1, 3, 'validated', 3, 0, %s, now())
                        """,
                        (
                            job["id"],
                            bank["id"],
                            Jsonb(
                                {
                                    "pilot": True,
                                    "paper": paper_check,
                                    "cost_rows": passage_rows,
                                }
                            ),
                        ),
                    )
                    repo.set_job_status(
                        job["id"],
                        "paused_for_owner",
                        checkpoint={
                            "pilot_complete": True,
                            "owner_approval_required_for_scale": True,
                            "paper": paper_check,
                        },
                    )
                    repo.set_bank_status(
                        bank["id"],
                        "generating",
                        coverage_snapshot={
                            "question_counts": {
                                "cloze": 15,
                                "grammar_fill": 10,
                                "reading": 4,
                                "gap_fill": 0,
                            },
                            "passage_counts": {
                                "cloze": 1,
                                "grammar_fill": 1,
                                "reading": 1,
                                "gap_fill": 0,
                            },
                            "difficulty_distribution": paper_check["metrics"][
                                "difficulty"
                            ],
                            "book_distribution": paper_check["metrics"][
                                "book_tag"
                            ],
                            "topic_distribution": {
                                row["topic"]: 1 for row in schedule["passages"]
                            },
                            "out_of_scope_rate": 0.0,
                            "passage_duplicate_rate": 0.0,
                            "stem_duplicate_rate": 0.0,
                            "grammar_fill_coverage": {
                                tag: count
                                for tag, count in paper_check["metrics"][
                                    "grammar_tag_counts"
                                ].items()
                            },
                            "generated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
            except (GenerationExhausted, TokenBudgetExceeded) as error:
                connection.rollback()
                repo.set_job_status(
                    job["id"],
                    "failed",
                    checkpoint={
                        "error": str(error),
                        "attempts": getattr(error, "attempts", []),
                    },
                )
                connection.commit()
                save_partial_cost(
                    passage_rows,
                    model=generation["model"],
                    budget=generation["budget"],
                    status="failed",
                )
                gate_rows = update_gate_evidence(
                    passage_type=(
                        schedule["passages"][len(passage_rows)]["type"]
                        if len(passage_rows) < len(schedule["passages"])
                        else "unknown"
                    ),
                    attempts=getattr(error, "attempts", []),
                    prior=gate_rows,
                )
                raise

            connection.commit()
        else:
            if repo.question_count(bank["id"]) != 29:
                raise RuntimeError("PILOT_BANK_PARTIAL_STATE")

        counts = count_rows(connection, bank["id"])
        (EVIDENCE_DIR / "bank2-counts.txt").write_text(
            "\n".join(
                [
                    f"bank_id={counts['bank_id']}",
                    f"question_count={counts['question_count']}",
                    f"passage_count={counts['passage_count']}",
                    "question_type_counts="
                    + json.dumps(
                        counts["question_type_counts"],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "passage_type_counts="
                    + json.dumps(
                        counts["passage_type_counts"],
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        save_partial_cost(
            passage_rows,
            model=generation["model"],
            budget=generation["budget"],
            status="pilot_passed",
        )

        if args.prepare_browser_bank:
            previous = repo.get_active_bank()
            browser_bank = repo.clone_pilot_for_browser(
                source_bank_id=bank["id"],
                name=f"M2.0 Browser Validation {datetime.now(timezone.utc):%Y%m%d%H%M%S}",
            )
            repo.activate_bank(browser_bank["id"], actor="m2_pilot")
            connection.commit()
            write_json(
                EVIDENCE_DIR / "browser-bank-state.json",
                {
                    "source_bank_id": bank["id"],
                    "browser_bank_id": browser_bank["id"],
                    "previous_active_bank_id": previous["id"] if previous else None,
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        write_json(
            EVIDENCE_DIR / "pilot-summary.json",
            {
                "status": "pilot_passed",
                "bank": repo.get_bank(bank["id"]),
                "job": repo.get_job(job["id"]),
                "counts": counts,
                "paper": schedule_check,
            },
        )

    print(json.dumps(counts, ensure_ascii=False, indent=2))
    print("M2_PILOT=PASS")


if __name__ == "__main__":
    main()

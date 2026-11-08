#!/usr/bin/env python3
"""Audit M2.6 placeholder/form validation against the existing 47 passages."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.generation import (
    _answer_occurrence_count,
    _load_vocabulary_audit_module,
    _same_inflection,
    validate_generated_passage,
)


OUTPUT = ROOT / "qa" / "evidence" / "m26" / "validator-calibration.json"
STAGE0_SUMMARY = (
    ROOT / "qa" / "evidence" / "m26" / "post-stage0-impact-summary.json"
)
KNOWN_BAD = {
    "M2-FULL-CLOZE-03",
    "M2-FULL-CLOZE-04",
    "M2-FULL-CLOZE-05",
    "M2-FULL-GRAMMAR-03",
    "M2-FULL-GRAMMAR-05",
    "M2-FULL-GRAMMAR-06",
    "M2-FULL-GAP-03",
    "M2-FULL-GAP-05",
    "M2-FULL-GAP-06",
}
TOKEN_PATTERN = r"[a-z]+(?:['-][a-z]+)*"


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def load_records() -> tuple[str, list[dict]]:
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        bank_id = str(
            connection.execute(
                """
                SELECT active_bank_id
                FROM bank_active_state
                WHERE singleton=TRUE
                """
            ).fetchone()["active_bank_id"]
        )
        rows = connection.execute(
            """
            SELECT
                p.passage_group_id,
                p.type,
                p.content,
                p.topic,
                p.book_source,
                p.difficulty,
                q.id AS question_id,
                q.stem,
                q.options,
                q.answer#>>'{}' AS answer,
                q.explanation,
                q.knowledge_points,
                q.grammar_tags,
                q.book_source AS question_book_source,
                q.difficulty AS question_difficulty
            FROM passages p
            JOIN questions q
              ON q.bank_id=p.bank_id
             AND q.passage_group_id=p.passage_group_id
            WHERE p.bank_id=%s
              AND q.status='published'
            ORDER BY p.passage_group_id, q.id
            """,
            (bank_id,),
        ).fetchall()

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["passage_group_id"], []).append(row)

    records = []
    for passage_group_id, passage_rows in grouped.items():
        first = passage_rows[0]
        records.append(
            {
                "type": first["type"],
                "passage_group_id": passage_group_id,
                "topic": first["topic"],
                "book_source": first["book_source"],
                "difficulty": first["difficulty"],
                "passage": first["content"],
                "questions": [
                    {
                        "stem": row["stem"],
                        "options": row["options"],
                        "answer": row["answer"],
                        "explanation": row["explanation"],
                        "knowledge_points": row["knowledge_points"],
                        "grammar_tags": row["grammar_tags"],
                        "book_source": row["question_book_source"],
                        "difficulty": row["question_difficulty"],
                    }
                    for row in passage_rows
                ],
            }
        )
    return bank_id, records


def form_examples() -> list[dict]:
    candidate_lemmas = _load_vocabulary_audit_module().candidate_lemmas
    examples = [
        ("achieve", "achievement"),
        ("succeed", "success"),
        ("confident", "confidence"),
        ("achieve", "achieved"),
    ]
    return [
        {
            "answer": answer,
            "passage_form": passage_form,
            "answer_candidates": candidate_lemmas(answer),
            "passage_candidates": candidate_lemmas(passage_form),
            "counts_as_leak": _same_inflection(answer, passage_form),
        }
        for answer, passage_form in examples
    ]


def main() -> None:
    bank_id, records = load_records()
    vocabulary = json.loads(
        (ROOT / "contracts" / "vocabulary-whitelist.json").read_text(
            encoding="utf-8"
        )
    )
    entries = {
        entry["word"].casefold(): entry
        for entry in vocabulary["entries"]
    }

    findings = []
    blocked = []
    allowed = []
    new_lemma_leaks: list[dict] = []
    open_class_lemma_leaks: list[dict] = []
    literal_open_class_leaks: list[dict] = []
    token_level_all_leaks: list[dict] = []
    token_level_open_class_leaks: list[dict] = []
    for record in records:
        report = validate_generated_passage(record)
        failure_rows = [failure.as_dict() for failure in report.failures]
        accepted = report.accepted
        (allowed if accepted else blocked).append(record["passage_group_id"])
        for row in report.metrics.get("fill_integrity", []):
            answer_tokens = re.findall(
                TOKEN_PATTERN,
                row["answer"].casefold(),
            )
            matching_tokens = [
                token
                for token in answer_tokens
                if _answer_occurrence_count(record["passage"], token)
            ]
            literal_matching_tokens = [
                token
                for token in answer_tokens
                if re.search(
                    rf"\b{re.escape(token)}\b",
                    record["passage"].casefold(),
                )
            ]
            one_token_leak = {
                "passage_group_id": record["passage_group_id"],
                "question_index": row["question_index"],
                "answer": row["answer"],
                "matching_answer_words": matching_tokens,
            }
            if matching_tokens:
                token_level_all_leaks.append(one_token_leak)
            open_matching_tokens = [
                token
                for token in matching_tokens
                if entries.get(token) is None
                or not entries[token].get("closed_class")
            ]
            if open_matching_tokens:
                token_level_open_class_leaks.append(one_token_leak)
            open_literal_tokens = [
                token
                for token in literal_matching_tokens
                if entries.get(token) is None
                or not entries[token].get("closed_class")
            ]
            if open_literal_tokens:
                literal_open_class_leaks.append(one_token_leak)
            if row["answer_occurrences"]:
                leak = {
                    "passage_group_id": record["passage_group_id"],
                    "question_index": row["question_index"],
                    "answer": row["answer"],
                    "occurrences": row["answer_occurrences"],
                }
                new_lemma_leaks.append(leak)
                open_tokens = [
                    token
                    for token in re.findall(
                        TOKEN_PATTERN,
                        row["answer"].casefold(),
                    )
                    if entries.get(token) is None
                    or not entries[token].get("closed_class")
                ]
                if open_tokens and _answer_occurrence_count(
                    record["passage"],
                    " ".join(open_tokens),
                ):
                    open_class_lemma_leaks.append(leak)
        findings.append(
            {
                "passage_group_id": record["passage_group_id"],
                "type": record["type"],
                "accepted": accepted,
                "failure_codes": [
                    row["message"].split(":", 1)[0]
                    for row in failure_rows
                ],
                "failures": failure_rows,
                "fill_integrity": report.metrics.get("fill_integrity", []),
            }
        )

    known_bad_blocked = {
        passage_id: passage_id in blocked for passage_id in sorted(KNOWN_BAD)
    }
    allowed_fill_defects = [
        finding["passage_group_id"]
        for finding in findings
        if finding["accepted"]
        and any(not row["valid"] or row["answer_occurrences"] for row in finding["fill_integrity"])
    ]
    stage0 = json.loads(STAGE0_SUMMARY.read_text(encoding="utf-8"))
    literal_keys = {
        (row["passage_group_id"], row["question_index"])
        for row in literal_open_class_leaks
    }
    token_level_added_by_inflection = [
        row
        for row in token_level_open_class_leaks
        if (row["passage_group_id"], row["question_index"])
        not in literal_keys
    ]
    by_id = {
        finding["passage_group_id"]: finding
        for finding in findings
    }
    records_by_id = {
        record["passage_group_id"]: record
        for record in records
    }

    result = {
        "bank_id": bank_id,
        "passages_checked": len(records),
        "form_rule_examples": form_examples(),
        "lemma_rule_source": {
            "contract": "contracts/vocabulary-normalization.json",
            "resolver": "scripts/vocabulary-audit.py:candidate_lemmas/resolve_with_audit",
            "answer_leak_rule": (
                "irregular table plus regular inflection suffixes; "
                "derivational suffixes are excluded"
            ),
            "answer_leak_chain_depth": 1,
            "vocabulary_audit_max_chain_depth": (
                _load_vocabulary_audit_module().MAX_CHAIN_DEPTH
            ),
        },
        "answer_form_anywhere": {
            "new_inflection_rule_blanks": len(new_lemma_leaks),
            "new_inflection_rule_passages": len(
                {row["passage_group_id"] for row in new_lemma_leaks}
            ),
            "new_inflection_open_class_blanks": len(open_class_lemma_leaks),
            "new_inflection_open_class_passages": len(
                {
                    row["passage_group_id"]
                    for row in open_class_lemma_leaks
                }
            ),
            "token_level_inflection_blanks": len(token_level_all_leaks),
            "token_level_inflection_passages": len(
                {
                    row["passage_group_id"]
                    for row in token_level_all_leaks
                }
            ),
            "token_level_inflection_open_class_blanks": len(
                token_level_open_class_leaks
            ),
            "token_level_inflection_open_class_passages": len(
                {
                    row["passage_group_id"]
                    for row in token_level_open_class_leaks
                }
            ),
            "stage0_literal_open_class_blanks": stage0[
                "open_class_answer_word_anywhere"
            ]["blanks"],
            "stage0_literal_open_class_passages": stage0[
                "open_class_answer_word_anywhere"
            ]["passages"],
            "recomputed_literal_open_class_blanks": len(
                literal_open_class_leaks
            ),
            "recomputed_literal_open_class_passages": len(
                {
                    row["passage_group_id"]
                    for row in literal_open_class_leaks
                }
            ),
            "matches_stage0_summary": (
                len(literal_open_class_leaks)
                == stage0["open_class_answer_word_anywhere"]["blanks"]
                and len(
                    {
                        row["passage_group_id"]
                        for row in literal_open_class_leaks
                    }
                )
                == stage0["open_class_answer_word_anywhere"]["passages"]
            ),
            "token_level_added_by_inflection": (
                token_level_added_by_inflection
            ),
        },
        "validation_outcome": {
            "blocked_count": len(blocked),
            "allowed_count": len(allowed),
            "blocked": blocked,
            "allowed": allowed,
            "known_bad_blocked": known_bad_blocked,
            "all_known_bad_blocked": all(known_bad_blocked.values()),
            "allowed_fill_with_defect": allowed_fill_defects,
        },
        "calibration_samples": {
            "known_bad": {
                "passage_group_id": "M2-FULL-CLOZE-04",
                "passage_snippet": records_by_id["M2-FULL-CLOZE-04"][
                    "passage"
                ][:700],
                "accepted": by_id["M2-FULL-CLOZE-04"]["accepted"],
                "failure_codes": by_id["M2-FULL-CLOZE-04"][
                    "failure_codes"
                ],
            },
            "known_good": {
                "passage_group_id": "M2-FULL-GAP-10",
                "passage_snippet": records_by_id["M2-FULL-GAP-10"][
                    "passage"
                ][:700],
                "accepted": by_id["M2-FULL-GAP-10"]["accepted"],
                "failure_codes": by_id["M2-FULL-GAP-10"][
                    "failure_codes"
                ],
            },
        },
        "new_lemma_leaks": new_lemma_leaks,
        "token_level_inflection_leaks": token_level_all_leaks,
        "token_level_open_class_leaks": token_level_open_class_leaks,
        "passages": findings,
    }
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "bank_id",
                    "passages_checked",
                    "form_rule_examples",
                    "lemma_rule_source",
                    "answer_form_anywhere",
                    "validation_outcome",
                    "calibration_samples",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

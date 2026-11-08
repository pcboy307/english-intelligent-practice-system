from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import jsonschema
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

os.environ.setdefault("WEAKNESS_ANALYSIS_DISABLED", "1")

from backend.app.main import app, store
from backend.app.bank_transfer import delete_bank
from backend.app.m26_audit import audit_records


ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app, client=("127.0.0.1", 43000))
remote_client = TestClient(app, client=("192.168.1.9", 43001))


def database_url() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("DATABASE_URL_NOT_CONFIGURED")


def import_package() -> dict:
    records = [
        record
        for record in json.loads(
        (
            ROOT
            / "qa"
            / "evidence"
            / "m26"
            / "stage-a"
            / "stage-a-generated.json"
        ).read_text(encoding="utf-8")
        )
        if record["type"] == "reading"
    ][:1]
    counts = {"cloze": 0, "grammar_fill": 0, "reading": 1, "gap_fill": 0}
    return {
        "format_version": "bank-v1",
        "name": f"Import test {uuid.uuid4().hex[:10]}",
        "target_size": 4,
        "difficulty_profile": "advanced",
        "generated_at": "2026-11-09",
        "composition": counts,
        "passages": records,
    }


def gap_fill_import_package() -> dict:
    options = [
        f"{letter}. Shared option {letter}"
        for letter in "ABCDEFG"
    ]
    record = {
        "validation_profile": "stored",
        "type": "gap_fill",
        "passage_group_id": "GAP-EXPORT-01",
        "topic": "school life",
        "book_source": "必修一 U1",
        "difficulty": 2,
        "word_count": 90,
        "passage": (
            "A school is starting a reading club. (1) Members will meet on Friday. "
            "(2) They will choose books together. (3) Everyone can share an idea. "
            "(4) The club will keep a simple record. (5)"
        ),
        "options": options,
        "questions": [
            {
                "number": number,
                "stem": f"Choose the best sentence for blank ({number}).",
                "options": options,
                "answer": "ABCDE"[number - 1],
                "explanation": f"第 {number} 空的句子与上下文衔接最自然。",
                "knowledge_points": ["gap_fill_transition"],
                "grammar_tags": ["conjunctions"],
                "book_source": "必修一 U1",
                "difficulty": 2,
            }
            for number in range(1, 6)
        ],
    }
    return {
        "format_version": "bank-v1",
        "name": f"Gap export test {uuid.uuid4().hex[:10]}",
        "target_size": 5,
        "difficulty_profile": "standard",
        "generated_at": "2026-11-09",
        "composition": {
            "cloze": 0,
            "grammar_fill": 0,
            "reading": 0,
            "gap_fill": 1,
        },
        "passages": [record],
    }


def student_headers() -> dict[str, str]:
    return {"X-Student-Id": str(uuid.uuid4())}


def test_import_preview_returns_counts_without_writing_a_bank() -> None:
    package = import_package()
    with store.connection() as connection:
        before = connection.execute(
            "SELECT count(*) AS count FROM question_banks"
        ).fetchone()["count"]

    response = client.post(
        "/api/v1/banks/import/preview?semantic_check=false",
        json=package,
        headers=student_headers(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["summary"]["passages"] == 1
    assert body["summary"]["questions"] == 4
    with store.connection() as connection:
        after = connection.execute(
            "SELECT count(*) AS count FROM question_banks"
        ).fetchone()["count"]
    assert after == before


def test_import_preview_rejects_target_size_mismatch() -> None:
    package = import_package()
    package["target_size"] += 1

    response = client.post(
        "/api/v1/banks/import/preview?semantic_check=false",
        json=package,
        headers=student_headers(),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "IMPORT_VALIDATION_FAILED"
    assert any(
        item["code"] == "TARGET_SIZE_MISMATCH"
        for item in response.json()["detail"]["errors"]
    )


def test_import_rejects_an_empty_bank_name() -> None:
    package = import_package()
    package["name"] = "   "

    response = client.post(
        "/api/v1/banks/import",
        json=package,
        headers=student_headers(),
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "IMPORT_VALIDATION_FAILED"
    assert any(
        item["code"] == "BANK_NAME_INVALID"
        and "不能为空" in item["message"]
        for item in response.json()["detail"]["errors"]
    )


def test_invalid_import_never_writes_a_bank() -> None:
    package = import_package()
    del package["passages"][0]["questions"][0]["answer"]
    with store.connection() as connection:
        before = connection.execute(
            "SELECT count(*) AS count FROM question_banks"
        ).fetchone()["count"]

    response = client.post(
        "/api/v1/banks/import?semantic_check=false",
        json=package,
        headers=student_headers(),
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "IMPORT_VALIDATION_FAILED"
    with store.connection() as connection:
        after = connection.execute(
            "SELECT count(*) AS count FROM question_banks"
        ).fetchone()["count"]
    assert after == before


def test_import_bypasses_quality_validation_and_persists_content() -> None:
    original_bank_id = store.bank["bank_id"]
    package = import_package()
    package["passages"][0]["questions"][0]["explanation"] = ""
    imported_id = ""
    try:
        response = client.post(
            "/api/v1/banks/import",
            json=package,
            headers=student_headers(),
        )
        assert response.status_code == 201, response.text
        imported_id = response.json()["bank_id"]
        with store.connection() as connection:
            explanation = connection.execute(
                """
                SELECT explanation
                FROM questions
                WHERE bank_id=%s
                ORDER BY id
                LIMIT 1
                """,
                (imported_id,),
            ).fetchone()["explanation"]
        assert explanation == "导入时未提供解析。"
    finally:
        if imported_id:
            with psycopg.connect(database_url(), row_factory=dict_row) as connection:
                with connection.transaction():
                    connection.execute(
                        "UPDATE question_banks SET status='archived' WHERE id=%s",
                        (imported_id,),
                    )
                    connection.execute(
                        "UPDATE question_banks SET status='ready' WHERE id=%s",
                        (original_bank_id,),
                    )
                    connection.execute(
                        "UPDATE bank_active_state SET active_bank_id=%s WHERE singleton=TRUE",
                        (original_bank_id,),
                    )
                    delete_bank(connection, imported_id)
            store.reload_active_bank()


def test_import_accepts_a_minimal_name_and_passages_package() -> None:
    original_bank_id = store.bank["bank_id"]
    package = import_package()
    for field in (
        "format_version",
        "target_size",
        "difficulty_profile",
        "generated_at",
        "composition",
    ):
        package.pop(field)
    imported_id = ""
    try:
        response = client.post(
            "/api/v1/banks/import",
            json=package,
            headers=student_headers(),
        )
        assert response.status_code == 201, response.text
        imported_id = response.json()["bank_id"]
        assert response.json()["summary"]["questions"] == 4
    finally:
        if imported_id:
            with psycopg.connect(database_url(), row_factory=dict_row) as connection:
                with connection.transaction():
                    connection.execute(
                        "UPDATE question_banks SET status='archived' WHERE id=%s",
                        (imported_id,),
                    )
                    connection.execute(
                        "UPDATE question_banks SET status='ready' WHERE id=%s",
                        (original_bank_id,),
                    )
                    connection.execute(
                        "UPDATE bank_active_state SET active_bank_id=%s WHERE singleton=TRUE",
                        (original_bank_id,),
                    )
                    delete_bank(connection, imported_id)
            store.reload_active_bank()


def test_import_preview_rejects_non_loopback_clients() -> None:
    response = remote_client.post(
        "/api/v1/banks/import/preview?semantic_check=false",
        json=import_package(),
        headers=student_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_LOCAL_ONLY"


def test_export_bank_uses_import_contract_and_can_be_previewed_again() -> None:
    original_bank_id = store.bank["bank_id"]
    imported_id = ""
    try:
        imported = client.post(
            "/api/v1/banks/import?semantic_check=false",
            json=import_package(),
            headers=student_headers(),
        )
        assert imported.status_code == 201, imported.text
        imported_id = imported.json()["bank_id"]

        exported = client.get(
            f"/api/v1/banks/{imported_id}/export",
            headers=student_headers(),
        )
        assert exported.status_code == 200, exported.text
        package = exported.json()
        assert set(package) == {
            "format_version",
            "name",
            "target_size",
            "difficulty_profile",
            "generated_at",
            "composition",
            "passages",
        }
        assert package["format_version"] == "bank-v1"
        assert package["target_size"] == sum(
            len(passage["questions"]) for passage in package["passages"]
        )
        assert package["target_size"] == 4
        assert package["passages"][0]["validation_profile"] == "stored"

        package["name"] = f"Exported roundtrip {uuid.uuid4().hex[:10]}"
        preview = client.post(
            "/api/v1/banks/import/preview?semantic_check=false",
            json=package,
            headers=student_headers(),
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["summary"]["questions"] == package["target_size"]
    finally:
        if imported_id:
            with psycopg.connect(database_url(), row_factory=dict_row) as connection:
                with connection.transaction():
                    connection.execute(
                        "UPDATE question_banks SET status='archived' WHERE id=%s",
                        (imported_id,),
                    )
                    connection.execute(
                        "UPDATE question_banks SET status='ready' WHERE id=%s",
                        (original_bank_id,),
                    )
                    connection.execute(
                        "UPDATE bank_active_state SET active_bank_id=%s WHERE singleton=TRUE",
                        (original_bank_id,),
                    )
                    delete_bank(connection, imported_id)
            store.reload_active_bank()


def test_exported_gap_fill_matches_import_schema() -> None:
    original_bank_id = store.bank["bank_id"]
    imported_id = ""
    try:
        imported = client.post(
            "/api/v1/banks/import?semantic_check=false",
            json=gap_fill_import_package(),
            headers=student_headers(),
        )
        assert imported.status_code == 201, imported.text
        imported_id = imported.json()["bank_id"]

        exported = client.get(
            f"/api/v1/banks/{imported_id}/export",
            headers=student_headers(),
        )
        assert exported.status_code == 200, exported.text
        package = exported.json()
        gap_fill = next(
            passage
            for passage in package["passages"]
            if passage["type"] == "gap_fill"
        )
        assert gap_fill["options"] == gap_fill["questions"][0]["options"]
        schema = json.loads(
            (
                ROOT
                / "contracts"
                / "schemas"
                / "bank-import-package.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.validate(package, schema)
    finally:
        if imported_id:
            with psycopg.connect(database_url(), row_factory=dict_row) as connection:
                with connection.transaction():
                    connection.execute(
                        "UPDATE question_banks SET status='archived' WHERE id=%s",
                        (imported_id,),
                    )
                    connection.execute(
                        "UPDATE question_banks SET status='ready' WHERE id=%s",
                        (original_bank_id,),
                    )
                    connection.execute(
                        "UPDATE bank_active_state SET active_bank_id=%s WHERE singleton=TRUE",
                        (original_bank_id,),
                    )
                    delete_bank(connection, imported_id)
            store.reload_active_bank()


def test_export_endpoint_rejects_non_loopback_clients() -> None:
    response = remote_client.get(
        f"/api/v1/banks/{store.bank['bank_id']}/export",
        headers=student_headers(),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_LOCAL_ONLY"


def test_delete_endpoints_reject_non_loopback_clients() -> None:
    response = remote_client.get(
        f"/api/v1/banks/{store.bank['bank_id']}/delete-preview"
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_LOCAL_ONLY"

    response = remote_client.delete(
        f"/api/v1/banks/{store.bank['bank_id']}"
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "ADMIN_LOCAL_ONLY"


def test_m26_import_requires_the_full_quota() -> None:
    package = import_package()
    package["format_version"] = "m26-v1"

    response = client.post(
        "/api/v1/banks/import/preview?semantic_check=false",
        json=package,
        headers=student_headers(),
    )

    assert response.status_code == 400
    codes = {item["code"] for item in response.json()["detail"]["errors"]}
    assert "M26_TARGET_SIZE_INVALID" in codes
    assert "M26_COMPOSITION_INVALID" in codes


def test_semantic_audit_stops_at_five_cny_and_returns_no_valid_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = import_package()["passages"][0]

    class FakeResponse:
        prompt_tokens = 0
        completion_tokens = 1_000_000
        data = {
            "coherent": True,
            "coherence_reason": "One coherent passage.",
            "questions": [
                {
                    "question_index": index,
                    "unique_best": True,
                    "answer_supported": True,
                    "same_part_of_speech": True,
                    "same_semantic_field": True,
                    "near_synonym_distractor": False,
                    "evidence_ok": True,
                    "options_rewritten": True,
                    "verdict": "ok",
                    "reason": "One clear answer.",
                }
                for index in range(1, 5)
            ],
        }

    class FakeClient:
        requests: list[object] = []

        def __init__(self, config: dict) -> None:
            self.config = config

        def chat_json(self, purpose: str, prompt: str) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr("backend.app.m26_audit.DeepSeekClient", FakeClient)
    result = audit_records([record])

    assert result["valid"] is False
    assert result["budget_exceeded"] is True
    assert result["cost_cny"] >= 5
    assert result["audited_passages"] == 0
    assert any(
        failure["code"] == "SEMANTIC_AUDIT_BUDGET_EXCEEDED"
        for failure in result["failures"]
    )


def test_active_bank_delete_preview_is_rejected() -> None:
    response = client.get(
        f"/api/v1/banks/{store.bank['bank_id']}/delete-preview",
        headers=student_headers(),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ACTIVE_BANK_CANNOT_BE_DELETED"


def test_import_then_delete_removes_the_bank_and_restores_previous_active() -> None:
    original_bank_id = store.bank["bank_id"]
    package = import_package()
    imported_id = ""
    try:
        response = client.post(
            "/api/v1/banks/import?semantic_check=false",
            json=package,
            headers=student_headers(),
        )
        assert response.status_code == 201, response.text
        imported_id = response.json()["bank_id"]
        assert response.json()["status"] == "active"
        assert store.bank["bank_id"] == imported_id

        preview = client.get(
            f"/api/v1/banks/{imported_id}/delete-preview",
            headers=student_headers(),
        )
        assert preview.status_code == 409
        assert preview.json()["detail"]["code"] == "ACTIVE_BANK_CANNOT_BE_DELETED"

        switched = client.post(
            f"/api/v1/admin/banks/{original_bank_id}/activate",
            headers=student_headers(),
        )
        assert switched.status_code == 200, switched.text
        assert store.bank["bank_id"] == original_bank_id

        preview = client.get(
            f"/api/v1/banks/{imported_id}/delete-preview",
            headers=student_headers(),
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["bank_id"] == imported_id
        assert preview.json()["can_delete"] is True

        deleted = client.delete(
            f"/api/v1/banks/{imported_id}",
            headers=student_headers(),
        )
        assert deleted.status_code == 204, deleted.text
        imported_id = ""
    finally:
        if imported_id:
            with psycopg.connect(database_url(), row_factory=dict_row) as connection:
                with connection.transaction():
                    connection.execute(
                        "UPDATE question_banks SET status='archived' WHERE id=%s",
                        (imported_id,),
                    )
                    connection.execute(
                        "UPDATE question_banks SET status='ready' WHERE id=%s",
                        (original_bank_id,),
                    )
                    connection.execute(
                        "UPDATE bank_active_state SET active_bank_id=%s WHERE singleton=TRUE",
                        (original_bank_id,),
                    )
                    delete_bank(connection, imported_id)
            store.reload_active_bank()


def test_duplicate_bank_name_is_rejected() -> None:
    original_bank_id = store.bank["bank_id"]
    package = import_package()
    imported_id = ""
    try:
        imported = client.post(
            "/api/v1/banks/import?semantic_check=false",
            json=package,
            headers=student_headers(),
        )
        assert imported.status_code == 201, imported.text
        imported_id = imported.json()["bank_id"]

        switched = client.post(
            f"/api/v1/admin/banks/{original_bank_id}/activate",
            headers=student_headers(),
        )
        assert switched.status_code == 200, switched.text

        duplicate = client.post(
            "/api/v1/banks/import/preview?semantic_check=false",
            json=package,
            headers=student_headers(),
        )
        assert duplicate.status_code == 400
        assert any(
            item["code"] == "BANK_NAME_EXISTS"
            for item in duplicate.json()["detail"]["errors"]
        )
    finally:
        if imported_id:
            with psycopg.connect(database_url(), row_factory=dict_row) as connection:
                with connection.transaction():
                    connection.execute(
                        "UPDATE question_banks SET status='archived' WHERE id=%s",
                        (imported_id,),
                    )
                    connection.execute(
                        "UPDATE question_banks SET status='ready' WHERE id=%s",
                        (original_bank_id,),
                    )
                    connection.execute(
                        "UPDATE bank_active_state SET active_bank_id=%s WHERE singleton=TRUE",
                        (original_bank_id,),
                    )
                    delete_bank(connection, imported_id)
            store.reload_active_bank()


def test_delete_removes_all_user_history_associated_with_the_bank() -> None:
    original_bank_id = store.bank["bank_id"]
    package = import_package()
    imported_id = ""
    student_id = uuid.uuid4()
    session_id = uuid.uuid4()
    try:
        imported = client.post(
            "/api/v1/banks/import?semantic_check=false",
            json=package,
            headers=student_headers(),
        )
        assert imported.status_code == 201, imported.text
        imported_id = imported.json()["bank_id"]
        switched = client.post(
            f"/api/v1/admin/banks/{original_bank_id}/activate",
            headers=student_headers(),
        )
        assert switched.status_code == 200, switched.text

        with store.connection() as connection:
            question = connection.execute(
                """
                SELECT id, passage_group_id, type
                FROM questions
                WHERE bank_id=%s
                ORDER BY passage_group_id, id
                LIMIT 1
                """,
                (imported_id,),
            ).fetchone()
            assert question is not None
            connection.execute(
                """
                INSERT INTO practice_sessions
                    (id, student_id, bank_id, bank_name, duration_minutes,
                     status, started_at, deadline, submitted_at,
                     submit_idempotency_key, composition_note, session_kind)
                VALUES (%s, %s, %s, 'Import history', 30, 'submitted',
                        now() - interval '40 minutes', now() - interval '10 minutes',
                        now() - interval '10 minutes', %s, %s, 'practice')
                """,
                (
                    session_id,
                    student_id,
                    imported_id,
                    uuid.uuid4(),
                    Jsonb({"question_count": 4}),
                ),
            )
            connection.execute(
                """
                INSERT INTO session_items (session_id, question_id, bank_id, ordinal)
                VALUES (%s, %s, %s, 0)
                """,
                (session_id, question["id"], imported_id),
            )
            connection.execute(
                """
                INSERT INTO saved_answers (session_id, question_id, answer)
                VALUES (%s, %s, %s)
                """,
                (session_id, question["id"], Jsonb("A")),
            )
            connection.execute(
                """
                INSERT INTO question_attempts
                    (student_id, session_id, bank_id, question_id, passage_id,
                     question_type, chosen_option, correct_option, is_correct,
                     attempt_kind)
                VALUES (%s, %s, %s, %s, %s, 'reading', 'A', 'A', TRUE, 'practice')
                """,
                (
                    student_id,
                    session_id,
                    imported_id,
                    question["id"],
                    question["passage_group_id"],
                ),
            )
            tag = connection.execute(
                """
                INSERT INTO error_tags
                    (student_id, question_id, bank_id, question_type,
                     knowledge_points, grammar_tags)
                VALUES (%s, %s, %s, 'reading', ARRAY['reading'], ARRAY['tense_system'])
                RETURNING id
                """,
                (student_id, question["id"], imported_id),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO error_tag_successes (tag_id, session_id)
                VALUES (%s, %s)
                """,
                (tag["id"], session_id),
            )
            connection.execute(
                """
                INSERT INTO practice_reports
                    (session_id, student_id, bank_id, bank_name, report)
                VALUES (%s, %s, %s, 'Import history', %s)
                """,
                (session_id, student_id, imported_id, Jsonb({"question_count": 4})),
            )
            connection.execute(
                """
                INSERT INTO report_deletions (session_id, student_id)
                VALUES (%s, %s)
                """,
                (session_id, student_id),
            )
            connection.execute(
                """
                INSERT INTO mistake_items
                    (student_id, bank_id, question_id, passage_id, question_type,
                     first_wrong_at, last_wrong_at)
                VALUES (%s, %s, %s, %s, 'reading', now(), now())
                """,
                (
                    student_id,
                    imported_id,
                    question["id"],
                    question["passage_group_id"],
                ),
            )

        preview = client.get(
            f"/api/v1/banks/{imported_id}/delete-preview",
            headers=student_headers(),
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["sessions"] == 1
        assert preview.json()["reports"] == 1
        assert preview.json()["attempts"] == 1
        assert preview.json()["mistakes"] == 1

        deleted = client.delete(
            f"/api/v1/banks/{imported_id}",
            headers=student_headers(),
        )
        assert deleted.status_code == 204, deleted.text
        with store.connection() as connection:
            for table in (
                "question_banks",
                "passages",
                "questions",
                "practice_sessions",
                "session_items",
                "saved_answers",
                "question_attempts",
                "error_tags",
                "practice_reports",
                "report_deletions",
                "mistake_items",
            ):
                if table == "saved_answers":
                    count = connection.execute(
                        "SELECT count(*) AS count FROM saved_answers WHERE session_id=%s",
                        (session_id,),
                    ).fetchone()["count"]
                elif table == "report_deletions":
                    count = connection.execute(
                        "SELECT count(*) AS count FROM report_deletions WHERE session_id=%s",
                        (session_id,),
                    ).fetchone()["count"]
                else:
                    id_column = "id" if table == "question_banks" else "bank_id"
                    count = connection.execute(
                        f"SELECT count(*) AS count FROM {table} WHERE {id_column}=%s",
                        (imported_id,),
                    ).fetchone()["count"]
                assert count == 0, table
        imported_id = ""
        assert store.bank["bank_id"] == original_bank_id
    finally:
        if imported_id:
            with psycopg.connect(database_url(), row_factory=dict_row) as connection:
                with connection.transaction():
                    connection.execute(
                        "UPDATE question_banks SET status='archived' WHERE id=%s",
                        (imported_id,),
                    )
                    connection.execute(
                        "UPDATE question_banks SET status='ready' WHERE id=%s",
                        (original_bank_id,),
                    )
                    connection.execute(
                        "UPDATE bank_active_state SET active_bank_id=%s WHERE singleton=TRUE",
                        (original_bank_id,),
                    )
                    delete_bank(connection, imported_id)
            store.reload_active_bank()

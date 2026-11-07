"""Verify report naming, LLM weakness analysis, and history deletion."""

from __future__ import annotations

import json
import os
import re
import uuid

import httpx
import psycopg
from psycopg.rows import dict_row


BASE = "http://127.0.0.1:8000/api/v1"
TITLE = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-(?:29|30)题-\d+\.\d{2}分")


def main() -> None:
    student_id = str(uuid.uuid4())
    headers = {"X-Student-Id": student_id}
    with httpx.Client(headers=headers, timeout=90) as client:
        started = client.post(
            f"{BASE}/practice/start",
            json={"duration_minutes": 30},
        )
        started.raise_for_status()
        session = started.json()
        submitted = client.post(
            f"{BASE}/practice/{session['session_id']}/submit",
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
        submitted.raise_for_status()
        report = submitted.json()
        analysis = report["weakness_analysis"]
        assert TITLE.fullmatch(report["report_title"])
        assert report["question_count"] in {29, 30}
        assert len(analysis) <= 300
        assert report["weakness_analysis_source"] in {"llm", "fallback"}
        assert re.search(r"[\u4e00-\u9fff]", analysis)

        history = client.get(f"{BASE}/reports")
        history.raise_for_status()
        listed = next(
            item
            for item in history.json()
            if item["session_id"] == session["session_id"]
        )
        assert listed["report_title"] == report["report_title"]
        opened = client.get(f"{BASE}/reports/{session['session_id']}")
        opened.raise_for_status()
        assert opened.json()["report_title"] == report["report_title"]
        deleted_rows = None
        if os.getenv("KEEP_CO005_REPORT") != "1":
            deleted = client.delete(f"{BASE}/reports/{session['session_id']}")
            assert deleted.status_code == 204
            assert client.get(f"{BASE}/reports/{session['session_id']}").status_code == 404

            with psycopg.connect(
                "postgresql://postgres@127.0.0.1:15432/english_practice",
                row_factory=dict_row,
            ) as connection:
                deleted_rows = {
                    table: connection.execute(
                        f"SELECT count(*) AS count FROM {table} WHERE {id_column}=%s",
                        (session["session_id"],),
                    ).fetchone()["count"]
                    for table, id_column in (
                        ("practice_reports", "session_id"),
                        ("saved_answers", "session_id"),
                        ("session_items", "session_id"),
                        ("practice_sessions", "id"),
                    )
                }
            assert all(count == 0 for count in deleted_rows.values())

        result = {
            "session_id": session["session_id"],
            "report_title": report["report_title"],
            "question_count": report["question_count"],
            "analysis_length": len(analysis),
            "analysis_source": report["weakness_analysis_source"],
            "analysis": analysis,
            "history_listed": True,
            "history_opened": True,
            "history_deleted": deleted_rows is not None,
            "deleted_rows": deleted_rows,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import secrets
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import psycopg
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .pg_store import PostgresStore
from .bank_transfer import (
    ImportValidationError,
    delete_bank,
    delete_preview,
    export_bank,
    import_bank,
    normalize_import_package,
    preview_import,
)
from .m26_audit import audit_records

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
API_CONFIG = json.loads((ROOT / "config" / "api.json").read_text(encoding="utf-8"))


def ensure_admin_token() -> str:
    global ADMIN_TOKEN
    if ADMIN_TOKEN:
        return ADMIN_TOKEN
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.startswith("ADMIN_TOKEN="):
                ADMIN_TOKEN = line.split("=", 1)[1].strip()
                return ADMIN_TOKEN
    ADMIN_TOKEN = secrets.token_urlsafe(32)
    with ENV_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"ADMIN_TOKEN={ADMIN_TOKEN}\n")
    print(f"ADMIN_TOKEN={ADMIN_TOKEN}")
    return ADMIN_TOKEN


ensure_admin_token()

app = FastAPI(title="English Practice API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CONFIG["cors"]["allow_origins"],
    allow_credentials=API_CONFIG["cors"]["allow_credentials"],
    allow_methods=API_CONFIG["cors"]["allow_methods"],
    allow_headers=API_CONFIG["cors"]["allow_headers"],
)
store = PostgresStore()


class StartPracticeRequest(BaseModel):
    duration_minutes: int = Field(ge=1)


class SaveAnswerRequest(BaseModel):
    question_id: str
    answer: str | list[str]
    client_revision: int = Field(default=0, ge=0)


def student_id_or_401(x_student_id: str | None) -> str:
    if not x_student_id:
        raise HTTPException(status_code=401, detail={"code": "STUDENT_ID_REQUIRED"})
    try:
        return str(UUID(x_student_id))
    except ValueError as error:
        raise HTTPException(status_code=401, detail={"code": "STUDENT_ID_REQUIRED"}) from error


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def session_payload(record) -> dict:
    remaining = max(0, int((record.deadline - now_utc()).total_seconds()))
    items = []
    for qid in record.question_ids:
        question = store.get_question(record.bank_id, qid)
        items.append(
            {
                "question_id": question.id,
                "type": question.type,
                "passage_group_id": question.passage_group_id,
                "passage": question.passage,
                "stem": question.stem,
                "options": question.options,
                "saved_answer": record.answers.get(qid),
                "presentation_mode": question.presentation_mode,
                "blank_label": question.blank_label,
                "passage_order": question.passage_order,
                "question_order": question.question_order,
                "book_tag": question.book_tag,
            }
        )
    return {
        "session_id": record.id,
        "bank_id": record.bank_id,
        "bank_name": record.bank_name,
        "bank_version": record.bank_version,
        "duration_minutes": record.duration_minutes,
        "status": record.status,
        "items": items,
        "composition_note": record.composition_note,
        "deadline": record.deadline.isoformat(),
        "server_time": now_utc().isoformat(),
        "remaining_seconds": remaining,
        "progress": {"answered": len(record.answers), "total": len(record.question_ids)},
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/healthz")
def api_healthz() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/bank/active")
def get_active_bank(
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id_or_401(x_student_id)
    return {
        "bank_id": store.bank["bank_id"],
        "name": store.bank["name"],
        "status": store.bank["status"],
    }


@app.post("/api/v1/practice/start", status_code=201)
def start_practice(
    payload: StartPracticeRequest,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    try:
        record = store.start_session(student_id, payload.duration_minutes, now_utc())
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"code": str(error)}) from error
    return session_payload(record)


@app.get("/api/v1/mistakes")
def list_mistakes(
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    return store.list_mistakes(student_id)


@app.get("/api/v1/mistakes/{passage_id}")
def get_mistake_passage(
    passage_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    try:
        return store.get_mistake_passage(student_id, passage_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": str(error)},
        ) from error


@app.post("/api/v1/mistakes/review/{passage_id}", status_code=201)
def start_mistake_review(
    passage_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    try:
        record = store.create_review_session(
            student_id,
            passage_id,
            now_utc(),
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": str(error)},
        ) from error
    return session_payload(record)


@app.get("/api/v1/stats/coverage")
def get_coverage_stats(
    bank_id: str = "active",
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    if bank_id != "active":
        raise HTTPException(
            status_code=400,
            detail={"code": "ONLY_ACTIVE_BANK_SUPPORTED"},
        )
    return store.get_coverage_stats(student_id)


@app.get("/api/v1/banks")
def list_switchable_banks(
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    return store.list_switchable_banks(student_id)


@app.get("/api/v1/banks/{bank_id}/export")
def export_bank_endpoint(request: Request, bank_id: str) -> dict:
    require_local_request(request)
    try:
        with store.connection() as connection:
            return export_bank(connection, bank_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "BANK_NOT_FOUND"},
        ) from error


@app.post("/api/v1/banks/import/preview")
def preview_bank_import(
    request: Request,
    payload: dict,
    semantic_check: bool = False,
) -> dict:
    require_local_request(request)
    try:
        with store.connection() as connection:
            summary = preview_import(connection, payload)
        if semantic_check:
            normalized = normalize_import_package(payload)
            audit = audit_records(normalized["records"])
            summary["semantic_audit"] = {
                "valid": audit["valid"],
                "failures": audit["failures"],
                "cost_cny": audit["cost_cny"],
                "audited_passages": audit["audited_passages"],
                "budget_cap_cny": audit["budget_cap_cny"],
                "budget_exceeded": audit["budget_exceeded"],
            }
            if not audit["valid"]:
                raise ImportValidationError(audit["failures"])
        return summary
    except ImportValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": str(error), "errors": error.errors},
        ) from error
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "IMPORT_VALIDATION_FAILED",
                "errors": [
                    {
                        "code": "BANK_NAME_EXISTS",
                        "message": "题库名称已存在，请换一个名称。",
                    }
                ],
            },
        ) from error


@app.post("/api/v1/banks/import", status_code=201)
def import_bank_endpoint(
    request: Request,
    payload: dict,
    semantic_check: bool = False,
) -> dict:
    require_local_request(request)
    try:
        with store.connection() as connection:
            with connection.transaction():
                result = import_bank(
                    connection,
                    payload,
                    strict_validation=False,
                )
        store.reload_active_bank()
        return result
    except ImportValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={"code": str(error), "errors": error.errors},
        ) from error
    except psycopg.errors.UniqueViolation as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "IMPORT_VALIDATION_FAILED",
                "errors": [
                    {
                        "code": "BANK_NAME_EXISTS",
                        "message": "题库名称已存在，请换一个名称。",
                    }
                ],
            },
        ) from error


@app.get("/api/v1/banks/{bank_id}/delete-preview")
def preview_bank_delete(bank_id: str, request: Request) -> dict:
    require_local_request(request)
    try:
        with store.connection() as connection:
            return delete_preview(connection, bank_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": str(error)},
        ) from error


@app.delete("/api/v1/banks/{bank_id}", status_code=204)
def delete_bank_endpoint(bank_id: str, request: Request) -> None:
    require_local_request(request)
    try:
        with store.connection() as connection:
            with connection.transaction():
                delete_bank(connection, bank_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": str(error)},
        ) from error
    return None


@app.get("/api/v1/maintenance/clear-mistakes/preview")
def preview_clear_mistakes(
    request: Request,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    require_local_request(request)
    return store.clear_mistakes_preview(student_id)


@app.post("/api/v1/maintenance/clear-mistakes")
def clear_mistakes(
    request: Request,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    require_local_request(request)
    return store.clear_mistakes(student_id)


@app.get("/api/v1/maintenance/reset-coverage/preview")
def preview_reset_coverage(
    request: Request,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    require_local_request(request)
    return store.reset_coverage_preview(student_id)


@app.post("/api/v1/maintenance/reset-coverage")
def reset_coverage(
    request: Request,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    require_local_request(request)
    return store.reset_coverage(student_id)


@app.get("/api/v1/practice/{session_id}")
def get_practice(
    session_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    try:
        record = store.get_session(student_id, session_id, now_utc())
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": str(error)}) from error
    return session_payload(record)


@app.get("/api/v1/practice/{session_id}/review")
def get_practice_review(
    session_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    try:
        return store.get_review(student_id, session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail={"code": str(error)}) from error


@app.delete("/api/v1/practice/{session_id}", status_code=204)
def abandon_practice(
    session_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> None:
    student_id = student_id_or_401(x_student_id)
    try:
        store.abandon_session(student_id, session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail={"code": str(error)}) from error
    return None


@app.put("/api/v1/practice/{session_id}/answer", status_code=204)
def save_answer(
    session_id: str,
    payload: SaveAnswerRequest,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> None:
    student_id = student_id_or_401(x_student_id)
    answer = payload.answer if isinstance(payload.answer, str) else "|".join(payload.answer)
    try:
        store.save_answer(student_id, session_id, payload.question_id, answer, now_utc())
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail={"code": str(error)}) from error
    return None


@app.post("/api/v1/practice/{session_id}/submit")
def submit_practice(
    session_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED"})
    try:
        return store.submit_session(student_id, session_id, idempotency_key, now_utc())
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": str(error)}) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail={"code": str(error)}) from error


@app.get("/api/v1/reports/{session_id}")
def get_report(
    session_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> dict:
    student_id = student_id_or_401(x_student_id)
    try:
        return store.get_report(student_id, session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND"}) from error


@app.get("/api/v1/reports")
def list_reports(
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> list[dict]:
    student_id = student_id_or_401(x_student_id)
    return store.list_reports(student_id)


@app.delete("/api/v1/reports/{session_id}", status_code=204)
def delete_report(
    session_id: str,
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> None:
    student_id = student_id_or_401(x_student_id)
    try:
        store.delete_report(student_id, session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "REPORT_NOT_FOUND"}) from error
    return None


@app.get("/api/v1/error-tags")
def get_error_tags(
    x_student_id: str | None = Header(default=None, alias="X-Student-Id"),
) -> list[dict]:
    student_id = student_id_or_401(x_student_id)
    return store.get_error_tags(student_id)


def require_local_request(request: Request) -> None:
    peer = request.client.host if request.client else ""
    if peer not in {"127.0.0.1", "::1"}:
        raise HTTPException(status_code=403, detail={"code": "ADMIN_LOCAL_ONLY"})


def require_local_admin(request: Request, x_admin_token: str | None) -> str:
    require_local_request(request)
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail={"code": "ADMIN_AUTH_FAILED"})
    return x_admin_token


@app.get("/api/v1/admin/banks")
def list_banks(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> list[dict]:
    token = require_local_admin(request, x_admin_token)
    store.admin_audit("GET", "/api/v1/admin/banks", token, "ok", 200)
    return [
        {
            "bank_id": store.bank["bank_id"],
            "name": store.bank["name"],
            "target_size": store.bank["target_size"],
            "difficulty_profile": store.bank["difficulty_profile"],
            "status": store.bank["status"],
        }
    ]


@app.post("/api/v1/admin/banks/{bank_id}/activate")
def activate_bank(
    bank_id: str,
    request: Request,
) -> dict:
    require_local_request(request)
    try:
        activated = store.activate_bank(bank_id, operator="student_ui")
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": str(error)},
        ) from error
    return activated

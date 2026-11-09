from __future__ import annotations

import hashlib
import secrets
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .analysis import generate_weakness_analysis
from .composer import assemble_demo_paper
from .demo_bank import DemoQuestion, demo_bank


@dataclass
class ErrorTag:
    question_id: str
    bank_id: str
    knowledge_points: list[str]
    grammar_tags: list[str]
    status: str = "active"
    streak: int = 0
    successful_session_ids: list[str] = field(default_factory=list)
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SessionRecord:
    id: str
    student_id: str
    bank_id: str
    bank_name: str
    bank_version: str
    duration_minutes: int
    started_at: datetime
    deadline: datetime
    question_ids: list[str]
    composition_note: dict
    status: str = "in_progress"
    answers: dict[str, str] = field(default_factory=dict)
    submitted_at: datetime | None = None
    idempotency_key: str | None = None
    report: dict | None = None
    session_kind: str = "practice"


class InMemoryStore:
    """Test adapter. Production persistence is PostgreSQL-only."""

    def __init__(self, seed: int = 7) -> None:
        self.bank = demo_bank()
        self.questions: dict[str, DemoQuestion] = {
            item.id: item for item in self.bank["questions"]
        }
        self.sessions: dict[str, SessionRecord] = {}
        self.error_tags: dict[tuple[str, str, str], ErrorTag] = {}
        self.history: dict[str, list[tuple[str, bool, datetime]]] = defaultdict(list)
        self.appearances: dict[str, list[datetime]] = defaultdict(list)
        self.idempotency: dict[tuple[str, str], dict] = {}
        self.audit_log: list[dict] = []

    def active_bank(self) -> dict:
        return self.bank

    def mastery_values(self, student_id: str) -> list[tuple[str, str, float]]:
        by_point: dict[str, list[bool]] = defaultdict(list)
        for qid, correct, _ in self.history.get(student_id, []):
            for point in self.questions[qid].knowledge_points:
                by_point[point].append(correct)
        return [(student_id, point, sum(values) / len(values)) for point, values in by_point.items()]

    def start_session(self, student_id: str, duration_minutes: int, now: datetime) -> SessionRecord:
        if duration_minutes != 30:
            raise ValueError("INVALID_DURATION")
        if self.bank["status"] != "active":
            raise ValueError("BANK_NOT_ACTIVE")
        covered_at: dict[str, list[datetime]] = defaultdict(list)
        submitted_count = 0
        for record in self.sessions.values():
            if (
                record.student_id == student_id
                and record.bank_id == self.bank["bank_id"]
                and record.status in {"submitted", "expired"}
            ):
                submitted_count += 1
                for question_id in record.question_ids:
                    covered_at[question_id].append(record.started_at)
        selected_questions, assembly_log = assemble_demo_paper(
            list(self.questions.values()),
            submitted_count + 1,
            covered_at,
        )
        selected = [question.id for question in selected_questions]
        session_id = str(uuid.uuid4())
        record = SessionRecord(
            id=session_id,
            student_id=student_id,
            bank_id=self.bank["bank_id"],
            bank_name=self.bank["name"],
            bank_version=self.bank["version"],
            duration_minutes=30,
            started_at=now,
            deadline=now + timedelta(minutes=30),
            question_ids=selected,
            composition_note={
                "bank_name": self.bank["name"],
                "session_kind": "practice",
                "question_type_counts": assembly_log["question_type_counts"],
                "topics": assembly_log["topics"],
                "assembly_log": assembly_log,
            },
        )
        self.sessions[session_id] = record
        for qid in selected:
            self.appearances[qid].append(now)
        return record

    def get_session(self, student_id: str, session_id: str, now: datetime) -> SessionRecord:
        record = self._find_session(student_id, session_id)
        if record.status == "in_progress" and now >= record.deadline:
            self.submit_session(student_id, session_id, f"auto:{session_id}", now)
        return record

    def _find_session(self, student_id: str, session_id: str) -> SessionRecord:
        record = self.sessions.get(session_id)
        if not record or record.student_id != student_id:
            raise KeyError("SESSION_NOT_FOUND")
        return record

    def save_answer(
        self, student_id: str, session_id: str, question_id: str, answer: str, now: datetime
    ) -> SessionRecord:
        record = self.get_session(student_id, session_id, now)
        if record.status != "in_progress":
            raise ValueError("SESSION_SUBMITTED")
        if question_id not in record.question_ids:
            raise KeyError("QUESTION_NOT_FOUND")
        record.answers[question_id] = answer
        return record

    def _normalize_answer(self, question: DemoQuestion, answer: str) -> str:
        value = " ".join(answer.strip().split()).casefold()
        if question.type == "cloze":
            for option in question.options or []:
                if value == option.casefold():
                    return option.casefold()
            return value
        if question.type == "gap_fill":
            for option in question.options or []:
                if value == option.casefold() or value == option.split(".", 1)[0].casefold():
                    return option.split(".", 1)[0]
            return value.upper()
        return value

    def submit_session(
        self, student_id: str, session_id: str, idempotency_key: str, now: datetime
    ) -> dict:
        record = self._find_session(student_id, session_id)

        key = (session_id, idempotency_key)
        if key in self.idempotency:
            return self.idempotency[key]
        if record.status == "submitted":
            if record.idempotency_key != idempotency_key:
                raise ValueError("IDEMPOTENCY_KEY_MISMATCH")
            return record.report or {}

        record.status = "expired" if now >= record.deadline else "submitted"
        record.submitted_at = now
        record.idempotency_key = idempotency_key
        results = []
        type_stats: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
        point_stats: dict[str, list[bool]] = defaultdict(list)
        changes = []

        for qid in record.question_ids:
            question = self.questions[qid]
            user_answer = record.answers.get(qid, "")
            normalized = self._normalize_answer(question, user_answer)
            correct = normalized == question.answer.casefold()
            self.history[student_id].append((qid, correct, now))
            type_stats[question.type]["total"] += 1
            type_stats[question.type]["correct"] += int(correct)
            for point in question.knowledge_points:
                point_stats[point].append(correct)
            tag_key = (student_id, qid, question.bank_id)
            tag = self.error_tags.get(tag_key)
            previous_status = tag.status if tag else "none"
            previous_streak = tag.streak if tag else 0
            if not correct:
                if tag is None:
                    tag = ErrorTag(qid, question.bank_id, question.knowledge_points, question.grammar_tags)
                    self.error_tags[tag_key] = tag
                else:
                    tag.status = "active"
                    tag.streak = 0
                    tag.successful_session_ids = []
            elif tag and tag.status == "active" and session_id not in tag.successful_session_ids:
                tag.successful_session_ids.append(session_id)
                tag.streak = min(2, len(tag.successful_session_ids))
                if tag.streak >= 2:
                    tag.status = "mastered"
            current_status = tag.status if tag else "none"
            current_streak = tag.streak if tag else 0
            if (previous_status, previous_streak) != (current_status, current_streak):
                changes.append(
                    {
                        "question_id": qid,
                        "from_status": previous_status,
                        "to_status": current_status,
                        "streak": current_streak,
                    }
                )
            results.append(
                {
                    "question_id": qid,
                    "type": question.type,
                    "passage_group_id": question.passage_group_id,
                    "stem": question.stem,
                    "options": question.options or [],
                    "blank_label": question.blank_label,
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

        total = len(results)
        correct_count = sum(item["correct"] for item in results)
        levels = []
        for point, outcomes in point_stats.items():
            mastery = sum(outcomes) / len(outcomes)
            levels.append(
                {
                    "knowledge_point": point,
                    "level": "mastered" if mastery >= 0.85 else ("weak" if mastery < 0.6 else "consolidating"),
                    "mastery": round(mastery, 4),
                    "attempts": len(outcomes),
                }
            )
        weak = sorted(levels, key=lambda item: item["mastery"])[:3]
        suggestions = [
            {
                "knowledge_point": item["knowledge_point"],
                "action": f"复习“{item['knowledge_point']}”并在下一套练习前完成一组针对性短练。",
            }
            for item in weak
        ]
        weak_points = [
            {"knowledge_point": item["knowledge_point"], "error_stage": "答案选择"}
            for item in weak
        ]
        analysis = generate_weakness_analysis(results, weak_points)
        local_now = now.astimezone(ZoneInfo("Asia/Shanghai"))
        raw_score = correct_count / total * 100
        type_scores = {
            qtype: {
                "correct": values["correct"],
                "total": values["total"],
                "accuracy": round(values["correct"] / values["total"], 4),
            }
            for qtype, values in type_stats.items()
        }
        report = {
            "session_id": session_id,
            "bank_id": record.bank_id,
            "bank_name": record.bank_name,
            "report_title": f"{local_now:%Y-%m-%d-%H-%M}-{total}题-{raw_score:.2f}分",
            "score": round(raw_score, 2),
            "max_score": 100,
            "question_count": total,
            "accuracy": round(correct_count / total, 4),
            "duration_seconds": max(0, int((now - record.started_at).total_seconds())),
            "type_scores": type_scores,
            "knowledge_point_levels": levels,
            "weak_points": weak_points,
            "weakness_analysis": analysis["text"],
            "weakness_analysis_source": analysis["source"],
            "suggestions": suggestions,
            "question_results": results,
            "error_tag_changes": changes,
        }
        record.report = report
        self.idempotency[key] = report
        return report

    def admin_audit(self, method: str, path: str, token: str, result: str, status_code: int) -> None:
        self.audit_log.append(
            {
                "method": method,
                "path": path,
                "token_fingerprint": hashlib.sha256(token.encode("utf-8")).hexdigest()[:8],
                "result": result,
                "status_code": status_code,
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )


store = InMemoryStore()

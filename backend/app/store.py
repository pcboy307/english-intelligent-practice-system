from __future__ import annotations

import hashlib
import random
import secrets
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .analysis import generate_weakness_analysis
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
        self.random = random.Random(seed)

    def active_bank(self) -> dict:
        return self.bank

    def _question_weight(self, question: DemoQuestion, student_id: str, now: datetime) -> float:
        tag = self.error_tags.get((student_id, question.id, question.bank_id))
        i_err = 1.0 if tag and tag.status == "active" and question.bank_id == self.bank["bank_id"] else 0.0
        s_kp = min(
            3,
            sum(
                other.status == "active"
                and (
                    set(other.knowledge_points) & set(question.knowledge_points)
                    or set(other.grammar_tags) & set(question.grammar_tags)
                )
                for (sid, _qid, bid), other in self.error_tags.items()
                if sid == student_id and bid == question.bank_id
            ),
        )
        history = self.history.get(student_id, [])
        same_type = [correct for qid, correct, _ in history if self.questions[qid].type == question.type]
        s_type = 1.0 if same_type and sum(same_type) / len(same_type) < 0.6 else 0.0
        mastery_values = [
            tag_mastery
            for _sid, kp, tag_mastery in self.mastery_values(student_id)
            if kp in question.knowledge_points
        ]
        mastery = sum(mastery_values) / len(mastery_values) if mastery_values else 0.7
        g_gap = max(0.0, 0.7 - mastery) * 2.0
        appearances = self.appearances.get(question.id, [])
        recent3 = len(appearances[-3:]) >= 3
        recent7 = any(now - seen <= timedelta(days=7) for seen in appearances)
        recent_penalty = 1.2 if recent3 else (0.6 if recent7 else 0.0)
        return max(
            0.1,
            1.0 + 2.0 * i_err + 1.0 * s_kp + 0.5 * s_type + 0.8 * g_gap - recent_penalty,
        )

    def mastery_values(self, student_id: str) -> list[tuple[str, str, float]]:
        by_point: dict[str, list[bool]] = defaultdict(list)
        for qid, correct, _ in self.history.get(student_id, []):
            for point in self.questions[qid].knowledge_points:
                by_point[point].append(correct)
        return [(student_id, point, sum(values) / len(values)) for point, values in by_point.items()]

    def _weighted_without_replacement(
        self, ids: list[str], weights: list[float], count: int
    ) -> list[str]:
        remaining = list(zip(ids, weights))
        selected: list[str] = []
        while remaining and len(selected) < count:
            total = sum(weight for _, weight in remaining)
            pick = self.random.random() * total
            upto = 0.0
            chosen_index = len(remaining) - 1
            for index, (_, weight) in enumerate(remaining):
                upto += weight
                if pick <= upto:
                    chosen_index = index
                    break
            selected.append(remaining.pop(chosen_index)[0])
        return selected

    def start_session(self, student_id: str, duration_minutes: int, now: datetime) -> SessionRecord:
        if duration_minutes != 30:
            raise ValueError("INVALID_DURATION")
        if self.bank["status"] != "active":
            raise ValueError("BANK_NOT_ACTIVE")
        counts = {"cloze": 15, "grammar_fill": 10, "gap_fill": 5}
        selected: list[str] = []
        for qtype, amount in counts.items():
            candidates = [
                question
                for question in self.questions.values()
                if question.bank_id == self.bank["bank_id"] and question.type == qtype
            ]
            ids = [question.id for question in candidates]
            weights = [self._question_weight(question, student_id, now) for question in candidates]
            selected.extend(self._weighted_without_replacement(ids, weights, amount))
        selected.sort(
            key=lambda question_id: (
                self.questions[question_id].passage_order,
                self.questions[question_id].question_order,
            )
        )
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
                "question_type_counts": counts,
                "error_pool_ratio": 0.0,
                "difficulty_distribution": {"easy": 0.4, "medium": 0.4, "hard": 0.2},
                "book_distribution": {"必修": 0.2, "选必一": 0.3, "选必二": 0.45, "cross_book": 0.05},
                "topics": ["environment", "community life", "reading"],
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

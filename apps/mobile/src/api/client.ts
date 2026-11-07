import type { components, paths } from "./generated";

const API_BASE = "http://localhost:8000/api/v1";

export type PracticeSession = components["schemas"]["SessionResponse"];
export type SessionItem = PracticeSession["items"][number];
export type PracticeReview = components["schemas"]["ReviewResponse"];
export type ReviewItem = PracticeReview["items"][number];
export type Report = components["schemas"]["Report"];
export type ReportSummary =
  paths["/reports"]["get"]["responses"]["200"]["content"]["application/json"][number];

export function getStudentId(): string {
  const key = "device_student_id";
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const id = crypto.randomUUID();
  window.localStorage.setItem(key, id);
  return id;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Student-Id": getStudentId(),
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail?.code || `HTTP ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function getActiveBank() {
  return request<{ bank_id: string; name: string; status: string }>("/bank/active");
}

export async function startPractice(duration_minutes: number) {
  return request<PracticeSession>("/practice/start", {
    method: "POST",
    body: JSON.stringify({ duration_minutes }),
  });
}

export async function getPractice(sessionId: string) {
  return request<PracticeSession>(`/practice/${sessionId}`);
}

export async function abandonPractice(sessionId: string) {
  return request<void>(`/practice/${sessionId}`, { method: "DELETE" });
}

export async function saveAnswer(sessionId: string, questionId: string, answer: string) {
  return request<void>(`/practice/${sessionId}/answer`, {
    method: "PUT",
    body: JSON.stringify({
      question_id: questionId,
      answer,
      client_revision: 0,
    }),
  });
}

export async function submitPractice(sessionId: string, idempotencyKey: string) {
  return request<Report>(`/practice/${sessionId}/submit`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
  });
}

export async function getPracticeReview(sessionId: string) {
  return request<PracticeReview>(`/practice/${sessionId}/review`);
}

export async function getReport(sessionId: string) {
  return request<Report>(`/reports/${sessionId}`);
}

export async function listReports() {
  return request<ReportSummary[]>("/reports");
}

export async function deleteReport(sessionId: string) {
  return request<void>(`/reports/${sessionId}`, { method: "DELETE" });
}

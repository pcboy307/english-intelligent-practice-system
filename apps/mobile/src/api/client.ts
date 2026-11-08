import type { components, paths } from "./generated";

const API_BASE = "http://localhost:8000/api/v1";

export type PracticeSession = components["schemas"]["SessionResponse"];
export type SessionItem = PracticeSession["items"][number];
export type PracticeReview = components["schemas"]["ReviewResponse"];
export type ReviewItem = PracticeReview["items"][number];
export type Report = components["schemas"]["Report"];
export type ReportSummary =
  paths["/reports"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type MistakeList =
  components["schemas"]["MistakeListResponse"];
export type MistakePassageGroup =
  components["schemas"]["MistakePassageGroup"];
export type MistakeBankGroup =
  components["schemas"]["MistakeBankGroup"];
export type CoverageStats = components["schemas"]["CoverageStats"];
export type ClearPreview = components["schemas"]["ClearPreview"];
export type MaintenanceResult =
  components["schemas"]["MaintenanceResult"];
export type MistakeEntry = components["schemas"]["MistakeEntry"];
export type MistakeDetailQuestion = {
  question_id: string;
  type: string;
  passage_group_id: string;
  stem: string;
  options: string[];
  answer: string;
  label: string;
  locked: boolean;
};
export type MistakeDetail = {
  bank_id: string;
  bank_name: string;
  passage_id: string;
  question_type: "cloze" | "grammar" | "reading" | "seven";
  passage: string;
  questions: MistakeDetailQuestion[];
  target_items: MistakeEntry[];
  target_question_ids: string[];
};

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

export async function getMistakes() {
  return request<MistakeList>("/mistakes?status=open");
}

export async function getMistakePassage(passageId: string) {
  return request<MistakeDetail>(
    `/mistakes/${encodeURIComponent(passageId)}`,
  );
}

export async function startMistakeReview(passageId: string) {
  return request<PracticeSession>(
    `/mistakes/review/${encodeURIComponent(passageId)}`,
    { method: "POST" },
  );
}

export async function getCoverageStats() {
  return request<CoverageStats>("/stats/coverage?bank_id=active");
}

export async function previewClearMistakes(adminToken: string) {
  return request<ClearPreview>("/maintenance/clear-mistakes/preview", {
    headers: { "X-Admin-Token": adminToken },
  });
}

export async function clearMistakes(adminToken: string) {
  return request<MaintenanceResult>("/maintenance/clear-mistakes", {
    method: "POST",
    headers: { "X-Admin-Token": adminToken },
  });
}

export async function previewResetCoverage(adminToken: string) {
  return request<ClearPreview>("/maintenance/reset-coverage/preview", {
    headers: { "X-Admin-Token": adminToken },
  });
}

export async function resetCoverage(adminToken: string) {
  return request<MaintenanceResult>("/maintenance/reset-coverage", {
    method: "POST",
    headers: { "X-Admin-Token": adminToken },
  });
}

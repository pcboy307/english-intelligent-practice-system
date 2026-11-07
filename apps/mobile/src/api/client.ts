const API_BASE = "http://localhost:8000/api/v1";

export type SessionItem = {
  question_id: string;
  type: "cloze" | "grammar_fill" | "reading" | "gap_fill";
  passage_group_id: string;
  passage: string;
  stem: string;
  options: string[] | null;
  saved_answer: string | string[] | null;
};

export type PracticeSession = {
  session_id: string;
  bank_id: string;
  bank_name: string;
  bank_version: string;
  duration_minutes: number;
  status: "in_progress" | "submitted" | "expired";
  items: SessionItem[];
  composition_note: {
    bank_name: string;
    question_type_counts: Record<string, number>;
    error_pool_ratio: number;
    difficulty_distribution: Record<string, number>;
    book_distribution: Record<string, number>;
    topics: string[];
  };
  deadline: string;
  server_time: string;
  remaining_seconds: number;
  progress: { answered: number; total: number };
};

export type Report = {
  session_id: string;
  bank_id: string;
  bank_name: string;
  score: number;
  max_score: number;
  accuracy: number;
  duration_seconds: number;
  type_scores: Record<string, { correct: number; total: number; accuracy: number }>;
  weak_points: Array<{ knowledge_point: string; error_stage: string }>;
  suggestions: Array<{ knowledge_point: string; action: string }>;
  question_results: Array<{
    question_id: string;
    correct: boolean;
    user_answer: string;
    correct_answer: string;
    explanation: string;
    knowledge_points: string[];
    grammar_tags: string[];
    book_source: string;
    difficulty: number;
  }>;
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

export async function getReport(sessionId: string) {
  return request<Report>(`/reports/${sessionId}`);
}

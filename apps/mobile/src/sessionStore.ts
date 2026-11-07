import type { PracticeSession, Report } from "./api/client";

let currentSession: PracticeSession | null = null;
let currentReport: Report | null = null;

export function setSession(session: PracticeSession | null) {
  currentSession = session;
}

export function getSession() {
  return currentSession;
}

export function setReport(report: Report) {
  currentReport = report;
}

export function getStoredReport() {
  return currentReport;
}

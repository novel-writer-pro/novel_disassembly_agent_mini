import type {
  ReviewCluster,
  ReviewClusterSummary,
  RiskSignal,
  RiskAuditResult,
  ChapterBundle,
  ChapterSource,
  SearchHit,
} from "@/types/risk";

const requestJson = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, init);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.detail || `backend returned ${response.status}`);
  }
  return payload as T;
};

export const fetchReviewClusters = (apiBase: string, runId: string, branchId: string, severity?: string) => {
  const params = new URLSearchParams({ run_id: runId, branch_id: branchId });
  if (severity) params.set("severity", severity);
  return requestJson<{ items: ReviewCluster[]; total: number; filtered: number }>(`${apiBase}/api/review-clusters?${params}`);
};

export const fetchReviewClusterSummary = (apiBase: string, runId: string, branchId: string) =>
  requestJson<ReviewClusterSummary>(`${apiBase}/api/review-cluster-summary?${params(runId, branchId)}`);

export const fetchRiskAudit = (apiBase: string, branchId: string, chapterIndex: number) =>
  requestJson<RiskAuditResult>(`${apiBase}/api/risk-audit?branch_id=${branchId}&chapter_index=${chapterIndex}`);

export const fetchRiskSignals = (apiBase: string, branchId: string, chapterIndex: number) =>
  requestJson<{ items: RiskSignal[] }>(`${apiBase}/api/risk-signals?branch_id=${branchId}&chapter_index=${chapterIndex}`);

export const fetchChapterBundle = (apiBase: string, branchId: string, chapterIndex: number) =>
  requestJson<ChapterBundle>(`${apiBase}/api/chapter-bundle?branch_id=${branchId}&chapter_index=${chapterIndex}`);

export const fetchChapterSource = (apiBase: string, branchId: string, chapterIndex: number) =>
  requestJson<ChapterSource>(`${apiBase}/api/chapter-source?branch_id=${branchId}&chapter_index=${chapterIndex}`);

export const fetchSearchBranch = (apiBase: string, branchId: string, query: string, limit?: number) =>
  requestJson<{ hits: SearchHit[] }>(`${apiBase}/api/search-branch?branch_id=${branchId}&query=${encodeURIComponent(query)}&limit=${limit || 10}`);

function params(runId: string, branchId: string) {
  return new URLSearchParams({ run_id: runId, branch_id: branchId }).toString();
}

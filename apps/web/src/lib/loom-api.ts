import type {
  LoomStatus,
  LoomSignals,
  LoomAssembleResult,
  ReferenceEvalResult,
  WriterImitateResult,
  QualityHealth,
  QualityTrend,
  PairsStats,
} from "@/types/loom";

const requestJson = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, init);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.detail || `backend returned ${response.status}`);
  }
  return payload as T;
};

export const fetchLoomStatus = (apiBase: string, branchId: string) =>
  requestJson<LoomStatus>(`${apiBase}/api/loom/status?branch_id=${branchId}`);

export const fetchLoomSignals = (apiBase: string, branchId: string, chapterIndex: number) =>
  requestJson<LoomSignals>(`${apiBase}/api/loom/signals?branch_id=${branchId}&chapter_index=${chapterIndex}`);

export const fetchLoomAssemble = (apiBase: string, branchId: string, targetChapter: number) =>
  requestJson<LoomAssembleResult>(`${apiBase}/api/loom/assemble?branch_id=${branchId}&target_chapter=${targetChapter}`);

export const fetchReferenceEval = (apiBase: string, branchId: string, chapterIndex: number, draftDir: string) =>
  requestJson<ReferenceEvalResult>(`${apiBase}/api/loom/reference-eval?branch_id=${branchId}&chapter_index=${chapterIndex}&draft_dir=${encodeURIComponent(draftDir)}`);

export const postWriterImitate = (apiBase: string, body: {
  branch_id: string;
  chapter_index: number;
  target_goal: string;
  use_llm?: boolean;
  loom_memory_mode?: string;
  loom_pairwise_enabled?: boolean;
  loom_style_enabled?: boolean;
  loom_character_enabled?: boolean;
}) =>
  requestJson<WriterImitateResult>(`${apiBase}/api/writer/imitate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export const fetchWriterSignals = (apiBase: string, branchId: string, chapterIndex: number) =>
  requestJson<LoomSignals>(`${apiBase}/api/writer/imitate/signals?branch_id=${branchId}&chapter_index=${chapterIndex}`);

export const fetchQualityHealth = (apiBase: string, branchId: string) =>
  requestJson<QualityHealth>(`${apiBase}/api/quality/health?branch_id=${branchId}`);

export const fetchQualityTrend = (apiBase: string, branchId: string) =>
  requestJson<QualityTrend>(`${apiBase}/api/quality/trend?branch_id=${branchId}`);

export const fetchPairsStats = (apiBase: string, pairsFile?: string) => {
  const query = pairsFile ? `?pairs_file=${encodeURIComponent(pairsFile)}` : "";
  return requestJson<PairsStats>(`${apiBase}/api/quality/pairs-stats${query}`);
};

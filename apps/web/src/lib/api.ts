import type {
  BranchExports,
  BranchSnapshot,
  ChapterBundle,
  ChapterQaContext,
  ChapterSource,
  RecoveryResult,
  RunSnapshot,
  RetrievalHit,
  BranchAskResult,
} from "@/types/workbench";

const requestJson = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, init);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `backend returned ${response.status}`);
  }
  return payload as T;
};

export const fetchRunSnapshot = (apiBase: string, runId: string, branchId: string, databaseUrl?: string) => {
  const query = new URLSearchParams({ run_id: runId, branch_id: branchId });
  if (databaseUrl) query.set("database_url", databaseUrl);
  return requestJson<RunSnapshot>(`${apiBase}/api/run-snapshot?${query.toString()}`);
};

export const fetchBranchSnapshot = (
  apiBase: string,
  runId: string,
  branchId: string,
  databaseUrl?: string,
) => {
  const query = new URLSearchParams({ run_id: runId, branch_id: branchId });
  if (databaseUrl) query.set("database_url", databaseUrl);
  return requestJson<BranchSnapshot>(`${apiBase}/api/branch-snapshot?${query.toString()}`);
};

export const fetchChapterBundle = (
  apiBase: string,
  branchId: string,
  chapterIndex: number,
  databaseUrl?: string,
) => {
  const query = new URLSearchParams({
    branch_id: branchId,
    chapter_index: String(chapterIndex),
  });
  if (databaseUrl) query.set("database_url", databaseUrl);
  return requestJson<ChapterBundle>(`${apiBase}/api/chapter-bundle?${query.toString()}`);
};

export const fetchChapterQaContext = (
  apiBase: string,
  branchId: string,
  chapterIndex: number,
  databaseUrl?: string,
) => {
  const query = new URLSearchParams({
    branch_id: branchId,
    chapter_index: String(chapterIndex),
  });
  if (databaseUrl) query.set("database_url", databaseUrl);
  return requestJson<ChapterQaContext>(`${apiBase}/api/chapter-qa-context?${query.toString()}`);
};

export const fetchChapterSource = (
  apiBase: string,
  branchId: string,
  chapterIndex: number,
  databaseUrl?: string,
) => {
  const query = new URLSearchParams({
    branch_id: branchId,
    chapter_index: String(chapterIndex),
  });
  if (databaseUrl) query.set("database_url", databaseUrl);
  return requestJson<ChapterSource>(`${apiBase}/api/chapter-source?${query.toString()}`);
};

export const postImport = async (
  apiBase: string,
  payload: FormData,
) => requestJson<any>(`${apiBase}/api/import`, { method: "POST", body: payload });

export const postStart = async (
  apiBase: string,
  payload: FormData,
) => requestJson<{ processed_chapters: number; next_chapter: number | null; pipeline_state: string }>(
  `${apiBase}/api/start`,
  { method: "POST", body: payload },
);

export const postRecovery = async (
  apiBase: string,
  payload: FormData,
) => requestJson<RecoveryResult>(`${apiBase}/api/recovery`, { method: "POST", body: payload });

export const fetchBranchExports = (
  apiBase: string,
  runId: string,
  branchId: string,
  databaseUrl?: string,
) => {
  const query = new URLSearchParams({ run_id: runId, branch_id: branchId });
  if (databaseUrl) query.set("database_url", databaseUrl);
  return requestJson<BranchExports>(`${apiBase}/api/branch-exports?${query.toString()}`);
};


export const searchBranch = (
  apiBase: string,
  branchId: string,
  queryText: string,
  databaseUrl?: string,
  limit = 8,
) => {
  const query = new URLSearchParams({ branch_id: branchId, q: queryText, limit: String(limit) });
  if (databaseUrl) query.set("database_url", databaseUrl);
  return requestJson<{ hits: RetrievalHit[] }>(`${apiBase}/api/search-branch?${query.toString()}`);
};

export const askBranch = (
  apiBase: string,
  branchId: string,
  question: string,
  databaseUrl?: string,
  limit = 6,
) => requestJson<BranchAskResult>(`${apiBase}/api/ask-branch`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ branch_id: branchId, question, database_url: databaseUrl, limit }),
});

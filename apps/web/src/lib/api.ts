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
  BranchAskStreamEvent,
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

export const askBranchStream = async (
  apiBase: string,
  branchId: string,
  question: string,
  onEvent: (event: BranchAskStreamEvent) => void,
  databaseUrl?: string,
  limit = 6,
) => {
  const response = await fetch(`${apiBase}/api/ask-branch-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ branch_id: branchId, question, database_url: databaseUrl, limit }),
  });

  if (!response.ok) {
    let payload: { error?: string } | null = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(payload?.error || `backend returned ${response.status}`);
  }

  if (!response.body) {
    throw new Error("当前浏览器未返回可读取的数据流");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() || "";

    for (const chunk of chunks) {
      const dataLine = chunk
        .split("\n")
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;
      const raw = dataLine.slice(5).trim();
      if (!raw) continue;
      const event = JSON.parse(raw) as BranchAskStreamEvent;
      onEvent(event);
    }
  }

  if (buffer.trim()) {
    const dataLine = buffer
      .split("\n")
      .find((line) => line.startsWith("data:"));
    if (dataLine) {
      const raw = dataLine.slice(5).trim();
      if (raw) onEvent(JSON.parse(raw) as BranchAskStreamEvent);
    }
  }
};

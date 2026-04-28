import { useEffect, useState } from "react";
import type { WorkbenchState } from "@/types/workbench";

const STORAGE_KEY = "novel-analyzer-workbench-state-v2";

const defaultState: WorkbenchState = {
  title: "",
  apiBase: "http://127.0.0.1:8011",
  databaseUrl: "postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer",
  runId: "7e22a5d8-eb57-4306-858b-90386f1c2b22",
  branchId: "72da24e9-e65c-45a9-836d-957c4ae783ec",
  profile: "auto-lite",
  maxChapters: "",
  lastChapterIndex: null,
  lastChapterIndexByBranch: {},
};

export function useWorkbenchState() {
  const [state, setState] = useState<WorkbenchState>(defaultState);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        setState({ ...defaultState, ...JSON.parse(raw) });
      } catch {
        // ignore bad cache
      }
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state, hydrated]);

  return {
    state,
    setState,
    hydrated,
    patchState: (patch: Partial<WorkbenchState>) =>
      setState((current) => ({ ...current, ...patch })),
  };
}

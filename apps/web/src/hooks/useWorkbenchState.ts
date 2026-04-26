import { useEffect, useState } from "react";
import type { WorkbenchState } from "@/types/workbench";

const STORAGE_KEY = "novel-analyzer-workbench-state";

const defaultState: WorkbenchState = {
  title: "",
  apiBase: "http://127.0.0.1:8011",
  databaseUrl: "postgresql+psycopg://d2:d2pass@127.0.0.1:5432/novel_analyzer",
  runId: "dc4b547a-50d0-4d78-96de-191f12d981af",
  branchId: "f9d93eca-d82d-4276-bd63-ec90fec16e9d",
  profile: "auto-lite",
  maxChapters: "",
  lastChapterIndex: null,
};

export function useWorkbenchState() {
  const [state, setState] = useState<WorkbenchState>(defaultState);

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    try {
      setState({ ...defaultState, ...JSON.parse(raw) });
    } catch {
      // ignore bad cache
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  return {
    state,
    setState,
    patchState: (patch: Partial<WorkbenchState>) =>
      setState((current) => ({ ...current, ...patch })),
  };
}

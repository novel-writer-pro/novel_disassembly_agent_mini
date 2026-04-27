import { useEffect, useMemo, useRef, useState } from "react";
import { message, Space } from "antd";
import WorkbenchLayout from "@/components/WorkbenchLayout";
import ControlPage from "@/components/ControlPage";
import ReaderPage from "@/components/ReaderPage";
import BranchQaPanel from "@/components/BranchQaPanel";
import OpsPage from "@/components/OpsPage";
import { useWorkbenchState } from "@/hooks/useWorkbenchState";
import {
  fetchBranchExports,
  fetchBranchSnapshot,
  fetchChapterBundle,
  fetchChapterQaContext,
  fetchChapterSource,
  fetchRunSnapshot,
  postImport,
  postRecovery,
  postStart,
} from "@/lib/api";
import type {
  BranchExports,
  BranchSnapshot,
  ChapterBundle,
  ChapterQaContext,
  ChapterSource,
  RunSnapshot,
} from "@/types/workbench";
import ChapterSidebar from "@/components/ChapterSidebar";
import { useRouter } from "next/router";

const routeByWorkspace: Record<string, string> = {
  control: "/control",
  reader: "/reader",
  ops: "/ops",
};

interface Props {
  initialWorkspace: "control" | "reader" | "ops";
}

export default function WorkbenchApp({ initialWorkspace }: Props) {
  const router = useRouter();
  const { state, patchState } = useWorkbenchState();
  const [workspace, setWorkspace] = useState(initialWorkspace);
  const [importText, setImportText] = useState("");
  const [runSnapshot, setRunSnapshot] = useState<RunSnapshot | null>(null);
  const [branchSnapshot, setBranchSnapshot] = useState<BranchSnapshot | null>(null);
  const [bundle, setBundle] = useState<ChapterBundle | null>(null);
  const [qa, setQa] = useState<ChapterQaContext | null>(null);
  const [source, setSource] = useState<ChapterSource | null>(null);
  const [exportsData, setExportsData] = useState<BranchExports | null>(null);
  const [recoveryResultText, setRecoveryResultText] = useState("");
  const [activeChapterIndex, setActiveChapterIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState({
    importing: false,
    refreshing: false,
    starting: false,
    retrying: false,
    clearing: false,
    repairing: false,
    exporting: false,
    chapter: false,
  });

  const didBootstrapRef = useRef(false);
  const chapterRequestSeqRef = useRef(0);

  const navigateWorkspace = (nextWorkspace: string, options?: { chapterIndex?: number | null }) => {
    setWorkspace(nextWorkspace as "control" | "reader" | "ops");
    const nextRoute = routeByWorkspace[nextWorkspace] || "/";
    const nextQuery: Record<string, string> = {};
    if (options?.chapterIndex) nextQuery.chapter = String(options.chapterIndex);
    if (router.pathname !== nextRoute || (options?.chapterIndex && router.query.chapter !== String(options.chapterIndex))) {
      void router.push({ pathname: nextRoute, query: nextQuery });
    }
  };

  const refreshBranch = async () => {
    setLoading((current) => ({ ...current, refreshing: true }));
    try {
      const [runData, branchData] = await Promise.all([
        fetchRunSnapshot(state.apiBase, state.runId, state.branchId, state.databaseUrl),
        fetchBranchSnapshot(state.apiBase, state.runId, state.branchId, state.databaseUrl),
      ]);
      setRunSnapshot(runData);
      setBranchSnapshot(branchData);
      setImportText("已读取当前真实分支数据。");
    } finally {
      setLoading((current) => ({ ...current, refreshing: false }));
    }
  };

  const loadChapter = async (chapterIndex: number, options?: { navigate?: boolean }) => {
    const requestId = chapterRequestSeqRef.current + 1;
    chapterRequestSeqRef.current = requestId;
    const row = branchSnapshot?.chapter_rows?.find((item) => item.chapter_index === chapterIndex) || null;
    setActiveChapterIndex(chapterIndex);
    patchState({ lastChapterIndex: chapterIndex });

    if (options?.navigate) {
      navigateWorkspace("reader", { chapterIndex });
    }

    if (row && !row.has_artifact) {
      if (chapterRequestSeqRef.current === requestId) {
        setBundle(null);
        setQa(null);
        setSource(null);
        message.info(row.job_status === "running" ? `第 ${chapterIndex} 章正在整理中，请稍后再看。` : `第 ${chapterIndex} 章还没有拆书结果，请先继续整理。`);
      }
      return;
    }

    setLoading((current) => ({ ...current, chapter: true }));
    try {
      const [bundleData, qaData, sourceData] = await Promise.all([
        fetchChapterBundle(state.apiBase, state.branchId, chapterIndex, state.databaseUrl),
        fetchChapterQaContext(state.apiBase, state.branchId, chapterIndex, state.databaseUrl),
        fetchChapterSource(state.apiBase, state.branchId, chapterIndex, state.databaseUrl),
      ]);
      if (chapterRequestSeqRef.current !== requestId) return;
      setBundle(bundleData);
      setQa(qaData);
      setSource(sourceData);
    } catch (error) {
      if (chapterRequestSeqRef.current !== requestId) return;
      setBundle(null);
      setQa(null);
      setSource(null);
      message.error(error instanceof Error ? error.message : "章节读取失败");
    } finally {
      if (chapterRequestSeqRef.current === requestId) {
        setLoading((current) => ({ ...current, chapter: false }));
      }
    }
  };

  const openChapter = async (chapterIndex: number) => {
    await loadChapter(chapterIndex, { navigate: true });
  };

  const handleImport = async () => {
    const input = document.getElementById("novel-file") as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) {
      message.error("请先选择小说文件");
      return;
    }
    setLoading((current) => ({ ...current, importing: true }));
    try {
      const formData = new FormData();
      formData.set("file", file);
      formData.set("title", state.title || "");
      formData.set("pipeline_profile", state.profile);
      if (state.databaseUrl) formData.set("database_url", state.databaseUrl);
      if (state.maxChapters) formData.set("max_chapters", state.maxChapters);
      const payload = await postImport(state.apiBase, formData);
      setImportText("作品已导入，当前结果已同步到工作台。");
      patchState({
        runId: payload.import_result.run_id || state.runId,
        branchId: payload.import_result.branch_id || state.branchId,
      });
      setRunSnapshot(payload.run_snapshot);
      setBranchSnapshot(payload.branch_snapshot);
      message.success("作品已导入，可以开始阅读章节内容");
      navigateWorkspace("reader");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "导入失败");
    } finally {
      setLoading((current) => ({ ...current, importing: false }));
    }
  };

  const handleSimulate = async () => {
    const branchData = await fetchBranchSnapshot(
      state.apiBase,
      state.runId,
      state.branchId,
      state.databaseUrl,
    ).catch(() => null);
    if (branchData) {
      setBranchSnapshot(branchData);
      setImportText("已载入当前示例数据。");
      message.success("已载入当前示例数据");
      return;
    }
    setImportText("当前没有可载入的示例数据，请先读取真实分支。");
    message.warning("当前没有可载入的示例数据");
  };

  const handleStart = async () => {
    setLoading((current) => ({ ...current, starting: true }));
    try {
      const formData = new FormData();
      formData.set("run_id", state.runId);
      formData.set("branch_id", state.branchId);
      formData.set("pipeline_profile", state.profile);
      if (state.databaseUrl) formData.set("database_url", state.databaseUrl);
      if (state.maxChapters) formData.set("max_chapters", state.maxChapters);
      const payload = await postStart(state.apiBase, formData);
      setImportText(`已继续整理，当前处理结果：${payload.pipeline_state}`);
      message.success("已继续整理后续章节");
      await refreshBranch();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "继续整理失败");
    } finally {
      setLoading((current) => ({ ...current, starting: false }));
    }
  };

  const handleRecovery = async (action: string) => {
    const key =
      action === "retry-failed"
        ? "retrying"
        : action === "clear-running"
          ? "clearing"
          : "repairing";
    setLoading((current) => ({ ...current, [key]: true }));
    try {
      const formData = new FormData();
      formData.set("run_id", state.runId);
      formData.set("branch_id", state.branchId);
      formData.set("action", action);
      if (state.databaseUrl) formData.set("database_url", state.databaseUrl);
      const payload = await postRecovery(state.apiBase, formData);
      setRecoveryResultText(JSON.stringify(payload, null, 2));
      message.success(payload.message || "处理完成");
      await refreshBranch();
      navigateWorkspace("ops");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "处理失败");
    } finally {
      setLoading((current) => ({ ...current, [key]: false }));
    }
  };

  useEffect(() => {
    setWorkspace(initialWorkspace);
  }, [initialWorkspace]);

  useEffect(() => {
    if (didBootstrapRef.current) return;
    if (!state.runId || !state.branchId) return;
    didBootstrapRef.current = true;
    void refreshBranch();
  }, [state.apiBase, state.branchId, state.databaseUrl, state.runId]);

  useEffect(() => {
    if (workspace !== "reader") return;
    if (loading.chapter) return;
    const chapterFromQuery = Number(router.query.chapter || "");
    const chapterFromState = state.lastChapterIndex || null;
    const candidate = Number.isFinite(chapterFromQuery) && chapterFromQuery > 0 ? chapterFromQuery : chapterFromState;
    if (candidate && candidate !== activeChapterIndex) {
      void loadChapter(candidate);
      return;
    }
    if (!candidate && branchSnapshot?.chapter_rows?.length) {
      const preferred =
        branchSnapshot.chapter_rows.find((row) => row.has_artifact) ||
        branchSnapshot.chapter_rows.find((row) => row.job_status !== "failed") ||
        branchSnapshot.chapter_rows[0];
      if (preferred && preferred.chapter_index !== activeChapterIndex) {
        void loadChapter(preferred.chapter_index);
      }
    }
  }, [activeChapterIndex, branchSnapshot, loading.chapter, router.query.chapter, state.lastChapterIndex, workspace]);

  const chapterMenu = useMemo(
    () => (
      <ChapterSidebar
        rows={branchSnapshot?.chapter_rows || []}
        activeChapterIndex={activeChapterIndex}
        onSelect={openChapter}
      />
    ),
    [activeChapterIndex, branchSnapshot],
  );

  return (
    <WorkbenchLayout activeKey={workspace} chapterMenu={chapterMenu} onNavigate={navigateWorkspace}>
      {workspace === "control" ? (
        <ControlPage
          state={state}
          importText={importText}
          runSnapshot={runSnapshot}
          branchSnapshot={branchSnapshot}
          loading={loading}
          onChange={patchState}
          onImport={handleImport}
          onSimulate={handleSimulate}
          onRefresh={refreshBranch}
          onStart={handleStart}
          onOpenRecovery={() => navigateWorkspace("ops")}
        />
      ) : null}

      {workspace === "reader" ? (
        <ReaderPage
          bundle={bundle}
          qa={qa}
          source={source}
          loading={loading.chapter}
          onJumpChapter={(chapterIndex) => void loadChapter(chapterIndex)}
        />
      ) : null}

      {workspace === "ops" ? (
        <OpsPage
          recoveryResultText={recoveryResultText}
          exportsData={exportsData}
          loading={loading}
          onRetryFailed={() => handleRecovery("retry-failed")}
          onClearRunning={() => handleRecovery("clear-running")}
          onRepair={() => handleRecovery("repair")}
          onLoadExports={async () => {
            setLoading((current) => ({ ...current, exporting: true }));
            try {
              const payload = await fetchBranchExports(
                state.apiBase,
                state.runId,
                state.branchId,
                state.databaseUrl,
              );
              setExportsData(payload);
              message.success("导出文件已准备好");
            } catch (error) {
              message.error(error instanceof Error ? error.message : "导出生成失败");
            } finally {
              setLoading((current) => ({ ...current, exporting: false }));
            }
          }}
          apiBase={state.apiBase}
        />
      ) : null}
    </WorkbenchLayout>
  );
}

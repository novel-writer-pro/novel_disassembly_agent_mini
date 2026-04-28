import { useEffect, useMemo, useRef, useState } from "react";
import { message, Space } from "antd";
import WorkbenchLayout from "@/components/WorkbenchLayout";
import LibraryPage from "@/components/LibraryPage";
import TaskCenterPanel from "@/components/TaskCenterPanel";
import SystemHealthPanel from "@/components/SystemHealthPanel";
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
  fetchLibrary,
  fetchProviderHealth,
  fetchRuntimeHealth,
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
  LibraryItem,
  ProviderHealth,
  RuntimeHealth,
} from "@/types/workbench";
import ChapterSidebar from "@/components/ChapterSidebar";
import { useRouter } from "next/router";

const routeByWorkspace: Record<string, string> = {
  library: "/library",
  control: "/control",
  reader: "/reader",
  qa: "/qa",
  ops: "/ops",
};

interface Props {
  initialWorkspace: "library" | "control" | "reader" | "qa" | "ops";
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
  const [libraryItems, setLibraryItems] = useState<LibraryItem[]>([]);
  const [runtimeHealth, setRuntimeHealth] = useState<RuntimeHealth | null>(null);
  const [providerHealth, setProviderHealth] = useState<ProviderHealth | null>(null);
  const [recoveryResultText, setRecoveryResultText] = useState("");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true);
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
  const workspaceRequestSeqRef = useRef(0);

  const loadWorkspaceData = async (runId: string, branchId: string, databaseUrl: string, apiBase: string) => {
    const requestId = workspaceRequestSeqRef.current + 1;
    workspaceRequestSeqRef.current = requestId;
    const [runData, branchData, libraryData] = await Promise.all([
      fetchRunSnapshot(apiBase, runId, branchId, databaseUrl),
      fetchBranchSnapshot(apiBase, runId, branchId, databaseUrl),
      fetchLibrary(apiBase, databaseUrl),
    ]);
    const [runtimeHealthData, providerHealthData] = await Promise.all([
      fetchRuntimeHealth(apiBase).catch(() => null),
      fetchProviderHealth(apiBase).catch(() => null),
    ]);
    if (workspaceRequestSeqRef.current !== requestId) return;
    setRunSnapshot(runData);
    setBranchSnapshot(branchData);
    setLibraryItems(libraryData.items || []);
    setRuntimeHealth(runtimeHealthData);
    setProviderHealth(providerHealthData);
    setLastRefreshedAt(new Date().toLocaleString("zh-CN", { hour12: false }));
  };

  const navigateWorkspace = (nextWorkspace: string, options?: { chapterIndex?: number | null }) => {
    setWorkspace(nextWorkspace as "library" | "control" | "reader" | "qa" | "ops");
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
      await loadWorkspaceData(state.runId, state.branchId, state.databaseUrl, state.apiBase);
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
    patchState({
      lastChapterIndex: chapterIndex,
      lastChapterIndexByBranch: {
        ...(state.lastChapterIndexByBranch || {}),
        [state.branchId]: chapterIndex,
      },
    });

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
        title: state.title || payload.import_result.title || file.name.replace(/\.[^.]+$/, ""),
        runId: payload.import_result.run_id || state.runId,
        branchId: payload.import_result.branch_id || state.branchId,
      });
      setRunSnapshot(payload.run_snapshot);
      setBranchSnapshot(payload.branch_snapshot);
      const libraryData = await fetchLibrary(state.apiBase, state.databaseUrl);
      setLibraryItems(libraryData.items || []);
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
    const chapterFromBranchMemory = state.branchId ? (state.lastChapterIndexByBranch || {})[state.branchId] : null;
    const chapterFromState = chapterFromBranchMemory ?? state.lastChapterIndex ?? null;
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

  const hasActiveTasks = useMemo(
    () => libraryItems.some((item) => (item.running_jobs || 0) > 0 || item.pipeline_state === "needs_recovery" || item.pipeline_state === "auto_running"),
    [libraryItems],
  );

  useEffect(() => {
    if (!autoRefreshEnabled) return;
    if (!state.runId || !state.branchId) return;
    const intervalMs = hasActiveTasks ? 15000 : 45000;
    const timer = window.setInterval(() => {
      if (loading.importing || loading.starting || loading.retrying || loading.clearing || loading.repairing || loading.exporting) return;
      void loadWorkspaceData(state.runId, state.branchId, state.databaseUrl, state.apiBase);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [
    autoRefreshEnabled,
    hasActiveTasks,
    loading.clearing,
    loading.exporting,
    loading.importing,
    loading.repairing,
    loading.retrying,
    loading.starting,
    state.apiBase,
    state.branchId,
    state.databaseUrl,
    state.runId,
  ]);

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

  const currentLibraryItem = useMemo(
    () => libraryItems.find((item) => item.branch_id === state.branchId) || null,
    [libraryItems, state.branchId],
  );

  const activateLibraryItem = async (item: LibraryItem, nextWorkspace?: "library" | "control" | "reader" | "qa" | "ops") => {
    chapterRequestSeqRef.current += 1;
    const rememberedChapter = (state.lastChapterIndexByBranch || {})[item.branch_id] ?? null;
    patchState({
      title: item.title,
      runId: item.run_id,
      branchId: item.branch_id,
      lastChapterIndex: rememberedChapter,
    });
    setRunSnapshot(null);
    setBranchSnapshot(null);
    setBundle(null);
    setQa(null);
    setSource(null);
    setActiveChapterIndex(rememberedChapter);
    setImportText(`已切换到《${item.title}》`);
    await loadWorkspaceData(item.run_id, item.branch_id, state.databaseUrl, state.apiBase);
    if (nextWorkspace) navigateWorkspace(nextWorkspace);
  };

  const taskCenter = (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <TaskCenterPanel
        items={libraryItems}
        activeBranchId={state.branchId}
        onRefresh={refreshBranch}
        autoRefreshEnabled={autoRefreshEnabled}
        onToggleAutoRefresh={() => setAutoRefreshEnabled((current) => !current)}
        lastRefreshedAt={lastRefreshedAt}
        providerHealth={providerHealth}
        onActivate={(item) => {
          void activateLibraryItem(item);
        }}
        onOpenRecovery={(item) => {
          void activateLibraryItem(item, "ops");
        }}
      />
      <SystemHealthPanel runtimeHealth={runtimeHealth} providerHealth={providerHealth} lastRefreshedAt={lastRefreshedAt} />
    </Space>
  );

  return (
    <WorkbenchLayout
      activeKey={workspace}
      chapterMenu={chapterMenu}
      onNavigate={navigateWorkspace}
      currentNovelTitle={currentLibraryItem?.title || state.title}
      currentBranchId={state.branchId}
    >
      {workspace === "control" ? (
        <ControlPage
          state={state}
          importText={importText}
          runSnapshot={runSnapshot}
          branchSnapshot={branchSnapshot}
          loading={loading}
          libraryItems={libraryItems}
          onChange={patchState}
          onImport={handleImport}
          onSimulate={handleSimulate}
          onRefresh={refreshBranch}
          onStart={handleStart}
          onOpenRecovery={() => navigateWorkspace("ops")}
          onSelectLibraryItem={(item) => {
            void activateLibraryItem(item);
          }}
        />
      ) : null}

      {workspace === "library" ? (
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <LibraryPage
            items={libraryItems}
            activeBranchId={state.branchId}
            onRefresh={refreshBranch}
            onActivate={(item) => {
              void activateLibraryItem(item);
            }}
            onOpenReader={(item) => {
              void activateLibraryItem(item, "reader");
            }}
            onOpenQa={(item) => {
              void activateLibraryItem(item, "qa");
            }}
          />
          {taskCenter}
        </Space>
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

      {workspace === "qa" ? (
        <BranchQaPanel
          apiBase={state.apiBase}
          branchId={state.branchId}
          databaseUrl={state.databaseUrl}
          onJumpChapter={(chapterIndex) => void openChapter(chapterIndex)}
        />
      ) : null}

      {workspace === "ops" ? (
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          {taskCenter}
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
        </Space>
      ) : null}
    </WorkbenchLayout>
  );
}

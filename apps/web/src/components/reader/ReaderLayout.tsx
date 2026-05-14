import { useState, useEffect, useCallback } from "react";
import { Layout, Tabs, Empty, Typography, Switch, Space, Tag } from "antd";
import ChapterNavPanel from "./ChapterNavPanel";
import AntiSpoilerQA from "./AntiSpoilerQA";
import ReaderSimPanel from "./ReaderSimPanel";
import ReaderFeedbackPanel from "./ReaderFeedbackPanel";
import ReaderPage from "@/components/ReaderPage";
import { useWorkbenchState } from "@/hooks/useWorkbenchState";
import {
  fetchBranchSnapshot,
  fetchChapterBundle,
  fetchChapterQaContext,
  fetchChapterSource,
} from "@/lib/api";
import type {
  BranchSnapshot,
  ChapterBundle,
  ChapterQaContext,
  ChapterSource,
} from "@/types/workbench";

const { Sider, Content, Header } = Layout;

interface Props {
  branchId: string | null;
}

export default function ReaderLayout({ branchId }: Props) {
  const { state } = useWorkbenchState();
  const apiBase = state.apiBase || "";
  const databaseUrl = state.databaseUrl || "";

  const [branchSnapshot, setBranchSnapshot] = useState<BranchSnapshot | null>(null);
  const [activeChapter, setActiveChapter] = useState<number | null>(null);
  const [bundle, setBundle] = useState<ChapterBundle | null>(null);
  const [qa, setQa] = useState<ChapterQaContext | null>(null);
  const [source, setSource] = useState<ChapterSource | null>(null);
  const [loadingChapter, setLoadingChapter] = useState(false);
  const [antiSpoiler, setAntiSpoiler] = useState(true);
  const [rightTab, setRightTab] = useState<"qa" | "sim" | "feedback">("qa");

  useEffect(() => {
    if (!branchId || !apiBase) return;
    fetchBranchSnapshot(apiBase, "", branchId, databaseUrl)
      .then(setBranchSnapshot)
      .catch(() => {});
  }, [branchId, apiBase, databaseUrl]);

  const loadChapter = useCallback(async (chapterIndex: number) => {
    if (!branchId || !apiBase) return;
    setActiveChapter(chapterIndex);
    setLoadingChapter(true);
    try {
      const [b, q, s] = await Promise.all([
        fetchChapterBundle(apiBase, branchId, chapterIndex, databaseUrl),
        fetchChapterQaContext(apiBase, branchId, chapterIndex, databaseUrl),
        fetchChapterSource(apiBase, branchId, chapterIndex, databaseUrl),
      ]);
      setBundle(b);
      setQa(q);
      setSource(s);
    } catch {
    } finally {
      setLoadingChapter(false);
    }
  }, [branchId, apiBase, databaseUrl]);

  useEffect(() => {
    if (!branchSnapshot || activeChapter !== null) return;
    const first = branchSnapshot.chapter_rows?.find((r) => r.has_artifact);
    if (first) loadChapter(first.chapter_index);
  }, [branchSnapshot, activeChapter, loadChapter]);

  if (!branchId) {
    return (
      <Layout style={{ minHeight: "100vh" }}>
        <Content style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Empty description="请先选择一本小说">
            <a href="/library">前往书库</a>
          </Empty>
        </Content>
      </Layout>
    );
  }

  const novelTitle = branchSnapshot?.chapter_rows?.[0]
    ? `共 ${branchSnapshot.chapter_rows.length} 章`
    : branchId;

  return (
    <Layout style={{ minHeight: "100vh" }} data-testid="reader-layout">
      <Header style={{ background: "#fff", borderBottom: "1px solid #f0f0f0", padding: "0 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Space>
          <Typography.Text strong>Reader Studio</Typography.Text>
          <Tag color="blue">{novelTitle}</Tag>
          {activeChapter && <Tag>第 {activeChapter} 章</Tag>}
        </Space>
        <Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>防剧透</Typography.Text>
          <Switch
            checked={antiSpoiler}
            onChange={setAntiSpoiler}
            checkedChildren="开"
            unCheckedChildren="关"
            size="small"
          />
        </Space>
      </Header>
      <Layout>
        <Sider
          width={280}
          theme="light"
          data-testid="reader-nav"
          style={{ borderRight: "1px solid #f0f0f0", overflow: "auto", height: "calc(100vh - 64px)" }}
        >
          <ChapterNavPanel
            rows={branchSnapshot?.chapter_rows || []}
            activeChapterIndex={activeChapter}
            onSelect={loadChapter}
          />
        </Sider>
        <Content
          data-testid="reader-main"
          style={{ padding: 24, background: "#fafafa", overflow: "auto", height: "calc(100vh - 64px)" }}
        >
          <ReaderPage
            bundle={bundle}
            qa={qa}
            source={source}
            loading={loadingChapter}
            onJumpChapter={loadChapter}
          />
          {activeChapter && branchId && (
            <div style={{ marginTop: 24 }}>
              <ReaderSimPanel
                apiBase={apiBase}
                branchId={branchId}
                chapterIndex={activeChapter}
                databaseUrl={databaseUrl}
              />
            </div>
          )}
          {activeChapter && branchId && (
            <div style={{ marginTop: 16 }}>
              <ReaderFeedbackPanel
                apiBase={apiBase}
                branchId={branchId}
                chapterIndex={activeChapter}
                databaseUrl={databaseUrl}
              />
            </div>
          )}
        </Content>
        <Sider
          width={380}
          theme="light"
          data-testid="reader-qa"
          style={{ borderLeft: "1px solid #f0f0f0", overflow: "auto", height: "calc(100vh - 64px)" }}
        >
          <AntiSpoilerQA
            apiBase={apiBase}
            branchId={branchId}
            databaseUrl={databaseUrl}
            maxChapter={antiSpoiler && activeChapter ? activeChapter : undefined}
            onJumpChapter={loadChapter}
          />
        </Sider>
      </Layout>
    </Layout>
  );
}

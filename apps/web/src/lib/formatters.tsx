import type { BranchSnapshot, ChapterBundle, ChapterQaContext, ChapterSource, ProviderHealth, RunSnapshot, RuntimeHealth } from "@/types/workbench";
import { Tag } from "antd";
import React from "react";

export const stateColor = (state?: string) => {
  switch (state) {
    case "completed":
      return "success";
    case "auto_running":
      return "processing";
    case "needs_recovery":
      return "warning";
    case "failed_terminal":
      return "error";
    default:
      return "default";
  }
};

export const renderStateTag = (state?: string) => <Tag color={stateColor(state)}>{state || "unknown"}</Tag>;

export const providerDegraded = (providerHealth?: ProviderHealth | null) => providerHealth?.last_status === "degraded";

export const runtimeNeedsAttention = (runtimeHealth?: RuntimeHealth | null) =>
  runtimeHealth ? runtimeHealth.missing_from_cache > 0 : false;

export const systemRecommendation = (
  providerHealth?: ProviderHealth | null,
  runtimeHealth?: RuntimeHealth | null,
) => {
  if (providerDegraded(providerHealth)) {
    return "当前更适合先观察 ask-stream / provider 恢复情况，再集中继续问答或批量恢复。";
  }
  if (runtimeNeedsAttention(runtimeHealth)) {
    return "建议先完成历史 .omx 到 .cache 的迁移检查，避免重启后出现文件读取问题。";
  }
  return "当前系统没有明显健康阻塞，可按正常节奏继续阅读、问答和恢复。";
};

export const recoveryRecommendation = (providerHealth?: ProviderHealth | null) =>
  providerDegraded(providerHealth)
    ? "如果只是 ask-stream / 问答异常，优先先观察与刷新；更适合等服务恢复后再重试失败章节。只有当章节任务本身持续失败、数据库状态异常，或运行态明显卡住时，才建议立刻手动恢复。"
    : "如果失败章节已经达到自动重试上限，或运行态明显卡住，再进入这里执行手动恢复。";

export const recoveryActionPolicy = (
  providerHealth?: ProviderHealth | null,
): { emphasized: boolean; buttonLabel: string; tone: "default" | "primary" } => ({
  emphasized: !providerDegraded(providerHealth),
  buttonLabel: providerDegraded(providerHealth) ? "查看恢复建议" : "打开恢复",
  tone: providerDegraded(providerHealth) ? "default" : "primary",
});

export const providerOperationalNotice = (providerHealth?: ProviderHealth | null) =>
  providerDegraded(providerHealth)
    ? `当前上游 provider 正处于降级期。${recoveryRecommendation(providerHealth)}${providerHealth?.last_error ? ` 最近错误：${providerHealth.last_error}` : ""}`
    : "当前上游 provider 状态稳定，可按正常节奏处理运行中与待恢复任务。";

export const libraryPriority = (
  item: {
    pipeline_state?: string;
    failed_jobs?: number;
    running_jobs?: number;
    next_chapter?: number | null;
    completed_chapters?: number;
  },
  providerHealth?: ProviderHealth | null,
) => {
  if (item.pipeline_state === "needs_recovery" || (item.failed_jobs || 0) > 0) {
    return {
      score: 100 + (item.failed_jobs || 0),
      reason: providerDegraded(providerHealth) ? "待恢复（建议先观察 provider）" : "待恢复（优先处理）",
    };
  }
  if ((item.running_jobs || 0) > 0 || item.pipeline_state === "auto_running") {
    return {
      score: 70 + (item.running_jobs || 0),
      reason: "运行中（持续跟踪）",
    };
  }
  if ((item.next_chapter || 0) > 0) {
    return {
      score: 40 + Math.min(item.completed_chapters || 0, 30),
      reason: "可继续推进",
    };
  }
  return {
    score: 10,
    reason: "已完成或暂不紧急",
  };
};

export const summarizeRun = (run: RunSnapshot) => [
  { label: "当前状态", value: run.pipeline_state },
  { label: "已整理章节", value: String(run.completed_chapters) },
  { label: "下一章", value: run.next_chapter ?? "已完成" },
  { label: "失败任务", value: String(run.failed_jobs) },
  { label: "建议操作", value: run.allowed_actions.join(" / ") || "-" },
];

export const summarizeBranch = (branch: BranchSnapshot) => ({
  actions: branch.allowed_actions,
  failed: branch.failed_summary,
  rows: branch.chapter_rows,
});

export const chapterOverviewCards = (bundle: ChapterBundle) => {
  const artifact = bundle.artifact || {};
  const stateSummary = bundle.state_summary || {};
  return {
    title: artifact.normalized_title || `第${bundle.chapter_index}章`,
    summary: artifact.chapter_summary || "暂无章节摘要",
    entities: artifact.key_entities || [],
    events: artifact.key_events || [],
    continuity: artifact.continuity_notes || [],
    resolutions: artifact.evidence_backed_resolutions || [],
    unresolved: artifact.unresolved_threads || [],
    stateSummary,
    review: Boolean(artifact.needs_human_review),
    hookScore: artifact.hook_score,
  };
};

export const qaCards = (qa: ChapterQaContext) => ({
  recommendedQuestions: qa.recommended_questions || [],
  transitionNotes: qa.state_transition_notes || [],
  unresolvedThreads: qa.unresolved_threads || [],
  reasoningPaths: (qa.reasoning_graph && qa.reasoning_graph.reasoning_paths) || [],
});

export const chapterThemes = (bundle: ChapterBundle) => {
  const stateLines = Object.entries(bundle.state_summary || {}).flatMap(([key, value]) =>
    Array.isArray(value) ? value.map((item) => `${key}: ${item}`) : [`${key}: ${value}`],
  );
  return {
    facts: (bundle.facts || []).map((item) => `${item.fact_type}: ${item.label}`),
    conflict: stateLines.filter((line) => line.includes("conflict") || line.includes("冲突")),
    foreshadow: stateLines.filter((line) => line.includes("foreshadow") || line.includes("伏笔")),
    world: stateLines.filter((line) => line.includes("world") || line.includes("规则")),
    retrievalKeywords: (bundle.retrieval && bundle.retrieval.keyword_list) || [],
    graphOverview: bundle.reasoning_graph?.overview || {},
  };
};

export const sourceMeta = (source: ChapterSource) => [
  `原始标题：${source.raw_heading || "无"}`,
  `偏移范围：${source.start_offset} - ${source.end_offset}`,
];

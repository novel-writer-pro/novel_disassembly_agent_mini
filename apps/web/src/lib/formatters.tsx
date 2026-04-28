import type { BranchSnapshot, ChapterBundle, ChapterQaContext, ChapterSource } from "@/types/workbench";
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

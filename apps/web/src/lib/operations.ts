import type { LibraryItem, ProviderHealth, RunSnapshot, RuntimeHealth } from "@/types/workbench";

export type NoticeTone = "success" | "warning" | "info";

export const providerDegraded = (providerHealth?: ProviderHealth | null) => providerHealth?.last_status === "degraded";

export const runtimeNeedsAttention = (runtimeHealth?: RuntimeHealth | null) =>
  runtimeHealth ? runtimeHealth.missing_from_cache > 0 : false;

export const refreshPolicyLabel = (providerHealth?: ProviderHealth | null, autoRefreshEnabled?: boolean) => {
  if (providerDegraded(providerHealth)) return "退避刷新";
  return autoRefreshEnabled ? "自动刷新开启" : "自动刷新关闭";
};

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

export const providerStatusSummary = (providerHealth?: ProviderHealth | null) => {
  if (!providerHealth) {
    return {
      tone: "info" as NoticeTone,
      label: "provider 信息未加载",
      detail: "后端可用后，这里会展示最近一次 ask-stream / ask 的 provider 状态。",
    };
  }
  if (providerDegraded(providerHealth)) {
    return {
      tone: "warning" as NoticeTone,
      label: "问答服务处于降级期",
      detail: providerOperationalNotice(providerHealth),
    };
  }
  return {
    tone: "success" as NoticeTone,
    label: "问答服务状态稳定",
    detail: providerOperationalNotice(providerHealth),
  };
};

export const cacheStatusSummary = (runtimeHealth?: RuntimeHealth | null) => {
  if (!runtimeHealth) {
    return {
      tone: "info" as NoticeTone,
      label: "缓存状态未加载",
      detail: "后端可用后，这里会展示 .cache 与历史 .omx 运行时文件的健康状态。",
    };
  }
  if (runtimeNeedsAttention(runtimeHealth)) {
    return {
      tone: "warning" as NoticeTone,
      label: "运行时缓存仍有待迁移内容",
      detail: "建议优先完成历史 .omx 到 .cache 的迁移检查，避免重启后出现文件缺失。",
    };
  }
  return {
    tone: "success" as NoticeTone,
    label: "运行时缓存状态正常",
    detail: ".cache/novel-analyzer 已接管当前运行时文件，重启稳定性更高。",
  };
};

export const healthBannerSummary = (
  providerHealth?: ProviderHealth | null,
  runtimeHealth?: RuntimeHealth | null,
  autoRefreshEnabled = true,
) => {
  const provider = providerStatusSummary(providerHealth);
  const cache = cacheStatusSummary(runtimeHealth);
  const warning = provider.tone === "warning" || cache.tone === "warning";
  return {
    type: (warning ? "warning" : "success") as Exclude<NoticeTone, "info">,
    headline: provider.tone === "warning"
      ? provider.label
      : cache.tone === "warning"
        ? cache.label
        : "系统状态稳定",
    providerTag: providerHealth?.last_status || "unknown",
    cacheTag: runtimeNeedsAttention(runtimeHealth) ? "待迁移" : "正常",
    refreshTag: refreshPolicyLabel(providerHealth, autoRefreshEnabled),
    recommendation: systemRecommendation(providerHealth, runtimeHealth),
  };
};

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

export const libraryStatusTone = (item: LibraryItem & { score?: number }) => {
  if ((item.failed_jobs || 0) > 0 || item.pipeline_state === "needs_recovery") return "error" as const;
  if ((item.running_jobs || 0) > 0 || item.pipeline_state === "auto_running") return "processing" as const;
  if ((item.score || 0) >= 40) return "blue" as const;
  return "default" as const;
};

export const summarizeRun = (run: RunSnapshot) => [
  { label: "当前状态", value: run.pipeline_state },
  { label: "已整理章节", value: String(run.completed_chapters) },
  { label: "下一章", value: run.next_chapter ?? "已完成" },
  { label: "失败任务", value: String(run.failed_jobs) },
  { label: "建议操作", value: run.allowed_actions.join(" / ") || "-" },
];

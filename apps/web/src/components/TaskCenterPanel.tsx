import { Alert, Button, Card, Empty, List, Segmented, Space, Tag, Typography } from "antd";
import type { LibraryItem, ProviderHealth } from "@/types/workbench";
import { useMemo, useState } from "react";

interface Props {
  items: LibraryItem[];
  activeBranchId: string;
  onActivate: (item: LibraryItem) => void;
  onOpenRecovery: (item: LibraryItem) => void;
  onRefresh: () => void;
  autoRefreshEnabled: boolean;
  onToggleAutoRefresh: () => void;
  lastRefreshedAt?: string | null;
  providerHealth?: ProviderHealth | null;
}

export default function TaskCenterPanel({
  items,
  activeBranchId,
  onActivate,
  onOpenRecovery,
  onRefresh,
  autoRefreshEnabled,
  onToggleAutoRefresh,
  lastRefreshedAt,
  providerHealth,
}: Props) {
  const [filter, setFilter] = useState<"focus" | "running" | "recovery">("focus");
  const runningItems = items.filter((item) => (item.running_jobs || 0) > 0 || item.pipeline_state === "auto_running");
  const recoveryItems = items.filter((item) => item.pipeline_state === "needs_recovery" || (item.failed_jobs || 0) > 0);
  const focusItems = [...runningItems, ...recoveryItems.filter((item) => !runningItems.find((run) => run.branch_id === item.branch_id))].slice(0, 12);
  const visibleItems = useMemo(() => {
    if (filter === "running") return runningItems;
    if (filter === "recovery") return recoveryItems;
    return focusItems;
  }, [filter, focusItems, recoveryItems, runningItems]);
  const providerDegraded = providerHealth?.last_status === "degraded";

  return (
    <Card
      title="多任务运行 / 恢复中心"
      bordered={false}
      className="product-panel"
      extra={(
        <Space wrap>
          <Tag color={autoRefreshEnabled ? "success" : "default"}>
            {autoRefreshEnabled ? "自动刷新开启" : "自动刷新关闭"}
          </Tag>
          <Button size="small" onClick={onToggleAutoRefresh}>
            {autoRefreshEnabled ? "关闭自动刷新" : "开启自动刷新"}
          </Button>
          <Button size="small" onClick={onRefresh}>立即刷新</Button>
        </Space>
      )}
    >
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <Alert
          type="info"
          showIcon
          message="这里优先盯住正在跑和需要恢复的小说"
          description={`最近刷新：${lastRefreshedAt || "尚未刷新"}`}
        />
        {providerDegraded ? (
          <Alert
            type="warning"
            showIcon
            message="当前上游 provider 正处于降级期"
            description={`最近 ask-stream / QA 请求出现过上游异常。当前更适合先观察运行任务与恢复任务，等服务恢复后再集中继续追问或批量恢复。${providerHealth?.last_error ? ` 最近错误：${providerHealth.last_error}` : ""}`}
          />
        ) : null}
        <Segmented
          value={filter}
          onChange={(value) => setFilter(value as typeof filter)}
          options={[
            { label: `聚焦 ${focusItems.length}`, value: "focus" },
            { label: `运行中 ${runningItems.length}`, value: "running" },
            { label: `待恢复 ${recoveryItems.length}`, value: "recovery" },
          ]}
        />
        {visibleItems.length ? (
          <List
            split={false}
            dataSource={visibleItems}
            renderItem={(item) => (
              <List.Item className="task-center-item">
                <div className="task-center-main">
                  <div>
                    <Typography.Text strong>{item.title}</Typography.Text>
                    <Typography.Paragraph type="secondary" style={{ margin: "6px 0 0" }}>
                      {item.branch_name} · 已完成 {item.completed_chapters}/{item.manifest_chapter_count} 章 · 下一章 {item.next_chapter ?? "已完成"}
                    </Typography.Paragraph>
                  </div>
                  <Space wrap>
                    {item.branch_id === activeBranchId ? <Tag color="success">当前生效</Tag> : null}
                    <Tag color={(item.running_jobs || 0) > 0 ? "processing" : item.pipeline_state === "needs_recovery" ? "error" : "blue"}>
                      {item.pipeline_state}
                    </Tag>
                    <Tag color="warning">失败 {item.failed_jobs || 0}</Tag>
                    <Tag color="processing">运行中 {item.running_jobs || 0}</Tag>
                  </Space>
                </div>
                <Space wrap>
                  <Button size="small" onClick={() => onActivate(item)}>切换到这本</Button>
                  {(item.failed_jobs || 0) > 0 || item.pipeline_state === "needs_recovery" ? (
                    <Button size="small" type={providerDegraded ? "default" : "primary"} onClick={() => onOpenRecovery(item)}>
                      {providerDegraded ? "查看恢复建议" : "打开恢复"}
                    </Button>
                  ) : null}
                </Space>
              </List.Item>
            )}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有正在运行或待恢复的小说任务" />
        )}
      </Space>
    </Card>
  );
}

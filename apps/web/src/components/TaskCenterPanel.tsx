import { Alert, Button, Card, Empty, List, Space, Tag, Typography } from "antd";
import type { LibraryItem } from "@/types/workbench";

interface Props {
  items: LibraryItem[];
  activeBranchId: string;
  onActivate: (item: LibraryItem) => void;
  onOpenRecovery: (item: LibraryItem) => void;
  onRefresh: () => void;
  autoRefreshEnabled: boolean;
  onToggleAutoRefresh: () => void;
  lastRefreshedAt?: string | null;
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
}: Props) {
  const runningItems = items.filter((item) => (item.running_jobs || 0) > 0 || item.pipeline_state === "auto_running");
  const recoveryItems = items.filter((item) => item.pipeline_state === "needs_recovery" || (item.failed_jobs || 0) > 0);
  const focusItems = [...runningItems, ...recoveryItems.filter((item) => !runningItems.find((run) => run.branch_id === item.branch_id))].slice(0, 12);

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
        {focusItems.length ? (
          <List
            split={false}
            dataSource={focusItems}
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
                    <Button size="small" type="primary" onClick={() => onOpenRecovery(item)}>
                      打开恢复
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

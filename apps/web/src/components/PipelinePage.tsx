import { Alert, Button, Card, Col, Drawer, Empty, InputNumber, List, Progress, Row, Select, Space, Table, Tag, Timeline, Typography } from "antd";
import type { ChapterJobRow, JobEventItem, PipelineRunSnapshot } from "@/types/workbench";
import { useMemo, useState } from "react";

interface Props {
  runId: string;
  branchId: string;
  nextChapter?: number | null;
  completedChapters?: number;
  manifestChapterCount?: number;
  loading?: boolean;
  pipelineRuns: PipelineRunSnapshot[];
  events: JobEventItem[];
  chapterJobs: ChapterJobRow[];
  chapterEventItems: JobEventItem[];
  onRefresh: () => void;
  targetToChapter: number | null;
  onChangeTargetToChapter: (value: number | null) => void;
  providerProfile: string;
  onChangeProviderProfile: (value: string) => void;
  onStart: () => void;
  onPause: (pipelineRunId: string) => void;
  onResume: (pipelineRunId: string) => void;
  onCancel: (pipelineRunId: string) => void;
  onOpenChapterDetail: (chapterIndex: number) => void;
  onCloseChapterDetail: () => void;
}

const runTone = (status: string) => {
  if (status === "failed" || status === "cancelled") return "error";
  if (status === "paused") return "warning";
  if (status === "running") return "processing";
  if (status === "completed") return "success";
  return "default";
};

export default function PipelinePage(props: Props) {
  const {
    runId,
    branchId,
    nextChapter,
    completedChapters,
    manifestChapterCount,
    loading,
    pipelineRuns,
    events,
    chapterJobs,
    chapterEventItems,
    onRefresh,
    targetToChapter,
    onChangeTargetToChapter,
    providerProfile,
    onChangeProviderProfile,
    onStart,
    onPause,
    onResume,
    onCancel,
    onOpenChapterDetail,
    onCloseChapterDetail,
  } = props;
  const [selectedChapterIndex, setSelectedChapterIndex] = useState<number | null>(null);

  const latestRun = pipelineRuns[0] || null;
  const stalledJobs = chapterJobs.filter((item) => item.failure_class === "stalled");
  const activeRunningJobs = chapterJobs.filter((item) => item.status === "running");
  const failedJobs = chapterJobs.filter((item) => item.status === "failed");
  const chapterEventTitle = useMemo(
    () => (selectedChapterIndex ? `第 ${selectedChapterIndex} 章任务详情` : "章节任务详情"),
    [selectedChapterIndex],
  );

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card bordered={false} className="page-hero-card">
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <div>
            <Typography.Text className="reader-eyebrow">拆书流水线控制台</Typography.Text>
            <Typography.Title level={2} style={{ margin: "8px 0 10px" }}>
              用后台任务方式持续推进拆书，而不是前台阻塞等待
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              这里用于启动、暂停、恢复、取消一条后台拆书流水线，并查看最近章节事件流。当前版本先支持从当前 next_chapter 连续往后推进。
            </Typography.Paragraph>
          </div>
          <Space wrap>
            <Tag color="blue">run: {runId.slice(0, 8)}</Tag>
            <Tag color="processing">branch: {branchId.slice(0, 8)}</Tag>
            <Tag color="purple">当前 next_chapter: {nextChapter ?? "已完成"}</Tag>
          </Space>
        </Space>
      </Card>

      {stalledJobs.length ? (
        <Alert
          type="warning"
          showIcon
          message="检测到疑似卡住的章节任务"
          description={`当前有 ${stalledJobs.length} 个章节任务因心跳超时被标记为 stalled/failed。建议先观察事件流，必要时再到恢复页处理。`}
        />
      ) : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="启动后台拆书" bordered={false} className="product-panel" extra={<Button onClick={onRefresh}>刷新</Button>}>
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              <Alert
                type="info"
                showIcon
                message="当前最小异步版本"
                description="当前仅支持从 next_chapter 连续往后拆到目标章节，先把后台控制链路跑通。"
              />
              <InputNumber
                style={{ width: "100%" }}
                min={nextChapter || 1}
                placeholder="目标章节，例如 80 / 100"
                value={targetToChapter}
                onChange={(value) => onChangeTargetToChapter(value)}
              />
              <Select
                value={providerProfile}
                options={[
                  { value: "default", label: "default" },
                  { value: "deepseek-local", label: "deepseek-local" },
                  { value: "vip1129-gpt54mini", label: "vip1129-gpt54mini" },
                ]}
                onChange={onChangeProviderProfile}
              />
              <Button type="primary" loading={loading} onClick={onStart}>
                启动后台拆书
              </Button>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                已完成 {completedChapters ?? 0} / {manifestChapterCount ?? 0} 章，启动后会从当前 next_chapter 顺序往后推进。
              </Typography.Paragraph>
              <Space wrap>
                <Tag color="processing">运行中任务 {activeRunningJobs.length}</Tag>
                <Tag color="warning">失败任务 {failedJobs.length}</Tag>
                <Tag color={stalledJobs.length ? "error" : "success"}>
                  stalled {stalledJobs.length}
                </Tag>
              </Space>
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card title="最近流水线任务" bordered={false} className="product-panel">
            {pipelineRuns.length ? (
              <List
                split={false}
                dataSource={pipelineRuns}
                renderItem={(item) => (
                  <List.Item className="task-center-item">
                    <div className="task-center-main">
                      <div>
                        <Typography.Text strong>{item.id.slice(0, 8)}</Typography.Text>
                        <Typography.Paragraph type="secondary" style={{ margin: "6px 0 0" }}>
                          目标区间：{item.target_from_chapter ?? "-"} → {item.target_to_chapter ?? "-"} · 最近完成：{String(item.summary_json?.last_completed_chapter || "-")}
                        </Typography.Paragraph>
                      </div>
                      <Space wrap>
                        <Tag color={runTone(item.status)}>{item.status}</Tag>
                        <Tag>profile: {item.provider_profile || "default"}</Tag>
                        {latestRun?.id === item.id ? <Tag color="success">当前观察中</Tag> : null}
                      </Space>
                    </div>
                    <Space wrap>
                      {item.status === "running" ? <Button size="small" onClick={() => onPause(item.id)}>暂停</Button> : null}
                      {item.status === "paused" ? <Button size="small" type="primary" onClick={() => onResume(item.id)}>恢复</Button> : null}
                      {item.status === "running" || item.status === "paused" || item.status === "pending" ? (
                        <Button size="small" danger onClick={() => onCancel(item.id)}>取消</Button>
                      ) : null}
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前还没有后台拆书任务" />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="最近章节事件流" bordered={false} className="product-panel">
        {events.length ? (
          <Timeline
            items={events.map((item) => ({
              color: item.level === "error" ? "red" : item.level === "warning" ? "orange" : "blue",
              children: (
                <div className="pipeline-event-item">
                  <Space wrap>
                    <Tag color="processing">第 {item.chapter_index} 章</Tag>
                    <Tag>{item.event_type}</Tag>
                    {item.stage ? <Tag color="purple">{item.stage}</Tag> : null}
                    <Typography.Text type="secondary">{item.created_at}</Typography.Text>
                  </Space>
                  <Typography.Paragraph style={{ margin: "6px 0 0" }}>
                    {item.message}
                  </Typography.Paragraph>
                </div>
              ),
            }))}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前还没有章节事件流" />
        )}
      </Card>

      <Card title="章节任务表" bordered={false} className="product-panel">
        {chapterJobs.length ? (
          <Table
            rowKey={(row) => String(row.chapter_index)}
            pagination={{ pageSize: 12 }}
            dataSource={chapterJobs}
            columns={[
              {
                title: "章节",
                dataIndex: "chapter_index",
                width: 88,
                render: (value: number) => (
                  <Button
                    type="link"
                    style={{ paddingInline: 0 }}
                    onClick={() => {
                      setSelectedChapterIndex(value);
                      onOpenChapterDetail(value);
                    }}
                  >
                    第 {value} 章
                  </Button>
                ),
              },
              {
                title: "标题",
                dataIndex: "title",
                ellipsis: true,
              },
              {
                title: "状态",
                dataIndex: "status",
                width: 120,
                render: (value: string) => <Tag color={runTone(value)}>{value}</Tag>,
              },
              {
                title: "当前阶段",
                dataIndex: "current_stage",
                width: 160,
                render: (value?: string | null) => value ? <Tag color="purple">{value}</Tag> : <Tag>-</Tag>,
              },
              {
                title: "进度",
                dataIndex: "progress_percent",
                width: 180,
                render: (value: number) => <Progress percent={value || 0} size="small" />,
              },
              {
                title: "尝试次数",
                dataIndex: "attempts",
                width: 100,
              },
              {
                title: "最近心跳",
                dataIndex: "heartbeat_at",
                width: 180,
                render: (value?: string | null) => value || "-",
              },
              {
                title: "失败分类",
                dataIndex: "failure_class",
                width: 140,
                render: (value?: string | null) => value ? <Tag color="error">{value}</Tag> : "-",
              },
              {
                title: "结果",
                dataIndex: "has_artifact",
                width: 100,
                render: (value: boolean) => value ? <Tag color="success">已产出</Tag> : <Tag>-</Tag>,
              },
            ]}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前还没有章节任务表数据" />
        )}
      </Card>

      <Drawer
        open={selectedChapterIndex !== null}
        onClose={() => {
          setSelectedChapterIndex(null);
          onCloseChapterDetail();
        }}
        width={720}
        title={chapterEventTitle}
      >
        {selectedChapterIndex === null ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="请选择章节" />
        ) : chapterEventItems.length ? (
          <Timeline
            items={chapterEventItems.map((item) => ({
              color: item.level === "error" ? "red" : item.level === "warning" ? "orange" : "blue",
              children: (
                <div className="pipeline-event-item">
                  <Space wrap>
                    <Tag>{item.event_type}</Tag>
                    {item.stage ? <Tag color="purple">{item.stage}</Tag> : null}
                    <Typography.Text type="secondary">{item.created_at}</Typography.Text>
                  </Space>
                  <Typography.Paragraph style={{ margin: "6px 0 0" }}>
                    {item.message}
                  </Typography.Paragraph>
                </div>
              ),
            }))}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前还没有这章的事件记录" />
        )}
      </Drawer>
    </Space>
  );
}

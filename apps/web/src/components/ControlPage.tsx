import {
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Statistic,
  Steps,
  Typography,
} from "antd";
import type { BranchSnapshot, ImportResult, LibraryItem, PipelineProfile, RunSnapshot, WorkbenchState } from "@/types/workbench";
import { renderStateTag } from "@/lib/formatters";

interface Props {
  state: WorkbenchState;
  importText: string;
  runSnapshot?: RunSnapshot | null;
  branchSnapshot?: BranchSnapshot | null;
  libraryItems?: LibraryItem[];
  loading?: {
    importing?: boolean;
    refreshing?: boolean;
    starting?: boolean;
  };
  onChange: (patch: Partial<WorkbenchState>) => void;
  onImport: () => void;
  onSimulate: () => void;
  onRefresh: () => void;
  onStart: () => void;
  onOpenRecovery: () => void;
  onSelectLibraryItem: (item: LibraryItem) => void;
}

function ProgressCard({ title, value, suffix, hint }: { title: string; value: string | number; suffix?: string; hint?: string }) {
  return (
    <Card bordered={false} className="product-panel stat-panel">
      <Statistic title={title} value={value} suffix={suffix} valueStyle={{ color: "#eaf2ff" }} />
      {hint ? (
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 8 }}>
          {hint}
        </Typography.Paragraph>
      ) : null}
    </Card>
  );
}

export default function ControlPage(props: Props) {
  const {
    state,
    importText,
    runSnapshot,
    branchSnapshot,
    libraryItems,
    loading,
    onChange,
    onImport,
    onSimulate,
    onRefresh,
    onStart,
    onOpenRecovery,
    onSelectLibraryItem,
  } = props;

  let parsedImport: ImportResult | null = null;

  const quotaFailure = branchSnapshot?.failed_summary?.find((item) => item.error.includes("DAILY_LIMIT_EXCEEDED") || item.error.includes("USAGE_LIMIT_EXCEEDED")) || null;
  try {
    parsedImport = importText.startsWith("{") ? JSON.parse(importText) : null;
  } catch {
    parsedImport = null;
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card bordered={false} className="page-hero-card">
        <Row gutter={[18, 18]} align="middle">
          <Col xs={24} xl={15}>
            <Typography.Text className="reader-eyebrow">开始整理</Typography.Text>
            <Typography.Title level={2} style={{ margin: "8px 0 10px" }}>
              把作品导入进来，然后按章节持续拆解
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ fontSize: 15, marginBottom: 0 }}>
              这里负责“开始”和“继续”。导入作品后，你就可以去左侧目录按章节阅读；如果效果满意，也可以继续批量往后拆。
            </Typography.Paragraph>
          </Col>
          <Col xs={24} xl={9}>
            <Alert showIcon type="info" message="推荐流程" description="导入作品 → 先看前几章效果 → 继续整理更多章节 → 最后导出手册。" />
          </Col>
        </Row>
      </Card>

      <Card bordered={false} className="product-panel steps-panel">
        <Steps
          responsive
          current={runSnapshot ? (runSnapshot.completed_chapters > 0 ? 1 : 0) : 0}
          items={[
            { title: "导入作品", description: "选择正文文件并开始" },
            { title: "查看章节", description: "先看前几章拆书效果" },
            { title: "继续推进", description: "满意后继续往后整理" },
          ]}
        />
      </Card>

      {quotaFailure ? (
        <Alert
          type="warning"
          showIcon
          message="当前拆书已遇到额度上限"
          description={
            <Space direction="vertical">
              <span>第 {quotaFailure.chapter_index} 章因为 provider 当日额度耗尽而停止，恢复额度后请先进入“导出与恢复”页重试失败章节，再继续整理后续章节。</span>
              <Space wrap>
                <Button type="primary" onClick={onOpenRecovery}>前往恢复页</Button>
                <Button onClick={onRefresh}>重新刷新进度</Button>
              </Space>
            </Space>
          }
        />
      ) : null}

      {runSnapshot ? (
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}><ProgressCard title="已整理章节" value={runSnapshot.completed_chapters} hint="已可直接阅读" /></Col>
          <Col xs={12} md={6}><ProgressCard title="下一章" value={runSnapshot.next_chapter ?? "已完成"} hint="即将继续处理" /></Col>
          <Col xs={12} md={6}><ProgressCard title="失败任务" value={runSnapshot.failed_jobs} hint="达到 5 次才需人工介入" /></Col>
          <Col xs={12} md={6}><ProgressCard title="当前状态" value={runSnapshot.pipeline_state} hint="看整体节奏即可" /></Col>
        </Row>
      ) : null}

      <Card bordered={false} className="product-panel">
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="当前作品">{state.title || "未命名作品"}</Descriptions.Item>
          <Descriptions.Item label="当前分支">{state.branchId || "未选择"}</Descriptions.Item>
          <Descriptions.Item label="当前 Run">{state.runId || "未选择"}</Descriptions.Item>
          <Descriptions.Item label="当前模式">{state.profile}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={11}>
          <Card title="第一步：导入作品" bordered={false} className="product-panel" extra={<Typography.Text type="secondary">开始入口</Typography.Text>}>
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              <div>
                <Typography.Text type="secondary">选择要整理的小说正文文件</Typography.Text>
                <Input type="file" id="novel-file" />
              </div>
              <Input
                placeholder="作品标题，例如：凡人修仙传"
                value={state.title || ""}
                onChange={(e) => onChange({ title: e.target.value })}
              />
              <Select
                value={state.profile}
                options={[
                  { value: "manual", label: "仅导入作品，稍后再开始整理" },
                  { value: "auto-lite", label: "先自动整理前几章，快速预览效果" },
                  { value: "auto-full", label: "尽量连续整理更多章节" },
                ]}
                onChange={(value: PipelineProfile) => onChange({ profile: value })}
              />
              <InputNumber
                style={{ width: "100%" }}
                min={0}
                placeholder="首次自动整理章节数，例如 3 / 10"
                value={state.maxChapters ? Number(state.maxChapters) : null}
                onChange={(value) => onChange({ maxChapters: value === null ? "" : String(value) })}
              />
              <Space wrap>
                <Button type="primary" loading={loading?.importing} onClick={onImport}>导入并开始整理</Button>
                <Button disabled={loading?.importing} onClick={onSimulate}>载入当前示例</Button>
              </Space>
              <Collapse
                size="small"
                items={[
                  {
                    key: "advanced",
                    label: "高级设置（仅调试时使用）",
                    children: (
                      <Space direction="vertical" style={{ width: "100%" }}>
                        <Input value={state.apiBase} onChange={(e) => onChange({ apiBase: e.target.value })} />
                        <Input value={state.databaseUrl} onChange={(e) => onChange({ databaseUrl: e.target.value })} />
                        <Input value={state.runId} onChange={(e) => onChange({ runId: e.target.value })} placeholder="作品标识" />
                        <Input value={state.branchId} onChange={(e) => onChange({ branchId: e.target.value })} placeholder="整理分支" />
                      </Space>
                    ),
                  },
                ]}
              />
            </Space>
          </Card>
        </Col>

        <Col xs={24} xl={13}>
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            <Card title="当前作品库" bordered={false} className="product-panel" extra={<Typography.Text type="secondary">多本切换</Typography.Text>}>
              {libraryItems?.length ? (
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    当前 UI 仍是“单工作台聚焦一个 branch”，但已经可以从这里切换不同小说/分支；后续可继续扩展为多作品总览页。
                  </Typography.Paragraph>
                  <Select
                    showSearch
                    style={{ width: "100%" }}
                    value={state.branchId || undefined}
                    optionFilterProp="label"
                    options={libraryItems.map((item) => ({
                      value: item.branch_id,
                      label: `${item.title} · ${item.branch_name} · ${item.completed_chapters}/${item.manifest_chapter_count}`,
                      item,
                    }))}
                    onChange={(value, option) => {
                      const selected = (option as { item?: LibraryItem })?.item;
                      if (selected) onSelectLibraryItem(selected);
                    }}
                  />
                  <div className="library-quick-grid">
                    {libraryItems.slice(0, 6).map((item) => (
                      <button
                        key={`${item.run_id}-${item.branch_id}`}
                        type="button"
                        className={`library-quick-card ${state.branchId === item.branch_id ? "active" : ""}`}
                        onClick={() => onSelectLibraryItem(item)}
                      >
                        <strong>{item.title}</strong>
                        <span>{item.completed_chapters}/{item.manifest_chapter_count} 章</span>
                        <span>{item.pipeline_state}</span>
                      </button>
                    ))}
                  </div>
                </Space>
              ) : (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  当前还没有读取到作品库。先导入一本，或刷新当前进度后，这里会列出最近可切换的作品与分支。
                </Typography.Paragraph>
              )}
            </Card>

            <Card title="第二步：查看当前进度" bordered={false} className="product-panel" extra={<Typography.Text type="secondary">整体概览</Typography.Text>}>
              <Space wrap>
                <Button type="primary" loading={loading?.refreshing} onClick={onRefresh}>刷新当前进度</Button>
                <Button loading={loading?.starting} onClick={onStart}>继续整理后续章节</Button>
              </Space>
              <Alert
                type="info"
                showIcon
                style={{ marginTop: 16 }}
                message="这里看整体，左侧看章节"
                description="如果你要逐章阅读内容，请直接使用左侧章节目录进入章节阅读页。"
              />
              {runSnapshot ? (
                <Descriptions column={2} bordered size="small" style={{ marginTop: 16 }}>
                  <Descriptions.Item label="当前状态">{renderStateTag(runSnapshot.pipeline_state)}</Descriptions.Item>
                  <Descriptions.Item label="已整理章节">{runSnapshot.completed_chapters}</Descriptions.Item>
                  <Descriptions.Item label="下一章">{runSnapshot.next_chapter ?? "已完成"}</Descriptions.Item>
                  <Descriptions.Item label="失败任务">{runSnapshot.failed_jobs}</Descriptions.Item>
                  <Descriptions.Item label="运行中">{runSnapshot.running_jobs}</Descriptions.Item>
                  <Descriptions.Item label="建议动作">{runSnapshot.allowed_actions.join(" / ") || "暂无"}</Descriptions.Item>
                </Descriptions>
              ) : (
                <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
                  还没有读取到当前进度。导入作品或点击“刷新当前进度”后，这里会显示整体整理情况。
                </Typography.Paragraph>
              )}
            </Card>

            <Card title="第三步：接下来建议做什么" bordered={false} className="product-panel" extra={<Typography.Text type="secondary">下一步建议</Typography.Text>}>
              {branchSnapshot ? (
                <Space direction="vertical" style={{ width: "100%" }}>
                  <Typography.Paragraph style={{ marginBottom: 0 }}>
                    当前建议：{branchSnapshot.allowed_actions.join(" / ") || "暂无"}
                  </Typography.Paragraph>
                  <Typography.Paragraph style={{ marginBottom: 0 }}>
                    优先关注：{branchSnapshot.failed_summary.length
                      ? branchSnapshot.failed_summary.map((item) => `第${item.chapter_index}章`).join("、")
                      : "暂无异常章节，可以直接从左侧目录选择你想看的章节。"}
                  </Typography.Paragraph>
                  <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                    如果章节较多，可以在左侧目录中直接搜索章节名、章节号或摘要关键字。
                  </Typography.Paragraph>
                </Space>
              ) : (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  读取分支后，这里会告诉你当前有哪些章节值得优先看、是否有异常章节需要留意。
                </Typography.Paragraph>
              )}
            </Card>

            <Card title="本次操作反馈" bordered={false} className="product-panel" extra={<Typography.Text type="secondary">即时结果</Typography.Text>}>
              {parsedImport ? (
                <Descriptions column={2} size="small" bordered>
                  <Descriptions.Item label="当前状态">{renderStateTag(parsedImport.pipeline_state)}</Descriptions.Item>
                  <Descriptions.Item label="整理方式">{parsedImport.pipeline_profile}</Descriptions.Item>
                  <Descriptions.Item label="已处理章节">{parsedImport.processed_chapters ?? 0}</Descriptions.Item>
                  <Descriptions.Item label="下一章">{parsedImport.next_chapter ?? "已完成"}</Descriptions.Item>
                  <Descriptions.Item label="作品标识">{parsedImport.run_id || "尚未生成"}</Descriptions.Item>
                  <Descriptions.Item label="整理分支">{parsedImport.branch_id || "尚未生成"}</Descriptions.Item>
                </Descriptions>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message="这里会显示最新的一次操作结果"
                  description={importText || "你可以先导入作品，或载入当前示例。"}
                />
              )}
            </Card>
          </Space>
        </Col>
      </Row>
    </Space>
  );
}

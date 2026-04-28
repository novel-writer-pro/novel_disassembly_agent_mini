import { Alert, Button, Card, Col, Row, Space, Tag, Typography } from "antd";
import type { BranchExports, ProviderHealth } from "@/types/workbench";
import { providerDegraded as isProviderDegraded, providerOperationalNotice, recoveryActionPolicy, recoveryRecommendation } from "@/lib/formatters";

interface Props {
  recoveryResultText: string;
  exportsData: BranchExports | null;
  loading?: {
    retrying?: boolean;
    clearing?: boolean;
    repairing?: boolean;
    exporting?: boolean;
  };
  onRetryFailed: () => void;
  onClearRunning: () => void;
  onRepair: () => void;
  onLoadExports: () => void;
  apiBase: string;
  providerHealth?: ProviderHealth | null;
}

export default function OpsPage(props: Props) {
  const {
    recoveryResultText,
    exportsData,
    loading,
    onRetryFailed,
    onClearRunning,
    onRepair,
    onLoadExports,
    apiBase,
    providerHealth,
  } = props;
  const providerDegraded = isProviderDegraded(providerHealth);
  const recoveryPolicy = recoveryActionPolicy(providerHealth);

  let recoveryData: { message?: string; pipeline_state?: string; accepted_action?: string } | null = null;
  try {
    recoveryData = recoveryResultText.startsWith("{") ? JSON.parse(recoveryResultText) : null;
  } catch {
    recoveryData = null;
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card bordered={false} className="page-hero-card">
        <Typography.Text className="reader-eyebrow">导出与恢复</Typography.Text>
        <Typography.Title level={2} style={{ margin: "8px 0 10px" }}>
          结果整理好之后，在这里收尾
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ fontSize: 15, marginBottom: 0 }}>
          这一页主要负责收尾工作。平时阅读章节时几乎不会用到；只有准备导出手册，或者某些章节整理异常时，才需要进入这里。
        </Typography.Paragraph>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={10}>
          <Card title="异常恢复" bordered={false} className="product-panel" style={{ height: "100%" }} extra={<Typography.Text type="secondary">仅异常时使用</Typography.Text>}>
            <Typography.Paragraph type="secondary">
              失败会先自动重试；只有达到重试上限后，才需要你在这里手动恢复。
            </Typography.Paragraph>
            {providerDegraded ? (
              <Alert
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
                message="当前 provider 处于降级期"
                description={providerOperationalNotice(providerHealth)}
              />
            ) : null}
            <Space direction="vertical" style={{ width: "100%" }}>
              <Button block loading={loading?.retrying} onClick={onRetryFailed} type={recoveryPolicy.tone}>重试失败章节</Button>
              <Button block loading={loading?.clearing} onClick={onClearRunning}>清理卡住任务</Button>
              <Button block type={recoveryPolicy.tone} loading={loading?.repairing} onClick={onRepair}>修复章节清单</Button>
            </Space>
            <div style={{ marginTop: 18 }}>
              {recoveryData ? (
                <Alert
                  type={recoveryData.pipeline_state === "failed_terminal" ? "error" : "success"}
                  showIcon
                  message={recoveryData.message || "处理完成"}
                  description={`动作：${recoveryData.accepted_action || "-"} ｜ 当前状态：${recoveryData.pipeline_state || "-"}`}
                />
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message="没有异常时可以不用操作"
                  description="正常情况下，你只需要使用阅读页和导出页即可。"
                />
              )}
            </div>
          </Card>
        </Col>

        <Col xs={24} xl={14}>
          <Card
            title="导出手册"
            bordered={false}
            className="product-panel"
            extra={<Button loading={loading?.exporting} onClick={onLoadExports}>生成导出文件</Button>}
          >
            <Typography.Paragraph type="secondary">
              当你已经浏览过章节细节、准备整理成外部手册时，可以在这里生成导出文件。
            </Typography.Paragraph>
            {exportsData ? (
              <Row gutter={[16, 16]}>
                {[
                  {
                    label: "章节总包",
                    item: exportsData.branch_bundle,
                    summary: "适合整体归档章节拆书结果，方便统一留档。",
                  },
                  {
                    label: "问答上下文",
                    item: exportsData.branch_qa_context,
                    summary: "适合后续继续提问、扩写，或重新整理线索。",
                  },
                  {
                    label: "分支报告",
                    item: exportsData.branch_report,
                    summary: "适合输出成可阅读的拆书手册，便于交付或复盘。",
                  },
                ].map(({ label, item, summary }) => (
                  <Col xs={24} md={8} key={label}>
                    <Card size="small" className="export-resource-card" extra={<a href={`${apiBase}${item.download_ref}`} target="_blank" rel="noreferrer">下载</a>}>
                      <Typography.Title level={5} style={{ marginTop: 0 }}>{label}</Typography.Title>
                      <Tag color="blue" style={{ marginBottom: 10 }}>{item.content_type}</Tag>
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>{summary}</Typography.Paragraph>
                    </Card>
                  </Col>
                ))}
              </Row>
            ) : (
              <Alert
                type="info"
                showIcon
                message="还没有生成导出文件"
                description="当你准备把结果整理成手册时，再来这里生成即可。"
              />
            )}
          </Card>
        </Col>
      </Row>
    </Space>
  );
}

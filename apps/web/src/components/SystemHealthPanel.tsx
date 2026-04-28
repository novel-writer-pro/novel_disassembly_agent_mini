import { Alert, Card, Descriptions, Space, Tag, Typography } from "antd";
import type { ProviderHealth, RuntimeHealth } from "@/types/workbench";
import { providerDegraded, runtimeNeedsAttention, systemRecommendation } from "@/lib/formatters";

interface Props {
  runtimeHealth: RuntimeHealth | null;
  providerHealth: ProviderHealth | null;
  lastRefreshedAt?: string | null;
}

export default function SystemHealthPanel({ runtimeHealth, providerHealth, lastRefreshedAt }: Props) {
  if (!runtimeHealth && !providerHealth) {
    return (
      <Card title="系统健康面板" bordered={false} className="product-panel">
        <Alert
          type="info"
          showIcon
          message="暂未读取到运行时健康信息"
          description="当后端可用时，这里会显示 .cache 与历史 .omx 运行时文件的迁移/健康状态。"
        />
      </Card>
    );
  }

  const cacheHealthy = !runtimeNeedsAttention(runtimeHealth);
  const providerHealthy = !providerDegraded(providerHealth);
  const recommendation = systemRecommendation(providerHealth, runtimeHealth);

  return (
    <Card title="系统健康面板" bordered={false} className="product-panel">
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <Alert
          type={cacheHealthy && providerHealthy ? "success" : "warning"}
          showIcon
          message={cacheHealthy && providerHealthy ? "系统健康状态正常" : "系统存在需关注的健康信号"}
          description={`最近刷新：${lastRefreshedAt || "尚未刷新"}${runtimeHealth ? ` ｜ cache 根目录：${runtimeHealth.cache_root}` : ""}`}
        />
        {runtimeHealth ? (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="cache uploads">{runtimeHealth.cache_upload_files}</Descriptions.Item>
              <Descriptions.Item label="cache exports">{runtimeHealth.cache_export_files}</Descriptions.Item>
              <Descriptions.Item label="legacy uploads">{runtimeHealth.legacy_upload_files}</Descriptions.Item>
              <Descriptions.Item label="legacy exports">{runtimeHealth.legacy_export_files}</Descriptions.Item>
              <Descriptions.Item label="本次迁移">{runtimeHealth.migrated_this_run}</Descriptions.Item>
              <Descriptions.Item label="缺失文件">{runtimeHealth.missing_from_cache}</Descriptions.Item>
            </Descriptions>
            <Space wrap>
              <Tag color="blue">legacy: {runtimeHealth.legacy_root}</Tag>
              <Tag color={cacheHealthy ? "success" : "warning"}>
                {cacheHealthy ? "cache 已完整接管" : "建议继续检查迁移"}
              </Tag>
            </Space>
          </>
        ) : null}
        {providerHealth ? (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="provider">{providerHealth.provider_name}</Descriptions.Item>
              <Descriptions.Item label="model">{providerHealth.model_name}</Descriptions.Item>
              <Descriptions.Item label="最近状态">{providerHealth.last_status}</Descriptions.Item>
              <Descriptions.Item label="成功次数">{providerHealth.success_events}</Descriptions.Item>
              <Descriptions.Item label="降级次数">{providerHealth.degraded_events}</Descriptions.Item>
              <Descriptions.Item label="最近更新时间">{providerHealth.last_updated_at || "未知"}</Descriptions.Item>
            </Descriptions>
            {providerHealth.last_error ? (
              <Alert
                type={providerHealthy ? "info" : "warning"}
                showIcon
                message={providerHealthy ? "最近 provider 状态已恢复" : "最近 ask-stream 发生 provider 降级"}
                description={providerHealth.last_error}
              />
            ) : null}
          </>
        ) : null}
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          这个面板主要帮助判断：重启后遇到文件读取问题时，是否仍有旧 `.omx` 路径残留，`.cache/novel-analyzer` 是否已完全接管运行时文件，以及 ask-stream 最近是否因 provider 503 进入过降级状态。
        </Typography.Paragraph>
        <Alert
          type={cacheHealthy && providerHealthy ? "success" : "info"}
          showIcon
          message="当前建议"
          description={recommendation}
        />
      </Space>
    </Card>
  );
}

import { Alert, Card, Descriptions, Space, Tag, Typography } from "antd";
import type { RuntimeHealth } from "@/types/workbench";

interface Props {
  runtimeHealth: RuntimeHealth | null;
  lastRefreshedAt?: string | null;
}

export default function SystemHealthPanel({ runtimeHealth, lastRefreshedAt }: Props) {
  if (!runtimeHealth) {
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

  const healthy = runtimeHealth.missing_from_cache === 0;

  return (
    <Card title="系统健康面板" bordered={false} className="product-panel">
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <Alert
          type={healthy ? "success" : "warning"}
          showIcon
          message={healthy ? "运行时缓存状态正常" : "仍有历史运行时文件未完全迁移"}
          description={`最近刷新：${lastRefreshedAt || "尚未刷新"} ｜ cache 根目录：${runtimeHealth.cache_root}`}
        />
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
          <Tag color={healthy ? "success" : "warning"}>
            {healthy ? "cache 已完整接管" : "建议继续检查迁移"}
          </Tag>
        </Space>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          这个面板主要帮助判断：重启后遇到文件读取问题时，是否仍有旧 `.omx` 路径残留，或者 `.cache/novel-analyzer` 是否已完全接管运行时文件。
        </Typography.Paragraph>
      </Space>
    </Card>
  );
}

import { Alert, Space, Tag } from "antd";
import type { ProviderHealth, RuntimeHealth } from "@/types/workbench";
import { healthBannerSummary } from "@/lib/operations";

interface Props {
  runtimeHealth: RuntimeHealth | null;
  providerHealth: ProviderHealth | null;
  autoRefreshEnabled: boolean;
  lastRefreshedAt?: string | null;
}

export default function SystemStatusBar({ runtimeHealth, providerHealth, autoRefreshEnabled, lastRefreshedAt }: Props) {
  const banner = healthBannerSummary(providerHealth, runtimeHealth, autoRefreshEnabled);

  return (
    <Alert
      type={banner.type}
      showIcon
      message={banner.headline}
      description={(
        <Space wrap>
          <Tag color={providerHealth?.last_status === "degraded" ? "warning" : "success"}>
            provider: {banner.providerTag}
          </Tag>
          <Tag color={banner.cacheTag === "待迁移" ? "warning" : "success"}>
            cache: {banner.cacheTag}
          </Tag>
          <Tag color={banner.refreshTag === "退避刷新" ? "warning" : autoRefreshEnabled ? "processing" : "default"}>
            {banner.refreshTag}
          </Tag>
          {lastRefreshedAt ? <Tag>最近刷新 {lastRefreshedAt}</Tag> : null}
          <Tag>{banner.recommendation}</Tag>
        </Space>
      )}
    />
  );
}

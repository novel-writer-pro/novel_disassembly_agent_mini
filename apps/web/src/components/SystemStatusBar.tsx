import { Alert, Space, Tag } from "antd";
import type { ProviderHealth, RuntimeHealth } from "@/types/workbench";

interface Props {
  runtimeHealth: RuntimeHealth | null;
  providerHealth: ProviderHealth | null;
  autoRefreshEnabled: boolean;
  lastRefreshedAt?: string | null;
}

export default function SystemStatusBar({ runtimeHealth, providerHealth, autoRefreshEnabled, lastRefreshedAt }: Props) {
  const providerDegraded = providerHealth?.last_status === "degraded";
  const runtimeNeedsAttention = runtimeHealth ? runtimeHealth.missing_from_cache > 0 : false;
  const refreshPolicy = providerDegraded ? "退避刷新" : autoRefreshEnabled ? "自动刷新开启" : "自动刷新关闭";

  return (
    <Alert
      type={providerDegraded || runtimeNeedsAttention ? "warning" : "success"}
      showIcon
      message={providerDegraded ? "问答服务当前处于降级期" : runtimeNeedsAttention ? "运行时缓存仍有待迁移内容" : "系统状态稳定"}
      description={(
        <Space wrap>
          <Tag color={providerDegraded ? "warning" : "success"}>
            provider: {providerHealth?.last_status || "unknown"}
          </Tag>
          <Tag color={runtimeNeedsAttention ? "warning" : "success"}>
            cache: {runtimeNeedsAttention ? "待迁移" : "正常"}
          </Tag>
          <Tag color={providerDegraded ? "warning" : autoRefreshEnabled ? "processing" : "default"}>
            {refreshPolicy}
          </Tag>
          {lastRefreshedAt ? <Tag>最近刷新 {lastRefreshedAt}</Tag> : null}
        </Space>
      )}
    />
  );
}

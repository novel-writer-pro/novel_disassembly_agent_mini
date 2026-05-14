import { useEffect, useState } from "react";
import { Alert } from "antd";

interface Props {
  branchId: string;
  userId?: string;
}

const DIFY_BASE = process.env.NEXT_PUBLIC_DIFY_BASE_URL || "http://localhost:8080";
const DIFY_TOKEN = process.env.NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN || "";

export default function CopilotIframe({ branchId, userId = "local-default" }: Props) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!DIFY_TOKEN) {
      setError("NEXT_PUBLIC_DIFY_WRITER_COPILOT_TOKEN 未配置");
    }
  }, []);

  if (error) {
    return (
      <Alert
        type="warning"
        message={error}
        description="完成 N4 Dify 应用配置后，把 token 填到 .env.local"
        showIcon
      />
    );
  }

  const params = new URLSearchParams({ branch_id: branchId, user_id: userId });
  const src = `${DIFY_BASE}/chat/${DIFY_TOKEN}?${params.toString()}`;

  return (
    <iframe
      title="Writer Copilot"
      data-testid="copilot-iframe"
      src={src}
      style={{ width: "100%", height: "calc(100vh - 220px)", border: "none" }}
      allow="microphone"
    />
  );
}

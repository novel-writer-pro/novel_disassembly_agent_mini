import { useEffect, useState } from "react";
import { Alert, Empty, Space, Spin, Tag, Typography } from "antd";
import { fetchLoomSignals } from "@/lib/loom-api";
import type { LoomSignals } from "@/types/loom";

interface Props {
  branchId: string;
  chapterIndex: number;
  apiBase?: string;
}

function pickColor(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "default";
  if (value < 0.3) return "red";
  if (value < 0.6) return "gold";
  return "green";
}

function pickNumeric(group: Record<string, any> | undefined): number | null {
  if (!group) return null;
  const candidates = ["score", "value", "fidelity", "match", "intensity", "density", "overall"];
  for (const key of candidates) {
    const v = group[key];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  for (const v of Object.values(group)) {
    if (typeof v === "number" && Number.isFinite(v)) return v as number;
  }
  return null;
}

export default function LoomSignalsPanel({ branchId, chapterIndex, apiBase = "" }: Props) {
  const [signals, setSignals] = useState<LoomSignals | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchLoomSignals(apiBase, branchId, chapterIndex)
      .then((s) => {
        if (!cancelled) setSignals(s);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase, branchId, chapterIndex]);

  if (loading) return <Spin />;
  if (error) return <Alert type="warning" message="信号暂不可用" description={error} showIcon />;
  if (!signals) return <Empty description="无信号数据" />;

  const groups: Array<[string, Record<string, any> | undefined]> = [
    ["节奏", signals.rhythm],
    ["张力", signals.tension],
    ["风格", signals.style],
    ["对照保真", signals.reference_fidelity],
    ["对话", signals.dialogue],
    ["章节质量", signals.chapter_quality],
  ];

  return (
    <div data-testid="loom-panel">
      <Typography.Title level={5}>第 {chapterIndex} 章 · Loom 信号</Typography.Title>
      <Space direction="vertical" style={{ width: "100%" }}>
        {groups.map(([label, group]) => {
          const value = pickNumeric(group);
          return (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <Typography.Text>{label}</Typography.Text>
              <Tag color={pickColor(value)} data-testid={`loom-${label}`}>
                {value == null ? "N/A" : value.toFixed(2)}
              </Tag>
            </div>
          );
        })}
      </Space>
    </div>
  );
}

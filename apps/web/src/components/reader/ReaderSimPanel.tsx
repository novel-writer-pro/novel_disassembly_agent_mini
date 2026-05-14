import { useEffect, useState } from "react";
import { Card, Col, Progress, Row, Space, Spin, Tag, Typography } from "antd";
import { fetchLoomSignals } from "@/lib/loom-api";
import type { LoomSignals } from "@/types/loom";

interface ReaderSimSignal {
  panel_type: string;
  score: number;
  alert_level: string;
  feedback: string;
}

interface ReaderSim {
  overall_score: number;
  alert_level: string;
  suggestion: string;
  panels: ReaderSimSignal[];
}

interface Props {
  apiBase: string;
  branchId: string;
  chapterIndex: number;
  databaseUrl?: string;
}

const PANEL_LABELS: Record<string, string> = {
  casual: "普通读者",
  veteran: "资深读者",
  satisfaction: "情感满足",
  editor: "编辑视角",
};

function alertColor(level: string): string {
  if (level === "critical") return "red";
  if (level === "warn") return "orange";
  return "green";
}

export default function ReaderSimPanel({ apiBase, branchId, chapterIndex, databaseUrl }: Props) {
  const [readerSim, setReaderSim] = useState<ReaderSim | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchLoomSignals(apiBase, branchId, chapterIndex)
      .then((signals: LoomSignals & { reader_sim?: ReaderSim }) => {
        if (!cancelled && signals.reader_sim) {
          setReaderSim(signals.reader_sim);
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [apiBase, branchId, chapterIndex]);

  if (loading) return <Spin size="small" />;
  if (!readerSim) return null;

  return (
    <Card
      data-testid="reader-sim-panel"
      size="small"
      title={
        <Space>
          <Typography.Text strong>读者体验评分</Typography.Text>
          <Tag color={alertColor(readerSim.alert_level)}>
            {(readerSim.overall_score * 100).toFixed(0)}分
          </Tag>
        </Space>
      }
      extra={
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          {readerSim.suggestion}
        </Typography.Text>
      }
    >
      <Row gutter={[8, 8]}>
        {readerSim.panels.map((panel) => (
          <Col span={12} key={panel.panel_type}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                <Typography.Text style={{ fontSize: 12 }}>
                  {PANEL_LABELS[panel.panel_type] || panel.panel_type}
                </Typography.Text>
                <Tag color={alertColor(panel.alert_level)} style={{ fontSize: 11, padding: "0 4px" }}>
                  {(panel.score * 100).toFixed(0)}
                </Tag>
              </div>
              <Progress
                percent={Math.round(panel.score * 100)}
                showInfo={false}
                size="small"
                strokeColor={panel.alert_level === "warn" ? "#faad14" : panel.alert_level === "critical" ? "#ff4d4f" : "#52c41a"}
              />
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                {panel.feedback}
              </Typography.Text>
            </div>
          </Col>
        ))}
      </Row>
    </Card>
  );
}

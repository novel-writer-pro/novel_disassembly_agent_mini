import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Tag, Progress, Descriptions, Alert } from "antd";
import WorkbenchLayout from "@/components/WorkbenchLayout";
import { fetchQualityHealth, fetchQualityTrend, fetchPairsStats } from "@/lib/loom-api";
import type { QualityHealth, QualityTrend, PairsStats } from "@/types/loom";
import { useWorkbenchState } from "@/hooks/useWorkbenchState";
import { useRouter } from "next/router";

export default function QualityPage() {
  const { state } = useWorkbenchState();
  const apiBase = state.apiBase;
  const branchId = state.branchId;
  const router = useRouter();

  const [health, setHealth] = useState<QualityHealth | null>(null);
  const [trend, setTrend] = useState<QualityTrend | null>(null);
  const [pairs, setPairs] = useState<PairsStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!apiBase || !branchId) return;
    setLoading(true);
    Promise.all([
      fetchQualityHealth(apiBase, branchId).catch(() => null),
      fetchQualityTrend(apiBase, branchId).catch(() => null),
      fetchPairsStats(apiBase).catch(() => null),
    ]).then(([h, t, p]) => {
      setHealth(h);
      setTrend(t);
      setPairs(p);
      setLoading(false);
    });
  }, [apiBase, branchId]);

  const healthColor = (score: number) => {
    if (score >= 0.7) return "#52c41a";
    if (score >= 0.5) return "#faad14";
    return "#f5222d";
  };

  const trendTag = (t: string) => {
    if (t === "declining") return <Tag color="red">下滑</Tag>;
    if (t === "recovering") return <Tag color="green">恢复</Tag>;
    return <Tag color="blue">稳定</Tag>;
  };

  return (
    <WorkbenchLayout
      activeKey="quality"
      chapterMenu={null}
      onNavigate={(key) => router.push(`/${key}`)}
      currentNovelTitle={state.title || undefined}
      currentBranchId={branchId || undefined}
    >
      <div style={{ padding: 24 }}>
        <Row gutter={[16, 16]}>
          <Col span={6}>
            <Card loading={loading}>
              <Statistic
                title="整书健康度"
                value={health?.health_score ?? "-"}
                precision={4}
                valueStyle={{ color: health ? healthColor(health.health_score) : undefined }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card loading={loading}>
              <Statistic title="质量趋势" value={trend?.quality_trend ?? "-"} prefix={trend ? trendTag(trend.quality_trend) : null} />
            </Card>
          </Col>
          <Col span={6}>
            <Card loading={loading}>
              <Statistic title="当前章节" value={health?.as_of_chapter ?? "-"} />
            </Card>
          </Col>
          <Col span={6}>
            <Card loading={loading}>
              <Statistic title="Alert" value={health?.alert_level ?? "none"} />
            </Card>
          </Col>
        </Row>

        {health?.suggestion && (
          <Alert message="质量建议" description={health.suggestion} type="warning" showIcon style={{ marginTop: 16 }} />
        )}

        <Card title="Pairwise 数据积累" style={{ marginTop: 16 }} loading={loading}>
          {pairs && (
            <>
              <Progress
                percent={pairs.progress_pct}
                format={() => `${pairs.total_pairs} / ${pairs.target}`}
                status={pairs.progress_pct >= 100 ? "success" : "active"}
              />
              <Descriptions column={3} style={{ marginTop: 16 }}>
                <Descriptions.Item label="平均质量分">{pairs.avg_quality_score?.toFixed(4) ?? "N/A"}</Descriptions.Item>
                <Descriptions.Item label="覆盖章节">{pairs.unique_chapters}</Descriptions.Item>
                <Descriptions.Item label="章节范围">{pairs.chapter_range || "N/A"}</Descriptions.Item>
                <Descriptions.Item label="评估方法">
                  {Object.entries(pairs.evaluation_method_distribution || {}).map(([k, v]) => (
                    <Tag key={k}>{k}: {v}</Tag>
                  ))}
                </Descriptions.Item>
                <Descriptions.Item label="偏好分布">
                  {Object.entries(pairs.preference_distribution || {}).map(([k, v]) => (
                    <Tag key={k} color={k === "B" ? "green" : k === "A" ? "blue" : "default"}>{k}: {v}</Tag>
                  ))}
                </Descriptions.Item>
              </Descriptions>
            </>
          )}
        </Card>

        <Card title="近期质量分数" style={{ marginTop: 16 }} loading={loading}>
          {trend?.recent_quality_scores && trend.recent_quality_scores.length > 0 ? (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {trend.recent_quality_scores.map((score, i) => (
                <Tag key={i} color={score >= 0.7 ? "green" : score >= 0.5 ? "gold" : "red"}>
                  {score.toFixed(3)}
                </Tag>
              ))}
            </div>
          ) : (
            <span>暂无数据</span>
          )}
        </Card>
      </div>
    </WorkbenchLayout>
  );
}

export async function getServerSideProps() {
  return { props: {} };
}

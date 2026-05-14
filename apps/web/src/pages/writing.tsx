import { useEffect, useState } from "react";
import { Button, Card, Col, Descriptions, Input, Row, Select, Space, Spin, Tag, message } from "antd";
import WorkbenchLayout from "@/components/WorkbenchLayout";
import { fetchLoomSignals, fetchLoomAssemble, postWriterImitate } from "@/lib/loom-api";
import type { LoomSignals, LoomAssembleResult, WriterImitateResult } from "@/types/loom";
import { useWorkbenchState } from "@/hooks/useWorkbenchState";
import { useRouter } from "next/router";

function SignalTag({ label, value, warn }: { label: string; value: number | null | undefined; warn?: number }) {
  if (value == null) return <Tag>{label}: N/A</Tag>;
  const color = warn && value < warn ? "red" : value < 0.5 ? "gold" : "green";
  return <Tag color={color}>{label}: {value.toFixed(3)}</Tag>;
}

export default function WritingPage() {
  const { state } = useWorkbenchState();
  const apiBase = state.apiBase;
  const branchId = state.branchId;
  const router = useRouter();

  const [chapterIndex, setChapterIndex] = useState(2);
  const [targetGoal, setTargetGoal] = useState("");
  const [useLlm, setUseLlm] = useState(false);
  const [loomEnabled, setLoomEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WriterImitateResult | null>(null);
  const [signals, setSignals] = useState<LoomSignals | null>(null);
  const [carryOver, setCarryOver] = useState<LoomAssembleResult | null>(null);

  const loadSignals = async () => {
    if (!apiBase || !branchId) return;
    try {
      const [sig, co] = await Promise.all([
        fetchLoomSignals(apiBase, branchId, chapterIndex),
        fetchLoomAssemble(apiBase, branchId, chapterIndex + 1),
      ]);
      setSignals(sig);
      setCarryOver(co);
    } catch (e: any) {
      message.error(e.message);
    }
  };

  const runImitate = async () => {
    if (!apiBase || !branchId || !targetGoal) {
      message.warning("请填写章节目标");
      return;
    }
    setLoading(true);
    try {
      const res = await postWriterImitate(apiBase, {
        branch_id: branchId,
        chapter_index: chapterIndex,
        target_goal: targetGoal,
        use_llm: useLlm,
        loom_memory_mode: loomEnabled ? "enabled" : "shadow",
        loom_pairwise_enabled: true,
        loom_style_enabled: true,
        loom_character_enabled: true,
      });
      setResult(res);
      message.success("仿写完成");
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSignals();
  }, [apiBase, branchId, chapterIndex]);

  return (
    <WorkbenchLayout
      activeKey="writing"
      chapterMenu={null}
      onNavigate={(key) => router.push(`/${key}`)}
      currentNovelTitle={state.title || undefined}
      currentBranchId={branchId || undefined}
    >
      <div style={{ padding: 24 }}>
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space wrap>
            <span>章节：</span>
            <Input
              type="number"
              value={chapterIndex}
              onChange={(e) => setChapterIndex(Number(e.target.value))}
              style={{ width: 80 }}
            />
            <span>目标：</span>
            <Input
              value={targetGoal}
              onChange={(e) => setTargetGoal(e.target.value)}
              placeholder="本章仿写目标"
              style={{ width: 300 }}
            />
            <Select value={useLlm ? "llm" : "skeleton"} onChange={(v) => setUseLlm(v === "llm")} style={{ width: 120 }}>
              <Select.Option value="skeleton">Skeleton</Select.Option>
              <Select.Option value="llm">LLM 正文</Select.Option>
            </Select>
            <Select value={loomEnabled ? "enabled" : "shadow"} onChange={(v) => setLoomEnabled(v === "enabled")} style={{ width: 140 }}>
              <Select.Option value="enabled">Loom 启用</Select.Option>
              <Select.Option value="shadow">Loom 关闭</Select.Option>
            </Select>
            <Button type="primary" onClick={runImitate} loading={loading}>生成仿写</Button>
            <Button onClick={loadSignals}>刷新信号</Button>
          </Space>
        </Card>

        <Row gutter={16}>
          <Col span={14}>
            <Card title={result ? `仿写结果 — ${result.final_draft.draft_title}` : "仿写结果"} style={{ minHeight: 400 }}>
              {loading && <Spin tip="生成中..." />}
              {result && !loading && (
                <>
                  <Space style={{ marginBottom: 12 }}>
                    <Tag color={result.final_verdict === "pass" ? "green" : "orange"}>{result.final_verdict}</Tag>
                    <Tag>轮次: {result.rounds_count}</Tag>
                    <Tag>动作: {result.action_queue_count}</Tag>
                  </Space>
                  <div style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.8, maxHeight: 500, overflow: "auto", background: "#fafafa", padding: 16, borderRadius: 8 }}>
                    {result.final_draft.draft_text}
                  </div>
                </>
              )}
              {!result && !loading && <span style={{ color: "#999" }}>点击"生成仿写"开始</span>}
            </Card>
          </Col>

          <Col span={10}>
            <Card title="Loom 信号" size="small" style={{ marginBottom: 16 }}>
              {signals ? (
                <Space wrap>
                  <SignalTag label="tension" value={signals.tension?.tension_score} warn={0.4} />
                  <SignalTag label="hook" value={signals.rhythm?.hook_density} />
                  <SignalTag label="style_drift" value={signals.style?.style_drift_score} />
                  <SignalTag label="reader_sim" value={signals.reader_sim?.overall_score} warn={0.5} />
                  <SignalTag label="fidelity" value={signals.reference_fidelity?.overall_fidelity} warn={0.5} />
                </Space>
              ) : (
                <span style={{ color: "#999" }}>加载中...</span>
              )}
            </Card>

            {result?.chapter_quality_signal && Object.keys(result.chapter_quality_signal).length > 0 && (
              <Card title="章节质量" size="small" style={{ marginBottom: 16 }}>
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="评估方法">{result.chapter_quality_signal.evaluation_method}</Descriptions.Item>
                  <Descriptions.Item label="质量分">{result.chapter_quality_signal.quality_score}</Descriptions.Item>
                  <Descriptions.Item label="偏好">{result.chapter_quality_signal.overall_preference}</Descriptions.Item>
                </Descriptions>
              </Card>
            )}

            <Card title="记忆上下文" size="small" style={{ marginBottom: 16 }}>
              {carryOver ? (
                <>
                  <p style={{ fontSize: 12, color: "#666" }}>
                    活跃角色: {carryOver.working_memory.active_characters.slice(0, 5).map(c => c.label).join(", ")}
                  </p>
                  <p style={{ fontSize: 12, color: "#666" }}>
                    未解线索: {carryOver.working_memory.active_threads.slice(0, 3).map(t => t.label).join("; ")}
                  </p>
                  <p style={{ fontSize: 12, color: "#666" }}>
                    前情: {carryOver.working_memory.recent_summary.slice(0, 100)}...
                  </p>
                </>
              ) : (
                <span style={{ color: "#999" }}>加载中...</span>
              )}
            </Card>

            {signals?.reference_fidelity?.dimensions && (
              <Card title="还原度详情" size="small">
                <Descriptions column={1} size="small" bordered>
                  {Object.entries(signals.reference_fidelity.dimensions).map(([k, v]: [string, any]) => (
                    <Descriptions.Item key={k} label={k.replace("_fidelity", "").replace("_", " ")}>
                      <Tag color={v.score >= 0.7 ? "green" : v.score >= 0.4 ? "gold" : "red"}>
                        {v.score?.toFixed(2)}
                      </Tag>
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              </Card>
            )}
          </Col>
        </Row>
      </div>
    </WorkbenchLayout>
  );
}

export async function getServerSideProps() {
  return { props: {} };
}

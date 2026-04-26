import {
  Alert,
  Card,
  Col,
  Descriptions,
  Divider,
  List,
  Modal,
  Row,
  Space,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import type { ChapterBundle, ChapterQaContext, ChapterSource } from "@/types/workbench";

interface Props {
  bundle: ChapterBundle | null;
  qa: ChapterQaContext | null;
  source: ChapterSource | null;
  loading?: boolean;
  onJumpChapter: (chapterIndex: number) => void;
}

type DataModalState = { title: string; kind: "bundle" | "qa" } | null;

const jumpify = (text: string, onJumpChapter: (chapterIndex: number) => void) => {
  const parts = text.split(/(第\d+章)/g);
  return parts.map((part, index) => {
    const match = part.match(/^第(\d+)章$/);
    if (!match) return <span key={`${part}-${index}`}>{part}</span>;
    const chapterIndex = Number(match[1]);
    return (
      <a
        key={`${part}-${index}`}
        className="chapter-inline-link"
        onClick={(event) => {
          event.preventDefault();
          onJumpChapter(chapterIndex);
        }}
        href="#"
      >
        {part}
      </a>
    );
  });
};

const renderJumpList = (items: unknown[], onJumpChapter: (chapterIndex: number) => void, emptyText: string) =>
  items.length ? (
    <List
      split={false}
      dataSource={items}
      renderItem={(item, index) => (
        <List.Item className="reader-list-item">
          <span className="reader-list-index">{String(index + 1).padStart(2, "0")}</span>
          <span className="reader-list-content">{jumpify(String(item), onJumpChapter)}</span>
        </List.Item>
      )}
    />
  ) : (
    <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
      {emptyText}
    </Typography.Paragraph>
  );

const highlightSourceText = (
  sourceText: string,
  {
    entities,
    events,
    continuity,
  }: { entities: string[]; events: string[]; continuity: string[] },
) => {
  const escapeHtml = (value: string) =>
    value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const wrapMatches = (input: string, items: string[], cssClass: string) => {
    let output = input;
    [...items]
      .filter(Boolean)
      .sort((a, b) => b.length - a.length)
      .forEach((item) => {
        const escaped = item.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        output = output.replace(
          new RegExp(escaped, "g"),
          `<mark class="source-mark ${cssClass}">${escapeHtml(item)}</mark>`,
        );
      });
    return output;
  };

  let html = escapeHtml(sourceText);
  html = wrapMatches(html, entities, "entity");
  html = wrapMatches(html, events, "event");
  html = wrapMatches(html, continuity, "continuity");
  return html;
};

function ReaderMetric({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card bordered={false} className="reader-metric-card">
      <Typography.Text className="reader-metric-label">{label}</Typography.Text>
      <Typography.Title level={3} style={{ margin: "10px 0 6px" }}>
        {value}
      </Typography.Title>
      {hint ? (
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          {hint}
        </Typography.Paragraph>
      ) : null}
    </Card>
  );
}

function InsightCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <Card title={title} bordered={false} className="reader-insight-card">
      {subtitle ? (
        <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
          {subtitle}
        </Typography.Paragraph>
      ) : null}
      {children}
    </Card>
  );
}

function ChapterDataModal({
  state,
  bundle,
  qa,
  onJumpChapter,
  onClose,
}: {
  state: DataModalState;
  bundle: ChapterBundle;
  qa: ChapterQaContext;
  onJumpChapter: (chapterIndex: number) => void;
  onClose: () => void;
}) {
  const artifact = bundle.artifact || {};
  const sourceObject = state?.kind === "bundle" ? bundle : qa;
  const title = state?.kind === "bundle" ? artifact.normalized_title || `第${bundle.chapter_index}章` : qa.title || `第${qa.chapter_index}章`;

  return (
    <Modal open={Boolean(state)} onCancel={onClose} footer={null} width={1080} title={state?.title}>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Card bordered={false} className="reader-modal-hero">
          <Typography.Text type="secondary">章节细节总览</Typography.Text>
          <Typography.Title level={4} style={{ marginTop: 8, marginBottom: 8 }}>
            {title}
          </Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            这里展示的是系统整理后的结构信息，已经转为可直接阅读的分类视图，便于核对人物、事件、状态和追问方向。
          </Typography.Paragraph>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} md={8}>
            <ReaderMetric label="关键人物" value={(artifact.key_entities || qa.key_events || []).length} />
          </Col>
          <Col xs={24} md={8}>
            <ReaderMetric label="关键事件" value={(artifact.key_events || qa.key_events || []).length} />
          </Col>
          <Col xs={24} md={8}>
            <ReaderMetric label="未解决线索" value={(artifact.unresolved_threads || qa.unresolved_threads || []).length} />
          </Col>
        </Row>

        <Tabs
          defaultActiveKey="overview"
          items={[
            {
              key: "overview",
              label: "总览",
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={12}>
                    <InsightCard title="基础信息">
                      <Descriptions column={1} size="small">
                        <Descriptions.Item label="标题">{title}</Descriptions.Item>
                        <Descriptions.Item label="章节编号">{bundle.chapter_index}</Descriptions.Item>
                        <Descriptions.Item label="人工复核">
                          {artifact.needs_human_review ? <Tag color="warning">建议复核</Tag> : <Tag color="success">可直接使用</Tag>}
                        </Descriptions.Item>
                      </Descriptions>
                    </InsightCard>
                  </Col>
                  <Col xs={24} lg={12}>
                    <InsightCard title="本章摘要">
                      <Typography.Paragraph style={{ marginBottom: 0, lineHeight: 1.9 }}>
                        {artifact.chapter_summary || qa.chapter_summary || "暂无摘要。"}
                      </Typography.Paragraph>
                    </InsightCard>
                  </Col>
                </Row>
              ),
            },
            {
              key: "character",
              label: "人物与事件",
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={10}>
                    <InsightCard title="关键人物" subtitle="先确认这一章主要围绕谁展开。">
                      <Space wrap>
                        {(artifact.key_entities || []).length
                          ? (artifact.key_entities || []).map((item: string) => <Tag key={item}>{item}</Tag>)
                          : <Tag>暂无</Tag>}
                      </Space>
                    </InsightCard>
                  </Col>
                  <Col xs={24} lg={14}>
                    <InsightCard title="关键事件" subtitle="按阅读顺序整理，点击章节引用可跳转。">
                      {renderJumpList(artifact.key_events || qa.key_events || [], onJumpChapter, "暂无关键事件。")}
                    </InsightCard>
                  </Col>
                </Row>
              ),
            },
            {
              key: "state",
              label: "线索与状态",
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={12}>
                    <InsightCard title="未解决线索" subtitle="这些内容最适合后续创作时继续追踪。">
                      {renderJumpList(
                        artifact.unresolved_threads || qa.unresolved_threads || [],
                        onJumpChapter,
                        "当前没有明显未解决线索。",
                      )}
                    </InsightCard>
                  </Col>
                  <Col xs={24} lg={12}>
                    <InsightCard title="已解决与衔接" subtitle="便于快速回忆本章与前后文的关系。">
                      {renderJumpList(
                        [...(artifact.evidence_backed_resolutions || qa.evidence_backed_resolutions || []), ...(artifact.continuity_notes || qa.state_transition_notes || [])],
                        onJumpChapter,
                        "暂无可展示的衔接与已解决内容。",
                      )}
                    </InsightCard>
                  </Col>
                </Row>
              ),
            },
            {
              key: "qa",
              label: "追问与推理",
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} lg={12}>
                    <InsightCard title="推荐追问" subtitle="适合继续深挖章节时直接使用。">
                      {renderJumpList(qa.recommended_questions || [], onJumpChapter, "暂无推荐追问。")}
                    </InsightCard>
                  </Col>
                  <Col xs={24} lg={12}>
                    <InsightCard title="推理路径" subtitle="这里展示系统如何连接信息与结论。">
                      {renderJumpList((qa.reasoning_graph && qa.reasoning_graph.reasoning_paths) || [], onJumpChapter, "暂无推理路径。")}
                    </InsightCard>
                  </Col>
                </Row>
              ),
            },
            {
              key: "raw",
              label: "原始结构",
              children: (
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                  如需调试，可查看原始结构对象：
                  <pre style={{ whiteSpace: "pre-wrap", overflow: "auto", maxHeight: "48vh", marginTop: 12 }}>
                    {JSON.stringify(sourceObject, null, 2)}
                  </pre>
                </Typography.Paragraph>
              ),
            },
          ]}
        />
      </Space>
    </Modal>
  );
}

export default function ReaderPage({ bundle, qa, source, loading, onJumpChapter }: Props) {
  const [dataModal, setDataModal] = useState<DataModalState>(null);

  const artifact = bundle?.artifact || {};
  const stateSummary = bundle?.state_summary || {};
  const facts = bundle?.facts || [];
  const entities = artifact.key_entities || [];
  const events = artifact.key_events || [];
  const continuity = artifact.continuity_notes || [];
  const unresolvedThreads = artifact.unresolved_threads || [];
  const resolvedLines = artifact.evidence_backed_resolutions || [];
  const recommendedQuestions = qa?.recommended_questions || [];

  const stateLines = useMemo(
    () =>
      Object.entries(stateSummary).flatMap(([key, value]) =>
        Array.isArray(value) ? value.map((item) => `${key}: ${item}`) : [`${key}: ${value}`],
      ),
    [stateSummary],
  );

  if (!bundle || !qa || !source) {
    return (
      <Card bordered={false} style={{ borderColor: "#284267" }}>
        <Typography.Paragraph style={{ color: "#9bb2d1", marginBottom: 0 }}>
          {loading ? "正在加载章节内容…" : "请选择左侧章节，右侧会显示整理后的阅读卡片。"}
        </Typography.Paragraph>
      </Card>
    );
  }

  return (
    <>
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Card bordered={false} className="reader-hero-card">
          <Space direction="vertical" size="large" style={{ width: "100%" }}>
            <Space wrap align="center" style={{ justifyContent: "space-between", width: "100%" }}>
              <div>
                <Typography.Text className="reader-eyebrow">章节阅读卡</Typography.Text>
                <Typography.Title level={2} style={{ margin: "8px 0 4px" }}>
                  {artifact.normalized_title || `第${bundle.chapter_index}章`}
                </Typography.Title>
                <Typography.Paragraph type="secondary" style={{ marginBottom: 0, maxWidth: 860 }}>
                  先把握本章总述，再看人物、事件和线索，最后回到原文确认关键表达。整个页面都围绕“作家回看这一章时最关心什么”来组织。
                </Typography.Paragraph>
              </div>
              <Space wrap>
                {artifact.needs_human_review ? <Tag color="warning">建议复核</Tag> : <Tag color="success">可直接参考</Tag>}
                {artifact.hook_score !== undefined ? <Tag color="processing">吸引度 {artifact.hook_score}</Tag> : null}
                <Tag color="blue">{facts.length} 条事实</Tag>
              </Space>
            </Space>

            <Row gutter={[16, 16]}>
              <Col xs={24} md={12} xl={7}>
                <ReaderMetric label="本章总述" value={<span style={{ fontSize: 16 }}>{artifact.chapter_summary || "暂无摘要"}</span>} />
              </Col>
              <Col xs={12} md={6} xl={4}>
                <ReaderMetric label="关键人物" value={entities.length} hint="用于快速回忆出场角色" />
              </Col>
              <Col xs={12} md={6} xl={4}>
                <ReaderMetric label="关键事件" value={events.length} hint="本章推进了几件大事" />
              </Col>
              <Col xs={12} md={6} xl={4}>
                <ReaderMetric label="未解决线索" value={unresolvedThreads.length} hint="后续最值得追踪" />
              </Col>
              <Col xs={12} md={6} xl={5}>
                <ReaderMetric label="推荐追问" value={recommendedQuestions.length} hint="继续深挖这一章" />
              </Col>
            </Row>
          </Space>
        </Card>

        <Tabs
          defaultActiveKey="overview"
          className="reader-tabs"
          items={[
            {
              key: "overview",
              label: "阅读提要",
              children: (
                <Space direction="vertical" size="large" style={{ width: "100%" }}>
                  <Alert
                    type="info"
                    showIcon
                    message="建议阅读顺序"
                    description="先看本章总述，再看关键事件与未解决线索，最后回看原始正文中的关键表述。"
                  />
                  <Row gutter={[16, 16]}>
                    <Col xs={24} xl={14}>
                      <InsightCard title="这一章主要讲了什么" subtitle="适合先看，用来迅速进入本章状态。">
                        <Typography.Paragraph style={{ marginBottom: 0, lineHeight: 1.95, fontSize: 16 }}>
                          {artifact.chapter_summary || "暂无本章摘要。"}
                        </Typography.Paragraph>
                      </InsightCard>
                    </Col>
                    <Col xs={24} xl={10}>
                      <InsightCard title="这章最该盯住的地方" subtitle="创作回看时，优先关注这些点。">
                        {renderJumpList(
                          unresolvedThreads,
                          onJumpChapter,
                          "当前没有明显未解决线索，可以重点回看人物变化与事件落点。",
                        )}
                      </InsightCard>
                    </Col>
                  </Row>
                  <Row gutter={[16, 16]}>
                    <Col xs={24} lg={10}>
                      <InsightCard title="本章人物" subtitle="帮助你快速进入角色关系与场景。">
                        <Space wrap>
                          {entities.length ? entities.map((item: string) => <Tag key={item}>{item}</Tag>) : <Tag>暂无</Tag>}
                        </Space>
                      </InsightCard>
                    </Col>
                    <Col xs={24} lg={14}>
                      <InsightCard title="本章关键事件" subtitle="按阅读习惯整理，章节引用支持直接跳转。">
                        {renderJumpList(events, onJumpChapter, "暂无关键事件。")}
                      </InsightCard>
                    </Col>
                  </Row>
                </Space>
              ),
            },
            {
              key: "clues",
              label: "人物 / 线索",
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} xl={12}>
                    <InsightCard title="章节衔接" subtitle="帮助确认这一章与前文是怎么接上的。">
                      {renderJumpList(continuity, onJumpChapter, "暂无章节衔接说明。")}
                    </InsightCard>
                  </Col>
                  <Col xs={24} xl={12}>
                    <InsightCard title="已解决 / 未解决" subtitle="一眼看出哪些点已经落地，哪些点还要继续埋。">
                      {renderJumpList([...resolvedLines, ...unresolvedThreads], onJumpChapter, "暂无可展示线索。")}
                    </InsightCard>
                  </Col>
                  <Col xs={24} xl={12}>
                    <InsightCard title="专题状态摘要" subtitle="适合检查人物线、冲突线、伏笔线与规则线。">
                      {renderJumpList(stateLines, onJumpChapter, "暂无状态摘要。")}
                    </InsightCard>
                  </Col>
                  <Col xs={24} xl={12}>
                    <InsightCard title="本章事实层" subtitle="适合回收可引用事实与标签。">
                      {renderJumpList(
                        facts.map((item) => `${item.fact_type}: ${item.label}`),
                        onJumpChapter,
                        "暂无事实记录。",
                      )}
                    </InsightCard>
                  </Col>
                </Row>
              ),
            },
            {
              key: "qa",
              label: "追问 / 推理",
              children: (
                <Row gutter={[16, 16]}>
                  <Col xs={24} xl={12}>
                    <InsightCard title="推荐追问" subtitle="继续拆章、复盘角色或续写时可直接参考。">
                      {renderJumpList(recommendedQuestions, onJumpChapter, "暂无推荐追问。")}
                    </InsightCard>
                  </Col>
                  <Col xs={24} xl={12}>
                    <InsightCard title="推理路径" subtitle="查看这一章的结论是如何被串起来的。">
                      {renderJumpList((qa.reasoning_graph && qa.reasoning_graph.reasoning_paths) || [], onJumpChapter, "暂无推理路径。")}
                    </InsightCard>
                  </Col>
                  <Col xs={24}>
                    <InsightCard title="检索关键词" subtitle="如果你要继续追查人物、事件或伏笔，可以从这些词开始。">
                      <Space wrap>
                        {((bundle.retrieval && bundle.retrieval.keyword_list) || []).length ? (
                          ((bundle.retrieval && bundle.retrieval.keyword_list) || []).map((item: string) => (
                            <Tag key={item} color="processing">
                              {item}
                            </Tag>
                          ))
                        ) : (
                          <Tag>暂无</Tag>
                        )}
                      </Space>
                    </InsightCard>
                  </Col>
                </Row>
              ),
            },
            {
              key: "source",
              label: "原文回看",
              children: (
                <Card
                  bordered={false}
                  className="reader-source-card"
                  extra={
                    <Space>
                      <a onClick={() => setDataModal({ title: "拆书结构细节", kind: "bundle" })}>拆书结构细节</a>
                      <a onClick={() => setDataModal({ title: "问答与推理细节", kind: "qa" })}>问答与推理细节</a>
                    </Space>
                  }
                >
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message="原文回看提示"
                    description="这里适合核对人物、事件、伏笔和衔接线索在原文中的具体表述。高亮部分会帮助你更快定位。"
                  />
                  <Row gutter={[16, 16]} style={{ marginBottom: 18 }}>
                    <Col xs={24} lg={16}>
                      <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 8 }}>
                        {source.raw_heading || "无标题"}
                      </Typography.Title>
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                        如果拆书结果里提到某个关键人物、事件或章节引用，可以在这里直接回看原文。
                      </Typography.Paragraph>
                    </Col>
                    <Col xs={24} lg={8}>
                      <Card size="small" className="reader-source-meta">
                        <Descriptions column={1} size="small">
                          <Descriptions.Item label="章节编号">第 {bundle.chapter_index} 章</Descriptions.Item>
                          <Descriptions.Item label="原文范围">
                            {source.start_offset} - {source.end_offset}
                          </Descriptions.Item>
                          <Descriptions.Item label="高亮规则">
                            <Space wrap>
                              <Tag color="purple">人物</Tag>
                              <Tag color="gold">事件</Tag>
                              <Tag color="cyan">衔接</Tag>
                            </Space>
                          </Descriptions.Item>
                        </Descriptions>
                      </Card>
                    </Col>
                  </Row>
                  <div
                    className="reader-source-content"
                    dangerouslySetInnerHTML={{
                      __html: highlightSourceText(source.source_excerpt || "暂无原始正文", {
                        entities,
                        events,
                        continuity,
                      }),
                    }}
                  />
                </Card>
              ),
            },
          ]}
        />
      </Space>

      <ChapterDataModal
        state={dataModal}
        bundle={bundle}
        qa={qa}
        onJumpChapter={onJumpChapter}
        onClose={() => setDataModal(null)}
      />
    </>
  );
}

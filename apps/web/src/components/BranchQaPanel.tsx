import {
  Alert,
  Button,
  Card,
  Collapse,
  Empty,
  Input,
  List,
  Space,
  Spin,
  Statistic,
  Tag,
  Tabs,
  Timeline,
  Typography,
} from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { askBranch, askBranchStream, searchBranch } from "@/lib/api";
import type { BranchAskResult, BranchAskStreamEvent, RetrievalHit } from "@/types/workbench";

interface Props {
  apiBase: string;
  branchId: string;
  databaseUrl: string;
  onJumpChapter: (chapterIndex: number) => void;
  maxChapter?: number;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "streaming" | "done" | "error";
  result?: BranchAskResult | null;
  retrievalHits?: RetrievalHit[];
  errorText?: string;
  progressText?: string;
  degradedNoticeShown?: boolean;
}

const humanizeDegradedReason = (reason?: string | null) => {
  if (!reason) return "上游问答模型暂时不可用，已改用检索证据生成保守回答。";
  if (reason.includes("503")) return "上游问答服务暂时不可用（503），当前先用检索证据给出保守回答。";
  if (reason.includes("429")) return "上游问答服务当前限流，当前先用检索证据给出保守回答。";
  return "上游问答模型暂时不可用，已改用检索证据生成保守回答。";
};

const QUICK_QUESTIONS = [
  "卫图的人物背景是什么？",
  "当前主要冲突的前因后果是什么？",
  "卫图和杏的关系是怎么变化的？",
  "这段剧情里哪条伏笔最关键？",
];

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

const chunkText = (value: string, size = 18) => {
  const chunks: string[] = [];
  for (let index = 0; index < value.length; index += size) {
    chunks.push(value.slice(index, index + size));
  }
  return chunks;
};

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

export default function BranchQaPanel({ apiBase, branchId, databaseUrl, onJumpChapter, maxChapter }: Props) {
  const [searchText, setSearchText] = useState("");
  const [question, setQuestion] = useState("");
  const [hits, setHits] = useState<RetrievalHit[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingAsk, setLoadingAsk] = useState(false);
  const [errorText, setErrorText] = useState("");
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  const latestAnswer = useMemo(
    () => [...messages].reverse().find((item) => item.role === "assistant" && item.result)?.result || null,
    [messages],
  );
  const askedQuestions = useMemo(
    () => messages.filter((item) => item.role === "user").map((item) => item.content),
    [messages],
  );
  const latestReferencedChapters = useMemo(
    () => Array.from(new Set(latestAnswer?.used_chapters || [])).slice(0, 8),
    [latestAnswer],
  );

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const updateAssistantMessage = (messageId: string, patch: Partial<ChatMessage>) => {
    setMessages((current) =>
      current.map((item) => (item.id === messageId ? { ...item, ...patch } : item)),
    );
  };

  const runSearch = async () => {
    const q = searchText.trim();
    if (!q) return;
    setLoadingSearch(true);
    setErrorText("");
    try {
      const payload = await searchBranch(apiBase, branchId, q, databaseUrl);
      setHits(payload.hits || []);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "检索失败");
      setHits([]);
    } finally {
      setLoadingSearch(false);
    }
  };

  const streamWithFallback = async (messageId: string, q: string) => {
    const handleEvent = (event: BranchAskStreamEvent) => {
      if (event.type === "status" && event.message) {
        updateAssistantMessage(messageId, { progressText: event.message, status: "streaming" });
        return;
      }
      if (event.type === "retrieval") {
        updateAssistantMessage(messageId, {
          retrievalHits: event.hits || [],
          progressText: "已找到相关章节，正在组织回答…",
          status: "streaming",
        });
        return;
      }
      if (event.type === "delta" && event.delta) {
        setMessages((current) =>
          current.map((item) =>
            item.id === messageId
              ? { ...item, content: `${item.content}${event.delta}`, status: "streaming" }
              : item,
          ),
        );
        return;
      }
      if (event.type === "final" && event.result) {
        updateAssistantMessage(messageId, {
          content: event.result.answer,
          result: event.result,
          progressText: "",
          degradedNoticeShown: event.result.answer_mode === "degraded",
          status: "done",
        });
        return;
      }
      if (event.type === "error") {
        updateAssistantMessage(messageId, {
          status: "error",
          errorText: event.error || "问答失败",
        });
      }
    };

    try {
      await askBranchStream(apiBase, branchId, q, handleEvent, databaseUrl, 6, maxChapter);
      return;
    } catch {
      const payload = await askBranch(apiBase, branchId, q, databaseUrl);
      updateAssistantMessage(messageId, {
        content: "",
        result: payload,
        retrievalHits: [],
        degradedNoticeShown: payload.answer_mode === "degraded",
        status: "streaming",
      });
      for (const chunk of chunkText(payload.answer)) {
        setMessages((current) =>
          current.map((item) =>
            item.id === messageId
              ? { ...item, content: `${item.content}${chunk}`, result: payload, status: "streaming" }
              : item,
          ),
        );
        await wait(28);
      }
      updateAssistantMessage(messageId, { content: payload.answer, result: payload, status: "done" });
    }
  };

  const runAsk = async (overrideQuestion?: string) => {
    const q = (overrideQuestion ?? question).trim();
    if (!q || loadingAsk) return;
    if (!branchId) {
      setErrorText("当前还没有 branch，先回到“开始整理”页导入或载入示例。");
      return;
    }

    setLoadingAsk(true);
    setErrorText("");
    setQuestion("");

    const userId = `user-${Date.now()}`;
    const assistantId = `assistant-${Date.now() + 1}`;

    setMessages((current) => [
      ...current,
      { id: userId, role: "user", content: q, status: "done" },
      { id: assistantId, role: "assistant", content: "", progressText: "正在检索相关章节…", status: "streaming" },
    ]);

    try {
      await streamWithFallback(assistantId, q);
    } catch (error) {
      updateAssistantMessage(assistantId, {
        status: "error",
        content: "",
        errorText: error instanceof Error ? error.message : "问答失败",
      });
      setErrorText(error instanceof Error ? error.message : "问答失败");
    } finally {
      setLoadingAsk(false);
    }
  };

  return (
    <Space id="novel-qa-panel" direction="vertical" size="large" style={{ width: "100%" }}>
      <Card bordered={false} className="reader-hero-card">
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <div>
            <Typography.Text className="reader-eyebrow">小说问答</Typography.Text>
            <Typography.Title level={3} style={{ margin: "8px 0 10px" }}>
              像普通聊天一样追问人物、冲突、伏笔与关系变化
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              回答会基于当前小说分支的章节检索、摘要证据和图谱线索生成，并保留可跳转的章节引用。输出支持流式显示。
            </Typography.Paragraph>
          </div>
          <Space wrap>
            <Tag color="blue">聊天式追问</Tag>
            <Tag color="processing">引用章节可跳转</Tag>
            <Tag color="purple">附带推理摘要</Tag>
          </Space>
        </Space>
      </Card>

      {!branchId ? (
        <Alert
          type="warning"
          showIcon
          message="还没有可问答的作品分支"
          description="请先回到“开始整理”页导入作品，或载入当前示例分支，然后再回来发起问答。"
        />
      ) : null}

      {errorText ? <Alert type="error" showIcon message={errorText} /> : null}

      <Tabs
        className="reader-tabs"
        items={[
          {
            key: "chat",
            label: "小说问答",
            children: (
              <div className="qa-chat-layout">
                <Space direction="vertical" size="large" style={{ width: "100%" }}>
                  <div className="qa-overview-grid">
                    <Card bordered={false} className="reader-source-meta qa-overview-card">
                      <Statistic title="已提问轮次" value={askedQuestions.length} valueStyle={{ color: "#eaf2ff" }} />
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 10 }}>
                        会话会按正常聊天方式持续追加，你可以围绕上一问继续追问。
                      </Typography.Paragraph>
                    </Card>
                    <Card bordered={false} className="reader-source-meta qa-overview-card">
                      <Statistic title="最近引用章节" value={latestReferencedChapters.length || 0} valueStyle={{ color: "#eaf2ff" }} />
                      <Space wrap style={{ marginTop: 10 }}>
                        {latestReferencedChapters.length
                          ? latestReferencedChapters.map((chapter) => (
                            <Tag key={`top-${chapter}`} color="processing">
                              <a className="chapter-inline-link" onClick={() => onJumpChapter(chapter)}>第{chapter}章</a>
                            </Tag>
                          ))
                          : <Tag>等待回答中</Tag>}
                      </Space>
                    </Card>
                    <Card bordered={false} className="reader-source-meta qa-overview-card">
                      <Statistic title="当前模式" value={loadingAsk ? "生成中" : "可提问"} valueStyle={{ color: "#eaf2ff", fontSize: 24 }} />
                      <Typography.Paragraph type="secondary" style={{ marginBottom: 0, marginTop: 10 }}>
                        优先流式返回；如果流式不可用，会自动切回普通回答，不需要你手动处理。
                      </Typography.Paragraph>
                    </Card>
                  </div>

                  <Card bordered={false} className="reader-insight-card qa-chat-shell">
                    <div className="qa-message-list">
                      {messages.length ? (
                        messages.map((message) => (
                          <div
                            key={message.id}
                            className={`qa-message-row ${message.role === "user" ? "is-user" : "is-assistant"}`}
                          >
                            <Card
                              bordered={false}
                              className={`qa-message-bubble ${message.role === "user" ? "user-bubble" : "assistant-bubble"}`}
                            >
                              <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                                <Space wrap>
                                  <Tag color={message.role === "user" ? "gold" : "blue"}>
                                    {message.role === "user" ? "你" : "小说助手"}
                                  </Tag>
                                  {message.status === "streaming" ? <Tag color="processing">生成中</Tag> : null}
                                  {message.status === "error" ? <Tag color="error">失败</Tag> : null}
                                  {message.result?.answer_mode === "degraded" ? <Tag color="warning">降级回答</Tag> : null}
                                  {message.result ? (
                                    <Tag color={message.result.insufficient_context ? "warning" : "success"}>
                                      {message.result.insufficient_context
                                        ? "证据不足"
                                        : `可信度 ${Math.round((message.result.confidence || 0) * 100)}%`}
                                    </Tag>
                                  ) : null}
                                </Space>

                                {message.status === "error" ? (
                                  <Alert type="error" showIcon message={message.errorText || "问答失败"} />
                                ) : (
                                  <Space direction="vertical" style={{ width: "100%" }} size="small">
                                    {message.result?.answer_mode === "degraded" ? (
                                      <Alert
                                        type="warning"
                                        showIcon
                                        message="当前为降级回答"
                                        description={humanizeDegradedReason(message.result.degraded_reason)}
                                      />
                                    ) : null}
                                    <Typography.Paragraph style={{ marginBottom: 0, lineHeight: 1.95 }}>
                                      {message.content
                                        ? jumpify(message.content, onJumpChapter)
                                        : message.progressText || <Spin size="small" />}
                                      {message.status === "streaming" ? <span className="qa-cursor">▍</span> : null}
                                    </Typography.Paragraph>
                                  </Space>
                                )}

                                {message.retrievalHits?.length ? (
                                  <div className="qa-quick-reference">
                                    <Typography.Text strong>本次参考章节</Typography.Text>
                                    <Space wrap style={{ marginTop: 8 }}>
                                      {message.retrievalHits.map((hit) => (
                                        <Tag key={`${message.id}-${hit.chapter_index}`} color="processing">
                                          <a className="chapter-inline-link" onClick={() => onJumpChapter(hit.chapter_index)}>
                                            第{hit.chapter_index}章
                                          </a>
                                        </Tag>
                                      ))}
                                    </Space>
                                  </div>
                                ) : null}

                                {message.result ? (
                                  <Collapse
                                    ghost
                                    className="qa-detail-collapse"
                                    items={[
                                      {
                                        key: "chapters",
                                        label: "引用章节",
                                        children: (
                                          <Space wrap>
                                            {message.result.used_chapters.length ? message.result.used_chapters.map((chapter) => (
                                              <Tag key={`${message.id}-${chapter}`} color="processing">
                                                <a className="chapter-inline-link" onClick={() => onJumpChapter(chapter)}>第{chapter}章</a>
                                              </Tag>
                                            )) : <Tag>暂无</Tag>}
                                          </Space>
                                        ),
                                      },
                                      {
                                        key: "evidence",
                                        label: "证据摘要",
                                        children: (
                                          <List
                                            split={false}
                                            dataSource={message.result.evidence || []}
                                            locale={{ emptyText: "暂无证据摘要" }}
                                            renderItem={(item) => (
                                              <List.Item className="reader-list-item">
                                                <span className="reader-list-content">{jumpify(item, onJumpChapter)}</span>
                                              </List.Item>
                                            )}
                                          />
                                        ),
                                      },
                                      {
                                        key: "reasoning",
                                        label: "推理摘要",
                                        children: (
                                          <Timeline
                                            items={(message.result.reasoning_paths || []).map((item) => ({
                                              children: <span>{jumpify(item, onJumpChapter)}</span>,
                                              color: "blue",
                                            }))}
                                          />
                                        ),
                                      },
                                      {
                                        key: "signals",
                                        label: "图谱信号",
                                        children: (
                                          <Space wrap>
                                            {message.result.graph_signals.length
                                              ? message.result.graph_signals.map((item) => (
                                                <Tag key={`${message.id}-${item}`} color="purple">{item}</Tag>
                                              ))
                                              : <Tag>暂无</Tag>}
                                          </Space>
                                        ),
                                      },
                                      ...(message.result.answer_mode === "degraded" && !message.degradedNoticeShown
                                        ? [{
                                          key: "degraded",
                                          label: "降级说明",
                                          children: (
                                            <Typography.Paragraph style={{ marginBottom: 0 }}>
                                              {message.result.degraded_reason || "本次回答因为上游模型暂时不可用，已切换为检索保底回答。"}
                                            </Typography.Paragraph>
                                          ),
                                        }]
                                        : []),
                                    ]}
                                  />
                                ) : null}
                              </Space>
                            </Card>
                          </div>
                        ))
                      ) : (
                        <Empty
                          image={Empty.PRESENTED_IMAGE_SIMPLE}
                          description="还没有开始问答。你可以直接问人物背景、冲突前因后果、人物关系变化或某条伏笔。"
                        />
                      )}
                      <div ref={messageEndRef} />
                    </div>
                  </Card>

                  <Card bordered={false} className="reader-insight-card qa-composer-card">
                    <Space direction="vertical" style={{ width: "100%" }} size="middle">
                      <div className="qa-composer-header">
                        <Typography.Text strong>开始提问</Typography.Text>
                        <Button
                          disabled={!messages.length}
                          onClick={() => {
                            setMessages([]);
                            setErrorText("");
                          }}
                        >
                          清空会话
                        </Button>
                      </div>
                      <Input.TextArea
                        rows={4}
                        placeholder="例如：卫图的人物背景是什么？这段冲突为什么会发生？某条伏笔后来有没有兑现？"
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        onPressEnter={(event) => {
                          if (!event.shiftKey) {
                            event.preventDefault();
                            void runAsk();
                          }
                        }}
                      />
                      <Space wrap>
                        <Button type="primary" loading={loadingAsk} onClick={() => void runAsk()}>
                          发送问题
                        </Button>
                        {QUICK_QUESTIONS.map((item) => (
                          <Button key={item} onClick={() => {
                            setQuestion(item);
                            void runAsk(item);
                          }}>
                            {item}
                          </Button>
                        ))}
                      </Space>
                    </Space>
                  </Card>
                </Space>

                <div className="qa-side-column">
                  <Card bordered={false} className="reader-source-meta">
                    <Space direction="vertical" style={{ width: "100%" }} size="middle">
                      <div>
                        <Typography.Text className="reader-eyebrow">问答指引</Typography.Text>
                        <Typography.Title level={5} style={{ margin: "8px 0 0" }}>
                          适合怎么问
                        </Typography.Title>
                      </div>
                      <List
                        split={false}
                        dataSource={[
                          "先问人物背景，再追问人物关系变化。",
                          "先问冲突前因，再问冲突升级与代价。",
                          "先问某条伏笔，再问它后来是否兑现。",
                        ]}
                        renderItem={(item, index) => (
                          <List.Item className="reader-list-item">
                            <span className="reader-list-index">{index + 1}</span>
                            <span className="reader-list-content">{item}</span>
                          </List.Item>
                        )}
                      />
                    </Space>
                  </Card>

                  <Card bordered={false} className="reader-source-meta">
                    <Space direction="vertical" style={{ width: "100%" }} size="middle">
                      <Typography.Title level={5} style={{ margin: 0 }}>
                        本轮提问记录
                      </Typography.Title>
                      {askedQuestions.length ? (
                        <div className="qa-question-history">
                          {askedQuestions.slice().reverse().map((item, index) => (
                            <button
                              key={`${item}-${index}`}
                              type="button"
                              className="qa-question-chip"
                              onClick={() => setQuestion(item)}
                            >
                              {item}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                          你发起问答后，这里会保留最近的问题，方便二次编辑再问。
                        </Typography.Paragraph>
                      )}
                    </Space>
                  </Card>
                </div>
              </div>
            ),
          },
          {
            key: "search",
            label: "快速检索",
            children: (
              <Space direction="vertical" size="large" style={{ width: "100%" }}>
                <Card bordered={false} className="reader-insight-card" title="人物 / 事件检索">
                  <Space.Compact style={{ width: "100%" }}>
                    <Input
                      placeholder="例如：卫图、杏、命格、冲突、武举"
                      value={searchText}
                      onChange={(event) => setSearchText(event.target.value)}
                      onPressEnter={() => void runSearch()}
                    />
                    <Button type="primary" loading={loadingSearch} onClick={() => void runSearch()}>
                      检索
                    </Button>
                  </Space.Compact>
                  <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
                    适合先查某个人、某个事件或某条线索集中出现在哪些章节，再继续发起问答。
                  </Typography.Paragraph>
                </Card>

                <Card bordered={false} className="reader-insight-card" title={`检索结果（${hits.length}）`}>
                  {hits.length ? (
                    <List
                      split={false}
                      dataSource={hits}
                      renderItem={(hit) => (
                        <List.Item className="qa-search-item">
                          <Space direction="vertical" style={{ width: "100%" }}>
                            <Space wrap>
                              <a className="chapter-inline-link" onClick={() => onJumpChapter(hit.chapter_index)}>
                                第{hit.chapter_index}章 · {hit.title}
                              </a>
                              <Tag color="blue">匹配度 {hit.score.toFixed(2)}</Tag>
                            </Space>
                            <Typography.Paragraph style={{ marginBottom: 0, lineHeight: 1.8 }}>
                              {hit.summary_text}
                            </Typography.Paragraph>
                            <Space wrap>
                              {hit.keyword_list?.slice(0, 8).map((item) => (
                                <Tag key={`${hit.chapter_index}-${item}`}>{item}</Tag>
                              ))}
                            </Space>
                            <Space wrap>
                              <Button size="small" onClick={() => void runAsk(`围绕第${hit.chapter_index}章，解释${searchText || hit.title}的关键信息。`)}>
                                围绕这一章继续问
                              </Button>
                              <Button size="small" onClick={() => onJumpChapter(hit.chapter_index)}>
                                去看这一章
                              </Button>
                            </Space>
                          </Space>
                        </List.Item>
                      )}
                    />
                  ) : (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="先输入人物、事件或线索关键词开始检索" />
                  )}
                </Card>
              </Space>
            ),
          },
          {
            key: "summary",
            label: "当前回答摘要",
            children: (
              <Card bordered={false} className="reader-insight-card">
                {latestAnswer ? (
                  <Space direction="vertical" size="large" style={{ width: "100%" }}>
                    <Alert
                      type={latestAnswer.insufficient_context ? "warning" : "success"}
                      showIcon
                      message={latestAnswer.insufficient_context ? "当前回答证据仍有限" : "当前回答证据充足"}
                      description={`可信度 ${Math.round((latestAnswer.confidence || 0) * 100)}%，可直接根据引用章节回看原文。`}
                    />
                    <div className="qa-summary-grid">
                      <Card bordered={false} className="reader-source-meta" title="引用章节">
                        <Space wrap>
                          {latestAnswer.used_chapters.length ? latestAnswer.used_chapters.map((chapter) => (
                            <Tag key={`summary-${chapter}`} color="processing">
                              <a className="chapter-inline-link" onClick={() => onJumpChapter(chapter)}>第{chapter}章</a>
                            </Tag>
                          )) : <Tag>暂无</Tag>}
                        </Space>
                      </Card>
                      <Card bordered={false} className="reader-source-meta" title="图谱信号">
                        <Space wrap>
                          {latestAnswer.graph_signals.length
                            ? latestAnswer.graph_signals.map((item) => <Tag key={`signal-${item}`} color="purple">{item}</Tag>)
                            : <Tag>暂无</Tag>}
                        </Space>
                      </Card>
                    </div>
                  </Space>
                ) : (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="发起一次问答后，这里会汇总当前回答的章节引用与图谱信号。" />
                )}
              </Card>
            ),
          },
        ]}
      />
    </Space>
  );
}

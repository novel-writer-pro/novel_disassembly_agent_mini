import { Alert, Button, Card, Input, List, Space, Tag, Typography } from "antd";
import { useState } from "react";
import { askBranch, searchBranch } from "@/lib/api";
import type { BranchAskResult, RetrievalHit } from "@/types/workbench";

interface Props {
  apiBase: string;
  branchId: string;
  databaseUrl: string;
  onJumpChapter: (chapterIndex: number) => void;
}

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

export default function BranchQaPanel({ apiBase, branchId, databaseUrl, onJumpChapter }: Props) {
  const [searchText, setSearchText] = useState("");
  const [question, setQuestion] = useState("");
  const [hits, setHits] = useState<RetrievalHit[]>([]);
  const [answer, setAnswer] = useState<BranchAskResult | null>(null);
  const [loadingSearch, setLoadingSearch] = useState(false);
  const [loadingAsk, setLoadingAsk] = useState(false);
  const [errorText, setErrorText] = useState("");

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

  const runAsk = async () => {
    const q = question.trim();
    if (!q) return;
    setLoadingAsk(true);
    setErrorText("");
    try {
      const payload = await askBranch(apiBase, branchId, q, databaseUrl);
      setAnswer(payload);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "问答失败");
      setAnswer(null);
    } finally {
      setLoadingAsk(false);
    }
  };

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card bordered={false} className="reader-insight-card" title="人物 / 事件检索">
        <Space.Compact style={{ width: "100%" }}>
          <Input
            placeholder="例如：卫图、杏、命格、冲突、武举"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            onPressEnter={() => void runSearch()}
          />
          <Button type="primary" loading={loadingSearch} onClick={() => void runSearch()}>检索</Button>
        </Space.Compact>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          适合查人物背景、事件分布、某条线索在哪些章节出现过。
        </Typography.Paragraph>
      </Card>

      <Card bordered={false} className="reader-insight-card" title="基于小说问答">
        <Space direction="vertical" style={{ width: "100%" }}>
          <Input.TextArea
            rows={3}
            placeholder="例如：卫图的人物背景是什么？这场冲突的前因后果是什么？杏和卫图的关系是怎么变化的？"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <Space wrap>
            <Button type="primary" loading={loadingAsk} onClick={() => void runAsk()}>开始问答</Button>
            <Button onClick={() => setQuestion("卫图的人物背景是什么？")}>人物背景</Button>
            <Button onClick={() => setQuestion("当前主要冲突的前因后果是什么？")}>冲突前因后果</Button>
            <Button onClick={() => setQuestion("卫图和杏的关系是怎么变化的？")}>人物关系变化</Button>
          </Space>
        </Space>
      </Card>

      {errorText ? <Alert type="error" showIcon message={errorText} /> : null}

      {hits.length ? (
        <Card bordered={false} className="reader-insight-card" title={`检索结果（${hits.length}）`}>
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
                    {hit.keyword_list?.slice(0, 8).map((item) => <Tag key={`${hit.chapter_index}-${item}`}>{item}</Tag>)}
                  </Space>
                </Space>
              </List.Item>
            )}
          />
        </Card>
      ) : null}

      {answer ? (
        <Card bordered={false} className="reader-insight-card" title="问答结果">
          <Space direction="vertical" style={{ width: "100%" }} size="large">
            <Alert
              type={answer.insufficient_context ? "warning" : "success"}
              showIcon
              message={answer.insufficient_context ? "当前证据不足，答案参考性有限" : `回答可信度 ${Math.round((answer.confidence || 0) * 100)}%`}
            />
            <div>
              <Typography.Title level={5}>回答</Typography.Title>
              <Typography.Paragraph style={{ marginBottom: 0, lineHeight: 1.9 }}>
                {jumpify(answer.answer, onJumpChapter)}
              </Typography.Paragraph>
            </div>
            <div>
              <Typography.Title level={5}>引用章节</Typography.Title>
              <Space wrap>
                {answer.used_chapters?.length ? answer.used_chapters.map((chapter) => (
                  <Tag key={chapter} color="processing">
                    <a className="chapter-inline-link" onClick={() => onJumpChapter(chapter)}>第{chapter}章</a>
                  </Tag>
                )) : <Tag>暂无</Tag>}
              </Space>
            </div>
            <div>
              <Typography.Title level={5}>证据摘要</Typography.Title>
              <List split={false} dataSource={answer.evidence || []} renderItem={(item) => <List.Item className="reader-list-item"><span className="reader-list-content">{jumpify(item, onJumpChapter)}</span></List.Item>} />
            </div>
            <div>
              <Typography.Title level={5}>推理路径</Typography.Title>
              <List split={false} dataSource={answer.reasoning_paths || []} renderItem={(item) => <List.Item className="reader-list-item"><span className="reader-list-content">{jumpify(item, onJumpChapter)}</span></List.Item>} />
            </div>
            <div>
              <Typography.Title level={5}>图谱信号</Typography.Title>
              <Space wrap>
                {answer.graph_signals?.length ? answer.graph_signals.map((item) => <Tag key={item} color="purple">{item}</Tag>) : <Tag>暂无</Tag>}
              </Space>
            </div>
          </Space>
        </Card>
      ) : null}
    </Space>
  );
}

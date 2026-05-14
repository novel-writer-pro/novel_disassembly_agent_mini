import { useEffect, useState } from "react";
import { Button, Card, Input, Rate, Space, Typography, message } from "antd";

interface FeedbackSummary {
  positive_count?: number;
  negative_count?: number;
  neutral_count?: number;
  top_signals?: string[];
}

interface Props {
  apiBase: string;
  branchId: string;
  chapterIndex: number;
  databaseUrl?: string;
}

export default function ReaderFeedbackPanel({ apiBase, branchId, chapterIndex, databaseUrl }: Props) {
  const [rating, setRating] = useState<number>(0);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [summary, setSummary] = useState<FeedbackSummary | null>(null);

  useEffect(() => {
    setSubmitted(false);
    setRating(0);
    setComment("");
    const params = new URLSearchParams({ branch_id: branchId });
    if (databaseUrl) params.set("database_url", databaseUrl);
    fetch(`${apiBase}/api/reader/feedback-summary?${params}`)
      .then((r) => r.json())
      .then(setSummary)
      .catch(() => {});
  }, [apiBase, branchId, chapterIndex, databaseUrl]);

  const handleSubmit = async () => {
    if (!rating) { message.warning("请先评分"); return; }
    setSubmitting(true);
    try {
      const r = await fetch(`${apiBase}/api/reader/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ branch_id: branchId, chapter_index: chapterIndex, rating, comment, database_url: databaseUrl }),
      });
      if (!r.ok) throw new Error("提交失败");
      setSubmitted(true);
      message.success("感谢反馈！");
    } catch {
      message.error("提交失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card
      data-testid="reader-feedback-panel"
      size="small"
      title={<Typography.Text strong>这章怎么样？</Typography.Text>}
    >
      {submitted ? (
        <Typography.Text type="success">✓ 感谢你的反馈！</Typography.Text>
      ) : (
        <Space direction="vertical" style={{ width: "100%" }}>
          <Rate value={rating} onChange={setRating} />
          <Input.TextArea
            placeholder="可选：写下你的感受..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            maxLength={200}
          />
          <Button type="primary" size="small" loading={submitting} onClick={handleSubmit}>
            提交
          </Button>
        </Space>
      )}
      {summary && (
        <div style={{ marginTop: 8, borderTop: "1px solid #f0f0f0", paddingTop: 8 }}>
          <Space size={4}>
            {summary.positive_count != null && (
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                👍 {summary.positive_count}
              </Typography.Text>
            )}
            {summary.negative_count != null && (
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                👎 {summary.negative_count}
              </Typography.Text>
            )}
            {summary.neutral_count != null && (
              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                😐 {summary.neutral_count}
              </Typography.Text>
            )}
          </Space>
        </div>
      )}
    </Card>
  );
}

import { useState } from "react";
import { Input, List, Tag, Typography, Collapse, Button, Space } from "antd";
import { SearchOutlined, BookOutlined } from "@ant-design/icons";
import type { ChapterRow } from "@/types/workbench";

interface Props {
  rows: ChapterRow[];
  activeChapterIndex: number | null;
  onSelect: (chapterIndex: number) => void;
}

function riskColor(level?: string | null): string {
  if (!level) return "default";
  if (level === "high") return "red";
  if (level === "medium") return "orange";
  return "green";
}

function hookColor(score?: number | null): string {
  if (score == null) return "default";
  if (score >= 0.7) return "green";
  if (score >= 0.4) return "gold";
  return "default";
}

export default function ChapterNavPanel({ rows, activeChapterIndex, onSelect }: Props) {
  const [keyword, setKeyword] = useState("");
  const [filter, setFilter] = useState<"all" | "high_hook" | "has_risk">("all");

  const filtered = rows.filter((row) => {
    const matchKeyword =
      !keyword ||
      String(row.chapter_index).includes(keyword) ||
      (row.title || "").toLowerCase().includes(keyword.toLowerCase()) ||
      (row.summary || "").toLowerCase().includes(keyword.toLowerCase());
    const matchFilter =
      filter === "all" ||
      (filter === "high_hook" && (row.hook_score ?? 0) >= 0.7) ||
      (filter === "has_risk" && !!row.risk_level);
    return matchKeyword && matchFilter;
  });

  return (
    <div data-testid="chapter-nav-panel" style={{ padding: "12px 8px" }}>
      <Input
        prefix={<SearchOutlined />}
        placeholder="搜索章节..."
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        size="small"
        style={{ marginBottom: 8 }}
        allowClear
      />
      <Space size={4} style={{ marginBottom: 8, flexWrap: "wrap" }}>
        {(["all", "high_hook", "has_risk"] as const).map((f) => (
          <Tag
            key={f}
            color={filter === f ? "blue" : "default"}
            style={{ cursor: "pointer" }}
            onClick={() => setFilter(f)}
          >
            {f === "all" ? "全部" : f === "high_hook" ? "高吸引" : "有风险"}
          </Tag>
        ))}
      </Space>
      <List
        size="small"
        dataSource={filtered}
        renderItem={(row) => {
          const isActive = row.chapter_index === activeChapterIndex;
          return (
            <Collapse
              ghost
              size="small"
              items={[{
                key: row.chapter_index,
                label: (
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <BookOutlined style={{ color: isActive ? "#1677ff" : "#999" }} />
                    <Typography.Text
                      strong={isActive}
                      style={{ fontSize: 13, color: isActive ? "#1677ff" : undefined, flex: 1 }}
                      ellipsis
                    >
                      第{row.chapter_index}章 {row.title}
                    </Typography.Text>
                    {row.hook_score != null && (
                      <Tag color={hookColor(row.hook_score)} style={{ fontSize: 11, padding: "0 4px" }}>
                        {row.hook_score.toFixed(1)}
                      </Tag>
                    )}
                    {row.risk_level && (
                      <Tag color={riskColor(row.risk_level)} style={{ fontSize: 11, padding: "0 4px" }}>
                        {row.risk_level}
                      </Tag>
                    )}
                  </div>
                ),
                children: (
                  <div style={{ paddingLeft: 20 }}>
                    {row.summary ? (
                      <Typography.Paragraph
                        type="secondary"
                        style={{ fontSize: 12, marginBottom: 8 }}
                        ellipsis={{ rows: 3, expandable: true }}
                      >
                        {row.summary}
                      </Typography.Paragraph>
                    ) : (
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>暂无摘要</Typography.Text>
                    )}
                    <Button
                      type="primary"
                      size="small"
                      onClick={() => onSelect(row.chapter_index)}
                    >
                      进入阅读
                    </Button>
                  </div>
                ),
              }]}
            />
          );
        }}
      />
    </div>
  );
}

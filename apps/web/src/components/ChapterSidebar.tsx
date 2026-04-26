import { Badge, Empty, Input, Pagination, Select, Segmented, Space, Tag, Typography } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChapterRow } from "@/types/workbench";

interface Props {
  rows: ChapterRow[];
  activeChapterIndex: number | null;
  onSelect: (chapterIndex: number) => void;
}

const statusTone = (row: ChapterRow) => {
  if (row.job_status === "failed") return "error" as const;
  if (row.needs_human_review) return "warning" as const;
  if (row.has_artifact) return "success" as const;
  return "default" as const;
};

const statusLabel = (row: ChapterRow) => {
  if (row.job_status === "failed") return "失败";
  if (row.needs_human_review) return "待复核";
  if (row.has_artifact) return "可阅读";
  return "处理中";
};

export default function ChapterSidebar({ rows, activeChapterIndex, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "review" | "failed" | "unfinished">("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const activeItemRef = useRef<HTMLDivElement | null>(null);

  const reviewCount = rows.filter((row) => row.needs_human_review).length;
  const failedCount = rows.filter((row) => row.job_status === "failed").length;
  const unfinishedCount = rows.filter((row) => row.job_status !== "validated").length;

  const filteredRows = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return rows.filter((row) => {
      const keywordPass =
        !keyword ||
        String(row.chapter_index).includes(keyword) ||
        String(row.title || "").toLowerCase().includes(keyword) ||
        String(row.summary || "").toLowerCase().includes(keyword);

      const filterPass =
        filter === "all" ||
        (filter === "review" && row.needs_human_review) ||
        (filter === "failed" && row.job_status === "failed") ||
        (filter === "unfinished" && row.job_status !== "validated");

      return keywordPass && filterPass;
    });
  }, [filter, query, rows]);

  useEffect(() => {
    if (activeItemRef.current) {
      activeItemRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [activeChapterIndex, filter, query, page, pageSize]);

  const pageSizeOptions = [10, 20, 30, 50];

  useEffect(() => {
    setPage(1);
  }, [filter, query]);

  useEffect(() => {
    if (!activeChapterIndex) return;
    const index = filteredRows.findIndex((row) => row.chapter_index === activeChapterIndex);
    if (index < 0) return;
    const nextPage = Math.floor(index / pageSize) + 1;
    const currentPageStart = (page - 1) * pageSize;
    const currentPageEnd = currentPageStart + pageSize;
    const activeInCurrentPage = index >= currentPageStart && index < currentPageEnd;
    if (!activeInCurrentPage) setPage(nextPage);
  }, [activeChapterIndex, filteredRows, pageSize]);

  const pagedRows = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredRows.slice(start, start + pageSize);
  }, [filteredRows, page, pageSize]);

  const rangeOptions = useMemo(() => {
    const options = [];
    for (let start = 1; start <= filteredRows.length; start += pageSize) {
      const end = Math.min(start + pageSize - 1, filteredRows.length);
      options.push({ value: Math.floor((start - 1) / pageSize) + 1, label: `${start}-${end} 章` });
    }
    return options;
  }, [filteredRows.length, pageSize]);

  return (
    <div className="chapter-sidebar-shell">
      <div className="chapter-sidebar-summary">
        <Typography.Title level={4} style={{ color: "#eaf2ff", margin: 0 }}>
          章节目录
        </Typography.Title>
        <Typography.Paragraph style={{ color: "#9bb2d1", margin: "8px 0 0" }}>
          搜索章节号、标题或摘要，右侧会集中显示对应拆书卡片和原文。
        </Typography.Paragraph>
        <Space wrap style={{ marginTop: 12 }}>
          <Tag color="blue">共 {rows.length} 章</Tag>
          <Tag color="warning">待复核 {reviewCount}</Tag>
          <Tag color="error">失败 {failedCount}</Tag>
        </Space>
        {activeChapterIndex ? (
          <Typography.Text style={{ display: "block", color: "#68a7ff", marginTop: 12 }}>
            当前正在阅读：第 {activeChapterIndex} 章
          </Typography.Text>
        ) : null}
      </div>

      <Input
        placeholder="搜索章节标题 / 章节号 / 摘要"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        className="chapter-sidebar-search"
      />

      <Segmented
        block
        value={filter}
        onChange={(value) => setFilter(value as typeof filter)}
        options={[
          { label: `全部 ${rows.length}`, value: "all" },
          { label: `复核 ${reviewCount}`, value: "review" },
          { label: `失败 ${failedCount}`, value: "failed" },
          { label: `未完成 ${unfinishedCount}`, value: "unfinished" },
        ]}
        className="chapter-sidebar-segment"
      />

      <Space direction="vertical" size={10} style={{ width: "100%", marginBottom: 12 }}>
        <Typography.Paragraph style={{ color: "#9bb2d1", marginBottom: 0 }}>
          当前筛选到 {filteredRows.length} 章
        </Typography.Paragraph>
        {filteredRows.length ? (
          <div className="chapter-sidebar-pager-row">
            <Select
              value={page}
              options={rangeOptions}
              onChange={(value) => setPage(value)}
              className="chapter-sidebar-range-select"
            />
            <Select
              value={pageSize}
              options={pageSizeOptions.map((value) => ({ value, label: `每页 ${value} 章` }))}
              onChange={(value) => {
                setPageSize(value);
                setPage(1);
              }}
              className="chapter-sidebar-page-size-select"
            />
          </div>
        ) : null}
      </Space>

      <div className="chapter-sidebar-list">
        {pagedRows.length ? (
          pagedRows.map((row) => {
            const active = activeChapterIndex === row.chapter_index;
            const tone = statusTone(row);
            return (
              <div
                key={row.chapter_index}
                ref={active ? activeItemRef : null}
                className={`chapter-sidebar-item ${active ? "active" : ""}`}
                onClick={() => onSelect(row.chapter_index)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(row.chapter_index);
                  }
                }}
                role="button"
                tabIndex={0}
              >
                <div className="chapter-sidebar-item-header">
                  <div style={{ minWidth: 0 }}>
                    <Typography.Text strong className="chapter-sidebar-item-title">
                      第{row.chapter_index}章 {row.title || "未命名章节"}
                    </Typography.Text>
                    {row.summary ? (
                      <Typography.Paragraph ellipsis={{ rows: 2 }} className="chapter-sidebar-item-summary">
                        {row.summary}
                      </Typography.Paragraph>
                    ) : (
                      <Typography.Paragraph className="chapter-sidebar-item-summary muted">
                        暂无章节摘要，可先进入查看原文与拆书结果。
                      </Typography.Paragraph>
                    )}
                  </div>
                  <div className="chapter-sidebar-item-meta">
                    <Badge color={tone === "error" ? "#ff7875" : tone === "warning" ? "#faad14" : tone === "success" ? "#52c41a" : "#8c8c8c"} />
                    <Tag bordered={false} color={tone}>
                      {statusLabel(row)}
                    </Tag>
                    {row.hook_score !== null && row.hook_score !== undefined ? (
                      <Tag bordered={false} color="processing">
                        吸引度 {row.hook_score}
                      </Tag>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })
        ) : (
          <div className="chapter-sidebar-empty">
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="没有符合当前筛选条件的章节" />
          </div>
        )}
      </div>

      {filteredRows.length ? (
        <Pagination
          simple
          current={page}
          pageSize={pageSize}
          total={filteredRows.length}
          onChange={(nextPage) => setPage(nextPage)}
          className="chapter-sidebar-pagination"
        />
      ) : null}
    </div>
  );
}

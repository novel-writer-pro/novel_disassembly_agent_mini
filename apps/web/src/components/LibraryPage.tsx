import { BookOutlined, EyeOutlined, MessageOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Input, Pagination, Space, Statistic, Tag, Typography } from "antd";
import { useMemo, useState } from "react";
import type { LibraryItem } from "@/types/workbench";

interface Props {
  items: LibraryItem[];
  activeBranchId: string;
  onActivate: (item: LibraryItem) => void;
  onOpenReader: (item: LibraryItem) => void;
  onOpenQa: (item: LibraryItem) => void;
  onRefresh: () => void;
}

const statusColor = (item: LibraryItem) => {
  if (item.pipeline_state === "needs_recovery") return "error";
  if (item.running_jobs) return "processing";
  if (item.pipeline_state === "completed") return "success";
  return "blue";
};

export default function LibraryPage({ items, activeBranchId, onActivate, onOpenReader, onOpenQa, onRefresh }: Props) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 12;

  const filteredItems = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return items;
    return items.filter((item) =>
      [item.title, item.branch_name, item.pipeline_state, item.run_id, item.branch_id]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(keyword)),
    );
  }, [items, query]);

  const pagedItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, page]);

  const summary = useMemo(() => ({
    total: items.length,
    running: items.filter((item) => (item.running_jobs || 0) > 0 || item.pipeline_state === "auto_running").length,
    recovery: items.filter((item) => item.pipeline_state === "needs_recovery").length,
    completed: items.filter((item) => item.pipeline_state === "completed").length,
  }), [items]);

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card bordered={false} className="page-hero-card">
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <div>
            <Typography.Text className="reader-eyebrow">小说空间</Typography.Text>
            <Typography.Title level={2} style={{ margin: "8px 0 10px" }}>
              在一个阅读空间里统一管理多本小说
            </Typography.Title>
            <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
              这里是小说管理入口。你可以同时保留很多本小说，在这里选择当前生效的作品，然后再进入章节阅读、问答与导出流程。
            </Typography.Paragraph>
          </div>
          <Space wrap>
            <Tag color="blue">支持多本小说</Tag>
            <Tag color="processing">切换当前生效作品</Tag>
            <Tag color="purple">适合作为阅读工作空间入口</Tag>
          </Space>
        </Space>
      </Card>

      <div className="qa-overview-grid">
        <Card bordered={false} className="reader-source-meta qa-overview-card">
          <Statistic title="作品 / 分支总数" value={summary.total} valueStyle={{ color: "#eaf2ff" }} />
        </Card>
        <Card bordered={false} className="reader-source-meta qa-overview-card">
          <Statistic title="后台进行中" value={summary.running} valueStyle={{ color: "#eaf2ff" }} />
        </Card>
        <Card bordered={false} className="reader-source-meta qa-overview-card">
          <Statistic title="待恢复" value={summary.recovery} valueStyle={{ color: "#eaf2ff" }} />
        </Card>
        <Card bordered={false} className="reader-source-meta qa-overview-card">
          <Statistic title="已完成" value={summary.completed} valueStyle={{ color: "#eaf2ff" }} />
        </Card>
      </div>

      <Card bordered={false} className="product-panel" extra={<Button icon={<ReloadOutlined />} onClick={onRefresh}>刷新作品库</Button>}>
        <Space direction="vertical" style={{ width: "100%" }} size="middle">
          <Input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
            placeholder="搜索小说名、分支名、状态或 ID"
          />
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            当前共 {items.length} 本 / 分支记录，当前筛选后 {filteredItems.length} 条。
          </Typography.Paragraph>
        </Space>
      </Card>

      {pagedItems.length ? (
        <div className="library-card-grid">
          {pagedItems.map((item) => {
            const active = item.branch_id === activeBranchId;
            return (
              <Card
                key={`${item.run_id}-${item.branch_id}`}
                bordered={false}
                className={`product-panel library-card ${active ? "active" : ""}`}
              >
                <Space direction="vertical" style={{ width: "100%" }} size="middle">
                  <div className="library-card-top">
                    <div>
                      <Typography.Title level={4} style={{ margin: 0 }}>
                        {item.title}
                      </Typography.Title>
                      <Typography.Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
                        分支：{item.branch_name}
                      </Typography.Paragraph>
                    </div>
                    {active ? <Tag color="success">当前生效</Tag> : <Tag>可切换</Tag>}
                  </div>

                  <Space wrap>
                    <Tag color={statusColor(item)}>{item.pipeline_state}</Tag>
                    <Tag color="blue">{item.completed_chapters}/{item.manifest_chapter_count} 章</Tag>
                    <Tag color="warning">失败 {item.failed_jobs || 0}</Tag>
                    <Tag color="processing">运行中 {item.running_jobs || 0}</Tag>
                  </Space>

                  <div className="library-card-metrics">
                    <div>
                      <Typography.Text type="secondary">下一章</Typography.Text>
                      <Typography.Title level={5} style={{ margin: "6px 0 0" }}>
                        {item.next_chapter ?? "已完成"}
                      </Typography.Title>
                    </div>
                    <div>
                      <Typography.Text type="secondary">最近更新时间</Typography.Text>
                      <Typography.Title level={5} style={{ margin: "6px 0 0" }}>
                        {item.updated_at ? item.updated_at.slice(5, 16).replace("T", " ") : "未知"}
                      </Typography.Title>
                    </div>
                  </div>

                  <Space wrap>
                    <Button type={active ? "default" : "primary"} onClick={() => onActivate(item)} icon={<BookOutlined />}>
                      {active ? "当前作品" : "切换为当前作品"}
                    </Button>
                    <Button onClick={() => onOpenReader(item)} icon={<EyeOutlined />}>进入阅读</Button>
                    <Button onClick={() => onOpenQa(item)} icon={<MessageOutlined />}>进入问答</Button>
                  </Space>
                </Space>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card bordered={false} className="product-panel">
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有符合条件的小说记录" />
        </Card>
      )}

      {filteredItems.length > pageSize ? (
        <Pagination
          current={page}
          pageSize={pageSize}
          total={filteredItems.length}
          onChange={setPage}
          className="library-pagination"
        />
      ) : null}
    </Space>
  );
}

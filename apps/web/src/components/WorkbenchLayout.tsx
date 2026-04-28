import { BookOutlined, DashboardOutlined, ExportOutlined, MessageOutlined } from "@ant-design/icons";
import { Layout, Menu, Space, Tag, Typography } from "antd";
import type { ReactNode } from "react";

const { Header, Sider, Content } = Layout;

interface Props {
  activeKey: string;
  chapterMenu: ReactNode;
  onNavigate: (key: string) => void;
  currentNovelTitle?: string;
  currentBranchId?: string;
  children: ReactNode;
}

export default function WorkbenchLayout({ activeKey, chapterMenu, onNavigate, currentNovelTitle, currentBranchId, children }: Props) {
  const metaByKey: Record<string, { title: string; subtitle: string; tip: string }> = {
    control: {
      title: "开始整理作品",
      subtitle: "导入作品、查看整理进度，并决定接下来继续拆到哪里。",
      tip: "先导入，再阅读章节",
    },
    reader: {
      title: "章节阅读",
      subtitle: "围绕当前章节查看人物、事件、线索与原文，按作家的阅读习惯来组织。",
      tip: "按章节阅读与回看",
    },
    qa: {
      title: "小说问答",
      subtitle: "集中检索人物、事件、冲突与线索，并基于整本小说内容发起问答。",
      tip: "检索与追问",
    },
    ops: {
      title: "导出与恢复",
      subtitle: "把结果导出成手册；只有遇到异常时，才需要在这里处理恢复。",
      tip: "收尾与导出",
    },
  };

  const meta = metaByKey[activeKey] || metaByKey.reader;

  return (
    <Layout className="workbench-shell">
      <Sider width={320} theme="dark" className="workbench-sider" breakpoint="lg" collapsedWidth="0">
        <div className="workbench-brand-card">
          <Typography.Text className="workbench-brand-eyebrow">写作辅助阅读台</Typography.Text>
          <Typography.Title level={3} style={{ color: "#eaf2ff", margin: "8px 0 0" }}>
            小说拆书工作台
          </Typography.Title>
          <Typography.Paragraph style={{ color: "#9bb2d1", marginTop: 8, marginBottom: 0 }}>
            以章节为中心查看人物、事件、线索与原文片段，帮助你快速回看与继续创作。
          </Typography.Paragraph>
        </div>

        <Menu
          theme="dark"
          selectedKeys={[activeKey]}
          onClick={({ key }) => onNavigate(String(key))}
          items={[
            { key: "control", icon: <DashboardOutlined />, label: "开始整理" },
            { key: "reader", icon: <BookOutlined />, label: "章节阅读" },
            { key: "qa", icon: <MessageOutlined />, label: "小说问答" },
            { key: "ops", icon: <ExportOutlined />, label: "导出与恢复" },
          ]}
          className="workbench-main-menu"
        />

        <div className="workbench-sidebar-content">{chapterMenu}</div>
      </Sider>
      <Layout>
        <Header className="workbench-header">
          <div className="workbench-header-row">
            <div>
              <Space size={10} align="center" wrap>
                <Typography.Title level={3} style={{ color: "#eaf2ff", margin: 0 }}>
                  {meta.title}
                </Typography.Title>
                <Tag color="blue">{meta.tip}</Tag>
              </Space>
              <Typography.Paragraph style={{ color: "#9bb2d1", margin: "8px 0 0" }}>
                {meta.subtitle}
              </Typography.Paragraph>
            </div>
            <div className="workbench-current-novel">
              <Typography.Text className="workbench-current-label">当前作品</Typography.Text>
              <Typography.Title level={5} style={{ color: "#eaf2ff", margin: "6px 0 0" }}>
                {currentNovelTitle || "未选择作品"}
              </Typography.Title>
              {currentBranchId ? <Tag color="processing">branch: {currentBranchId.slice(0, 8)}</Tag> : null}
            </div>
          </div>
        </Header>
        <Content className="workbench-content">{children}</Content>
      </Layout>
    </Layout>
  );
}

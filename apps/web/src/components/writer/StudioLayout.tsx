import { useState } from "react";
import { Layout, Tabs, Empty, Typography } from "antd";
import EditorCanvas from "./EditorCanvas";
import LoomSignalsPanel from "./LoomSignalsPanel";
import CopilotIframe from "./CopilotIframe";

const { Sider, Content, Header } = Layout;

interface Props {
  branchId: string | null;
}

export default function StudioLayout({ branchId }: Props) {
  const [rightTab, setRightTab] = useState<"loom" | "copilot">("loom");
  const [chapterIndex, setChapterIndex] = useState<number>(1);

  if (!branchId) {
    return (
      <Layout style={{ minHeight: "100vh" }}>
        <Content style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Empty description="还没有作品，先到 /control 导入小说">
            <a href="/control">前往导入</a>
          </Empty>
        </Content>
      </Layout>
    );
  }

  return (
    <Layout style={{ minHeight: "100vh" }} data-testid="studio-layout">
      <Header style={{ background: "#fff", borderBottom: "1px solid #f0f0f0", padding: "0 24px" }}>
        <Typography.Text strong>Writer Studio · {branchId}</Typography.Text>
      </Header>
      <Layout>
        <Sider
          width={248}
          theme="light"
          data-testid="studio-sider-left"
          style={{ borderRight: "1px solid #f0f0f0", padding: 16 }}
        >
          <Typography.Title level={5}>大纲 / 角色 / 风格</Typography.Title>
          <Empty description="待接入" />
        </Sider>
        <Content data-testid="studio-canvas" style={{ padding: 24, background: "#fafafa" }}>
          <EditorCanvas branchId={branchId} chapterIndex={chapterIndex} />
        </Content>
        <Sider
          width={360}
          theme="light"
          data-testid="studio-sider-right"
          style={{ borderLeft: "1px solid #f0f0f0", padding: 16 }}
        >
          <Tabs
            activeKey={rightTab}
            onChange={(k) => setRightTab(k as "loom" | "copilot")}
            items={[
              {
                key: "loom",
                label: "Loom 信号",
                children: <LoomSignalsPanel branchId={branchId} chapterIndex={chapterIndex} />,
              },
              {
                key: "copilot",
                label: "AI 副驾",
                children: <CopilotIframe branchId={branchId} />,
              },
            ]}
          />
        </Sider>
      </Layout>
    </Layout>
  );
}

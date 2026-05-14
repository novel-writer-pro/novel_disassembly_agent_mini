import { useState } from "react";
import { Alert, Typography } from "antd";
import BranchQaPanel from "@/components/BranchQaPanel";

interface Props {
  apiBase: string;
  branchId: string;
  databaseUrl: string;
  maxChapter?: number;
  onJumpChapter: (chapterIndex: number) => void;
}

export default function AntiSpoilerQA({ apiBase, branchId, databaseUrl, maxChapter, onJumpChapter }: Props) {
  return (
    <div data-testid="anti-spoiler-qa" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {maxChapter != null && (
        <Alert
          type="info"
          showIcon
          message={
            <Typography.Text style={{ fontSize: 12 }}>
              防剧透模式：仅基于第 1–{maxChapter} 章回答
            </Typography.Text>
          }
          style={{ margin: "8px 8px 0", borderRadius: 6 }}
          banner
        />
      )}
      <div style={{ flex: 1, overflow: "hidden" }}>
        <BranchQaPanel
          apiBase={apiBase}
          branchId={branchId}
          databaseUrl={databaseUrl}
          onJumpChapter={onJumpChapter}
          maxChapter={maxChapter}
        />
      </div>
    </div>
  );
}

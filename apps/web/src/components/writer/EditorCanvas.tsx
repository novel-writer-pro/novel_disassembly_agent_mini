import { useEffect, useRef, useState } from "react";
import { Space, Typography, message } from "antd";

interface Props {
  branchId: string;
  chapterIndex: number;
  initialText?: string;
  onSave?: (text: string) => Promise<void>;
}

const AUTOSAVE_DEBOUNCE_MS = 500;

export default function EditorCanvas({ branchId, chapterIndex, initialText = "", onSave }: Props) {
  const [text, setText] = useState(initialText);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (text === initialText) return;
    timerRef.current = setTimeout(async () => {
      if (!onSave) {
        setSavedAt(new Date());
        return;
      }
      setSaving(true);
      try {
        await onSave(text);
        setSavedAt(new Date());
      } catch (e) {
        message.error("自动保存失败");
      } finally {
        setSaving(false);
      }
    }, AUTOSAVE_DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [text, initialText, onSave]);

  return (
    <div data-testid="editor-canvas" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
        <Typography.Text type="secondary">
          {branchId} · 第 {chapterIndex} 章
        </Typography.Text>
        <Space>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {saving ? "保存中..." : savedAt ? `已保存 ${savedAt.toLocaleTimeString()}` : "未保存"}
          </Typography.Text>
        </Space>
      </div>
      <textarea
        data-testid="editor-textarea"
        value={text}
        onChange={(e) => setText(e.target.value)}
        style={{
          flex: 1,
          width: "100%",
          minHeight: 480,
          padding: 16,
          fontSize: 16,
          lineHeight: 1.8,
          border: "1px solid #f0f0f0",
          borderRadius: 4,
          resize: "none",
          fontFamily: "var(--font-serif, 'Source Han Serif SC', 'Noto Serif SC', serif)",
        }}
        placeholder="在这里写作..."
      />
    </div>
  );
}

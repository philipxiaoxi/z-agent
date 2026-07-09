import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Spin } from "antd";
import {
  ToolOutlined,
  CheckCircleOutlined,
  DownOutlined,
  RightOutlined,
} from "@ant-design/icons";
import type { Block } from "../../stores/chat-store";
import { useChatStore } from "../../stores/chat-store";

const PREVIEW_MAX = 80;

const CODE_FONT = '"SF Mono", "Monaco", "Cascadia Code", monospace';

const STATUS_META = {
  connected: { color: "#52c41a", label: "已连接" },
  connecting: { color: "#faad14", label: "连接中" },
  disconnected: { color: "#ff4d4f", label: "未连接" },
} as const;

export { STATUS_META };
export type StatusKey = keyof typeof STATUS_META;

const ToolCallBlock = memo(function ToolCallBlock({ block }: { block: Block }) {
  return (
    <div style={{ border: "1px solid #e8e8e8", borderLeft: "3px solid #1677ff", borderRadius: 8, background: "#fafafa", padding: "10px 14px", fontSize: 13 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
        <ToolOutlined style={{ color: "#1677ff", fontSize: 14 }} />
        <span style={{ fontWeight: 600, color: "#333" }}>调用工具: {block.tool}</span>
      </div>
      <pre style={{ margin: 0, fontSize: 12, color: "#666", whiteSpace: "pre-wrap", wordBreak: "break-all", fontFamily: CODE_FONT }}>
        {JSON.stringify(block.args, null, 2)}
      </pre>
    </div>
  );
});

const ToolResultBlock = memo(function ToolResultBlock({ block }: { block: Block }) {
  const toggleToolResult = useChatStore((s) => s.toggleToolResult);
  const firstLine = block.result?.split("\n")[0] || "";
  const preview = firstLine.length > PREVIEW_MAX ? firstLine.slice(0, PREVIEW_MAX) + "…" : firstLine;

  return (
    <div style={{ border: "1px solid #b7eb8f", borderLeft: "3px solid #52c41a", borderRadius: 8, background: "#f6ffed", padding: "10px 14px", fontSize: 13 }}>
      <div onClick={() => toggleToolResult(block.id)} style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", userSelect: "none" }}>
        {block.collapsed ? <RightOutlined style={{ color: "#52c41a", fontSize: 12 }} /> : <DownOutlined style={{ color: "#52c41a", fontSize: 12 }} />}
        <CheckCircleOutlined style={{ color: "#52c41a", fontSize: 14 }} />
        <span style={{ fontWeight: 600, color: "#333" }}>{block.tool} 返回</span>
        {block.collapsed && preview && (
          <span style={{ marginLeft: 8, color: "#999", fontSize: 12, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{preview}</span>
        )}
      </div>
      {!block.collapsed && (
        <pre style={{ margin: "8px 0 0 0", fontSize: 12, color: "#333", whiteSpace: "pre-wrap", wordBreak: "break-all", maxHeight: 400, overflow: "auto", fontFamily: CODE_FONT }}>
          {block.result}
        </pre>
      )}
    </div>
  );
});

const TextBlock = memo(function TextBlock({ block }: { block: Block }) {
  if (!block.content) {
    return <Spin size="small" />;
  }

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p({ children }) {
          return <p style={{ margin: "4px 0" }}>{children}</p>;
        },
        code({ className, children, ...props }) {
          const isInline = !className;
          return isInline ? (
            <code style={{ background: "#f0f0f0", padding: "1px 5px", borderRadius: 4, fontSize: "0.88em" }} {...props}>
              {children}
            </code>
          ) : (
            <pre style={{ background: "#1e1e1e", color: "#d4d4d4", padding: 12, borderRadius: 8, overflow: "auto", fontSize: "0.85em", lineHeight: 1.5, margin: "8px 0" }}>
              <code className={className} {...props}>{children}</code>
            </pre>
          );
        },
      }}
    >
      {block.content}
    </ReactMarkdown>
  );
});

export default memo(function BlockView({ block }: { block: Block }) {
  switch (block.type) {
    case "tool_call":
      return <ToolCallBlock block={block} />;
    case "tool_result":
      return <ToolResultBlock block={block} />;
    default:
      return <TextBlock block={block} />;
  }
});

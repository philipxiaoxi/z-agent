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
    <div className="border border-gray-200 border-l-[3px] border-l-[#1677ff] rounded-lg bg-gray-50 px-3.5 py-2.5 text-[13px]">
      <div className="flex items-center gap-1.5 mb-1.5">
        <ToolOutlined className="text-[#1677ff] text-sm" />
        <span className="font-semibold text-gray-700">调用工具: {block.tool}</span>
      </div>
      <pre className="m-0 text-xs text-gray-500 whitespace-pre-wrap break-all" style={{ fontFamily: CODE_FONT }}>
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
    <div className="border border-green-300 border-l-[3px] border-l-green-500 rounded-lg bg-green-50 px-3.5 py-2.5 text-[13px]">
      <div onClick={() => toggleToolResult(block.id)} className="flex items-center gap-1.5 cursor-pointer select-none">
        {block.collapsed ? <RightOutlined className="text-green-500 text-xs" /> : <DownOutlined className="text-green-500 text-xs" />}
        <CheckCircleOutlined className="text-green-500 text-sm" />
        <span className="font-semibold text-gray-700">{block.tool} 返回</span>
        {block.collapsed && preview && (
          <span className="ml-2 text-gray-400 text-xs overflow-hidden text-ellipsis whitespace-nowrap flex-1">{preview}</span>
        )}
      </div>
      {!block.collapsed && (
        <pre className="mt-2 text-xs text-gray-700 whitespace-pre-wrap break-all max-h-[400px] overflow-auto" style={{ fontFamily: CODE_FONT }}>
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
          return <p className="my-1">{children}</p>;
        },
        code({ className, children, ...props }) {
          const isInline = !className;
          return isInline ? (
            <code className="bg-gray-100 px-1.5 py-0.5 rounded text-[0.88em]" {...props}>
              {children}
            </code>
          ) : (
            <pre className="bg-[#1e1e1e] text-[#d4d4d4] p-3 rounded-lg overflow-auto text-[0.85em] leading-relaxed my-2">
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

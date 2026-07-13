import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Spin } from "antd";
import {
  ToolOutlined,
  CheckCircleOutlined,
  DownOutlined,
  RightOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import type { Block } from "../../stores/chat-store";
import { useChatStore } from "../../stores/chat-store";
import FileListBlock from "./FileListBlock";
import HtmlPreviewBlock from "./HtmlPreviewBlock";

const CODE_FONT = '"SF Mono", "Monaco", "Cascadia Code", monospace';

const STATUS_META = {
  connected: { color: "#52c41a", label: "已连接" },
  connecting: { color: "#faad14", label: "连接中" },
  disconnected: { color: "#ff4d4f", label: "未连接" },
} as const;

export { STATUS_META };
export type StatusKey = keyof typeof STATUS_META;

const ToolCallBlock = memo(function ToolCallBlock({ block }: { block: Block }) {
  const toggle = useChatStore((s) => s.toggleBlockCollapsed);

  return (
    <div className="border border-gray-200 border-l-[3px] border-l-[#1677ff] rounded-lg bg-gray-50 px-3.5 py-2.5 text-[13px]">
      <div onClick={() => toggle(block.id)} className="flex items-center gap-1.5 cursor-pointer select-none">
        {block.collapsed ? <RightOutlined style={{ color: "#1677ff", fontSize: 12 }} /> : <DownOutlined style={{ color: "#1677ff", fontSize: 12 }} />}
        <ToolOutlined className="text-sm" style={{ color: "#1677ff" }} />
        <span className="font-semibold text-gray-700">调用工具: {block.tool}</span>
      </div>
      {!block.collapsed && (
        <pre className="mt-2 text-xs text-gray-500 whitespace-pre-wrap break-all" style={{ fontFamily: CODE_FONT }}>
          {JSON.stringify(block.args, null, 2)}
        </pre>
      )}
    </div>
  );
});

const ToolResultBlock = memo(function ToolResultBlock({ block }: { block: Block }) {
  const toggle = useChatStore((s) => s.toggleBlockCollapsed);

  return (
    <div className="border border-green-300 border-l-[3px] border-l-green-500 rounded-lg bg-green-50 px-3.5 py-2.5 text-[13px]">
      <div onClick={() => toggle(block.id)} className="flex items-center gap-1.5 cursor-pointer select-none">
        {block.collapsed ? <RightOutlined className="text-green-500 text-xs" /> : <DownOutlined className="text-green-500 text-xs" />}
        <CheckCircleOutlined className="text-green-500 text-sm" />
        <span className="font-semibold text-gray-700">{block.tool} 返回</span>
      </div>
      {!block.collapsed && (
        <pre className="mt-2 text-xs text-gray-700 whitespace-pre-wrap break-all max-h-[400px] overflow-auto" style={{ fontFamily: CODE_FONT }}>
          {block.result}
        </pre>
      )}
    </div>
  );
});

const ThinkingBlock = memo(function ThinkingBlock({ block }: { block: Block }) {
  const toggle = useChatStore((s) => s.toggleBlockCollapsed);

  return (
    <div className="border border-amber-200 border-l-[3px] border-l-amber-400 rounded-lg bg-amber-50 px-3.5 py-2.5 text-[13px]">
      <div onClick={() => toggle(block.id)} className="flex items-center gap-1.5 cursor-pointer select-none">
        {block.collapsed ? <RightOutlined style={{ color: "#d97706", fontSize: 12 }} /> : <DownOutlined style={{ color: "#d97706", fontSize: 12 }} />}
        <BulbOutlined className="text-sm" style={{ color: "#d97706" }} />
        <span className="font-semibold text-gray-700">思考过程</span>
      </div>
      {!block.collapsed && (
        <div className="mt-2 text-xs text-gray-600 whitespace-pre-wrap">
          {block.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{block.content}</ReactMarkdown>
          ) : (
            <Spin size="small" />
          )}
        </div>
      )}
    </div>
  );
});

const TextBlock = memo(function TextBlock({ block }: { block: Block }) {
  if (!block.content) {
    return <Spin size="small" />;
  }

  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>
        {block.content}
      </ReactMarkdown>
    </div>
  );
});

interface BlockViewProps {
  block: Block;
  onFileAction?: (action: "analyze" | "view" | "add_to_input", path: string) => void;
}

export default memo(function BlockView({ block, onFileAction }: BlockViewProps) {
  switch (block.type) {
    case "thinking":
      return <ThinkingBlock block={block} />;
    case "tool_call":
      return <ToolCallBlock block={block} />;
    case "tool_result":
      return <ToolResultBlock block={block} />;
    case "file_list":
      return (
        <FileListBlock
          fileList={block.fileList!}
          collapsed={block.collapsed}
          blockId={block.id}
          onFileAction={onFileAction}
        />
      );
    case "html_preview":
      return (
        <HtmlPreviewBlock
          htmlPreview={block.htmlPreview!}
          collapsed={block.collapsed}
          blockId={block.id}
        />
      );
    default:
      return <TextBlock block={block} />;
  }
});

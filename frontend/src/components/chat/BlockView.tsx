import { memo, useState, useCallback } from "react";
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
import type { Block, FileListData, HtmlPreviewData } from "../../stores/chat-store";
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

type Segment =
  | { type: "markdown"; content: string }
  | { type: "file-list"; data: FileListData }
  | { type: "html-preview"; data: HtmlPreviewData };

function parseTagBlocks(content: string): Segment[] {
  const segments: Segment[] = [];
  const regex = /```z-([\w-]+)\s*\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "markdown", content: content.slice(lastIndex, match.index) });
    }

    const name = match[1];
    const jsonStr = match[2].trim();
    try {
      const data = JSON.parse(jsonStr);
      if (name === "file-list") {
        segments.push({ type: "file-list", data });
      } else if (name === "html-preview") {
        segments.push({ type: "html-preview", data });
      } else {
        segments.push({ type: "markdown", content: match[0] });
      }
    } catch {
      segments.push({ type: "markdown", content: match[0] });
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < content.length) {
    segments.push({ type: "markdown", content: content.slice(lastIndex) });
  }

  return segments;
}

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

const CancelledBlock = memo(function CancelledBlock() {
  return (
    <div className="flex items-center gap-2 py-2 text-gray-400 text-sm select-none">
      <span className="flex-1 h-px bg-gray-200" />
      <span>⛔ 对话已终止</span>
      <span className="flex-1 h-px bg-gray-200" />
    </div>
  );
});

const TextBlock = memo(function TextBlock({ block, onFileAction }: { block: Block; onFileAction?: (action: "analyze" | "view" | "add_to_input", path: string) => void }) {
  if (!block.content) {
    return <Spin size="small" />;
  }

  const segments = parseTagBlocks(block.content);
  const [tagCollapsed, setTagCollapsed] = useState<Record<number, boolean>>({});

  const toggleTag = useCallback((idx: number) => {
    setTagCollapsed((prev) => ({ ...prev, [idx]: !prev[idx] }));
  }, []);

  if (segments.length === 1 && segments[0].type === "markdown") {
    return (
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {segments[0].content}
        </ReactMarkdown>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {segments.map((seg, i) => {
        if (seg.type === "markdown") {
          return (
            <div key={i} className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {seg.content}
              </ReactMarkdown>
            </div>
          );
        }
        if (seg.type === "file-list") {
          return (
            <FileListBlock
              key={i}
              fileList={seg.data}
              collapsed={tagCollapsed[i] ?? false}
              blockId={`ztag-${i}`}
              onFileAction={onFileAction}
              onToggle={() => toggleTag(i)}
            />
          );
        }
        if (seg.type === "html-preview") {
          return (
            <HtmlPreviewBlock
              key={i}
              htmlPreview={seg.data}
              collapsed={tagCollapsed[i] ?? true}
              blockId={`ztag-${i}`}
              onToggle={() => toggleTag(i)}
            />
          );
        }
        return null;
      })}
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
    case "cancelled":
      return <CancelledBlock />;
    default:
      return <TextBlock block={block} onFileAction={onFileAction} />;
  }
});

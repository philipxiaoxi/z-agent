import { useState, useRef, useEffect, useMemo } from "react";
import { Input, Button, Typography, Spin } from "antd";
import {
  SendOutlined,
  ThunderboltOutlined,
  UserOutlined,
  ReloadOutlined,
  FolderOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";
import { useChatStore } from "../../stores/chat-store";
import BlockView, { STATUS_META, type StatusKey } from "../../components/chat/BlockView";
import WelcomeCard from "../../components/chat/WelcomeCard";
import { useChatWs } from "../../hooks/useChatWs";

const { Text } = Typography;
const CHAT_MAX_WIDTH = 720;

export default function ChatPage() {
  const { messages, workdir, addMessage, setWorkdir } = useChatStore();
  const { wsStatus, loading, setLoading, handleSend, handleSetWorkdir, handleReconnect } = useChatWs();
  const [input, setInput] = useState("");
  const [editingWorkdir, setEditingWorkdir] = useState(false);
  const [workdirInput, setWorkdirInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollKey = useMemo(() => {
    const len = messages.length;
    if (len === 0) return "0";
    const last = messages[len - 1];
    const blocks = last.blocks;
    const lastBlock = blocks[blocks.length - 1];
    return `${len}-${blocks.length}-${lastBlock?.content?.length ?? 0}-${lastBlock?.result?.length ?? 0}`;
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [scrollKey]);

  const statusMeta = STATUS_META[wsStatus as StatusKey];

  function onSend() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    addMessage({
      id: crypto.randomUUID(),
      role: "user",
      blocks: [{ id: crypto.randomUUID(), type: "text", content: text, collapsed: false }],
    });
    addMessage({ id: crypto.randomUUID(), role: "assistant", blocks: [] });
    setLoading(true);
    handleSend(text);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }

  function startEditWorkdir() {
    setWorkdirInput(workdir);
    setEditingWorkdir(true);
  }

  function confirmWorkdir() {
    const path = workdirInput.trim();
    if (path) {
      setWorkdir(path);
      handleSetWorkdir(path);
    }
    setEditingWorkdir(false);
  }

  function clearWorkdir() {
    setWorkdir("");
    handleSetWorkdir("");
    setEditingWorkdir(false);
  }

  function onWorkdirKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      confirmWorkdir();
    } else if (e.key === "Escape") {
      setEditingWorkdir(false);
    }
  }

  const emptyState = useMemo(() => <WelcomeCard />, []);

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <div className="px-6 py-3.5 bg-white border-b border-gray-100 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <ThunderboltOutlined className="text-lg" style={{ color: "#1677ff" }} />
          <Text strong className="text-[15px]">极同学</Text>
          <span className="text-xs text-gray-400">你的 NAS AI 助手</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full inline-block shrink-0" style={{ background: statusMeta?.color ?? "#ff4d4f" }} />
          <Text className="text-xs text-gray-400">{statusMeta?.label ?? "未连接"}</Text>
          {wsStatus === "disconnected" && (
            <Button size="small" type="text" icon={<ReloadOutlined />} onClick={handleReconnect} className="text-xs text-gray-400" />
          )}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8 flex flex-col items-center">
        <div className="w-full flex flex-col gap-5" style={{ maxWidth: CHAT_MAX_WIDTH }}>
          {messages.length === 0 && emptyState}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-2.5 items-start ${
                msg.role === "user"
                  ? "justify-end pl-[42px] pr-0"
                  : "justify-start pl-0 pr-[42px]"
              }`}
            >
              {msg.role === "assistant" && (
                <div className="w-[30px] h-[30px] rounded-full bg-gray-200 flex items-center justify-center shrink-0 mt-1">
                  <ThunderboltOutlined className="text-gray-500 text-sm" />
                </div>
              )}
              <div
                className={`text-sm leading-relaxed shadow-sm break-words flex flex-col gap-2 ${
                  msg.role === "user"
                    ? "bg-[#1677ff] text-white px-4 py-2 rounded-[18px_18px_4px_18px]"
                    : "bg-white text-gray-700 px-4 py-3 rounded-[18px_18px_18px_4px]"
                }`}
                style={{ maxWidth: msg.role === "user" ? "70%" : "85%" }}
              >
                {msg.role === "assistant" ? (
                  msg.blocks.length === 0 ? <Spin size="small" /> : msg.blocks.map((b) => <BlockView key={b.id} block={b} />)
                ) : (
                  <span className="whitespace-pre-wrap">{msg.blocks.find((b) => b.type === "text")?.content || ""}</span>
                )}
              </div>
              {msg.role === "user" && (
                <div className="w-[30px] h-[30px] rounded-full bg-gray-200 flex items-center justify-center shrink-0 mt-1">
                  <UserOutlined className="text-gray-500 text-sm" />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="px-4 py-3 bg-white border-t border-gray-100 shrink-0">
        <div style={{ maxWidth: CHAT_MAX_WIDTH }} className="mx-auto">
          {editingWorkdir ? (
            <div className="flex items-center gap-2 mb-2">
              <FolderOutlined className="text-gray-400 text-sm shrink-0" />
              <Input
                size="small"
                value={workdirInput}
                onChange={(e) => setWorkdirInput(e.target.value)}
                onKeyDown={onWorkdirKeyDown}
                placeholder="/sata12/my/data"
                className="text-xs"
                autoFocus
              />
              <Button size="small" type="primary" onClick={confirmWorkdir} className="text-xs">
                确认
              </Button>
              <Button size="small" onClick={() => setEditingWorkdir(false)} className="text-xs">
                取消
              </Button>
            </div>
          ) : workdir ? (
            <div className="flex items-center gap-1.5 mb-2 px-2 py-1 rounded bg-gray-50 text-xs text-gray-500 cursor-pointer hover:bg-gray-100" onClick={startEditWorkdir}>
              <FolderOutlined className="text-gray-400" />
              <span className="font-mono flex-1">{workdir}</span>
              <CloseCircleOutlined className="text-gray-300 hover:text-gray-500" onClick={(e) => { e.stopPropagation(); clearWorkdir(); }} />
            </div>
          ) : (
            <div className="flex items-center gap-1.5 mb-2 px-2 py-1 text-xs text-gray-300 cursor-pointer hover:text-gray-400" onClick={startEditWorkdir}>
              <FolderOutlined />
              <span>设置工作目录以限定文件操作范围</span>
            </div>
          )}
          <div className="flex gap-2 items-end">
            <Input.TextArea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              autoSize={{ minRows: 1, maxRows: 4 }}
              disabled={loading}
              className="rounded-[10px] text-sm px-3 py-2"
            />
            <Button type="primary" icon={<SendOutlined />} onClick={onSend} loading={loading} className="rounded-[10px] h-[38px] px-[18px] flex items-center">
              发送
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

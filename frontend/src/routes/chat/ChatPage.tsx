import { useState, useRef, useEffect, useMemo } from "react";
import { Input, Button, Typography, Spin } from "antd";
import {
  SendOutlined,
  ThunderboltOutlined,
  UserOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useChatStore } from "../../stores/chat-store";
import BlockView, { STATUS_META, type StatusKey } from "../../components/chat/BlockView";
import WelcomeCard from "../../components/chat/WelcomeCard";
import { useChatWs } from "../../hooks/useChatWs";

const { Text } = Typography;
const CHAT_MAX_WIDTH = 720;

export default function ChatPage() {
  const { messages, addMessage } = useChatStore();
  const { wsStatus, loading, setLoading, handleSend, handleReconnect } = useChatWs();
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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

  const emptyState = useMemo(() => <WelcomeCard />, []);

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      <div className="px-6 py-3.5 bg-white border-b border-gray-100 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <ThunderboltOutlined className="text-lg text-[#1677ff]" />
          <Text strong className="text-[15px]">极同学</Text>
          <Text className="text-xs text-gray-400">你的 NAS AI 助手</Text>
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
                <div className="w-[30px] h-[30px] rounded-full bg-[#1677ff] flex items-center justify-center shrink-0 mt-1">
                  <ThunderboltOutlined className="text-white text-sm" />
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
                <div className="w-[30px] h-[30px] rounded-full bg-gray-100 flex items-center justify-center shrink-0 mt-1">
                  <UserOutlined className="text-gray-500 text-sm" />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="px-4 py-3 bg-white border-t border-gray-100 shrink-0">
        <div className="flex gap-2 mx-auto items-end" style={{ maxWidth: CHAT_MAX_WIDTH }}>
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
  );
}

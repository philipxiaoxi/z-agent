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
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#f5f5f5" }}>
      <div style={{ padding: "14px 24px", background: "#fff", borderBottom: "1px solid #f0f0f0", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ThunderboltOutlined style={{ fontSize: 18, color: "#1677ff" }} />
          <Text strong style={{ fontSize: 15 }}>极同学</Text>
          <Text style={{ fontSize: 12, color: "#999" }}>你的 NAS AI 助手</Text>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: statusMeta?.color ?? "#ff4d4f", display: "inline-block", flexShrink: 0 }} />
          <Text style={{ fontSize: 12, color: "#999" }}>{statusMeta?.label ?? "未连接"}</Text>
          {wsStatus === "disconnected" && (
            <Button size="small" type="text" icon={<ReloadOutlined />} onClick={handleReconnect} style={{ fontSize: 12, color: "#999" }} />
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "32px 16px", display: "flex", flexDirection: "column", alignItems: "center" }}>
        <div style={{ width: "100%", maxWidth: CHAT_MAX_WIDTH, display: "flex", flexDirection: "column", gap: 20 }}>
          {messages.length === 0 && emptyState}
          {messages.map((msg) => (
            <div key={msg.id} style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", gap: 10, alignItems: "flex-start", paddingLeft: msg.role === "assistant" ? 0 : 42, paddingRight: msg.role === "user" ? 0 : 42 }}>
              {msg.role === "assistant" && (
                <div style={{ width: 30, height: 30, borderRadius: "50%", background: "#1677ff", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 4 }}>
                  <ThunderboltOutlined style={{ color: "#fff", fontSize: 14 }} />
                </div>
              )}
              <div style={{ maxWidth: msg.role === "user" ? "70%" : "85%", padding: msg.role === "user" ? "8px 16px" : "12px 16px", borderRadius: msg.role === "user" ? "18px 18px 4px 18px" : "18px 18px 18px 4px", background: msg.role === "user" ? "#1677ff" : "#fff", color: msg.role === "user" ? "#fff" : "#333", lineHeight: 1.65, fontSize: 14, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", wordBreak: "break-word", display: "flex", flexDirection: "column", gap: 8 }}>
                {msg.role === "assistant" ? (
                  msg.blocks.length === 0 ? <Spin size="small" /> : msg.blocks.map((b) => <BlockView key={b.id} block={b} />)
                ) : (
                  <span style={{ whiteSpace: "pre-wrap" }}>{msg.blocks.find((b) => b.type === "text")?.content || ""}</span>
                )}
              </div>
              {msg.role === "user" && (
                <div style={{ width: 30, height: 30, borderRadius: "50%", background: "#f0f0f0", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 4 }}>
                  <UserOutlined style={{ color: "#666", fontSize: 14 }} />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <div style={{ padding: "12px 16px", background: "#fff", borderTop: "1px solid #f0f0f0", flexShrink: 0 }}>
        <div style={{ display: "flex", gap: 8, maxWidth: CHAT_MAX_WIDTH, margin: "0 auto", alignItems: "flex-end" }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
            style={{ borderRadius: 10, fontSize: 14, padding: "8px 12px" }}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={onSend} loading={loading} style={{ borderRadius: 10, height: 38, paddingInline: 18, display: "flex", alignItems: "center" }}>
            发送
          </Button>
        </div>
      </div>
    </div>
  );
}

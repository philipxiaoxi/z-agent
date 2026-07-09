import { useRef, useEffect, useState, useCallback } from "react";
import { Modal } from "antd";
import { ToolOutlined } from "@ant-design/icons";
import {
  createChatWs,
  type ChatWs,
  type WsStatus,
  type ToolResultEvent,
} from "../lib/ws";
import { useChatStore } from "../stores/chat-store";

export function useChatWs() {
  const { appendText, addToolCall, addToolResult } = useChatStore();
  const [loading, setLoading] = useState(false);
  const [wsStatus, setWsStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<ChatWs | null>(null);

  useEffect(() => {
    const ws = createChatWs({
      onStatusChange: setWsStatus,
      onText(content) {
        appendText(content);
      },
      onToolStart(data) {
        addToolCall(data.tool, data.args);
      },
      onToolResult(data: ToolResultEvent) {
        addToolResult(data.tool, data.result);
      },
      onRequireConfirm(data) {
        Modal.confirm({
          title: "需要确认",
          icon: <ToolOutlined />,
          content: data.question,
          okText: "允许",
          cancelText: "拒绝",
          onOk: () => ws.sendConfirm(data.id, true),
          onCancel: () => ws.sendConfirm(data.id, false),
        });
      },
      onDone() {
        setLoading(false);
      },
      onError(content) {
        appendText(`\n\n*${content}*`);
        setLoading(false);
      },
    });
    wsRef.current = ws;
    return () => ws.close();
  }, [appendText, addToolCall, addToolResult]);

  const handleSend = useCallback(
    (text: string) => {
      if (!wsRef.current) return;
      wsRef.current.sendMessage(text);
    },
    []
  );

  const handleReconnect = useCallback(() => {
    wsRef.current?.reconnect();
  }, []);

  return {
    wsStatus,
    loading,
    setLoading,
    handleSend,
    handleReconnect,
  };
}

import { useRef, useEffect, useState, useCallback } from "react";
import { Modal } from "antd";
import { ToolOutlined } from "@ant-design/icons";
import {
  createChatWs,
  type ChatWs,
  type WsStatus,
  type ToolResultEvent,
  type RequireConfirmEvent,
} from "../lib/ws";
import { useChatStore } from "../stores/chat-store";

export function useChatWs() {
  const { appendText, addToolCall, addToolResult, setWorkdir } = useChatStore();
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
      onRequireConfirm(data: RequireConfirmEvent) {
        const isPathGate = data.confirm_type === "path_gate";
        Modal.confirm({
          title: isPathGate ? "路径门禁" : "需要确认",
          icon: <ToolOutlined />,
          content: data.question,
          okText: "允许",
          cancelText: "拒绝",
          onOk: () => ws.sendConfirm(data.id, true),
          onCancel: () => ws.sendConfirm(data.id, false),
        });
      },
      onWorkdirChanged(path: string) {
        setWorkdir(path);
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
  }, [appendText, addToolCall, addToolResult, setWorkdir]);

  const handleSend = useCallback(
    (text: string) => {
      if (!wsRef.current) return;
      wsRef.current.sendMessage(text);
    },
    []
  );

  const handleSetWorkdir = useCallback((path: string) => {
    wsRef.current?.sendSetWorkdir(path);
  }, []);

  const handleReconnect = useCallback(() => {
    wsRef.current?.reconnect();
  }, []);

  return {
    wsStatus,
    loading,
    setLoading,
    handleSend,
    handleSetWorkdir,
    handleReconnect,
  };
}

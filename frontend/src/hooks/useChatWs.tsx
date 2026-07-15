import { useRef, useEffect, useState, useCallback } from "react";
import { Button, Modal } from "antd";
import { ToolOutlined } from "@ant-design/icons";
import {
  createChatWs,
  type ChatWs,
  type WsStatus,
  type ToolResultEvent,
  type RequireConfirmEvent,
  type SubagentStartEvent,
  type SubagentStepEvent,
  type SubagentEndEvent,
} from "../lib/ws";
import { useChatStore } from "../stores/chat-store";

export function useChatWs() {
  const { appendText, appendThinking, addToolCall, addToolResult, addSubagentStart, addSubagentStep, addSubagentEnd, markCancelled, setWorkdir, activeSessionId } = useChatStore();
  const [loading, setLoading] = useState(false);
  const [wsStatus, setWsStatus] = useState<WsStatus>("connecting");
  const wsRef = useRef<ChatWs | null>(null);
  const sessionIdRef = useRef(activeSessionId);

  sessionIdRef.current = activeSessionId;

  useEffect(() => {
    const ws = createChatWs({
      onStatusChange: setWsStatus,
      onText(content) {
        appendText(content);
      },
      onThinking(content) {
        appendThinking(content);
      },
      onToolStart(data) {
        addToolCall(data.tool, data.args);
      },
      onToolResult(data: ToolResultEvent) {
        addToolResult(data.tool, data.result);
      },
      onRequireConfirm(data: RequireConfirmEvent) {
        const modal = Modal.confirm({
          title: data.title ?? "需要确认",
          icon: <ToolOutlined />,
          content: data.question,
          footer: () => (
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <Button danger onClick={() => { ws.sendCancelRun(); modal.destroy(); }}>终止</Button>
              <Button onClick={() => { ws.sendConfirm(data.id, false); modal.destroy(); }}>拒绝</Button>
              <Button type="primary" onClick={() => { ws.sendConfirm(data.id, true); modal.destroy(); }}>允许</Button>
            </div>
          ),
        });
      },
      onSubagentStart(data: SubagentStartEvent) {
        addSubagentStart(data.id, data.task);
      },
      onSubagentStep(data: SubagentStepEvent) {
        addSubagentStep(data.id, {
          step_type: data.step_type,
          content: data.content,
          tool: data.tool,
          args: data.args,
          result: data.result,
        });
      },
      onSubagentEnd(data: SubagentEndEvent) {
        addSubagentEnd(data.id, data.result);
      },
      onCancelled() {
        markCancelled();
        setLoading(false);
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
  }, [appendText, appendThinking, addToolCall, addToolResult, addSubagentStart, addSubagentStep, addSubagentEnd, markCancelled, setWorkdir]);

  useEffect(() => {
    wsRef.current?.sendSetSession(activeSessionId ?? "");
  }, [activeSessionId]);

  const handleSend = useCallback(
    (text: string) => {
      if (!wsRef.current) return;
      wsRef.current.sendMessage(text, sessionIdRef.current ?? undefined);
    },
    []
  );

  const handleSetWorkdir = useCallback((path: string) => {
    wsRef.current?.sendSetWorkdir(path);
  }, []);

  const handleReconnect = useCallback(() => {
    wsRef.current?.reconnect();
  }, []);

  const handleCancelRun = useCallback(() => {
    wsRef.current?.sendCancelRun();
  }, []);

  return {
    wsStatus,
    loading,
    setLoading,
    handleSend,
    handleSetWorkdir,
    handleReconnect,
    handleCancelRun,
  };
}

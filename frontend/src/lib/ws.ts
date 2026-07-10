const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? "localhost:8000";
const WS_BASE = RAW_BASE.replace(/^https?:\/\//, "");

export interface ToolCallEvent {
  id: string;
  tool: string;
  args: Record<string, unknown>;
}

export interface RequireConfirmEvent extends ToolCallEvent {
  question: string;
  confirm_type?: string;
  path?: string;
  workdir?: string;
}

export interface ToolResultEvent {
  id: string;
  tool: string;
  result: string;
}

export interface FileListEvent {
  current_path: string;
  items: { name: string; type: "file" | "folder"; size?: number; modified_at?: string }[];
  total: number;
}

export type WsStatus = "connecting" | "connected" | "disconnected";

export interface WsEvents {
  onStatusChange: (status: WsStatus) => void;
  onText: (content: string) => void;
  onToolStart: (data: ToolCallEvent) => void;
  onToolResult: (data: ToolResultEvent) => void;
  onFileList: (data: FileListEvent) => void;
  onRequireConfirm: (data: RequireConfirmEvent) => void;
  onWorkdirChanged: (path: string) => void;
  onDone: () => void;
  onError: (content: string) => void;
}

export interface ChatWs {
  sendMessage: (text: string) => void;
  sendConfirm: (id: string, approved: boolean) => void;
  sendSetWorkdir: (path: string) => void;
  reconnect: () => void;
  close: () => void;
}

type ServerEvent =
  | { type: "text"; content: string }
  | { type: "tool_start"; id: string; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; id: string; tool: string; result: string }
  | { type: "file_list"; data: import("../stores/chat-store").FileListData }
  | { type: "require_confirm"; id: string; tool: string; args: Record<string, unknown>; question: string; confirm_type?: string; path?: string; workdir?: string }
  | { type: "workdir_changed"; path: string }
  | { type: "done" }
  | { type: "error"; content: string };

export function createChatWs(events: WsEvents): ChatWs {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${WS_BASE}/api/agent/ws`;
  let ws: WebSocket;

  function safeClose() {
    if (ws.readyState === WebSocket.OPEN) {
      ws.onclose = null;
      ws.onerror = null;
      ws.close();
    } else if (ws.readyState === WebSocket.CONNECTING) {
      ws.onopen = null;
      ws.onclose = null;
      ws.onerror = null;
    }
  }

  function connect() {
    ws = new WebSocket(url);
    events.onStatusChange("connecting");

    ws.onopen = () => {
      events.onStatusChange("connected");
      const saved = localStorage.getItem("zspace_workdir");
      if (saved) {
        ws.send(JSON.stringify({ type: "restore_workdir", path: saved }));
      }
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as ServerEvent;
        switch (data.type) {
          case "text":
            events.onText(data.content);
            break;
          case "tool_start":
            events.onToolStart({ id: data.id, tool: data.tool, args: data.args });
            break;
          case "tool_result":
            events.onToolResult({ id: data.id, tool: data.tool, result: data.result });
            break;
          case "file_list":
            events.onFileList(data.data);
            break;
          case "require_confirm":
            events.onRequireConfirm({ id: data.id, tool: data.tool, args: data.args, question: data.question, confirm_type: data.confirm_type, path: data.path, workdir: data.workdir });
            break;
          case "workdir_changed":
            events.onWorkdirChanged(data.path);
            break;
          case "done":
            events.onDone();
            break;
          case "error":
            events.onError(data.content);
            break;
        }
      } catch {
        // ignore non-JSON messages
      }
    };

    ws.onerror = () => {
      events.onStatusChange("disconnected");
      events.onError("WebSocket 连接失败");
    };

    ws.onclose = () => {
      events.onStatusChange("disconnected");
      events.onDone();
    };
  }

  connect();

  return {
    sendMessage(text: string) {
      if (ws.readyState !== WebSocket.OPEN) {
        events.onError("WebSocket 未连接");
        return;
      }
      ws.send(JSON.stringify({ type: "message", content: text }));
    },
    sendConfirm(id: string, approved: boolean) {
      ws.send(JSON.stringify({ type: "confirm", id, approved }));
    },
    sendSetWorkdir(path: string) {
      ws.send(JSON.stringify({ type: "set_workdir", path }));
    },
    reconnect() {
      safeClose();
      connect();
    },
    close() {
      safeClose();
    },
  };
}

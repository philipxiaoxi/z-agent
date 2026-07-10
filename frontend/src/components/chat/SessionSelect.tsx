import { useEffect, useState } from "react";
import { Select, Button, Input } from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  MessageOutlined,
} from "@ant-design/icons";
import { useChatStore } from "../../stores/chat-store";

function formatTime(ts: number): string {
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function SessionSelect({ loading }: { loading: boolean }) {
  const {
    sessions,
    activeSessionId,
    sessionsLoading,
    storeReady,
    initialize,
    createSession,
    deleteSession,
    renameSession,
    switchSession,
  } = useChatStore();

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  useEffect(() => {
    if (!storeReady) {
      initialize();
    }
  }, [storeReady]);

  useEffect(() => {
    if (storeReady && sessions.length > 0 && !activeSessionId) {
      switchSession(sessions[0].id);
    }
  }, [storeReady, sessions, activeSessionId]);

  async function handleCreate() {
    const id = await createSession();
    if (id) switchSession(id);
  }

  async function handleSelect(id: string) {
    if (id === activeSessionId || loading) return;
    switchSession(id);
  }

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    deleteSession(id);
  }

  function startRename(e: React.MouseEvent, id: string, name: string) {
    e.stopPropagation();
    setRenamingId(id);
    setRenameValue(name);
  }

  async function confirmRename() {
    if (renamingId && renameValue.trim()) {
      renameSession(renamingId, renameValue.trim());
    }
    setRenamingId(null);
  }

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <Select
      className="session-select"
      size="small"
      placeholder="选择会话"
      loading={sessionsLoading}
      value={activeSessionId}
      onChange={handleSelect}
      disabled={loading}
      classNames={{ popup: { root: "session-select-dropdown" } }}
      labelRender={() => {
        if (!activeSession) return <span>选择会话</span>;
        if (activeSession.id === renamingId) {
          return (
            <Input
              size="small"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === "Enter") confirmRename();
                if (e.key === "Escape") setRenamingId(null);
              }}
              onClick={(e) => e.stopPropagation()}
              autoFocus
            />
          );
        }
        return <span className="truncate text-[13px]">{activeSession.name}</span>;
      }}
      options={sessions.map((s) => ({
        label: s.id === renamingId ? (
          <Input
            size="small"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === "Enter") confirmRename();
              if (e.key === "Escape") setRenamingId(null);
            }}
            onClick={(e) => e.stopPropagation()}
            autoFocus
          />
        ) : (
          <div className="flex items-center gap-2 py-0.5">
            <div className="flex-1 min-w-0">
              <div className="text-[13px] leading-tight truncate">{s.name}</div>
              <div className="text-[11px] text-gray-400 mt-0.5 flex items-center gap-2">
                <span>{formatTime(s.createdAt)}</span>
                <span className="flex items-center gap-0.5">
                  <MessageOutlined className="text-[10px]" />
                  {s.messageCount}
                </span>
              </div>
            </div>
            <span className="action-icons flex items-center gap-2">
              <EditOutlined
                className="action-icon action-icon-edit"
                onClick={(e) => startRename(e, s.id, s.name)}
              />
              <DeleteOutlined
                className="action-icon action-icon-delete"
                onClick={(e) => handleDelete(e, s.id)}
              />
            </span>
          </div>
        ),
        value: s.id,
      }))}
      popupRender={(menu) => (
        <div>
          {menu}
          <div className="border-t border-gray-100 mt-1 pt-1 px-2 pb-1">
            <Button
              type="text"
              size="small"
              icon={<PlusOutlined />}
              className="w-full text-xs text-left justify-start text-gray-500 hover:text-blue-600"
              onClick={handleCreate}
            >
              新建会话
            </Button>
          </div>
        </div>
      )}
    />
  );
}

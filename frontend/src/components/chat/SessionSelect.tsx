import { useEffect, useState } from "react";
import { Select, Button, Input } from "antd";
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { useChatStore } from "../../stores/chat-store";

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

  return (
    <div className="flex items-center gap-2">
      <Select
        className="min-w-[160px]"
        size="small"
        placeholder="选择会话"
        loading={sessionsLoading}
        value={activeSessionId}
        onChange={handleSelect}
        disabled={loading}
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
              className="text-xs"
            />
          ) : (
            <div className="flex items-center justify-between group w-full">
              <span className="truncate text-xs">{s.name}</span>
              <span className="hidden group-hover:flex items-center gap-0.5 shrink-0">
                <EditOutlined
                  className="text-[11px] text-gray-400 hover:text-blue-500"
                  onClick={(e) => startRename(e, s.id, s.name)}
                />
                <DeleteOutlined
                  className="text-[11px] text-gray-400 hover:text-red-500"
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
            <div className="border-t border-gray-100 mt-1 pt-1 px-2">
              <Button
                type="text"
                size="small"
                icon={<PlusOutlined />}
                className="w-full text-xs text-left justify-start"
                onClick={handleCreate}
              >
                新建会话
              </Button>
            </div>
          </div>
        )}
      />
    </div>
  );
}

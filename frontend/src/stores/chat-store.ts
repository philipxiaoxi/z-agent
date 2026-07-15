import { create } from "zustand";

export type BlockType = "text" | "tool_call" | "tool_result" | "thinking" | "cancelled" | "subagent";

export interface FileItem {
  name: string;
  type: "file" | "folder";
  size?: number;
  modified_at?: string;
}

export interface FileListData {
  current_path?: string;
  path?: string;
  items?: FileItem[];
  total?: number;
}

export interface HtmlPreviewData {
  title: string;
  html: string;
  height: number;
}

export type SubagentStepType = "text" | "thinking" | "tool_start" | "tool_result" | "error";

export interface SubagentStep {
  step_type: SubagentStepType;
  content?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: string;
}

export interface Block {
  id: string;
  type: BlockType;
  content?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: string;
  collapsed: boolean;
  task?: string;
  steps?: SubagentStep[];
  done?: boolean;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  blocks: Block[];
}

export interface SessionSummary {
  id: string;
  name: string;
  createdAt: number;
  messageCount: number;
}

interface ChatState {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  messages: Message[];
  sessionsLoading: boolean;
  messagesLoading: boolean;
  storeReady: boolean;
  _initializing: boolean;

  initialize: () => Promise<void>;
  fetchSessions: () => Promise<void>;
  ensureOneSession: () => Promise<string | null>;
  createSession: () => Promise<string | null>;
  deleteSession: (id: string) => Promise<void>;
  renameSession: (id: string, name: string) => Promise<void>;
  switchSession: (id: string) => Promise<void>;

  addMessage: (msg: Message) => void;
  appendText: (chunk: string) => void;
  addToolCall: (tool: string, args: Record<string, unknown>) => void;
  addToolResult: (tool: string, result: string) => void;
  appendThinking: (chunk: string) => void;
  addSubagentStart: (id: string, task: string) => void;
  addSubagentStep: (id: string, step: SubagentStep) => void;
  addSubagentEnd: (id: string, result: string) => void;
  markCancelled: () => void;
  toggleBlockCollapsed: (blockId: string) => void;

  workdir: string;
  setWorkdir: (path: string) => void;

  clear: () => void;
}

function withNewBlock(s: ChatState, block: Block): Partial<ChatState> {
  if (!s.messages.length) return s;
  const last = s.messages[s.messages.length - 1]!;
  return {
    messages: [
      ...s.messages.slice(0, -1),
      { ...last, blocks: [...last.blocks, block] },
    ],
  };
}

const WORKDIR_KEY = "zagent_workdir";

function loadWorkdir(): string {
  try {
    return localStorage.getItem(WORKDIR_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveWorkdir(path: string) {
  try {
    if (path) {
      localStorage.setItem(WORKDIR_KEY, path);
    } else {
      localStorage.removeItem(WORKDIR_KEY);
    }
  } catch {
    // localStorage 不可用时静默失败
  }
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  messages: [],
  sessionsLoading: false,
  messagesLoading: false,
  storeReady: false,
  _initializing: false,
  workdir: loadWorkdir(),

  initialize: async () => {
    if (get()._initializing) return;
    set({ _initializing: true });
    await get().fetchSessions();
    await get().ensureOneSession();
    set({ _initializing: false });
  },

  fetchSessions: async () => {
    set({ sessionsLoading: true });
    try {
      const res = await fetch("/api/sessions/");
      const data = await res.json();
      set({ sessions: data.sessions ?? [], sessionsLoading: false, storeReady: true });
    } catch {
      set({ sessionsLoading: false, storeReady: true });
    }
  },

  ensureOneSession: async () => {
    const { sessions } = get();
    if (sessions.length > 0) return null;
    const id = await get().createSession();
    return id;
  },

  createSession: async () => {
    try {
      const res = await fetch("/api/sessions/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const session = await res.json();
      await get().fetchSessions();
      return session.id;
    } catch {
      return null;
    }
  },

  deleteSession: async (id: string) => {
    try {
      await fetch(`/api/sessions/${id}`, { method: "DELETE" });
      const { activeSessionId } = get();
      await get().fetchSessions();
      if (activeSessionId === id) {
        const { sessions } = get();
        if (sessions.length > 0) {
          get().switchSession(sessions[0].id);
        } else {
          set({ activeSessionId: null, messages: [] });
        }
      }
    } catch {
      // ignore
    }
  },

  renameSession: async (id: string, name: string) => {
    try {
      await fetch(`/api/sessions/${id}/name`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      set((s) => ({
        sessions: s.sessions.map((se) => (se.id === id ? { ...se, name } : se)),
      }));
    } catch {
      // ignore
    }
  },

  switchSession: async (id: string) => {
    if (id === get().activeSessionId) return;
    set({ messagesLoading: true });
    try {
      const res = await fetch(`/api/sessions/${id}`);
      const data = await res.json();
      set({
        activeSessionId: id,
        messages: data.messages ?? [],
        messagesLoading: false,
      });
    } catch {
      set({ messages: [], messagesLoading: false, activeSessionId: id });
    }
  },

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  appendText: (chunk) =>
    set((s) => {
      if (!s.messages.length) return s;
      const last = s.messages[s.messages.length - 1]!;
      const blocks = [...last.blocks];
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock?.type === "text") {
        blocks[blocks.length - 1] = {
          ...lastBlock,
          content: (lastBlock.content || "") + chunk,
        };
      } else {
        blocks.push({
          id: crypto.randomUUID(),
          type: "text",
          content: chunk,
          collapsed: false,
        });
      }
      return {
        messages: [
          ...s.messages.slice(0, -1),
          { ...last, blocks },
        ],
      };
    }),

  addToolCall: (tool, args) =>
    set((s) =>
      withNewBlock(s, {
        id: crypto.randomUUID(),
        type: "tool_call",
        tool,
        args,
        collapsed: true,
      })
    ),

  addToolResult: (tool, result) =>
    set((s) =>
      withNewBlock(s, {
        id: crypto.randomUUID(),
        type: "tool_result",
        tool,
        result,
        collapsed: true,
      })
    ),

  appendThinking: (chunk) =>
    set((s) => {
      if (!s.messages.length) return s;
      const last = s.messages[s.messages.length - 1]!;
      const blocks = [...last.blocks];
      const lastBlock = blocks[blocks.length - 1];
      if (lastBlock?.type === "thinking") {
        blocks[blocks.length - 1] = {
          ...lastBlock,
          content: (lastBlock.content || "") + chunk,
        };
      } else {
        blocks.push({
          id: crypto.randomUUID(),
          type: "thinking",
          content: chunk,
          collapsed: false,
        });
      }
      return {
        messages: [
          ...s.messages.slice(0, -1),
          { ...last, blocks },
        ],
      };
    }),

  markCancelled: () =>
    set((s) => {
      if (!s.messages.length) return s;
      const last = s.messages[s.messages.length - 1]!;
      return {
        messages: [
          ...s.messages.slice(0, -1),
          {
            ...last,
            blocks: [
              ...last.blocks,
              { id: crypto.randomUUID(), type: "cancelled" as BlockType, content: "对话已终止", collapsed: false },
            ],
          },
        ],
      };
    }),

  addSubagentStart: (id, task) =>
    set((s) =>
      withNewBlock(s, {
        id,
        type: "subagent" as BlockType,
        task,
        steps: [],
        result: "",
        done: false,
        collapsed: true,
      })
    ),

  addSubagentStep: (id, step) =>
    set((s) => {
      if (!s.messages.length) return s;
      const last = s.messages[s.messages.length - 1]!;
      const blocks = last.blocks.map((b) => {
        if (b.id !== id || b.type !== "subagent") return b;
        const steps = [...(b.steps ?? [])];
        if (step.step_type === "text" || step.step_type === "thinking") {
          if (steps.length > 0 && steps[steps.length - 1].step_type === step.step_type) {
            const prev = steps[steps.length - 1];
            steps[steps.length - 1] = { ...prev, content: (prev.content ?? "") + (step.content ?? "") };
          } else {
            steps.push({ ...step });
          }
        } else {
          steps.push({ ...step });
        }
        return { ...b, steps };
      });
      return {
        messages: [...s.messages.slice(0, -1), { ...last, blocks }],
      };
    }),

  addSubagentEnd: (id, result) =>
    set((s) => {
      if (!s.messages.length) return s;
      const last = s.messages[s.messages.length - 1]!;
      const blocks = last.blocks.map((b) =>
        b.id === id && b.type === "subagent"
          ? { ...b, result, done: true }
          : b
      );
      return {
        messages: [...s.messages.slice(0, -1), { ...last, blocks }],
      };
    }),

  toggleBlockCollapsed: (blockId) =>
    set((s) => ({
      messages: s.messages.map((msg) => ({
        ...msg,
        blocks: msg.blocks.map((b) =>
          b.id === blockId ? { ...b, collapsed: !b.collapsed } : b
        ),
      })),
    })),

  setWorkdir: (path) => {
    saveWorkdir(path);
    set({ workdir: path });
  },

  clear: () => {
    saveWorkdir("");
    set({ messages: [], workdir: "" });
  },
}));

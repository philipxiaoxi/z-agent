import { create } from "zustand";

export type BlockType = "text" | "tool_call" | "tool_result";

export interface Block {
  id: string;
  type: BlockType;
  content?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: string;
  collapsed: boolean;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  blocks: Block[];
}

interface ChatState {
  messages: Message[];
  workdir: string;
  addMessage: (msg: Message) => void;
  appendText: (chunk: string) => void;
  addToolCall: (tool: string, args: Record<string, unknown>) => void;
  addToolResult: (tool: string, result: string) => void;
  toggleBlockCollapsed: (blockId: string) => void;
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

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  workdir: "",

  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),

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

  toggleBlockCollapsed: (blockId) =>
    set((s) => ({
      messages: s.messages.map((msg) => ({
        ...msg,
        blocks: msg.blocks.map((b) =>
          b.id === blockId ? { ...b, collapsed: !b.collapsed } : b
        ),
      })),
    })),

  setWorkdir: (path) => set({ workdir: path }),

  clear: () => set({ messages: [], workdir: "" }),
}));

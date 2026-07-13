# 思考内容（Thinking）前后端支持方案

## 现状分析

### 后端

当前 `backend/app/api/routes/agent.py` 的流式循环处理了以下事件类型：

| 事件类型 | 当前处理 |
|----------|---------|
| `ToolCallStarted` | 发送 `tool_start`，加入 `segments` |
| `ToolCallCompleted` | 发送 `tool_result`，加入 `segments` |
| `ToolCallError` | 发送 `tool_result`（含错误信息）|
| `RunError` | 发送 `error` |
| `RunContent` / `IntermediateRunContent` | 提取 `event.content` 发 `text` 事件，加入 `segments` |
| `done` | 标记流结束 |
| **`reasoning_content`** | **完全忽略** |

### 前端

| 模块 | 当前状态 |
|------|---------|
| `BlockType` | `"text"` `"tool_call"` `"tool_result"` `"file_list"` `"html_preview"` — 无 `"thinking"` |
| `BlockView` | 按 type 分发，无 thinking 组件 |
| `ws.ts` ServerEvent | 无 `"thinking"` 类型 |
| `WsEvents` | 无 `onThinking` 回调 |
| `chat-store` | 无 `appendThinking` 方法 |

### 框架层（Agno）支持情况

- `_parse_provider_response_delta()` 已从 DeepSeek 流式 chunk 提取 `reasoning_content` 并设置到 `ModelResponse`
- `handle_model_response_chunk()` 已把 `reasoning_content` 传递到 `RunContentEvent.reasoning_content`
- DeepSeek 模型默认启用 thinking mode（`extra_body: {"thinking": {"type": "enabled"}}`）
- 当前 `agent.py` 只检查了 `event.content`，完全忽略了 `event.reasoning_content`

---

## 修改清单

### 1. 后端配置 — `backend/app/core/config.py`

新增配置项：

```python
STORE_THINKING_IN_CONTEXT: bool = True  # 控制是否将 reasoning_content 存入 LLM 上下文
```

通过环境变量 `STORE_THINKING_IN_CONTEXT=false` 可关闭。

### 2. 后端流式处理 — `backend/app/api/routes/agent.py`

#### 2a. 流式循环内新增 `thinking` 处理

在 `RunContent` / `IntermediateRunContent` 分支中，除了处理 `event.content`，新增 `event.reasoning_content` 的提取与发送：

```
对于每个 event:
  reasoning_chunk = getattr(event, "reasoning_content", None)
  if reasoning_chunk:
    → 追加到 thinking_buf
    → 每段 > 0 字符时发送 { type: "thinking", content: chunk }
    → 加入 segments: { type: "thinking", content: chunk }
```

流结束后 flush 余量。

#### 2b. Blocks 重建新增 `thinking` 类型

在 blocks 构建循环中新增分支：

```python
elif seg["type"] == "thinking":
    blocks.append({
        "id": str(uuid4()),
        "type": "thinking",
        "content": seg["content"],
        "collapsed": False,  # 默认展开
    })
```

#### 2c. LLM 消息构建新增 `reasoning_content`

在构建 assistant 消息时，如 `store_thinking_in_context` 为 True，将 thinking 内容合并到最后一个 assistant 消息的 `reasoning_content` 字段：

```python
if store_thinking and pending_text.strip():
    msg = {"role": "assistant", "content": pending_text.strip()}
    if thinking_text:
        msg["reasoning_content"] = thinking_text
    llm_msgs.append(msg)
```

### 3. 前端类型 — `frontend/src/stores/chat-store.ts`

```typescript
type BlockType = "text" | "tool_call" | "tool_result" | "file_list" | "html_preview" | "thinking";
```

`Block` 接口无需修改（复用 `content` 字段存储思考文本，`collapsed` 控制展开/折叠）。

新增方法 `appendThinking(chunk: string)`：

```
逻辑：
  1. 取出最后一条 assistant 消息
  2. 如果最后一块是 thinking 类型 → 追加到其 content
  3. 否则 → 新建一个 thinking block 追加到 blocks
```

### 4. 前端 WebSocket — `frontend/src/lib/ws.ts`

```typescript
type ServerEvent =
  | { type: "text"; content: string }
  | { type: "thinking"; content: string }   // ← 新增
  | { type: "tool_start"; ... }
  | ...

interface WsEvents {
  onThinking: (content: string) => void;     // ← 新增
  ...
}
```

### 5. 前端 WebSocket Hook — `frontend/src/hooks/useChatWs.tsx`

从 store 获取 `appendThinking`，在 `onThinking` 回调中调用。

### 6. 前端 ThinkingBlock 组件 — `frontend/src/components/chat/BlockView.tsx`

新增 `ThinkingBlock` 组件：

- 左侧灰色竖线边框
- 标题栏：💡 图标 + "思考过程" 文字
- 点击折叠/展开（默认展开）
- 内容用 `react-markdown` 渲染
- 加载中（无 content）时显示 `Spin`

在 `BlockView` 的 `switch` 中新增：

```typescript
case "thinking":
  return <ThinkingBlock block={block} />;
```

---

## 数据流

```
用户输入 → agent.arun(stream=True, stream_events=True)

  DeepSeek API streaming chunk
  ├─ delta.content              → ModelResponse.content
  │   → RunContentEvent.content → agent.py → { type: "text", content }
  │   → WebSocket → frontend → appendText()
  │
  └─ delta.reasoning_content    → ModelResponse.reasoning_content
      → RunContentEvent.reasoning_content → agent.py → { type: "thinking", content }
      → WebSocket → frontend → appendThinking()

流结束 → 重建 blocks（含 thinking）
       → 保存 session（messages 含 thinking block）
       → 保存 llm_history（含 reasoning_content，受开关控制）
```

---

## 会话持久化格式

### messages（始终包含 thinking block）

```json
{
  "id": "msg-uuid",
  "role": "assistant",
  "blocks": [
    {
      "id": "thinking-uuid",
      "type": "thinking",
      "content": "模型思考的完整文本...",
      "collapsed": false
    },
    {
      "id": "text-uuid",
      "type": "text",
      "content": "模型最终回答...",
      "collapsed": false
    }
  ]
}
```

### llm_history（受 `STORE_THINKING_IN_CONTEXT` 控制）

```json
{
  "role": "assistant",
  "content": "模型最终回答...",
  "reasoning_content": "模型思考的完整文本..."
}
```

---

## 注意事项

1. **thinking block 在 text block 之前**：按事件到达顺序，thinking 内容总是先于最终回答到达，所以自然排在前列。
2. **旧会话兼容**：旧数据没有 thinking block，BlockView 默认走 `TextBlock`，不会报错。
3. **多个 thinking block**：如果多次 reasoning（工具调用后重新推理），会产生多个 thinking block，各自独立折叠。
4. **thinking_buf flush 策略**：与 text_buf 类似，在 tool_call 事件前、流结束时 flush。

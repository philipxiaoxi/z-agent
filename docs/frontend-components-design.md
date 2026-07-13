# 前端组件标签系统设计方案

## 背景

当前 `show_directory` 和 `show_html_preview` 是注册在后端的 Agno 工具，通过工具调用 → `send_to_frontend` 回调 → WebSocket 事件 → 前端的链路工作。这条链路存在以下问题：

1. **上下文浪费**：工具定义、工具调用、工具返回三者都消耗 LLM token，每调用一次约 200-500 tokens
2. **链路复杂**：需要后端工具注册 → send_to_frontend 闭包注入 → segments 记录 → block 重建 → WebSocket 推送 → 前端路由，中间经过 5 个环节
3. **扩展成本高**：每增加一个"前端展示"类工具，都要走完整套链路，且继续消耗上下文
4. **前后端耦合**：前端 UI 渲染逻辑依赖后端工具定义的触发

## 新方案：前端组件标签系统

### 核心思想

AI 直接在文本回复中输出特定格式的标签，前端解析后渲染对应组件。完全不经过后端工具注册、工具调用、WebSocket 通知。

```
旧方案：AI → 调用工具 → 后端执行 → WebSocket → 前端渲染
新方案：AI → 输出标签 → 前端解析 → 前端渲染
```

### 标签格式

采用 **markdown fenced code block + `z-` prefix language** 格式：

````markdown
```z-{组件名}
{JSON 格式参数}
```
````

选择此格式的原因：
- 原生 markdown 语法，AI 天然熟悉 fenced code block
- JSON 天然支持多层嵌套、多参数、可选字段
- `z-` 前缀隔离命名空间，不会误伤普通代码块
- 无需 HTML 转义处理

### 组件定义

#### z-file-list

将文件列表渲染为可视化文件浏览器。

**参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | 是 | 目录路径，如 `/sata12/my/data` |
| `items` | array | 是 | 文件/文件夹列表 |
| `items[].name` | string | 是 | 文件名 |
| `items[].type` | string | 是 | `"file"` 或 `"folder"`（兼容 `"directory"`/`"dir"`） |
| `items[].size` | number | 否 | 文件大小（字节） |
| `items[].modified_at` | string | 否 | 修改时间戳 |
| `total` | number | 否 | 总条目数 |

**使用时机**：调用 `zspace-cli_list_files` 获取数据后，立即用此组件展示。

**示例**：

````markdown
```z-file-list
{
  "path": "/sata12/data",
  "items": [
    {"name": "文档", "type": "folder", "modified_at": "1700000000"},
    {"name": "readme.txt", "type": "file", "size": 2048, "modified_at": "1699000000"}
  ],
  "total": 2
}
```
````

**规则**：输出此标签后，文字中不要再总结文件信息（如"共有 X 个文件夹""以下是文件列表"等）。

#### z-html-preview

在对话中渲染 HTML 交互页面，以可折叠卡片形式展示。

**参数**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title` | string | 是 | 预览卡片标题 |
| `html` | string | 是 | 完整 HTML 文档（可含 `<style>`、`<script>`） |
| `height` | number | 否 | 预览区域高度（像素），默认 400 |

**使用时机**：需要展示数据可视化、文件内容预览、交互式演示、临时小程序等场景。

**示例**：

````markdown
```z-html-preview
{
  "title": "系统监控",
  "html": "<html><body><h1>Disk Usage</h1><div id='chart'>...</div><script>...</script></body></html>",
  "height": 500
}
```
````

**内置 API**：HTML 中可使用 `window.__zspace.fillInput(text)` 将文本填充到用户输入框，适合用户点击时填入文件路径等。例如：

```html
<button onclick="__zspace.fillInput('/sata12/my/data/file.txt')">填入路径</button>
```

注意：此 API 仅用于填充输入框，不可用于敏感操作。

### 工具 vs 前端组件的区分

| 维度 | 后端工具 (Tools) | 前端组件 (Components) |
|------|-----------------|----------------------|
| 注册方式 | Agno `Function` 注册 | 无——仅系统提示词描述 |
| 调用方式 | AI 发起工具调用，后端执行 | AI 直接输出标签，前端解析 |
| 运行位置 | 后端 Python | 前端浏览器 |
| 数据传输 | 工具参数 → WebSocket 推送 | 嵌入 AI 回复文本 |
| 上下文消耗 | 高（定义+调用+返回） | 低（仅文本中的 JSON 行） |
| 典型操作 | 获取数据、修改数据 | 展示数据、预览内容 |
| 示例 | `zspace-cli_list_files`, `set_workdir` | `z-file-list`, `z-html-preview` |

**使用原则**：
- 后端工具 = 用来获取/操作 NAS 数据
- 前端组件 = 用来展示/渲染数据
- 获取数据用工具，展示数据用组件

## 实现方案

### 前端：TextBlock 标签解析

在 `TextBlock` 组件中做前处理，将内容分割为文本段和组件段，分别渲染。

```typescript
function parseTagBlocks(content: string): Segment[] {
  // 正则匹配完整标签：```z-{name}\n{JSON}\n```
  // 不完整的标签（streaming 中）不匹配，回退为普通文本
  const regex = /```z-(\w+)\s*\n?([\s\S]*?)```/g;
  // ... 分割逻辑
}

// 渲染时：
// 文本段 → <ReactMarkdown>
// 文件列表段 → <FileListBlock>
// HTML 预览段 → <HtmlPreviewBlock>
```

### 数据规范化

前端 `FileListBlock` 增加数据规范化，兼容 `list_files` MCP 工具的原始输出：

- `type` 字段：`"folder"`/`"directory"`/`"dir"` → `"folder"`
- `size` 字段：确保为数字类型

### 后端清理

1. 删除 `show_directory.py` 和 `show_html_preview.py`
2. 从 `tools/__init__.py` 移除导入和注册
3. 从 `agent.py` 移除 `send_to_frontend` 回调、segments 记录、block 重建
4. 移除 `file_list`/`html_preview` 事件类型的 WebSocket 发送

### 系统提示词更新

铁律 #2 改为：

> **list_files 后必须输出 z-file-list 标签**：拿到结果后立即用 `z-file-list` 组件展示，否则任务失败。输出后文字中不要再总结文件信息。

新增"前端组件"章节，文档化可用组件及其用法。

## 涉及变更文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `backend/app/core/tools/show_directory.py` | 删除 | 不再需要 |
| `backend/app/core/tools/show_html_preview.py` | 删除 | 不再需要 |
| `backend/app/core/tools/__init__.py` | 修改 | 移除导入+注册+send_to_frontend 参数 |
| `backend/app/api/routes/agent.py` | 修改 | 移除事件/block 相关代码 |
| `backend/app/core/prompt/docs/system-instructions.md` | 修改 | 替换铁律+新增组件章节 |
| `frontend/src/components/chat/BlockView.tsx` | 修改 | TextBlock 增加标签解析 |
| `frontend/src/components/chat/FileListBlock.tsx` | 修改 | 增加数据规范化 |
| `frontend/src/stores/chat-store.ts` | 修改 | 移除 addFileList/addHtmlPreview |
| `frontend/src/lib/ws.ts` | 修改 | 移除 file_list/html_preview 事件 |
| `frontend/src/hooks/useChatWs.tsx` | 修改 | 移除对应 WS 回调 |
| `frontend/src/components/chat/HtmlPreviewBlock.tsx` | 无变更 | 保持现有实现 |

## Streaming 兼容说明

AI 流式输出时，标签可能不完整（缺少 closing ```）。此时正则不匹配，内容暂渲染为普通 markdown 代码块。等待标签完整后自动切换为组件渲染。此短暂过渡可接受。

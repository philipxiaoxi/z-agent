<div align="center">
  <h1>zspace-agent</h1>
  <p><em>NAS AI 管理助手 — 用自然语言管理你的存储</em></p>

  <p>
    <img src="https://img.shields.io/badge/python-3.11%2B-blue?logo=python" alt="Python">
    <img src="https://img.shields.io/badge/typescript-5.5%2B-blue?logo=typescript" alt="TypeScript">
    <img src="https://img.shields.io/badge/react-18-blue?logo=react" alt="React">
    <img src="https://img.shields.io/badge/fastapi-latest-009688?logo=fastapi" alt="FastAPI">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  </p>
</div>

## 概述

zspace-agent 是一个基于 AI 的 NAS（网络附加存储）管理助手，代号"极同学"。通过自然语言对话的方式，让你可以像聊天一样管理 NAS 上的文件和存储资源。

项目采用前后端分离架构，后端集成 DeepSeek V4 Flash 大语言模型，通过工具调用（MCP 协议）桥接 [z-cli](https://github.com/philipxiaoxi/z-cli) 命令行，实现对 zspace 私有云 NAS 的完整操作能力。

## 功能特性

- **自然语言交互** — 用日常语言管理 NAS，无需记忆命令
- **文件浏览** — 可视化文件浏览器，支持文件夹导航、按扩展名图标识别
- **会话管理** — 多会话支持，历史记录持久化，会话切换/重命名/删除
- **工作目录** — 限定文件操作范围，路径越界时自动触发用户确认
- **存储概览** — 查看存储池容量、磁盘健康状态、温度信息
- **文件操作** — 列表、搜索、创建、复制、移动、删除、重命名
- **流式输出** — AI 回复实时流式推送，工具调用/返回以卡片形式展示
- **反幻觉设计** — 系统指令强制工具优先，禁止 AI 编造文件状态

## 技术栈

| 层级 | 技术 |
|------|------|
| **AI 引擎** | Agno Framework + DeepSeek V4 Flash |
| **后端** | Python 3.11+ / FastAPI / Uvicorn |
| **前端** | React 18 / TypeScript / Vite |
| **UI 组件** | Ant Design 6 / Tailwind CSS 4 |
| **状态管理** | Zustand |
| **通信** | WebSocket（流式）+ REST API |
| **工具协议** | MCP (Model Context Protocol) |
| **包管理** | uv (Python) / npm (前端) |

## 快速开始

### 前置条件

- Python 3.11+
- Node.js 18+
- uv（Python 包管理器）
- zcli（zspace NAS 命令行工具）
- DeepSeek API Key

### 1. 克隆项目

```bash
git clone https://github.com/your-username/zspace-agent.git
cd zspace-agent
```

### 2. 启动后端

```bash
cd backend
uv sync
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY
uv run uvicorn app.main:app --reload
```

后端默认运行在 `http://localhost:8000`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，开发模式下自动代理 `/api` 到后端。

## 项目结构

```
zspace-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 应用入口
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── agent.py         # WebSocket 主通信（核心）
│   │   │       ├── sessions.py      # 会话 CRUD
│   │   │       ├── pools.py         # 存储池信息
│   │   │       ├── files.py         # 文件查询
│   │   │       └── system.py        # 系统健康检查
│   │   └── core/
│   │       ├── config.py            # 应用配置
│   │       ├── session_store.py     # 会话持久化
│   │       ├── context.py           # LLM 对话上下文
│   │       ├── prompt/
│   │       │   ├── prompts.py       # 提示词加载
│   │       │   └── docs/            # 角色定义 & 系统指令
│   │       └── tools/
│   │           ├── confirm.py       # 用户确认管理
│   │           ├── zcli_mcp_wrapper.py  # MCP 工具包装+路径门禁
│   │           ├── show_directory.py    # 文件浏览器推送
│   │           └── set_workdir.py       # 工作目录设置
│   ├── pyproject.toml
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── routes/chat/
│   │   │   └── ChatPage.tsx         # 主聊天页面
│   │   ├── components/chat/
│   │   │   ├── BlockView.tsx        # 消息块渲染（Markdown/工具/文件）
│   │   │   ├── FileListBlock.tsx    # 文件浏览器组件
│   │   │   ├── SessionSelect.tsx    # 会话选择器
│   │   │   └── WelcomeCard.tsx      # 存储概览欢迎卡片
│   │   ├── stores/
│   │   │   └── chat-store.ts        # Zustand 状态管理
│   │   ├── hooks/
│   │   │   └── useChatWs.tsx        # WebSocket 连接管理
│   │   └── lib/
│   │       └── ws.ts                # WebSocket 客户端
│   ├── package.json
│   └── vite.config.ts
│
├── docs/                            # 文档目录
└── README.md
```

## 架构设计

```
┌─────────────┐     WebSocket      ┌──────────────────┐     MCP      ┌─────────┐
│   React UI  │ ◄──── REST ──────► │  FastAPI Backend  │ ◄─────────► │  zcli   │
│  (Vite SPA) │     stream+JSON    │  + Agno + DeepSeek│             │ (NAS OS)│
└─────────────┘                    └──────────────────┘             └─────────┘
       │                                    │
       │  file_list 事件                     │  路径门禁确认
       │  (可视化文件浏览器)                   │  (异步用户确认)
       ▼                                    ▼
┌─────────────────────┐         ┌──────────────────────┐
│  FileListBlock.tsx   │         │  ConfirmManager       │
│  网格缩略图/文件图标   │         │  + ZcliMCPWrapper    │
└─────────────────────┘         └──────────────────────┘
```

### 数据流

1. **用户输入** → WebSocket → FastAPI `agent_ws` 路由
2. **AI 推理** → Agno 构建 LLM 历史 → 调用 DeepSeek API
3. **流式输出** → 文本块实时推送前端
4. **工具调用** → `tool_start` 事件 → MCP 工具执行 → 路径门禁检查 → `tool_result`
5. **文件可视化** → `show_directory` 工具触发 `file_list` 事件 → 前端渲染文件浏览器
6. **持久化** → 每轮对话后保存 LLM 历史 + 展示 blocks 到会话文件

## API 概览

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agent/ws` | WebSocket | AI 对话主通道 |
| `/api/sessions/` | GET/POST | 会话列表 / 创建 |
| `/api/sessions/{id}` | GET/DELETE | 会话详情 / 删除 |
| `/api/sessions/{id}/name` | PUT | 重命名会话 |
| `/api/pools/` | GET | 存储池列表 |
| `/api/pools/{id}` | GET | 存储池详情 |
| `/api/system/health` | GET | 健康检查 |

## 配置

### 后端 (.env)

```ini
APP_NAME=zspace-agent
APP_ENV=development
HOST=0.0.0.0
PORT=8000
DEEPSEEK_API_KEY=sk-your-key-here
CORS_ORIGINS=["http://localhost:5173"]
```

### 前端 (.env)

```ini
VITE_API_BASE_URL=http://localhost:8000
```

## 开发指南

### 后端开发

```bash
cd backend
uv sync                          # 安装依赖
uv sync --group dev              # 安装开发依赖（pytest, httpx）
uv run uvicorn app.main:app --reload --port 8000
```

### 前端开发

```bash
cd frontend
npm install
npm run dev                      # 启动开发服务器（热更新）
npm run build                    # 生产构建
npm run preview                  # 预览生产构建
```

### 代码风格

- 后端：遵循 PEP 8，使用 Python 3.11+ 类型注解
- 前端：TypeScript strict 模式，ES2020 目标

## 许可证

[MIT](LICENSE)

## 致谢

- [z-cli](https://github.com/philipxiaoxi/z-cli) — zspace NAS 命令行工具

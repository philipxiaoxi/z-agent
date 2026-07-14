# z-agent (极同学)

NAS AI 管理助手，前后端分离结构，通过 MCP 协议调用 z-cli 操作 zspace 私有云，同时支持 Docker sandbox 隔离执行环境。

## 架构

```
React UI (Vite SPA) ←WebSocket+REST→ FastAPI + Agno + DeepSeek V4 Flash ←MCP→ z-cli → zspace NAS
                                                                     └─Docker SDK→ AIO Sandbox 容器
```

- **后端**: `backend/` — Python 3.11+, FastAPI, Agno, uv
- **前端**: `frontend/` — React 18, TypeScript, Vite, Ant Design 6, Tailwind CSS 4, Zustand
- **入口**: `backend/app/main.py:app` (FastAPI app), `frontend/src/main.tsx` (React entry)

## 关键命令

```bash
# 后端（backend/ 下）
uv sync                        # 安装依赖（含 docker + httpx）
uv sync --group dev            # 包含 pytest/httpx（当前无测试）
uv run uvicorn app.main:app --reload --port 8000 --reload-dir app

# 前端（frontend/ 下）
npm install
npm run dev                    # Vite dev server → :5173，自动代理 /api → :8000
npm run build                  # tsc -b && vite build，产物 → backend/static/
npm run preview                # 预览构建产物

# 构建前端并放置到后端静态目录
./scripts/build.sh             # 等效于 cd frontend && npm run build
```

## 关键架构细节

- **前端构建产物**直接输出到 `backend/static/`（`vite.config.ts` 中 `outDir: "../backend/static"`）
- **生产模式**: `scripts/build.sh` 构建前端，然后后端同源服务 `/api` 和 SPA 页面
- **WebSocket 主通道**: `ws://localhost:8000/api/agent/ws` — AI 对话的核心路由（`backend/app/api/routes/agent.py`）
- **流式输出**: Agno `arun(stream=True, stream_events=True)` 实时推送文本 + 工具事件到前端
- **会话持久化**: JSON 文件 `data/sessions/{id}.json`，包含 `messages`（展示用 blocks）和 `llm_history`（LLM 对话历史）
- **工具组成**:
  - **MCP server**（配置驱动）：`backend/mcp_servers.yaml` 中声明，支持 stdio / SSE / Streamable HTTP 三种 transport
    - `zcli` — 13 个 NAS 管理工具
  - **本地工具**：`set_workdir`（NAS 文件操作的工作目录设置）+ `sandbox_*`（Docker 沙箱操作，通过动态 MCP 注册连接到 AIO Sandbox 原生 Hub）
- **动态 MCP 注册**：`MCPRegistry.connect_dynamic()` 支持运行时动态连接 Streamable HTTP MCP server
- **路径门禁**: 可在 `mcp_servers.yaml` 中对每个 MCP server 独立开启（`path_gate: true`）。开启后越界时异步请求前端用户确认
- **非路径确认**: 可在 `mcp_servers.yaml` 中为工具指定 `confirm_tools`（如 `create_container`），调用时发确认请求
- **MCP Registry**（`backend/app/core/mcp/`）：统一管理多个 MCPTools 实例的生命周期，配置驱动，新增 server 只需改 yaml
- **提示词系统**: `backend/app/core/prompt/docs/role.md` + `system-instructions.md`，启动时加载
  - 反幻觉设计：所有文件操作必须走工具，禁止 AI 编造文件状态
  - 铁律：list_files 后必须输出 z-file-list 组件
- **配置文件**: `backend/.env`（示例见 `backend/.env.example`）+ `backend/mcp_servers.yaml`
- **开发代理**: Vite dev server 自动代理 `/api` 到 `localhost:8000`

## 代码约定

- **后端**: PEP 8, Python 3.11+ 类型注解, async/await
- **前端**: TypeScript strict 模式, ES2020 target, 函数组件 + Hooks, Zustand 状态管理
- **命名可读性**: 禁止单字母/缩写命名（`d`, `x`, `v` 等），lambda 临时解构和数学公式除外；使用完整有语义的名称
- **提交规范**: Conventional Commits (`feat:/fix:/refactor:/docs:/chore:/style:`)，中文描述，行 ≤ 72 字符

## 边界

- 无 CI/CD 配置
- 无测试文件
- 无需 lint/format 命令（项目无 ruff/mypy 等配置，前端 lint 内置于 `npm run build` 的 `tsc -b` 中）
- 依赖外部 `z-cli`（命令行工具）+ DeepSeek API Key + zspace 桌面客户端 + Docker Desktop（macOS）/ Docker CE
- 会话数据 untracked（`data/sessions/` 在 `.gitignore` 中）

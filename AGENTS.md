# z-agent (极同学)

NAS AI 管理助手，前后端分离结构，通过 MCP 协议调用 z-cli 操作 zspace 私有云。

## 架构

```
React UI (Vite SPA) ←WebSocket+REST→ FastAPI + Agno + DeepSeek V4 Flash ←MCP→ z-cli → zspace NAS
```

- **后端**: `backend/` — Python 3.11+, FastAPI, Agno, uv
- **前端**: `frontend/` — React 18, TypeScript, Vite, Ant Design 6, Tailwind CSS 4, Zustand
- **入口**: `backend/app/main.py:app` (FastAPI app), `frontend/src/main.tsx` (React entry)

## 关键命令

```bash
# 后端（backend/ 下）
uv sync                        # 安装依赖
uv sync --group dev            # 包含 pytest/httpx（当前无测试）
uv run uvicorn app.main:app --reload --port 8000 --reload-exclude '.venv/**'

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
- **路径门禁**: 所有 MCP 工具调用前检查路径是否在工作目录内，越界时异步请求前端用户确认
- **提示词系统**: `backend/app/core/prompt/docs/role.md` + `system-instructions.md`，启动时加载
  - 反幻觉设计：所有文件操作必须走工具，禁止 AI 编造文件状态
  - 铁律：list_files → show_directory 必须成对调用
- **工具组成**: zcli MCP 工具（zspace-cli_list_files 等）+ 3 个本地工具（set_workdir, show_directory, show_html_preview）
- **配置文件**: `backend/.env`（示例见 `backend/.env.example`）
- **开发代理**: Vite dev server 自动代理 `/api` 到 `localhost:8000`

## 代码约定

- **后端**: PEP 8, Python 3.11+ 类型注解, async/await
- **前端**: TypeScript strict 模式, ES2020 target, 函数组件 + Hooks, Zustand 状态管理
- **提交规范**: Conventional Commits (`feat:/fix:/refactor:/docs:/chore:/style:`)，中文描述，行 ≤ 72 字符

## 边界

- 无 CI/CD 配置
- 无测试文件
- 无需 lint/format 命令（项目无 ruff/mypy 等配置，前端 lint 内置于 `npm run build` 的 `tsc -b` 中）
- 依赖外部 `z-cli`（命令行工具）+ DeepSeek API Key + zspace 桌面客户端
- 会话数据 untracked（`data/sessions/` 在 `.gitignore` 中）

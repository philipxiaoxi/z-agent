# Dify 工作流接入方案

## 概述

将 Dify Workflow 暴露为 AI 工具，AI 根据用户意图决定何时调用哪个工作流。每个 Dify 应用注册为一个独立工具，工具参数动态映射自 Dify 的 `user_input_form`。

```
dify_workflows.yaml → DifyClientPool(initialize → get_parameters)
                            │
get_tools()                  │
  ├─ dify_translation       │
  ├─ dify_content_review    ├─ run_workflow() [streaming]
  └─ dify_xxx ...           ├─ upload_file()   [文件上传]
                            └─ stream_events() [预留: 重连]
```

## 核心设计

### 1. 配置驱动

新建 `backend/dify_workflows.yaml`，声明所有 Dify 应用：

```yaml
workflows:
  translation:
    name: translation
    description: 多语言翻译工作流，接收文本和源文档，返回翻译结果
    api_base_url: https://dify.example.com/v1
    api_key: ${DIFY_TRANSLATION_API_KEY}
    enabled: true
    max_execution_time: 60

  content_review:
    name: content_review
    description: 内容审核工作流，检查文档合规性并生成审核报告
    api_base_url: https://dify.example.com/v1
    api_key: ${DIFY_CONTENT_REVIEW_API_KEY}
    enabled: false
    max_execution_time: 60
```

- `api_key` 支持 `${ENV_VAR}` 引用环境变量，避免明文
- 每个 workflow 独立配置 base URL 和 Key
- enabled=false 则跳过加载

### 2. 模块结构: `backend/app/core/dify/`

```
app/core/dify/
├── __init__.py       # 包入口
├── config.py         # DifyWorkflowConfig + load_dify_config()
├── client.py         # DifyClient: httpx 封装
├── streamer.py       # DifyEventStreamer: SSE 累积
├── file_resolver.py  # 本机路径 / zcli download 解析
├── tools.py          # DifyWorkflowToolFactory: 构建 Function
└── pool.py           # DifyClientPool: 生命周期管理
```

### 3. 类型映射

Dify `user_input_form` 类型 → JSON Schema 映射：

| Dify 类型 | Schema 类型 | 说明 |
|-----------|------------|------|
| `text-input` | `string` | 短文本输入 |
| `paragraph` | `string` | 段落文本 |
| `select` | `string` + `enum` | 下拉选择 |
| `number` | `number` | 数字 |
| `file` | `string` | NAS 或本机路径；本机直传，否则 `zcli download` 后上传 |
| `file-list` | `array[string]` | 同上，数组逐个处理 |

### 4. 工具执行流程

```
AI 调用 dify_translation(query="...", target_language="en")
  │
  ├─ ① 解析文件参数
  │   本机路径存在 → 直接读
  │   否则 → zcli download 到临时目录
  │   → DifyClient.upload_file() → upload_file_id（按扩展名推断 type）
  │   替换 inputs 中的路径为 {type, transfer_method, upload_file_id}
  │
  ├─ ② DifyClient.run_workflow(inputs, response_mode="streaming")
  │   POST /workflows/run → SSE 流
  │
  ├─ ③ DifyEventStreamer.accumulate()
  │   消耗 SSE 流，累积 text_chunk，遇 workflow_finished 返回
  │   60s 超时由 httpx.Timeout 控制
  │
  └─ ④ 返回累积文本 → tool_result → AI 总结
```

### 5. 数据流

```
用户: "帮我把这份合同翻译成英文"
  ↓
AI 决定调用 dify_translation(query="合同内容...", target_language="en")
  ↓
tool_start (dify_translation)  →  前端 tool_call block
  ↓ (工具内部，对 LLM 透明)
DifyClient.run_workflow()
  └─ SSE 流 → DifyEventStreamer 累积文本
  ↓
tool_result (dify_translation) →  前端 tool_result block
  ↓
AI 总结 → text stream
```

### 6. 集成点

| 文件 | 操作 |
|------|------|
| `backend/app/core/config.py` | 添加 `DIFY_WORKFLOWS_CONFIG: str = ""` |
| `backend/app/main.py` | lifespan 中初始化 `DifyClientPool` |
| `backend/app/core/tools/__init__.py` | `get_tools()` 接受 `dify_pool`，追加工具 |
| `backend/app/api/routes/agent.py` | 构建工具时传入 `dify_pool` |

### 7. 前端

一期无需改动。Dify 工作流执行表现为标准的 `tool_call` / `tool_result` block，复用现有事件体系和渲染组件。

## 扩展预留

| 未来需求 | 预留机制 |
|----------|----------|
| 人工介入 | `DifyEventStreamer.iter_events()` 遇 `workflow_paused` 返回事件流；复刻 `ConfirmManager` 模式 |
| 进度可视化 | `iter_events()` 基础上扩展，`node_started`/`node_finished` 映射为子事件 |
| 多个 Dify 实例 | 配置文件中声明多个 workflow，各自独立 base URL 和 Key |
| 断流重连 | `client.stream_events(workflow_run_id)` 使用 `GET /workflow/{run_id}/events` |
| 文件上传 | `file_resolver`：本机直传 / NAS 经 `zcli download` 后再 `upload_file`；每次工具调用有文件时弹一次确认 |

## 文件清单

| # | 文件 | 操作 |
|---|------|------|
| 1 | `backend/dify_workflows.yaml` | 新建 |
| 2 | `backend/app/core/dify/__init__.py` | 新建 |
| 3 | `backend/app/core/dify/config.py` | 新建 |
| 4 | `backend/app/core/dify/client.py` | 新建 |
| 5 | `backend/app/core/dify/streamer.py` | 新建 |
| 6 | `backend/app/core/dify/tools.py` | 新建 |
| 7 | `backend/app/core/dify/pool.py` | 新建 |
| 8 | `backend/app/core/config.py` | 修改 |
| 9 | `backend/app/main.py` | 修改 |
| 10 | `backend/app/core/tools/__init__.py` | 修改 |
| 11 | `backend/app/api/routes/agent.py` | 修改 |
| 12 | `backend/.env.example` | 修改 |

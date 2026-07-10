# 贡献指南

感谢你考虑为 zspace-agent 贡献代码！

## 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feat/amazing-feature`)
3. 提交改动 (`git commit -m 'feat: 添加某个功能'`)
4. 推送到分支 (`git push origin feat/amazing-feature`)
5. 创建 Pull Request

## 提交规范

项目使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>: <简短描述>

<详细说明（可选）>
```

### 常用类型

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构 |
| `docs` | 文档 |
| `chore` | 构建/工具链 |
| `style` | 格式调整 |

### 规则

- 描述行不超过 72 字符
- 使用中文描述
- 提交前确认只包含预期的改动

## 本地开发

参见 [README](README.md#快速开始) 中的快速开始指南。

### 后端

```bash
cd backend
uv sync --group dev  # 包含 pytest, httpx
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 代码规范

### 后端 (Python)

- 遵循 PEP 8
- 使用 Python 3.11+ 类型注解
- 异步优先（async/await）

### 前端 (TypeScript/React)

- TypeScript strict 模式
- 使用函数组件 + Hooks
- 状态管理使用 Zustand

## Pull Request 检查清单

- [ ] 代码已自测
- [ ] 无 TypeScript 编译错误
- [ ] 无 Python 语法错误
- [ ] 提交信息符合规范
- [ ] 只包含预期改动（无无关文件）

# Certificate Admin Console

Vue 3 + Element Plus / FastAPI + SQLAlchemy / SQLite 的技术面试项目。

当前仅完成工程初始化和共享契约。前端显示骨架说明；`/api/health` 可用，其他业务接口均返回 `501 not_implemented`。尚未实现登录、数据库模型、seed、发证或导出。

## 启动

需要 Node.js >= 22.12 和 Python 3.12 或 3.13。项目使用 npm workspaces；只在仓库根目录管理 npm 锁文件。

首次安装（每个 worktree 单独执行）：

```powershell
npm run setup
```

Python 不在 PATH 或指向 Windows Store 占位程序时，先设置真实解释器路径：

```powershell
$env:PYTHON_EXECUTABLE = 'C:\path\to\python.exe'
npm run setup
```

安装后，一条命令同时启动前后端：

```powershell
npm run dev
```

- 前端：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 前端通过 `/api` 同源代理访问后端，不手动设置跨域地址。
- Ctrl+C 停止两个子进程。单独启动：`npm run dev:backend` / `npm run dev:frontend`。
- PowerShell 若阻止 npm.ps1，可以把上述命令的 `npm` 换成 `npm.cmd`。
- `.env.example` 是配置说明，骨架没有自动读取 `.env`；配置通过 shell 环境传入。

## 验证

```powershell
npm run check
```

依次执行契约漂移检查、后端 lint、后端测试、Vue 类型检查和生产构建。单项命令见 [开发说明](docs/DEVELOPMENT.md)。当前测试验证骨架及样例契约，不代表业务功能已通过验收。

## 文档与任务

- [Spec](docs/SPEC.md)
- [API Contract](docs/API_CONTRACT.md) / [OpenAPI](docs/api/openapi.json) / [共享样例](docs/api/examples.json)
- [Backend Ticket](docs/tickets/BACKEND.md)
- [Frontend Ticket](docs/tickets/FRONTEND.md)
- [开发和并行协作说明](docs/DEVELOPMENT.md)
- [原始开发计划](docs/DEVELOPMENT_PLAN.md)

两个 Ticket 从 `feature/mvp` 的同一个基础提交建立各自分支和 worktree。当前尚未创建业务开发 worktree。

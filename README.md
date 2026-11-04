# Certificate Admin Console

Vue 3 + Element Plus / FastAPI + SQLAlchemy / SQLite 多租户证书管理演示。前后端已集成，默认连接真实 API；支持搜索、筛选、分页、批量签发、详情、撤销和 CSV 导出。

## 启动

需要 Node.js >=22.12、Python 3.12 或 3.13。在仓库根目录执行，每个 worktree 单独安装依赖：

```powershell
npm run setup
npm run seed
npm run dev
```

Python 不在 PATH 或指向 Windows Store 占位程序时，setup 前先指定真实解释器：

```powershell
$env:PYTHON_EXECUTABLE = 'C:\path\to\python.exe'
npm run setup
```

- 前端：[http://127.0.0.1:5173](http://127.0.0.1:5173)
- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- 使用 127.0.0.1，不混用 localhost。前端通过 `/api` 同源代理，cookie 自动携带。
- Ctrl+C 停止两个服务。单独启动：`npm run dev:backend` / `npm run dev:frontend`。
- PowerShell 若阻止 npm.ps1，可使用 `npm.cmd`。
- 根脚本/后端不会自动读取 `.env`，配置通过 shell 环境传入。真实联调确保未设置 `VITE_API_MODE=mock`。

默认端口被其他实例占用时，可使用已实际验证的独立端口；根脚本自动匹配代理目标及默认 Origin 白名单：

```powershell
$env:FRONTEND_PORT = '5180'
$env:BACKEND_PORT = '8010'
npm run dev
```

此时访问 [http://127.0.0.1:5180](http://127.0.0.1:5180)，API 文档在 [http://127.0.0.1:8010/docs](http://127.0.0.1:8010/docs)。显式设置的 `API_PROXY_TARGET` / `ALLOWED_ORIGINS` 优先，切换端口时须同步调整或清除。

## 演示账号和数据

| 用户名 | 密码 | 租户时区 |
| --- | --- | --- |
| sydney.admin | DemoPass123! | Australia/Sydney |
| perth.admin | DemoPass123! | Australia/Perth |

仅供本地演示。账号身份决定 tenant；切换租户需退出并登录另一账号。

默认数据库：`backend/data/certificates.db`。`npm run seed` 幂等，不覆盖已有演示租户或业务数据。初始 Sydney 有 25 张证书、4 条可签发报名、1 条未完成报名；Perth 有 2 张证书、2 条可签发报名。另有已撤销证书、未结束课程和空课程。普通启动只建表，不清库；可设置 `SEED_DEMO=true` 在启动时幂等 seed。

停止服务后，可**显式清空 DATABASE_URL 指定数据库的全部业务表并重新 seed**：

```powershell
npm run reset
```

自定义数据库：`$env:DATABASE_URL = 'sqlite:///./tmp/demo.db'`。数据库不提交 Git。后端重启需要重新登录；幂等结果保存在数据库中。

## 验证

```powershell
npm run check
```

包括契约漂移检查、Ruff、72 个后端测试、5 个前端单测、Vue 类型检查及生产构建。

真实浏览器联调（先 seed 并启动真实服务；会签发和撤销本地演示证书，不调用 reset）：

```powershell
# 使用机器已有 Playwright；若项目已可解析则无需 PLAYWRIGHT_MODULE。
$env:PLAYWRIGHT_MODULE = 'C:/path/to/playwright/index.mjs'
$env:PLAYWRIGHT_EXECUTABLE = 'C:/path/to/chrome.exe'
$env:FRONTEND_URL = 'http://127.0.0.1:5180'
# 可选：证据保存在仓库外
$env:SCREENSHOT_DIR = 'C:/path/to/evidence'
npm run test:integration --workspace @certificate-admin/frontend
```

独立 mock 场景测试及启用方法见 [前端说明](frontend/README.md)。mock 回归命令 `test:e2e` 与真实联调 `test:integration` 分开；请求失败不会回退假数据。

## 实际验证记录（2026-11-04）

Windows、Node 24.15、Python 3.12.14、已有 Playwright/Chromium。Browser 插件不可用，使用 Playwright。真实 Vite 5180 → FastAPI 8010；桌面 1440×1000、窄屏 390×844。

- setup、seed（含重复执行）、专用临时库 reset、单命令 dev 自定义端口启动均成功。默认 5173 被既有进程占用，未停止其他实例。
- `npm run check` 全通过：72 后端 + 5 前端测试，契约无漂移，类型检查及构建成功。
- 浏览器真实登录/刷新恢复、姓名及编号搜索、分页及筛选重置、排序、无匹配结果、课程和状态筛选。
- 首批真实签发 4 张、跳过 26 条、失败 0；未结束课程禁止提交；双击只发送一次。实际提交后丢弃响应，刷新后原 key 重试找回相同结果；新 key 再提交全部跳过。
- 详情、取消/确认撤销、重复撤销保持相同状态；切换 Sydney/Perth 清理搜索、详情及旧提示；跨租户详情、撤销、发证及课程筛选导出返回 404。真实会话失效后 401 返回登录页。
- 实际下载 CSV，内容匹配全部记录及排序（初始 25 条，跨页）；带筛选只导出匹配记录。核对 BOM、中文、逗号/引号/换行转义、公式文本保护、Sydney +11:00 / Perth +08:00。
- 修复身份切换后上一账号浮动操作提示短暂残留，回归通过。无相关 JS 运行错误、Vue warning 或 Vite overlay；截图检查桌面/窄屏无页面横向溢出。
- 后端自动化另覆盖同/不同 key 独立连接并发、持久化重放、审计/事务/提交失败回滚、锁超时 503 后重试、部分失败、冬夏时区、239 条分块 CSV、真实读快照及下载中断释放连接。

## 限制与未验证

- 未做生产部署、真实 HTTPS/反向代理端到端、其他操作系统、Firefox/Safari、长时间负载或大规模性能测试。窄屏使用 Chromium 模拟，未在实体手机测试。生产构建成功，未单独部署生产 bundle。
- 503、部分失败、审计失败及并发通过后端自动化注入/独立连接验证；本次真实浏览器链路未刻意制造数据库故障。
- 单后端 worker、进程内会话、SQLite 串行写；重启重新登录，锁超时原 key 重试。LIKE 使用 SQLite 默认规则，不承诺 Unicode 全文检索。
- CSV 流开始后的错误不能改为 JSON；页面只提示请求下载，本次自动化实际核对下载文件。未承诺任意规模无超时。
- Element Plus 全量导入有大 chunk 构建提示；Starlette TestClient/httpx 有弃用提示，均不阻断检查。
- Section 8 独立反思/设计回答及录屏由候选人自行完成。

## 文档

[Spec](docs/SPEC.md) · [API Contract](docs/API_CONTRACT.md) · [OpenAPI](docs/api/openapi.json) · [Backend Ticket](docs/tickets/BACKEND.md) · [Frontend Ticket](docs/tickets/FRONTEND.md) · [开发说明](docs/DEVELOPMENT.md) · [开发计划](docs/DEVELOPMENT_PLAN.md)

# BE-01 — Backend MVP

状态：Completed。实现分支：codex/backend-mvp；基于共享骨架提交 180fca6，已合入 feature/mvp；真实前后端联调记录见 README。下方交付记录保留独立开发时的验证范围。

## 目标

在现有 FastAPI 骨架上实现 Spec 全部后端行为，严格遵循冻结 API Contract。Frontend 可同时用共享样例开发，无需等待本 Ticket。

## 开始前阅读

AGENTS.md、docs/SPEC.md、docs/API_CONTRACT.md、docs/DEVELOPMENT.md、docs/api/openapi.json。

## 文件归属

- 可修改 backend/**，但 contracts.py 是共享冻结文件，不自行修改。
- 可更新本 Ticket 的完成记录；不修改 frontend、共享契约产物、根锁文件或共享文档。
- routes.py 仅替换实现/依赖，保持 wire contract 及 OpenAPI 输出一致。
- backend/requirements.txt 已锁依赖；新增依赖需协调，不直接改公共契约。

## 工作项

- [x] 八张表及租户复合外键、唯一约束、索引、UTC epoch 毫秒存储。
- [x] SQLite 每连接 foreign_keys、WAL、有限 busy_timeout；明确读写事务生命周期。
- [x] 自动建表、幂等 seed、显式 reset 命令；演示数据和账号遵循 Contract。
- [x] 哈希密码验证、后端内存会话和 TTL、HttpOnly cookie、登录/退出/me。
- [x] 写请求 Origin 校验；统一认证和租户依赖；各 API 均限定当前租户。
- [x] 课程列表及准确计数；课程未结束不可发证。
- [x] 证书列表搜索、筛选、排序、分页，详情和幂等撤销及其审计。
- [x] BEGIN IMMEDIATE + 唯一约束 + 每人 savepoint；证书与签发审计原子写入。
- [x] 持久化幂等响应，同 key 同请求原样重放，不同请求 409；不同 key 并发不能重复发证。
- [x] 逐报名 issued/skipped/failed；只能恢复已知单条数据问题，整体异常全批回滚。
- [x] CSV 共用筛选、导出全部结果、时区转换、BOM/转义/公式文本处理。
- [x] CSV 显式读事务、分批读取及流式输出；下载中断释放连接。
- [x] 统一错误 envelope、500 隐藏内部异常、503 锁超时可重试；完成后不再返回业务 501。
- [x] 替换 scaffold 占位测试，增加下列行为测试。

## 验收与测试

- [x] 双租户隔离覆盖列表、课程、详情、发证、撤销、导出；禁止伪造 tenant_id/操作者。
- [x] 登录错误、会话过期、退出重复调用、Origin 缺失/错误、参数校验符合 Contract。
- [x] 同 key 重放完全相同；不同 key 重复签发跳过；独立连接并发最终一张证书、一条 issued 审计。
- [x] 审计失败回滚证书；批次整体失败不提交部分成功；重启后原 key 仍能重放（重新登录）。
- [x] 已撤销不补发；重复撤销不重写时间或审计。
- [x] 姓名/编号搜索、排序次级 id、越界页、空课程和未结束课程。
- [x] CSV 超过一页且筛选一致；中文、逗号、双引号、换行、公式文本、空结果。
- [x] 固定 UTC 样例在 Sydney/Perth 的转换及显示/导出一致，覆盖冬夏和跨日。
- [x] 使用临时文件 SQLite 做事务/并发测试，不能只用共享单连接内存库。
- [x] npm run lint:backend、npm run test:backend、npm run contract:check 全部通过。

## 交付

有意义的实现提交；本 Ticket 记录启动、seed/reset 命令，测试结果、覆盖范围和限制，供集成者更新 README。不要宣称尚未做过的前端端到端验证。

## 不在范围内

UI、通知、PDF、补发、任务队列、权限角色管理、独立 Section 8 问答。

## 完成记录（执行者填写）

- 实现 Commit：`468ee84`（tenant schema、auth、业务 API、seed、CSV）；测试及本记录见后续 `test(backend)` 提交。未合并、未推送。
- 修改范围：仅 `backend/**` 和本 Ticket；未改前端、冻结 DTO、OpenAPI、生成 TS、根脚本或锁文件，也未编写 Section 8 回答。

### 实际验证（2026-11-04）

- Windows、Node 24.15.0、Python 3.12.14；使用仓库锁定依赖，没有新增依赖。
- `npm run lint:backend`：通过。
- `npm run contract:check`：通过；OpenAPI 与声明一致，生成 TypeScript 与 OpenAPI 一致。
- `npm run test:backend -- --basetemp=tmp/pytest-delivery`：**72 passed**，9.74 秒；包含原有 DTO/共享样例和 health 测试。
- 覆盖：所有业务接口认证、Origin、会话过期/轮换/退出、HTTPS Secure cookie、参数校验、双租户读写/导出隔离、数据库复合外键约束；同 key 重放/管理员与课程冲突/重启恢复、同 key 和不同 key 的独立连接并发；已撤销不补发、重复撤销；可恢复单条失败和新 key 重试、审计/连接/提交失败回滚、真实写锁超时 503 后原 key 重试。
- 列表覆盖姓名/编号搜索、LIKE 通配符转义、筛选、分页、越界页和全部排序方向；CSV 覆盖超过一页及多次 fetch（239 条）、筛选/排序一致、BOM、中文和 CSV 转义、公式文本、空结果、Sydney/Perth 冬夏与跨日转换、真实 SQLite 读事务与快照、提前关闭和实际发送中断后的连接释放。
- 额外启动真实 Uvicorn 子进程（127.0.0.1 临时端口），通过 HTTP 完成 health → 登录 → me/课程/列表 → 批量签发 → 同 key 重放 → 详情 → 撤销/重复撤销 → CSV（29 条）→ Perth 登录及跨租户 404 → 退出/401。已关闭该验证服务。
- 显式 seed/reset CLI 均实际运行通过，重复 seed 不重置已签发数据。测试库、验证脚本及日志均位于忽略的 `tmp/` 下，不提交。
- 当前沙箱限制 asyncio 本地 socket，TestClient 与 Uvicorn 验证在允许本地 socket 的执行环境运行；未为沙箱限制改业务代码。

### 启动、seed 与 reset（仓库根目录 PowerShell）

```powershell
# 首次安装：如 python 不在 PATH，先将 PYTHON_EXECUTABLE 指向 Python 3.12/3.13。
npm run setup

# 默认 DATABASE_URL=sqlite:///./backend/data/certificates.db；也可先设置自定义路径。
$env:PYTHONPATH = 'backend'
.\.venv\Scripts\python.exe -m app.seed
npm run dev:backend

# 显式清空 DATABASE_URL 指定数据库的八张业务表并重新填充演示数据；先停止服务。
.\.venv\Scripts\python.exe -m app.seed --reset
```

- 普通启动自动建表，不重置业务数据；seed 默认显式执行。可选 `$env:SEED_DEMO = 'true'` 启用本地演示启动 seed，它同样幂等。变量不自动从 `.env` 加载。
- 演示账号：`sydney.admin`、`perth.admin`；本地演示密码均为 `DemoPass123!`。Sydney 初始 25 张证书（含一张撤销）、4 条可签发 completed 报名和 1 条 in_progress；两个租户均有课程、学员、证书，另有空课程及未结束课程。
- 默认写请求 Origin：`http://127.0.0.1:5173`。独立脚本必须显式提供；`ALLOWED_ORIGINS` 支持逗号分隔精确白名单。会话 TTL 默认 28800 秒，可用 `SESSION_TTL_SECONDS` 配置；HTTPS cookie 自动 Secure，代理终止 HTTPS 时需正确配置可信转发头或设置 `COOKIE_SECURE=true`。

### 已知限制及集成边界

- 会话在单进程内，重启需重新登录；使用单 worker。幂等批次结果持久化在数据库，重启不丢失。SQLite 写入串行，busy_timeout 为 3000ms；锁超时返回 503，不伪造部分成功。
- seed 使用固定 UUID 和时间，已存在的演示 tenant 不重新写入；只有显式 reset 会重置。密码为 Argon2 哈希。
- CSV 采用真实显式读快照和每次 100 行流式输出；流开始后的错误不能改回 JSON，也不承诺任意规模导出无超时。
- SQLite 默认 LIKE 大小写规则保持演示版行为，不提供 Unicode 全文检索。
- 保留已有 Starlette TestClient/httpx 弃用提示（1 warning）；不影响 72 项测试通过，未擅自更改锁定依赖。
- 未做前端浏览器端到端或视觉验收；交付中只验证后端真实 HTTP 流程。集成者后续更新共享 README，并与 Frontend 运行浏览器链路。

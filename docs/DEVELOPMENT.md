# 开发与 Worktree 协作

## 1. 仓库结构

```text
backend/
  app/contracts.py       共享 DTO 声明（冻结）
  app/routes.py          固定 API 路由及真实业务实现
  app/errors.py          统一错误 envelope
  app/models/            Backend 数据库模型
  app/services/          Backend 业务逻辑
  tests/                 后端测试
  scripts/export_openapi.py
  requirements.in        直接依赖范围
  requirements.txt       已锁定的完整依赖
frontend/
  src/api/client.ts      基于 paths 的 typed client
  src/api/contract-examples.ts  共享样例入口，不自动启用 mock
  src/App.vue            证书控制台
packages/api-contract/   生成类型和公共类型别名
docs/api/               OpenAPI 和共享样例
docs/tickets/           两个并行任务
scripts/                setup、启动、契约生成和检查
```

## 2. 环境和命令

Node.js >=22.12，Python 3.12/3.13。首次执行 `npm run setup`，随后 `npm run dev`。解释器不在 PATH 时设置 PYTHON_EXECUTABLE；每个 worktree 各自安装 .venv 和 node_modules，不能共享可变依赖目录。

Python 依赖统一由 backend/requirements.txt 安装；requirements.in 是直接依赖清单，不能只改其中一个。当前锁文件在 Windows/Python 3.12 上生成和验证；其他平台需要实际验证，不宣称已测试。

| 命令 | 用途 |
| --- | --- |
| npm run dev:backend | 仅后端，127.0.0.1:8000，开发热重载 |
| npm run dev:frontend | 仅前端，127.0.0.1:5173 |
| npm run typecheck | Vue/TypeScript 检查 |
| npm run build | 类型检查和生产构建 |
| npm run lint:backend | Ruff |
| npm run test:backend | pytest |
| npm run contract:check | 只检查契约，不写文件 |
| npm run contract:generate | 协调后重建 OpenAPI 与 TS |
| npm run check | 全部基础检查 |

使用 127.0.0.1，不混用 localhost，以免 cookie 和 Origin 不一致。Root dev 默认 5173/8000；可设置 FRONTEND_PORT / BACKEND_PORT 自动匹配代理及 Origin。显式 API_PROXY_TARGET / ALLOWED_ORIGINS 优先。不要同时运行两个默认全栈实例。

启动自动建表；`npm run seed` 幂等填充演示数据，`npm run reset` 显式清空配置数据库并重新 seed（先停止服务）。演示账号和真实联调记录见 README。业务接口已实现，501 不再是预期结果。

## 3. 两个 Worktree 的边界

用户后续从同一个 feature/mvp 基础提交分别创建 `feature/backend`、`feature/frontend` 分支和 worktree。本次不自动创建 worktree 或开始业务开发。

| 范围 | 所有者 |
| --- | --- |
| backend/**（除 contracts.py） | Backend |
| frontend/** | Frontend |
| docs/tickets/BACKEND.md 的完成记录 | Backend |
| docs/tickets/FRONTEND.md 的完成记录 | Frontend |
| contracts.py、docs/api/**、packages/api-contract/** | 契约协调者 |
| 根 package.json、package-lock.json、scripts/**、README、共享 docs、AGENTS.md | 集成协调者 |

- Backend 改路由实现，但保持签名、response_model、operationId、security 声明和错误响应契约稳定；检查必须不产生 OpenAPI 差异。
- Frontend 仅按冻结契约实现；用 shared fixtures 做显式开发 mock，不等待 Backend 完成。
- 不直接在另一方目录修接口问题，不自行重命名字段，不吞掉类型错误。
- 基础依赖已准备；新增依赖必须说明必要性并协调根锁文件，避免两边各自 npm install 造成冲突。
- 不提交 .venv、node_modules、数据库、截图、临时输出和环境秘密。

## 4. 前端独立开发和联调

1. 从公共包导入 DTO 和 query 类型，使用已建的 openapi-fetch client；路径包含 /api。
2. 开发 mock 必须显式启用，例如 VITE_API_MODE=mock；默认 real，不得在请求失败时自动回退。
3. mock 由 Frontend 在其目录内实现，可基于共享样例覆盖 loading、空、错误、逐人结果和切换身份；不能修改共同样例来迁就 UI。
4. mock 不作为后端数据正确性证明，生产构建不启用 mock。
5. 联调关闭 mock，真实登录后依次操作列表、详情、发证、撤销、导出和账号切换。
6. 对比浏览器请求与 OpenAPI：路径、query、cookie、Origin、Idempotency-Key、响应字段和状态码。

## 5. 契约变更流程

提出具体原因和前后差异 → 两方确认 → 协调者修改 DTO/路由声明、本文或 Contract、共享样例 → `npm run contract:generate` → 更新别名与双方实现 → `npm run check` → 两方同步同一个契约提交。

不得手改 OpenAPI/生成 TS。固定字段和枚举优先不变，时间不足时削减额外功能。

## 6. 集成与交付

- 两个 Ticket 都以基础提交为起点，各自提交实现及测试，记录验证命令、结果和限制。
- Backend 完成时将 test_scaffold.py 的 501 断言替换为真实行为测试；不要保留测试要求接口永远返回 501。
- 保留 DTO/共享样例测试和 health 检查；补充业务测试，不把骨架绿灯当成最终验收。
- 先集成 Backend 再集成 Frontend，运行 npm run check，再进行浏览器真实链路验证。
- 集成者更新 README 的 seed/reset、账号、运行状态和已知限制；两个 Agent 不同时改这部分。
- 若契约完全遵循本基线，两方不应产生共同文件冲突；有冲突时逐项确认，不直接覆盖另一方。

## 7. 初始化验证记录

2026-11-04，在 Windows、Node 24、Python 3.12 环境完成：

- npm run setup：锁定依赖安装成功；每个新 worktree 仍需单独安装。
- npm run check：契约一致性、Ruff、12 个基础测试、Vue 类型检查及 Vite 生产构建通过。
- npm run dev：两个服务可启动；前端入口、后端 health、OpenAPI 和 Vite /api 代理 HTTP 检查通过；业务 /api/me 为预期的 501。
- 尚未做业务端到端或浏览器视觉验收，功能由两个 Ticket 实现后再验证。
- 非阻断提示：Element Plus 当前全量导入使构建产生大 chunk 提示；Starlette TestClient 对 httpx 发出弃用提示，现有测试通过。Frontend 可在其范围内改为按需导入；测试客户端升级需 Backend 协调依赖。
- Codex 沙箱中本地 asyncio socket 被阻塞，测试及启动在允许本地 socket 的执行环境通过；不要为沙箱限制修改业务实现。

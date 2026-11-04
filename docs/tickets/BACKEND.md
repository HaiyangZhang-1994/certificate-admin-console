# BE-01 — Backend MVP

状态：Ready，尚未开始。建议分支：feature/backend；基于 feature/mvp 的基础提交。

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

- [ ] 八张表及租户复合外键、唯一约束、索引、UTC epoch 毫秒存储。
- [ ] SQLite 每连接 foreign_keys、WAL、有限 busy_timeout；明确读写事务生命周期。
- [ ] 自动建表、幂等 seed、显式 reset 命令；演示数据和账号遵循 Contract。
- [ ] 哈希密码验证、后端内存会话和 TTL、HttpOnly cookie、登录/退出/me。
- [ ] 写请求 Origin 校验；统一认证和租户依赖；各 API 均限定当前租户。
- [ ] 课程列表及准确计数；课程未结束不可发证。
- [ ] 证书列表搜索、筛选、排序、分页，详情和幂等撤销及其审计。
- [ ] BEGIN IMMEDIATE + 唯一约束 + 每人 savepoint；证书与签发审计原子写入。
- [ ] 持久化幂等响应，同 key 同请求原样重放，不同请求 409；不同 key 并发不能重复发证。
- [ ] 逐报名 issued/skipped/failed；只能恢复已知单条数据问题，整体异常全批回滚。
- [ ] CSV 共用筛选、导出全部结果、时区转换、BOM/转义/公式文本处理。
- [ ] CSV 显式读事务、分批读取及流式输出；下载中断释放连接。
- [ ] 统一错误 envelope、500 隐藏内部异常、503 锁超时可重试；完成后不再返回业务 501。
- [ ] 替换 scaffold 占位测试，增加下列行为测试。

## 验收与测试

- [ ] 双租户隔离覆盖列表、课程、详情、发证、撤销、导出；禁止伪造 tenant_id/操作者。
- [ ] 登录错误、会话过期、退出重复调用、Origin 缺失/错误、参数校验符合 Contract。
- [ ] 同 key 重放完全相同；不同 key 重复签发跳过；独立连接并发最终一张证书、一条 issued 审计。
- [ ] 审计失败回滚证书；批次整体失败不提交部分成功；重启后原 key 仍能重放（重新登录）。
- [ ] 已撤销不补发；重复撤销不重写时间或审计。
- [ ] 姓名/编号搜索、排序次级 id、越界页、空课程和未结束课程。
- [ ] CSV 超过一页且筛选一致；中文、逗号、双引号、换行、公式文本、空结果。
- [ ] 固定 UTC 样例在 Sydney/Perth 的转换及显示/导出一致，覆盖冬夏和跨日。
- [ ] 使用临时文件 SQLite 做事务/并发测试，不能只用共享单连接内存库。
- [ ] npm run lint:backend、npm run test:backend、npm run contract:check 全部通过。

## 交付

有意义的实现提交；本 Ticket 记录启动、seed/reset 命令，测试结果、覆盖范围和限制，供集成者更新 README。不要宣称尚未做过的前端端到端验证。

## 不在范围内

UI、通知、PDF、补发、任务队列、权限角色管理、独立 Section 8 问答。

## 完成记录（执行者填写）

- Commit：待填写
- 验证命令及结果：待填写
- Seed/reset 命令：待填写
- 已知限制：待填写

# Certificate Admin Console — MVP Spec

状态：Backend / Frontend Ticket 已集成至 feature/mvp；已完成真实浏览器业务链路验证，范围与限制见 README。

接口字段、HTTP 状态和枚举以 [API Contract](API_CONTRACT.md) 及生成的 [OpenAPI](api/openapi.json) 为准。并行开发分别遵循 [Backend Ticket](tickets/BACKEND.md) 和 [Frontend Ticket](tickets/FRONTEND.md)。

## 1. 目标和范围

在有限时间内完成可直接演示的多租户证书管理后台。

- 前端：Vue 3、Vite、TypeScript、Element Plus。
- 后端：FastAPI、同步 SQLAlchemy、SQLite。
- 日期处理：UTC 存储，IANA 租户时区转换；后端使用 zoneinfo，并安装 tzdata。
- 必须完成：证书列表、批量发证、证书详情和撤销、CSV 导出。
- 本次不做：课程/学员 CRUD、证书 PDF、邮件通知、补发、RBAC、任务队列、实时百分比进度。
- 不编写题目第 8 节的独立反思和设计问答。

## 2. 已确认的业务规则

1. 发证资格：课程已结束（ends_at <= 当前 UTC 时间），报名状态为 completed。
2. 一个学员在一个课程下只有一条报名；一条报名最多一张证书。
3. 已有证书的报名返回 skipped，包括证书已撤销的情况，不自动补发。
4. 每次实际签发必须同时产生一条审计记录。
5. 使用两个演示管理员分别登录两个租户；当前身份决定租户范围。
6. 批量发证同步执行；按钮禁用、loading 和不定进度提示，完成后展示逐学员结果。
7. 同幂等 key 重试返回原批次结果；新的操作使用新的 key。
8. CSV 导出当前搜索/筛选下的全部匹配证书，不受页面分页限制。

## 3. 数据模型

主键统一使用字符串 UUID。所有时间字段统一使用 UTC epoch 毫秒整数；API 时间输出为带 Z 的 ISO 8601。

| 表 | 主要字段 |
| --- | --- |
| tenants | id, name, timezone |
| admins | id, tenant_id, username, name, password_hash |
| courses | id, tenant_id, title, ends_at |
| learners | id, tenant_id, name, email |
| enrollments | id, tenant_id, course_id, learner_id, status, completed_at |
| certificates | id, tenant_id, enrollment_id, serial_number, issued_at, issued_by, revoked_at, revoked_by |
| audit_logs | id, tenant_id, action, certificate_id, course_id, learner_id, actor_id, occurred_at |
| issuance_requests | id, tenant_id, idempotency_key, request_hash, response_json, created_at |

约束和索引：

- admins.username 全局唯一；密码只保存哈希。
- enrollments.status 为 in_progress 或 completed；completed 时必须有 completed_at。
- enrollments：UNIQUE(tenant_id, course_id, learner_id)。
- certificates：UNIQUE(tenant_id, enrollment_id)，serial_number 全局唯一。
- 编号格式为 CERT-<UUID>，不依赖记录数量。
- issuance_requests：UNIQUE(tenant_id, idempotency_key)。
- audit_logs.action 为 issued 或 revoked；UNIQUE(tenant_id, certificate_id, action)。
- certificates.status 不单独存储：revoked_at 为空则 valid，否则 revoked。
- tenant_id、实体外键和审计中的 actor_id 均不能为空；撤销字段可以为空。
- 租户内实体之间使用包含 tenant_id 的复合外键；被引用表补充 UNIQUE(tenant_id, id)。
- 每个 SQLite 连接启用 foreign_keys；设置有限 busy_timeout，启用 WAL。
- 关键索引：certificates(tenant_id, issued_at, id)、certificates(tenant_id, enrollment_id)、enrollments(tenant_id, course_id, status)。按实际查询补充，避免无依据添加索引。

演示版本使用 create_all 和可重复运行的 seed；不引入迁移框架，不在启动时重置已有业务数据。

## 4. 身份与租户隔离

- 简单用户名/密码登录，后端创建随机、不透明会话 token；会话在后端映射到管理员身份。
- 演示版会话保存在进程内，设定过期时间；服务重启后重新登录。使用单个后端 worker。
- token 使用 HttpOnly、SameSite=Lax cookie；生产 HTTPS 下设置 Secure。
- 开发时通过 Vite /api 代理访问后端；不开放任意来源的带凭据 CORS。
- 所有写请求校验允许的 Origin，登录和退出也适用。
- 所有业务 API 从服务端身份取得 tenant_id，禁止用客户端传入的 tenant_id 或 issued_by 授权。
- 查询、写入、JOIN、导出及幂等记录均限定当前租户。
- 别的租户或不存在的资源统一返回 404；未登录或会话过期返回 401。
- 不提供匿名租户列表；演示账号在 README 中说明。
- 切换账号时清空页面数据、选中项、详情和批次状态，取消或忽略旧请求。

## 5. API 契约

统一前缀：/api。错误结构：{"error":{"code":"...","message":"..."}}；不得返回数据库异常或堆栈。

| 方法 | 路径 | 契约 |
| --- | --- | --- |
| POST | /auth/login | username/password；设置会话 cookie，返回管理员和租户 |
| POST | /auth/logout | 清除当前会话和 cookie；重复调用安全 |
| GET | /me | 管理员 id/name、tenant id/name/timezone |
| GET | /courses | 当前租户课程及 completed、eligible、already_issued 数量 |
| GET | /certificates | 带分页的证书列表 |
| GET | /certificates/export.csv | 当前租户全部匹配记录的 CSV |
| GET | /certificates/{id} | 当前租户证书详情 |
| POST | /certificates/{id}/revoke | valid 变为 revoked；重复调用返回当前状态 |
| POST | /courses/{id}/issue-certificates | 必须携带 Idempotency-Key 请求头，返回完整批次结果 |

实现时应在 /certificates/{id} 之前注册固定的 export.csv 路由。

### 5.1 列表和导出

- q：学员姓名或证书编号的子串搜索，去除首尾空白；长度最多 200；转义 LIKE 通配符。
- course_id：可选，必须属于当前租户。
- status：可选，valid / revoked。
- sort_by：issued_at / learner_name / serial_number，默认 issued_at。
- sort_order：asc / desc，默认 desc。
- page：从 1 开始；page_size 默认 20，最大 100。
- 排序字段和方向使用白名单；追加同方向 id 排序保证稳定。
- 列表返回 items、total、page、page_size；分页和筛选在后端执行。
- 列表项包含 id、学员、课程、编号、issued_at、status；详情增加签发人和撤销信息。
- 导出与列表复用租户和筛选逻辑、采用相同排序；不传分页参数。

### 5.2 批量发证

- 校验课程归属；课程未结束返回 409/course_not_finished。
- 遍历该课程全部报名：未完成报名为 skipped/not_completed，已有有效证书为 skipped/already_issued，已有撤销证书为 skipped/certificate_revoked。
- 符合条件且签发成功为 issued；可恢复的单条数据错误为 failed，返回安全的 reason code。
- 没有报名时正常返回零计数和空 results。
- 返回 issued_count、skipped_count、failed_count、results。
- results 每项包含 enrollment_id、learner_id、learner_name、outcome、reason，以及存在时的 certificate_id 和 serial_number。
- HTTP 200 表示批次处理结束，仍须检查 failed_count；整体事务失败返回非 2xx，不能返回已签发成功的明细。
- 不伪造失败数据或处理进度；失败分支通过测试注入验证。

## 6. 幂等与事务

1. 前端新操作生成 UUID key，在请求发出前按管理员/租户/课程暂存到 sessionStorage。
2. 网络错误或结果不确定时保留原 key，重试同一请求；此时不允许无提示地改用新 key。
3. 后端开启 BEGIN IMMEDIATE 写事务；幂等查找必须在获得写事务后执行。
4. key 的作用域是租户；request_hash 由操作版本、课程 id、管理员 id 和规范化请求内容组成。
5. 同 key/hash 返回持久化原响应；同 key 不同 hash 返回 409/idempotency_conflict。
6. 每个待签发报名使用 savepoint，证书和 issued 审计一起写入。
7. 只将明确可恢复的单条问题记为 failed；锁错误、连接错误及未知内部错误使整个事务回滚。
8. 将批次完整响应写入 issuance_requests，与证书和审计一次提交；提交成功后才返回。
9. 锁等待超时返回 503/database_busy，提示使用原 key 重试。
10. 证书唯一约束是不同 key 并发请求的最终保护；只把对应报名证书已存在的冲突解释为 skipped，不吞掉其他完整性错误。

issuance_requests 只保存已完成结果，不需要后台任务状态。进程在提交前退出，事务回滚；提交后响应丢失，用原 key 找回原结果。

重试原批次不会重新处理 failed 项；用户确认开始新批次后使用新 key，已签发记录仍会跳过。幂等记录在演示版不自动过期。

撤销同样采用事务：状态变更和 revoked 审计一起提交；已撤销时不重复写审计。

## 7. 时间与 CSV

- 所有显示使用当前租户 timezone，不使用系统或浏览器默认时区，不保存固定 UTC offset。
- 前端通过 Intl.DateTimeFormat 显式指定 timeZone；页面展示租户时区名称。
- API 始终输出 UTC ISO 8601；后端 CSV 使用相同时间来源和租户时区。
- 默认按签发瞬间排序；本次不增加日期范围筛选或独立的本地日历日期排序功能。
- CSV 列为 learner_name、course_title、serial_number、issue_date。
- issue_date 输出租户本地 ISO 8601 时间，包含 UTC offset。
- UTF-8 BOM、标准 CSV 转义；对文本单元格处理公式起始字符及前导控制字符。
- 使用单次带 JOIN 的查询取得必要列，避免逐行查询；分批 fetch、分块输出，不调用全量 all()。
- 显式读事务提供导出快照；必须验证 SQLite 驱动确实开启读事务，不能只依赖 Session 对象的存在。
- 导出生成器拥有连接和游标生命周期；成功、异常、客户端下载中断均释放资源。
- 认证和参数校验在发送响应头前完成；空结果输出 BOM 和表头。
- 浏览器直接下载，避免先在 JavaScript 中组装完整 Blob；响应设置 CSV Content-Type、attachment 和 Cache-Control: no-store。
- 流式导出控制内存，不承诺任意规模下不会超时；本次不增加异步导出任务。

## 8. 页面状态

- 列表：loading、无数据、无搜索结果、错误及重试按钮；搜索约 300ms 防抖。
- 修改筛选或排序回到第 1 页；忽略旧搜索响应，401 清理身份状态并返回登录。
- 批量操作：未选课程不能提交；提交时禁用按钮、不定进度提示；完成后显示计数及逐人结果，刷新列表和课程计数。
- 网络失败明确提示“结果尚未确认”，提供原 key 重试，不直接显示“发证失败”。
- 详情：独立 loading/error；撤销二次确认；提交中防重复；成功后同步详情及列表。
- 导出：使用当前筛选；开始下载不显示虚假的完成百分比。

## 9. 验收标准

- 两个租户各有管理员、课程、学员和证书；一个账号无法读取、发证、撤销或导出另一个租户的资源。
- 搜索支持学员姓名及编号；分页、排序和三个列表状态可演示。
- 发证覆盖 issued、skipped；响应支持 failed；计数与逐人结果一致。
- 同 key 重试响应一致；不同 key 重试或并发不重复发证、不重复写签发审计。
- 模拟审计写入失败时，对应证书不能被提交；整体异常不会泄露部分成功结果。
- 证书详情的时间按租户时区显示；撤销确认和重复撤销行为正确。
- CSV 包含所有匹配记录，超过一页仍完整；搜索、课程、状态与列表一致。
- CSV 可正确处理中文、逗号、引号、换行及公式起始文本；空结果有表头。
- 有针对性的自动化测试覆盖隔离、幂等/并发、事务、时区及 CSV；浏览器完成一次完整操作链路。
- README 中记录环境前提、一键启动、演示账号、seed/reset 方法、已知限制；实际验证启动步骤。

## 10. 交付物

可运行源码、依赖锁文件、seed、关键测试、README、开发计划和有意义的 Git 历史。AI 指令文件如有新增则保留在仓库。

录屏链接和第 8 节个人回答由候选人提交；不由本 Spec 代写。

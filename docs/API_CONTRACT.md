# API Contract v1

状态：已冻结供 Backend / Frontend 并行开发。业务接口当前为 501 占位，不是已实现的服务。

## 1. 唯一契约和生成链

1. 后端声明：`backend/app/contracts.py` 的 Pydantic DTO + `backend/app/routes.py` 路由签名及响应声明。
2. `npm run contract:export` 生成 `docs/api/openapi.json`。
3. `npm run contract:types` 生成 `packages/api-contract/src/schema.d.ts`。
4. 前端从 `@certificate-admin/api-contract` 导入公共类型，通过 `frontend/src/api/client.ts` 调用。
5. `npm run contract:check` 验证声明、OpenAPI 和 TypeScript 完全一致，不修改文件。

OpenAPI 是双方联调时的机器可读基线；声明是生成来源。本文件补充 OpenAPI 无法完整表达的业务语义。冲突必须协调处理，不让两方各自解释或偷偷修改。

`docs/api/examples.json` 是共享成功/错误响应样例，后端测试会逐份校验 DTO。样例是独立场景，不是完整数据库 seed；批次 failed 样例不意味着生产要故意制造失败。

## 2. 公共规则

- API 前缀 `/api` 已包含在 OpenAPI paths 中；client baseUrl 为空，不再追加前缀。
- JSON 字段统一 snake_case，UUID 为字符串，时间为 UTC ISO 8601（Z）。
- DTO 禁止额外字段。响应中 nullable 字段必须显式返回 null，不省略。
- API 不接受用于授权的 tenant_id；身份由 cookie 解析。序号形如 `CERT-<UUID>`。
- 普通成功响应 200；退出 204 且无响应体；错误为下述统一 envelope。
- 发证和撤销 POST 无 JSON body；发证只通过必填 UUID 格式 `Idempotency-Key` 请求头传请求 key。
- Cookie 名称固定 `certificate_admin_session`，HttpOnly、SameSite=Lax、Path=/；HTTPS 时 Secure。
- 登录成功设置会话 cookie，退出删除；Frontend 始终 credentials=include。
- 登录和退出不要求有效旧身份；退出幂等。其余业务 API 要求已登录。
- 所有 POST 校验 Origin 白名单，默认 `http://127.0.0.1:5173`；拒绝缺失、null 和不允许的 Origin。脚本/测试需要显式带正确 Origin。
- 当前骨架只声明 cookie security，尚未实现认证或 Origin 校验；这由 Backend Ticket 完成。
- 前端不得根据 body.error 的有无猜测成功，先检查 HTTP 状态；网络异常没有可靠业务结果。

```json
{"error":{"code":"validation_error","message":"Invalid request parameters."}}
```

| HTTP | error.code | 含义 |
| --- | --- | --- |
| 401 | unauthorized / invalid_credentials | 会话不存在/过期，或登录失败 |
| 403 | forbidden_origin | 写请求来源不允许 |
| 404 | resource_not_found | 不存在或非当前租户资源 |
| 409 | course_not_finished / idempotency_conflict | 课程未结束，或同 key 请求内容不一致 |
| 422 | validation_error | 参数、路径 UUID、请求头或 body 无效 |
| 500 | internal_error | 整体操作失败，无异常堆栈或敏感信息 |
| 501 | not_implemented | 仅骨架阶段 |
| 503 | database_busy | 写锁等待超时，可沿用原 key 重试 |

## 3. Endpoint 与响应

| 方法 | 路径 | operationId | 成功响应 |
| --- | --- | --- | --- |
| GET | /api/health | health | HealthResponse |
| POST | /api/auth/login | login | Identity；body 为 LoginRequest |
| POST | /api/auth/logout | logout | 204 无 body |
| GET | /api/me | getIdentity | Identity |
| GET | /api/courses | listCourses | CourseList：items 数组，不分页 |
| GET | /api/certificates | listCertificates | CertificatePage |
| GET | /api/certificates/export.csv | exportCertificates | text/csv，非 JSON |
| GET | /api/certificates/{id} | getCertificate | CertificateDetail |
| POST | /api/certificates/{id}/revoke | revokeCertificate | CertificateDetail（最新状态） |
| POST | /api/courses/{id}/issue-certificates | issueCertificates | BulkIssueResult |

字段的精确定义和 required/nullable 以 OpenAPI 为准。常用前端类型已经从共享包导出，不另写一套 interface。

Identity 使用嵌套结构 `{admin:{id,username,name},tenant:{id,name,timezone}}`。证书使用嵌套 learner 和 course；不使用 learner_name/course_title 的另一套 JSON 结构。CSV 的扁平字段是导出专用格式。

CourseSummary 的计数：

- enrollment_count：全部报名数量。
- completed_count：已完成报名数量。
- already_issued_count：拥有证书的报名数量，包括 revoked。
- eligible_count：课程已结束，报名 completed，且尚无证书的数量；课程未结束时为 0。
- is_finished：ends_at <= 当前 UTC 时间。

## 4. 列表与导出参数

| 参数 | 类型/范围 | 默认 |
| --- | --- | --- |
| q | string，最多 200 字符，后端 trim；姓名或编号子串搜索 | 空字符串 |
| course_id | UUID，省略表示不限；别的租户/不存在的课程返回 404 | 省略 |
| status | valid / revoked；不传表示全部 | 省略 |
| sort_by | issued_at / learner_name / serial_number | issued_at |
| sort_order | asc / desc | desc |
| page | integer >= 1，仅列表 | 1 |
| page_size | integer 1..100，仅列表 | 20 |

无筛选条件应省略参数，不传字符串 `null` 或空 UUID。未知参数为 422。q 中 `%`、`_` 为普通字符，不是调用方提供的 SQL 通配符。SQLite 默认 LIKE 的大小写行为作为演示版限制，不承诺 Unicode 全文检索。

CertificatePage 包含 items、total、page、page_size；total 为当前筛选总数，越界页返回 items=[]，不自动改页。相同排序值追加同方向 id。

## 5. 批量结果与重试

- 遍历课程全部报名，结果按 enrollment_id 升序稳定排列；每条报名一项。
- 已有证书优先判定为 skipped，返回已有 certificate_id/serial_number，reason 为 already_issued 或 certificate_revoked。
- 无证书且报名未完成：skipped/not_completed，两个证书字段为 null。
- 新签发成功：issued，reason=null，两个证书字段必有值。
- 明确可恢复的非法报名数据：failed/invalid_enrollment，两个证书字段为 null；未知错误必须整体回滚，不能伪装成单条失败。
- 计数与 results 的 outcome 数量一致；空课程返回三个 0 和空数组。
- 课程结束校验在正常处理前完成；对已完成的同 key/hash 重放返回持久化原结果，不重新检查会影响重放的动态业务状态。
- 同 key/hash 重放 HTTP 状态和 JSON body 一致，不额外添加 replayed 字段或重写时间。
- hash 包含操作版本、课程 id、管理员 id；key 按租户隔离；不同管理员复用 key 会冲突。
- 网络异常、超时、503 或结果不确定时保留 key。只有用户明确开始新批次才换 key。确定性 4xx 应显示原因，不能自动无限重试。
- HTTP 200 可能有 failed_count > 0；UI 展示部分失败及明细。
- 已撤销证书不补发；重复撤销返回相同撤销信息，不新增审计。

## 6. CSV

- 参数与当前列表搜索、筛选、排序一致，但移除 page/page_size；传分页参数为 422。
- 按钮使用同源 URL 导航/下载，浏览器携带 cookie，不将完整 CSV 组装成 Blob。
- Content-Type: text/csv; charset=utf-8；Content-Disposition: attachment; filename="certificates.csv"；Cache-Control: no-store。
- UTF-8 BOM，列顺序固定：learner_name,course_title,serial_number,issue_date。
- issue_date 是租户本地带 offset 的 ISO 8601 时间，例如 Sydney 样例 `2026-10-21T10:30:00+11:00`；不使用浏览器本地时间。
- 没有数据也返回 BOM 和表头；认证/参数错误在响应头前返回统一 JSON error。
- 流已开始后的中断不能改成 JSON 错误；UI 只能提示已开始下载，不能宣称下载完成。

## 7. 演示 seed 约定（由 Backend 实现）

- 两个账号：sydney.admin / perth.admin；统一仅本地演示密码 `DemoPass123!`。
- 两租户、两个管理员和首个 Sydney 课程的 UUID 使用 examples.json 中的值，方便联调。
- seed 扩展到至少 25 张 Sydney 证书，另有可发证的 completed 报名、in_progress 报名、已撤销证书、未结束课程和空课程。
- 时间样例固定可复现；seed 幂等，普通启动不重置数据库。真实时间只用于新签发和撤销。
- JSON 样例不携带密码；不要把仅供演示的凭据用于任何外部系统。

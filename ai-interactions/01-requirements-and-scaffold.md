# 分析 Take-home 技术方案

Session: `01a1a8c0-8f01-71e2-9328-c161ac525ca8`

Source: local Codex session; original order and timestamps (UTC). Sanitized export; see README for exclusions.

## 2026-11-04T22:49:15.199Z — user

我这边要做一个技术面试的 take-home assignment，题目我已经放到 docs文件夹里了。
你先完整读一下题目，然后帮我分析一下整体需求和技术实现方案。
我打算前端用 vue3和element plus，后端用 FastAPI，数据库先用 SQLite。因为时间比较有限，我希望尽量简单一点，优先保证所有核心功能都能跑通，最后可以直接演示。
先不用着急写代码。我们先确认一下数据模型、API 设计，还有批量发证书的幂等性、多租户隔离、时区和 CSV 导出这些地方怎么处理。
如果发现题目有什么容易漏掉的要求，也提醒我一下。
等方案确认之后，再把它整理成简单的 Spec 和开发计划。


## 2026-11-04T22:49:18.924Z — assistant (commentary)

我先完整阅读 `docs` 里的题目，梳理核心流程和容易遗漏的约束，再结合你选的技术栈分析数据模型、API 和几个关键边界；这一步先不写代码。

## 2026-11-04T22:49:29.861Z — assistant (commentary)

题目是 PDF，我会用 PDF 技能提取全文并检查页面，避免漏掉表格、脚注或验收条件。

## 2026-11-04T22:50:03.154Z — assistant (commentary)

5 页题目已读完。四项核心功能都要求完成，其中容易漏掉的是：逐学员的批量发证结果、每次实际发证的审计记录、遵循当前筛选条件的完整 CSV，以及列表的加载、空结果和错误状态。

另外，第 8 节是要求候选人独立完成的反思和设计问答；我们这里讨论构建阶段的实现方案，不代写那部分提交答案。实现上我倾向于同步批量发证、数据库事务和唯一约束，先避免引入任务队列。

## 2026-11-04T22:51:19.857Z — assistant (final_answer)

我已完整阅读并核对了 5 页题目：:codex-file-citation{path="<USER_HOME>\\Desktop\\take-home\\docs\\Ocean AI Labs Beijing Technical Interview Assessment - 2026101701.pdf" purpose="source"}

**你的技术栈完全符合要求。建议做成一个小型单体应用：Vue 3 + Element Plus + FastAPI + SQLite，同步完成批量发证，优先把四个核心流程和数据正确性做好。** 暂时不引入 Redis、任务队列、复杂权限系统。

下面是待确认的方案，还不是最终 Spec，也没有开始写代码。

**1. 先明确产品范围**

题目要求四项核心功能全部具备：

| 功能 | 最小完整实现 |
|---|---|
| 证书列表 | 当前租户数据；按学员姓名或证书编号搜索；分页、排序；明确的加载、空结果、错误状态 |
| 批量发证 | 选择课程，一次处理全部符合条件的学员；防重复点击；处理中提示；逐学员结果；审计记录 |
| 证书详情 | 编号、课程、学员、租户时区的签发时间、有效／撤销状态；撤销前确认 |
| CSV 导出 | 导出当前租户、当前搜索及筛选条件下的全部匹配记录 |

可以用一个主页面，加两个抽屉／弹窗完成：

- 主页面：租户信息、搜索筛选、证书表格、分页、导出按钮。
- 发证弹窗：课程选择、处理状态、逐学员结果。
- 详情抽屉：证书信息、撤销确认。

课程、学员和报名关系使用 seed 数据即可；题目没有要求它们的 CRUD 页面，也没有要求生成 PDF 证书。

**2. 数据模型建议**

保留五个核心实体，补上操作者、审计和请求幂等记录。

| 表 | 关键字段及用途 |
|---|---|
| `tenants` | `id, name, timezone` |
| `admins` | `id, tenant_id, username, password_hash`，识别操作者和所属租户 |
| `courses` | `id, tenant_id, title, ends_at` |
| `learners` | `id, tenant_id, name, email` |
| `enrollments` | `id, tenant_id, course_id, learner_id, status, completed_at` |
| `certificates` | `id, tenant_id, enrollment_id, serial_number, issued_at, issued_by, revoked_at, revoked_by` |
| `audit_logs` | `id, tenant_id, action, certificate_id, course_id, learner_id, actor_id, occurred_at` |
| `issuance_requests` | `id, tenant_id, idempotency_key, request_hash, response_json, created_at` |

建议提前确定这几个业务规则：

- **符合发证条件**：课程已经结束，且报名记录为 `completed`。
- **同一报名关系最多一张证书**：数据库设置 `UNIQUE(tenant_id, enrollment_id)`。
- **撤销后不自动补发**：再次批量操作仍返回 `skipped`，理由是证书已撤销。补发属于额外业务，本次不做。
- **证书状态由 `revoked_at` 推导**：为空是 `valid`，否则是 `revoked`，避免状态字段和时间字段不一致。
- **编号独立生成且唯一**：例如 `CERT-<UUID>`，不采用“当前数量加一”。

报名关系还应有 `UNIQUE(tenant_id, course_id, learner_id)`。

外键最好连同 `tenant_id` 一起约束，防止出现“租户 A 的报名记录引用租户 B 的课程”这种非法数据。SQLite 的外键检查需要在每个连接上启用。

**3. API 设计**

建议 URL 简单一些，租户范围由登录身份决定。

| 方法与路径 | 用途 |
|---|---|
| `POST /api/auth/login` | 演示管理员登录 |
| `GET /api/me` | 当前管理员和租户，包括租户时区 |
| `GET /api/courses` | 当前租户课程，附可发证／已发证数量 |
| `GET /api/certificates` | 搜索、筛选、分页、排序 |
| `GET /api/certificates/export.csv` | 导出全部匹配记录 |
| `GET /api/certificates/{id}` | 证书详情 |
| `POST /api/certificates/{id}/revoke` | 撤销证书 |
| `POST /api/courses/{id}/issue-certificates` | 批量发证 |

列表参数建议：

```text
q
course_id
status
page
page_size
sort_by
sort_order
```

只开放少量排序字段，例如签发时间、学员姓名、编号；后端做白名单校验。所有排序都增加 `id` 作为次级排序，保证翻页稳定。

批量接口要求请求头：

```text
Idempotency-Key: <客户端生成的 UUID>
```

返回逐学员结果：

```json
{
  "issued_count": 2,
  "skipped_count": 1,
  "failed_count": 0,
  "results": [
    {
      "learner_id": "…",
      "learner_name": "…",
      "outcome": "issued",
      "certificate_id": "…",
      "reason": null
    }
  ]
}
```

建议统一错误结构，例如 `code + message`。跨租户资源访问返回 `404`，避免透露其他租户的资源是否存在。

**4. 批量发证：需要两层幂等保护**

**第一层是业务唯一性。** 无论用户点多少次、换多少个请求 key，同一报名关系只能有一张证书。这个保证必须来自数据库唯一约束，不能只靠“先查询有没有”。

**第二层是请求重放。** 网络超时后重试同一个请求，应拿到第一次的结果，而不是把第一次的 `issued` 全变成 `skipped`。

建议处理流程：

1. 校验管理员、课程归属、课程结束时间和请求参数。
2. 开启写事务，查找当前租户下的幂等记录。
3. 同 key、同请求：返回已保存结果。
4. 同 key、不同请求：返回 `409`。
5. 读取该课程的报名记录，逐条判断。
6. 新证书和对应的签发审计记录一起写入。
7. 保存完整响应到 `issuance_requests`。
8. 提交事务后返回。

每个学员使用 savepoint：某条可恢复的数据错误只回滚该学员的证书及审计，记为 `failed`；数据库整体不可用等错误则回滚整个批次。

这样能够保证：

- **证书存在，就有对应的签发审计。**
- 重放请求不会重复写签发审计。
- 不同 key 并发请求，也无法绕过证书唯一约束。
- 提交后响应丢失，客户端仍可用原 key 找回结果。

SQLite 同时只有一个写事务，演示版本可以用短事务配合 `BEGIN IMMEDIATE` 和有限的锁等待；超时返回可重试错误，不能误报成功。[SQLite 事务文档](https://www.sqlite.org/lang_transaction.html)

前端应在首次提交时生成 key，网络重试沿用原 key。建议暂存到 `sessionStorage`；明确开始一次新操作时才换 key。

还有一个语义需要说清楚：**同 key 重试重放原结果；想重新尝试原先失败的学员，发起新批次。** 已成功的学员会被业务唯一约束保护并跳过。

**5. 多租户隔离：后端身份决定范围**

只做前端租户下拉框，再把 `tenant_id` 传给后端，不足以满足隔离要求。

建议最小方案：

- Seed 两个租户，各有一个管理员。
- 做简单登录，由后端把身份绑定到租户。
- 每次请求通过统一依赖取得 `current_admin` 和 `tenant_id`。
- 所有列表、详情、课程、发证、撤销、导出和幂等查询，都应用这个租户范围。
- 客户端不传 `issued_by` 或业务对象的 `tenant_id`。
- 切换演示账号时，清空列表、详情、选择项及批量结果，防止旧数据残留。
- 搜索请求取消或忽略过期响应，防止切换账号后旧请求覆盖页面。

当前场景不需要 RBAC。一个管理员属于一个租户，就足够演示和验证隔离。

**6. 时区：统一存储，显示和导出使用租户配置**

建议约定：

- 数据库存 UTC 时间；SQLite 中可统一使用整数 epoch 毫秒，避免混入没有时区的时间字符串。
- API 输出标准 UTC ISO 8601，例如以 `Z` 结尾。
- 租户保存 `Australia/Sydney` 这样的 IANA 时区名称。
- 前端明确指定租户时区格式化，不能使用浏览器默认时区。
- CSV 在后端使用同一租户时区格式化。
- 页面显示当前时区，CSV 时间携带偏移量，便于核对。

后端使用 Python `zoneinfo`，并声明 `tzdata` 依赖，尤其考虑你当前的 Windows 环境。[Python 时区文档](https://docs.python.org/3/library/zoneinfo.html)

本轮先不增加日期范围筛选，减少边界处理。列表默认按签发时间排序；“按租户本地日历日期排序”出现在第 8 节的独立设计问答中，并非前面四项核心功能额外要求的筛选功能。

**7. CSV：和列表共用筛选规则，但不受分页限制**

最容易做错的是直接导出前端当前页，或者给接口传一个特别大的 `page_size`。

建议：

- 列表和 CSV 共用查询条件构造函数，保证租户、搜索、课程、状态一致。
- CSV 忽略 `page`、`page_size`，输出全部匹配记录。
- 字段至少包含题目要求的：学员姓名、课程名称、证书编号、签发时间。
- 使用 CSV 标准库处理逗号、双引号和换行。
- UTF-8 加 BOM，便于 Excel 打开中文。
- 对用户可控文本处理公式注入风险。
- 后端分批读取、分块输出，不先 `.all()` 再拼整个文件；SQLAlchemy 的批量读取机制支持控制结果缓冲规模。[SQLAlchemy 文档](https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#fetching-large-result-sets-with-yield-per)
- 在一次明确的读事务中完成导出，保持一致的数据快照；生成器结束或下载断开时关闭游标和连接。

前端尽量使用浏览器下载能力，避免把完整文件先装进 JavaScript 内存。流式输出可以控制内存，但不等于解决所有查询耗时；本次先验证完整性和稳定性。

**8. 如何控制实现复杂度**

建议后端采用同步 SQLAlchemy Session，按 API、业务服务、模型分层即可，不做通用 Repository 框架。

前端用 Composition API 和少量 composable 保存查询及操作状态，暂时无需 Pinia。Element Plus 足够完成表格、弹窗、详情、确认和错误提示。

批量操作采用同步接口，因此进度展示为：

> 正在处理，请勿重复提交 → 完成，显示成功／跳过／失败数量及明细。

按钮禁用并显示 loading，使用不定进度条；不要显示虚构的百分比。题目只写了“show progress”，没有明确要求实时逐条进度。**这是当前方案中最值得明确的取舍**：如果要求真实的“已处理 20/100”，就需要增加任务状态接口和轮询，实现成本会明显增加。

**9. 容易漏掉的要求与验证点**

除了功能，还要注意：

- 审计记录必须包含**谁、何时、哪个课程、哪个学员**。
- 批量结果要有逐人明细，不能只显示“成功 10 人”。
- 撤销必须确认；重复撤销建议返回当前状态，不重复产生状态变更。
- 初始化脚本应可重复运行，不能每次启动都追加重复数据。
- 演示数据要覆盖两租户、未完成报名、已签发、已撤销、可发证课程，以及足够翻页的数据。
- 保留一键启动说明，并从干净环境实际走一遍。
- 有意义的 Git 提交历史是交付物之一。
- 正式过程要求全程录屏、全程摄像头开启，并显示编辑器、终端和 AI 工具。
- 开始阶段需要一份不超过 100 words 的简短计划；第 8 节的反思和设计回答由你独立完成。
- 题目是连续 3 小时，已经给出时间分配，应留出最后的独立作答时间。

测试不必多，但这几项值得自动化：重复及并发发证、审计原子性、跨租户访问、时区显示／导出一致性、CSV 超过一页后的完整性。

**我建议先确认四个业务选择：**

1. 发证资格采用“课程已结束 + 报名已完成”。
2. 一次报名最多一张证书，撤销后不补发。
3. 使用两个演示管理员登录来体现租户隔离。
4. 批量发证采用同步请求和不定进度提示。

这四点确定后，就可以把方案收敛成简短的 Spec 和开发计划。

## 2026-11-04T22:54:41.403Z — user

可以按照这个方案


## 2026-11-04T22:54:43.622Z — assistant (commentary)

我会按已确认的方案整理 `Spec` 和开发计划，明确业务规则、接口契约、验收标准和时间分配，暂不写代码。

## 2026-11-04T22:56:41.511Z — assistant (commentary)

两份文档已整理好。Spec 补充了可直接用于验收的细节：响应丢失后沿用原 key 重试、撤销也写审计、CSV 导出不受分页限制，以及切换账号时清理旧数据。开发计划按题目的 180 分钟分配，保留了最后 25 分钟独立作答时间。

## 2026-11-04T22:56:48.087Z — assistant (final_answer)

已按确认的方案整理完成：

- [SPEC.md](<USER_HOME>/Desktop/take-home/docs/SPEC.md)：业务规则、数据模型、API、幂等事务、多租户隔离、时区、CSV 和验收标准。
- [DEVELOPMENT_PLAN.md](<USER_HOME>/Desktop/take-home/docs/DEVELOPMENT_PLAN.md)：三小时时间分配、开发顺序、测试重点、演示流程和交付检查。

目前只新增文档，尚未开始写业务代码。

## 2026-11-04T22:57:36.940Z — user

方案看起来没问题，接下来帮我把项目初始化一下，然后把开发任务拆成两个可以并行的 Ticket，一个负责 Backend，一个负责 Frontend。
你先把项目基础结构、依赖、共享的数据结构和 API Contract 定义好，避免后面两个 Agent 各写各的，最后接口对不上。
把 Spec、两个 Tickets 和需要的开发说明放到 docs 里面，AGENTS.md 也可以简单写一下。
这一步完成之后，把基础代码和文档 Commit 到 Git，创建一个 feature/mvp 分支。
暂时不用实现具体的业务功能，我后面会开两个不同的 Worktree，让它们并行开发。


## 2026-11-04T22:57:39.778Z — assistant (commentary)

我会先初始化前后端骨架，定义共享 API Contract 和数据结构，再拆出 Backend、Frontend 两个可并行的 Ticket，并补上开发约定。验证基础构建后提交到 Git，创建 `feature/mvp` 分支；这一步不实现业务功能。

## 2026-11-04T22:58:29.239Z — assistant (commentary)

契约会采用一条生成链：后端 Pydantic DTO 和路由声明生成 OpenAPI，再生成前端 TypeScript 类型，并加上检查命令来发现接口漂移。业务接口暂时统一返回 `501 not_implemented`，方便区分骨架和已完成功能；两个 Ticket 会划定文件归属和契约修改规则。

## 2026-11-04T23:00:46.489Z — user

<send_user_message_question_reply>
[{"questionItemId":"[\"request_user_input_async\",\"call_610e5a7799764d33aee8b266c20556c2\",0]","question":"当前机器没有配置 Git 提交身份。请提供这次 commit 使用的姓名和邮箱（可以用 GitHub noreply 邮箱）；我只会配置到当前仓库，其他初始化工作会继续进行。","answer":"[REDACTED_PERSONAL_EMAIL]  \nHaiyang Zhang"}]
</send_user_message_question_reply>


## 2026-11-04T23:02:01.859Z — assistant (commentary)

前后端骨架和接口声明已建立，覆盖字段、枚举、错误码、分页、幂等请求头及 CSV 响应格式。Git 身份已收到，会只配置到当前仓库。

安装依赖时遇到了沙箱网络限制；我会尝试通过允许的方式完成安装，继续验证类型生成和构建。

## 2026-11-04T23:07:32.887Z — assistant (commentary)

两个 Ticket 和开发说明已写好：Backend、Frontend 分别负责各自目录，共享契约和根锁文件需要协调修改，前端可用显式 mock 独立开发。

契约检查和后端 lint 已通过，测试及前端构建正在运行。Git 仓库也已初始化，并配置了你提供的提交身份。

## 2026-11-04T23:10:30.016Z — assistant (commentary)

基础检查已通过：12 个后端测试、契约一致性检查、lint、Vue 类型检查和生产构建。安装和启动命令也已实测，前端 HTTP 入口、后端健康检查及 `/api` 代理均正常。

业务接口仍按预期返回 `501`，没有实现发证等业务功能。接下来会把验证结果写入文档，提交基础代码，并创建 `feature/mvp` 分支。

## 2026-11-04T23:12:07.243Z — assistant (final_answer)

已完成初始化并提交：

- 当前分支：`feature/mvp`
- Commit：`180fca6`
- 工作区干净，尚未创建 Worktree。

前后端骨架、依赖锁文件、共享 DTO、OpenAPI、生成的 TypeScript 类型和类型化客户端均已就绪，并提供契约漂移检查。

开发入口：

- [Backend Ticket](<USER_HOME>/Desktop/take-home/docs/tickets/BACKEND.md)
- [Frontend Ticket](<USER_HOME>/Desktop/take-home/docs/tickets/FRONTEND.md)
- [API Contract](<USER_HOME>/Desktop/take-home/docs/API_CONTRACT.md)
- [开发说明](<USER_HOME>/Desktop/take-home/docs/DEVELOPMENT.md)
- [AGENTS.md](<USER_HOME>/Desktop/take-home/AGENTS.md)

已验证安装、启动、代理、12 个基础测试、类型检查及生产构建。业务接口仍为 `501` 占位，未实现具体业务功能。

后续两个 Worktree 可从这个提交分别创建 Backend、Frontend 分支。

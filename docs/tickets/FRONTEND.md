# FE-01 — Frontend MVP

状态：Completed；实现提交 bb7d9d8，已与 Backend 集成至 feature/mvp。原完成记录中的 mock 验证为独立开发阶段，后续真实联调记录见 README。

## 目标

在 Vue 3 + Element Plus 骨架上完成可演示控制台。严格使用共享 DTO、现有 typed client 和 API Contract，可先用显式 mock 独立开发。

## 开始前阅读

AGENTS.md、docs/SPEC.md、docs/API_CONTRACT.md、docs/DEVELOPMENT.md、docs/api/examples.json。

## 文件归属

- 可修改 frontend/** 和本 Ticket 的完成记录。
- 不修改 backend、docs/api、packages/api-contract、根脚本/锁文件和共享文档。
- 不复制 wire interface，不用 any 或类型断言掩盖接口不一致。
- 已有 Vue/Element Plus/openapi-fetch；优先 Composition API，无需 Pinia/Router 或额外 UI 库。

## 工作项

- [ ] 登录表单、me 恢复身份、退出；显示管理员、租户和 IANA 时区。
- [ ] 所有 API 使用 typed client，携带 cookie；统一识别 HTTP error 和无响应的网络异常。
- [ ] 列表姓名/编号搜索、课程/状态筛选、后端分页和排序；参数变化重置第一页。
- [ ] 明确 loading、空租户数据、无匹配结果、错误/重试；约 300ms 防抖和旧响应保护。
- [ ] 详情抽屉，租户时区格式化、状态、签发人、撤销信息。
- [ ] 撤销确认、提交禁用，成功刷新详情和列表；重复撤销状态可正确显示。
- [ ] 批量弹窗选课程、展示资格数量；未结束课程不能提交，后端仍是最终判断者。
- [ ] 发证按钮防重复点击，不定进度，完成后的数量及逐学员 issued/skipped/failed 明细。
- [ ] key 在发送前按身份/租户/课程保存到 sessionStorage；不确定结果保留原 key，显式重试复用。
- [ ] HTTP 200 仍检查 failed_count；新批次才生成新 key，不做无限自动重试。
- [ ] 账号切换/401 清空私有 UI 状态并取消或忽略旧响应；保留的待确认 key 必须按身份隔离，不能跨账号复用。
- [ ] CSV 同源直接下载 URL，复用当前搜索、筛选、排序但移除分页；不先加载完整 Blob，不宣称下载完成。
- [ ] 使用租户 timeZone 而非浏览器默认时区；不对 UTC 时间手工加固定小时数。
- [ ] 若启用开发 mock，显式模式且默认 real，仅 Frontend 目录内实现；不得请求出错后回退假数据。
- [ ] 页面使用 Element Plus，桌面可演示，较窄屏幕不遮挡关键操作。

## 独立开发与联调

Backend 未完成时 501 是预期。共享样例用于显式 mock；复用已提供的 Identity、CertificatePage 等类型，逐人结果为 discriminated union。

开发 mock 至少覆盖加载、空、错误、正常结果、部分失败、已撤销和切换身份。mock 是开发工具，不作为真实发证成功的证据。Backend 完成后关闭 mock 再走真实链路。

## 验收与验证

- [ ] npm run typecheck、npm run build、npm run contract:check 全部通过。
- [ ] 浏览器验证：登录 → 搜索/筛选/分页/排序 → 详情 → 批量发证 → 撤销 → 导出 → 切换账号。
- [ ] 批量处理中重复点击不会发出新请求；网络结果不确定时重试头仍为同一个 key。
- [ ] 401 正确退出，409 展示具体原因，503 保留原 key；错误不被成功 toast 覆盖。
- [ ] 改筛选/账号后旧响应不覆盖新状态；详情和发证明细无其他身份残留。
- [ ] 页面时间与 Contract 样例的租户本地时间一致；CSV URL 不含分页参数。
- [ ] 无相关运行时错误或框架 overlay，加载/空/错误状态有明确用户反馈。
- [ ] 写明验证使用 mock 还是真实 Backend，区分尚未联调项目。

## 交付

有意义的实现提交；本 Ticket 记录验证方式、结果、mock 启用方法及待联调事项。截图等临时证据不提交源码仓库。

## 不在范围内

后端行为、数据库、全套业务管理 CRUD、实时百分比、PDF、额外状态管理框架和独立 Section 8 问答。

## 完成记录（执行者填写）

- Commit：`feat(frontend): implement certificate admin console`，与下方记录同一提交。
- 验证命令及浏览器结果：类型检查、5 个单元测试、Build、Contract 检查和 Playwright 回归通过，详见下方。
- Mock 模式/真实 API 验证情况：显式开发 Mock 验证完成；真实 API 尚待后端联调。
- 已知限制及待联调事项：Element Plus 大 chunk 提示、浏览器直接下载的最终结果需浏览器确认；详见下方。

### FE-01 完成记录 · 2026-11-04

- Commit：与本记录一起提交，主题 `feat(frontend): implement certificate admin console`；提交 hash 见交付消息。
- 实现：登录/me/退出、身份与租户时区；typed client；300ms 搜索防抖、课程/状态筛选、服务端分页和排序；loading、空租户、无匹配、错误/重试；详情抽屉、撤销二次确认和刷新；批量资格、提交锁定、不定进度、计数和逐人结果；身份/租户/课程隔离的 sessionStorage key、原 key 恢复与重试；同源全匹配 CSV 下载。无后端、共享契约、根配置或锁文件修改。
- 验证通过：`npm run typecheck`；`npm run test --workspace @certificate-admin/frontend`（5 个 Node 单元测试）；`npm run build`；`npm run contract:check`；`git diff --check`。
- 浏览器：Browser 插件未提供，使用已有 Playwright + Chromium；沙箱阻止本地 socket/浏览器启动，因此服务和浏览器验证在获准的沙箱外执行。`npm run test:e2e --workspace @certificate-admin/frontend` 全部通过。覆盖登录失败/恢复、搜索/排序/筛选/分页重置、旧搜索响应、空/错误/重试、详情时区、撤销取消/确认、27 条跨页 CSV、未结束课程、防重复、部分失败、丢失响应后关闭/刷新/原 key 重试、503、409、延迟详情跨账号隔离、待确认 key 账号隔离、401 清理。无 runtime error、Vue warning 或框架 overlay；有测试刻意触发的 HTTP/network 错误。
- Mock：仅显式 `VITE_API_MODE=mock` 的 Vite 开发服务；默认 real，无 API 出错回退。Mock 提供可见标识和场景选择，内存状态可由测试专用 `/__dev/reset` 重置。生产模式不启用 Mock 服务或场景 UI。运行、账号、测试环境变量见 `frontend/README.md`。
- 视觉 QA：Playwright 截图，已通过 view_image 检查概念图及最终页面；验证 1440×1000 桌面、390×844 窄屏和概念原生 1487×1058 视口。检查了表格布局、标题/操作文案、字号层级、白底/浅灰/蓝色配色、间距/边框、状态标签和响应式。首屏关键标题与按钮文案一致；有意差异为开发 Mock 条、契约默认 20 条分页与固定表头/内部滚动、Element Plus 原生控件及等宽编号。原型仅用作视觉方向，保留规范要求的实际数据与交互。修复长列表挤压分页、长弹窗超出视口及撤销成功后关闭短暂被锁定的问题；最终无阻断性视觉问题。截图与概念保存在仓库外，未提交。
- 实际验证全部使用显式 Mock，尚未与真实 Backend 联调；不宣称验证了后端租户授权、事务/并发、幂等持久化或真实 CSV 流式/安全转义。后端交付后需关闭 Mock，重新执行真实业务链路。
- 已知限制：Element Plus 全量导入保留，Build 有非阻断大 chunk 提示；CSV 为浏览器直接下载，页面只提示请求下载，不确认流式下载最终成功；sessionStorage 不可用时禁止新发证请求。契约类型辅助丢失 null-only 字段的问题在前端经运行时检查处理，未修改生成文件或使用类型断言。
- 未修改 Section 8 独立回答；未创建 worktree、启动其他 agent、合并或推送代码。

# FE-01 — Frontend MVP

状态：Ready，尚未开始。建议分支：feature/frontend；基于 feature/mvp 的基础提交。

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

- Commit：待填写
- 验证命令及浏览器结果：待填写
- Mock 模式/真实 API 验证情况：待填写
- 已知限制及待联调事项：待填写

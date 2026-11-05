# 审查 main 与 feature/mvp

Session: `01a1a8fd-bb7e-7642-a000-cbd67a606d3f`

Source: local Codex session; original order and timestamps (UTC). Sanitized export; see README for exclusions.

## 2026-11-04T23:56:04.986Z — user

[@Open Code Review](plugin://open-code-review-codex@open-code-review)&#x20;
现在这个项目基本的功能基本完成了，帮我做一轮完整的 Code Review。
我平时用的是 Open Code Review，你先检查一下当前环境有没有安装和配置好。如果可以用，就对比 main 和 feature/mvp，把这次所有变更都审查一遍。
重点检查逻辑 Bug、安全性、多租户隔离、幂等性、时区处理和测试覆盖。
同时对照一下原来的 Spec，看看有没有漏掉的需求。
先给我一份按严重程度排序的问题列表，不要一上来就大范围改代码。我们确认完问题之后再修复。


## 2026-11-04T23:56:08.759Z — assistant (commentary)

我会先按 Open Code Review 技能检查安装和配置，再读取 Spec、API 契约和开发说明，审查 `main` 与 `feature/mvp` 的全部差异。先给出按严重程度排序、带代码位置和验证依据的问题列表，不修改代码。


## 2026-11-04T23:56:53.475Z — assistant (commentary)

当前能读取 Open Code Review 插件技能，但终端找不到 `ocr` 命令；正在尝试安装 CLI。审查范围已确认是 34 个变更文件，当前 HEAD 与 `feature/mvp` 一致，工作区干净。我会继续核对源码和测试，特别检查批次重试及账号切换这些正常链路容易遗漏的状态。


## 2026-11-04T23:58:08.842Z — assistant (commentary)

`ocr v1.13.5` 已安装，分支差异预览正常；但 `ocr llm test` 显示没有配置 LLM endpoint，因此暂时无法运行 OCR 的模型审查。我会继续直接审查全部 34 个文件，包括 OCR 默认排除的后端测试和文档，并运行项目检查。最终会明确区分这轮人工审查与尚未执行的 OCR 模型审查。


## 2026-11-04T23:59:37.532Z — assistant (commentary)

基础检查目前通过：72 个后端测试、5 个前端单测、契约一致性和 Ruff 都是绿灯。后端的租户过滤、复合外键、写事务及审计回滚已有较扎实的覆盖；接下来我会用前端测试技能检查页面状态，重点验证确定性错误之后能否恢复操作。Browser 插件未提供，将使用环境已有的 Playwright。


## 2026-11-05T00:01:30.669Z — assistant (commentary)

真实浏览器联调也已通过，包括响应丢失后原 key 恢复、撤销、CSV 和双租户拒绝访问。额外复现了一个缺口：发生确定性的幂等 key 冲突后，弹窗只允许继续重试冲突 key，没有开始新操作的入口；现有 409 测试只检查错误文案，未检查恢复能力。我还在核对双标签页切换账号的行为。


## 2026-11-05T00:02:54.311Z — assistant (commentary)

最终确认了 3 个问题，均已用真实浏览器复现：双标签页切换账号会让旧页面混用旧身份和新租户数据，并显示错误时区；幂等冲突后缺少恢复入口；课程结束后，缓存的未结束状态仍会禁用发证。仓库源码未修改。后端测试、契约检查、构建和现有真实联调均通过，这些问题目前未被测试捕获。


## 2026-11-05T00:03:27.187Z — assistant (final_answer)

审查完成：`main (180fca6)` → `feature/mvp (1f49ff7)`，共 **34 个变更文件**。确认 **1 个高优先级、2 个中优先级问题**，均已通过真实浏览器复现。未修改源码，未提交代码。

1. **[P1] 双标签页切换账号后，旧页面混用旧身份和新租户数据**  
   位置：[useConsole.ts:54](<USER_HOME>/.codex/worktrees/4e57/take-home/frontend/src/useConsole.ts:54)  
   标签页 A 登录 Sydney；标签页 B 退出并登录 Perth；回到 A 搜索，页面仍显示 Sydney 管理员和时区，但列表已是 Perth 证书。Perth 应显示的 `07:30` 被显示为 Sydney 的 `10:30`，并且仍能进入撤销操作。  
   原因是 cookie 在标签页间共享，`identity/sessionVersion` 只在当前页面更新。这不是后端授权绕过，但会造成租户身份误导和误操作风险，遗漏了 Spec §4 的账号切换清理要求。建议同步登录状态变化，清空旧页面并重新校验身份。

2. **[P2] 幂等冲突后无法通过页面开始新批次**  
   位置：[BulkIssue.vue:64](<USER_HOME>/.codex/worktrees/4e57/take-home/frontend/src/components/BulkIssue.vue:64)  
   后端返回 `409/idempotency_conflict` 后，冲突 key 永久保留；页面只有“Retry original batch”，反复提交仍然冲突，关闭重开也无法恢复。“Start a new batch”只在成功取得结果后出现。  
   建议为确定性错误提供用户明确确认后的新批次入口；网络异常和 503 仍必须保留原 key。现有 409 测试只验证错误文案，没有验证后续恢复。

3. **[P2] 课程结束后，缓存状态仍会阻止发证**  
   位置：[BulkIssue.vue:100](<USER_HOME>/.codex/worktrees/4e57/take-home/frontend/src/components/BulkIssue.vue:100)  
   登录时课程尚未结束，等待超过结束时间后再打开弹窗，后端已返回 `is_finished=true`，页面仍提示未结束并禁用发证。关闭重开弹窗也不会刷新课程。  
   建议打开弹窗时刷新课程状态，并补充跨越结束时刻的测试。这是时间相关业务状态陈旧问题，UTC/IANA 转换本身未发现错误。

**实际验证**

- 72 个后端测试、5 个前端单测全部通过。
- 契约一致性、Ruff、类型检查及生产构建通过。
- 现有真实浏览器联调通过；另增加上述三项临时复现。
- 本轮未发现可确认的后端跨租户授权绕过、重复签发或审计原子性缺陷。核心功能已覆盖 Spec，缺口主要集中在上述前端状态边界。

**Open Code Review 环境**

按 [Open Code Review 技能](<USER_HOME>/.codex/plugins/cache/open-code-review/open-code-review-codex/1.0.0/skills/open-code-review/SKILL.md) 检查：原环境缺少 CLI，现已安装 **v1.13.5**，差异预览正常；但 `ocr llm test` 报告未配置 LLM endpoint。因此本次结果来自直接源码审查与测试验证，**未执行 OCR 模型审查**。后续可用 `ocr config provider` 配置，不需要在聊天中提供密钥。

::code-comment{title="[P1] 跨标签账号切换未使旧身份失效" body="真实浏览器复现：A 标签登录 Sydney，B 标签切换为 Perth，A 再搜索会把 Perth 证书显示在 Sydney 身份和时区下。共享 cookie 已变化，但本地 sessionVersion 未变化，旧页面仍接受新身份下的响应并允许继续操作。需要同步账号变化并重新校验身份。" file="<USER_HOME>/.codex/worktrees/4e57/take-home/frontend/src/useConsole.ts" start=56 end=60 priority=1}
::code-comment{title="[P2] 幂等冲突后缺少恢复入口" body="确定性的 idempotency_conflict 仍保留 pending key，而开始新批次按钮仅在 result 存在时出现。复现后只能重复提交冲突 key，关闭重开也无法恢复。应提供用户明确确认后的新批次入口，并保留网络异常及 503 的原 key 重试行为。" file="<USER_HOME>/.codex/worktrees/4e57/take-home/frontend/src/components/BulkIssue.vue" start=64 end=68 priority=2}
::code-comment{title="[P2] 课程结束状态过期后仍禁用发证" body="发证按钮依赖登录时缓存的 is_finished。已复现课程跨越结束时刻后，后端已判定结束，重新打开弹窗仍显示未结束且禁止发证。应在打开弹窗时刷新课程状态，并覆盖结束时刻边界。" file="<USER_HOME>/.codex/worktrees/4e57/take-home/frontend/src/components/BulkIssue.vue" start=100 priority=2}

<oai-mem-citation>
<citation_entries>
MEMORY.md:30-32|note=[marketplace registration is distinct from CLI installation; environment verified live]
</citation_entries>
<rollout_ids>
01a1a559-1891-7180-8401-e74a38aaeafe
</rollout_ids>
</oai-mem-citation>

## 2026-11-05T00:07:26.747Z — user

我配置了LLM endpoint，可以重试一下


## 2026-11-05T00:07:33.036Z — assistant (commentary)

我会重新验证 LLM 连通性；通过后运行 `main` → `feature/mvp` 的 OCR 审查，再逐项核实结果，与上一轮发现对照。本轮仍只审查，不修改代码。


## 2026-11-05T00:08:04.921Z — assistant (commentary)

LLM 连接测试和工具调用测试都通过了。之前的 DNS 错误来自沙箱网络限制，联网重试后已成功连接配置的 `deepseek-v4-pro`。我现在开始正式审查，并检查 OCR 的排除规则，避免遗漏测试文件。


## 2026-11-05T00:08:43.903Z — assistant (commentary)

连通性验证通过了，但正式审查被自动审批拒绝：它要求明确确认，才能将这个私有仓库的代码差异、Spec、任务说明和测试发送到配置的 DeepSeek endpoint。我会先准备好审查输入清单，不发送仓库内容。

需要确认的是向 `https://api.deepseek.com` 发送上述审查内容的授权；这个额外确认来自自动审批要求。


## 2026-11-05T00:08:54.850Z — assistant (final_answer)

LLM 连通性和工具调用测试已通过，当前配置为 **DeepSeek / deepseek-v4-pro**。

是否授权将 `main` → `feature/mvp` 的代码差异，以及 Spec、API 契约、任务说明和相关测试发送到 `https://api.deepseek.com`，用于本次只读审查？

**自动审批拒绝了正式审查调用**：它认为配置 endpoint 和要求重试，尚不足以明确授权向该外部服务发送这批私有仓库内容。审查输入已在本地准备好，源码未修改；确认后即可继续。

## 2026-11-05T00:13:57.289Z — user

暂不授权，修复刚才检查出的三个问题


## 2026-11-05T00:14:02.341Z — assistant (commentary)

我会修复上一轮确认的三个前端问题，补上对应回归测试，不向外部 LLM 发送仓库内容。先检查当前代码，再验证跨标签页身份同步、幂等冲突恢复和课程状态刷新。


## 2026-11-05T00:14:58.265Z — assistant (commentary)

身份切换会在标签页之间通知并清空旧状态，同时丢弃旧请求的响应；幂等冲突后会增加二次确认的新批次入口，网络异常和 503 仍复用原 key；发证弹窗打开时会重新获取课程资格，并在刷新完成前禁用提交。本轮继续使用前端测试技能和已有 Playwright 验证。


## 2026-11-05T00:17:44.659Z — assistant (commentary)

三个修复已完成，类型检查通过。新增的浏览器回归会验证：双标签页切换时清空旧状态并忽略延迟响应；幂等冲突确认后才能换 key，网络异常和 503 保留原 key；课程资格重新加载时禁用提交，并能在加载失败后重试。接下来运行新增回归和原有真实联调。


## 2026-11-05T00:20:27.075Z — assistant (commentary)

新增回归和原有真实联调均已通过：双标签页通知的两种机制分别可用，旧响应不会恢复旧租户页面；幂等冲突确认后使用新 key，网络异常和 503 仍沿用原 key；课程刷新失败时无法提交，重试后可恢复。正在跑最后一轮既有 mock 回归，并整理验证记录和提交。


## 2026-11-05T00:22:40.573Z — assistant (commentary)

三项修复的回归和既有 mock 回归现已全部通过，原有真实联调也通过。改动仅在前端及其测试、说明和 Ticket 记录中，后端与 API 契约未改。接下来保存本地提交；现有 Element Plus 大包构建提示仍在，不影响构建。


## 2026-11-05T00:23:16.889Z — assistant (final_answer)

三个问题已修复，提交为 **`f71d163`**，位于 `codex/fix-mvp-review`，工作区干净。

- 跨标签页切换账号会清空旧身份、数据和弹窗，并忽略旧响应。
- 幂等冲突后可确认开始新批次；网络异常和 503 仍保留原 key。
- 发证弹窗打开时刷新课程资格，加载或失败时禁止提交，并支持刷新重试。

新增回归、原有真实联调、mock 浏览器回归、5 个前端单测、类型检查、契约检查及构建全部通过。未发送仓库内容到外部 LLM，未合并或推送。

验证记录见 [Frontend Ticket](<USER_HOME>/.codex/worktrees/4e57/take-home/docs/tickets/FRONTEND.md)。

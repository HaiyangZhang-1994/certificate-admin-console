# Frontend console

Vue 3 + TypeScript + Element Plus. All business requests go through the existing cookie-authenticated typed client and shared DTOs. No backend or shared contract files are changed.

## Run

From the repository root, after `npm ci`:

```powershell
npm run dev:frontend
```

Default is real API mode, proxied from `http://127.0.0.1:5173/api` to `http://127.0.0.1:8000`. Start the backend separately for integration. A 501 response is displayed as an error; there is no fallback to fake data.

For isolated development only:

```powershell
$env:VITE_API_MODE = 'mock'
npm run dev:frontend
```

The mock banner and scenario selector are always visible in this mode. Accounts: `sydney.admin` / `perth.admin`, password `DemoPass123!`. Mock state lives only in the Vite process and resets on restart. The scenario selector demonstrates empty/list error, partial batch failure, lost response, 503, 409 and 401. Loading is visible on every mock request. There are 27 initial Sydney records and four Perth records, a future course and an empty course. Mock CSV downloads use the same development middleware. No mock module is shipped in the browser production bundle; Vite preview does not serve mock endpoints.

To return to real mode, stop Vite, run `Remove-Item Env:VITE_API_MODE -ErrorAction SilentlyContinue`, then restart. Session cookies from the mock are not real backend sessions; sign in again.

## Checks

真实 Backend 联调：先按根 README 启动/seed，再执行 `npm run test:integration --workspace @certificate-admin/frontend`。支持与下方 mock 测试相同的 PLAYWRIGHT_MODULE、PLAYWRIGHT_EXECUTABLE、FRONTEND_URL 和 SCREENSHOT_DIR。真实测试会签发及撤销本地演示证书，不 reset 数据库；覆盖范围与未验证项见根 README。

```powershell
npm run test --workspace @certificate-admin/frontend
npm run typecheck
npm run build
npm run contract:check
```

The unit suite uses the existing TypeScript compiler and Node test runner. It checks CSV parameters, identity-scoped pending keys, tenant timezones and DST, HTTP status handling and uncertain outcomes.

Browser regression tests require a running explicit mock server and an existing Playwright installation (no new dependencies or root lockfile changes):

```powershell
# Optional when Playwright is supplied by an external tool runtime:
$env:PLAYWRIGHT_MODULE = 'C:/path/to/playwright/index.mjs'
$env:PLAYWRIGHT_EXECUTABLE = 'C:/path/to/chrome.exe'
# Optional evidence directory outside the repository:
$env:SCREENSHOT_DIR = 'C:/path/to/evidence'
npm run test:e2e --workspace @certificate-admin/frontend
```

The browser suite explicitly resets only development mock memory using `POST /__dev/reset`; this route exists exclusively when mock mode is enabled. It never calls a real-backend reset endpoint. It tests login/restoration, searches, filters, pagination/sort, stale responses, loading/empty/errors, details, revoke cancel/confirm, all-matching CSV, partial results, pending-key reload/retry, 503/409, account switching, 401 cleanup, desktop/mobile overflow and runtime errors. It intentionally generates HTTP errors and a lost connection in development scenarios.

## Behavior and integration notes

- Issuance is synchronous, with an indeterminate indicator. Counts and results come from the completed response; partial failures are never called full success.
- Pending UUIDs are saved before submission in sessionStorage, scoped by administrator, tenant and course. Unknown outcomes and errors retain the original key. Selecting that course again, including after a reload, exposes the original-key retry. Completed batches clear the key; starting another operation is explicit, and discarding a rejected conflict key requires confirmation. Session storage must be enabled.
- Authentication/session changes clear private UI state and invalidate previous requests. Pending keys remain isolated so the original administrator can recover a result later.
- Login/logout notify other tabs through BroadcastChannel and a storage-event fallback, clearing their private state and invalidating outstanding requests (including session restoration). Notifications contain only a random event ID. Cross-tab notification requires at least one of these browser facilities to be available.
- An idempotency conflict offers “Start a new batch” with confirmation. Cancelling preserves the original key; confirming discards only that rejected key. Network errors and 503 never offer this shortcut and retain the original-key retry.
- Opening the issuance dialog reloads course eligibility from the backend. Submission is disabled while eligibility loads or fails; “Refresh courses” also updates eligibility without reopening, and a failed refresh offers a retry.
- The installed openapi-fetch helper omits null-only properties in its inferred response type. Issued/failed variants are checked for their required nulls at runtime and reconstructed as shared DTOs without assertions or new wire interfaces.
- Dates use the authenticated tenant IANA timezone via Intl. CSV is a same-origin browser download with filters/sort and no page parameters. The frontend reports only that the download was requested; browser/server errors during a download must be checked in the browser downloads panel.
- Mock testing does not verify real backend authentication, authorization, transactions, concurrency, CSV escaping/streaming or database correctness. These require backend integration.
- Element Plus retains the scaffold's full registration/CSS import. The production build passes with a nonblocking large-chunk warning; tree-shaken registration is a future optimization.
- Section 8 independent reflection/design answers are untouched.

Review-fix regressions use the same Playwright/Chromium and FRONTEND_URL variables as the real integration test. Start the real services against a disposable seeded database, then run from the repository root:

```powershell
node frontend/tests/review-regressions.mjs
```

This suite uses real authentication and idempotency conflicts, tests both cross-tab notification mechanisms independently, delays old list/session responses, and verifies cancellation/new-key recovery plus original-key preservation for network/503 errors. Course-response interception exercises stale eligibility and refresh failures; those cases verify UI behavior rather than backend time calculations. It does not reset the database, but can issue eligible certificates in the demo Workplace Safety course. Optional SCREENSHOT_DIR saves evidence outside the repository.

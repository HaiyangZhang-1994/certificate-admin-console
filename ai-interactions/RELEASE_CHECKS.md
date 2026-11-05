# Submission checks — 2026-11-04

Performed from the release checkout on `main`, Windows, Node 24.15.0 and Python 3.12.14. This is an engineering validation record, not the candidate's Section 8 response.

## Git and integration

- Inspected all six registered worktrees. The five other checkouts had no uncommitted tracked or untracked project changes. Ignored dependencies, databases and temporary evidence are excluded.
- Original main was `180fca6`; it was fast-forwarded to `f71d163`, without squash, rebase, amend or history rewriting.
- Backend implementation `468ee84`, backend tests `a6e389a`, frontend `bb7d9d8`, backend merge `d05ea67`, frontend merge `11388b6`, integration fix `a81e84f`, integration documentation `1f49ff7` and review fixes `f71d163` are ancestors of main.
- `git rev-list --all --not main` returned no commits before the archive commit: all existing branch history is included. The two original merge commits and all nine original commits remain reachable.
- Spec, API Contract, development plan, both tickets, AGENTS.md, lockfiles, generated contract artifacts, README, seed and test sources are present. No independent Section 8 submission or recording link was authored.

## Commands actually run

| Check | Result |
| --- | --- |
| `npm run setup` | Installed locked Python and npm dependencies in this worktree; npm reported 0 vulnerabilities. Initial sandbox ensurepip failure was resolved using permitted execution. |
| `npm run check` | Passed: contract unchanged; Ruff; 72 backend tests; 5 frontend unit tests; Vue/TypeScript checking; Vite production build. |
| `npm run seed` twice | Passed against `sqlite:///./tmp/release-demo.db`; repeat seed remained idempotent. |
| `npm run dev` | Started real services on frontend 5191 / backend 8021 using that isolated database. |
| `npm run test:integration --workspace @certificate-admin/frontend` | Passed with existing Playwright and Chrome: real login/restoration, search/pagination/sorting/filtering, all-page and filtered CSV/escaping/timezones, issuance/double-click guard, response loss and original-key replay, revocation, account switch and cross-tenant denials, desktop/narrow viewport, expired-session cleanup. |
| `node frontend/tests/review-regressions.mjs` | Passed: both cross-tab mechanisms together and separately; stale-response rejection and pending-key isolation; real 409 conflict cancellation/confirmed recovery; original-key preservation for network/503; course refresh and failure/loading guards. Course-response interception is limited to the documented UI refresh scenarios. |
| `git diff --check` | Passed for maintained project documentation. Raw historical transcript whitespace is preserved. |

## Security and archive

- Gitleaks 8.30.1 `git . --log-opts=--all --redact=100` scanned the original history; no leaks found. Gitleaks counts seven non-merge commits while Git contains nine commits including the two merges.
- Gitleaks `dir ai-interactions --redact=100` scanned the sanitized dialogue and textual tool activity; no leaks found. A complete staged submission snapshot was also scanned before commit/push, with no leaks found.
- Reviewed tracked paths and credential-related references. No `.env` secret files, private keys, database files, dependencies, virtual environments, OCR user configuration, raw runtime sessions or temporary outputs are part of the submission. `backend/.env.example` contains local configuration only.
- `DemoPass123!` and test credentials remain intentionally available for local seed/demo and automated tests; they are not real service credentials. Real GitHub credentials were used only in process memory or by Git Credential Manager and were never written to project files or tool output.
- Personal email addresses in exported conversations and local home-directory prefixes were redacted. Original Git author metadata remains unchanged to preserve history. Archive exclusions and capture cutoffs are documented in its README and manifest.
- Automated secret scanning is pattern based and is not a guarantee against every possible secret. Binary screenshots/media are excluded; the original assessment PDF is retained as project input.

## Remote and limitations

- Created `HaiyangZhang-1994/certificate-admin-console` using the existing authenticated account. Creation response confirmed `private: true` and push/admin permission; no public visibility change was requested or performed.
- The local archive captures release preparation before its own final commit/push. The final chat reports the actual remote commit/tree/history verification after upload.
- Existing nonblocking warnings: Element Plus large bundle and Starlette TestClient/httpx deprecation. No production deployment, HTTPS/proxy integration, cross-platform or extended load testing was performed. Existing mock browser coverage is retained; this release reran real integration and review regressions.

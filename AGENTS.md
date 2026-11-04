# Development rules

- Read `docs/SPEC.md`, `docs/API_CONTRACT.md`, `docs/DEVELOPMENT.md`, then your assigned ticket.
- Implement only your ticket. Backend owns `backend/`; Frontend owns `frontend/`.
- `backend/app/contracts.py`, `docs/api/`, `packages/api-contract/`, root scripts/config/lockfile and shared docs are coordinated files. Do not change their contract independently.
- Backend may replace route bodies/dependencies without changing paths, operation IDs, DTOs, status codes or parameter names. Run `npm run contract:check` before handoff.
- Never hand-edit generated OpenAPI or TypeScript. A contract change requires updating the declarations, examples and both tickets together, then regenerating.
- Do not create duplicate wire interfaces in frontend. Import types from `@certificate-admin/api-contract` and use the typed client.
- Authenticated identity supplies tenant scope. Certificate, audit and idempotency behavior must follow the Spec.
- No fake successes or production fallback to mock data. Development mocks must be explicit and isolated.
- Run ticket-specific checks, make meaningful commits and report actual tests and limitations.
- Do not commit database files, secrets, virtual environments, dependencies, or temporary outputs.
- Do not write or revise the candidate's independent Section 8 reflection/design answers.
- Do not create worktrees, merge other branches, or start another agent unless the user explicitly asks.

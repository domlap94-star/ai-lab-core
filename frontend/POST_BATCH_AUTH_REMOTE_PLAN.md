# AI-Lab post-batch auth/version/remote plan

This file is intentionally implementation planning only.
No backend runtime files are changed while the client AI batch is active.

Current database state observed on 2026-08-13:

- one user: `admin`
- one role: `Administrator`
- current Alembic head: `98987aa23248`
- `users` does not yet contain `must_change_password`

## Phase 2 after client batch

1. Add role `User` if missing.
2. Add `users.must_change_password BOOLEAN NOT NULL DEFAULT FALSE`.
3. Keep existing administrator as `Administrator`.
4. Add authenticated password change endpoint.
5. Add admin-only user creation endpoint.
6. Add controlled password reset flow.
7. Extend `/version` with:
   - api_version
   - minimum_app_version
   - latest_app_version
   - update_required semantics
8. Make CORS configurable from environment.
9. Apply localhost-only Docker port bindings.
10. Restart stack once and verify:
    - PostgreSQL
    - Qdrant
    - Ollama
    - backend
    - n8n
    - Open WebUI
11. Configure private HTTPS remote access.
12. Build Windows / Android / Web release clients.
13. Build/sign iOS on macOS/Xcode when available.

## Security boundary

Externally reachable client traffic should terminate at one controlled
HTTPS endpoint.

Do not expose directly:

- PostgreSQL
- Qdrant
- Ollama
- n8n
- Open WebUI

The Docker compose files are prepared to bind service ports only to
127.0.0.1 after the next container recreation/restart.

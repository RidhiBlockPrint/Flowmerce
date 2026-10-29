# ADR 0005: Local operator mode (no sign-in, local-only access)

- Status: approved (owner instruction, 2026-10-29); implemented; phase 2 (Next.js frontend, one launcher, smoke test) completed the same day
- Date: 2026-10-29

## Decision
Phase 1 of removing sign-in. Flowmerce becomes a **local-only operator tool**, not an internet-facing application with authentication removed.

1. **Request boundary.** Every request is answered only when the connecting address is a loopback address (127.0.0.0/8, `::1`, or an IPv4-mapped loopback). Anything else gets HTTP 403 (`local_only`) **before** any page, static file or API is served. The check applies to the dashboard, its assets and every ordinary API path, not just `/api`. It fails closed: a missing or unparsable address is not local. Forwarded-IP headers (`X-Forwarded-For`, `X-Real-IP`, `Forwarded`) are never used to decide that a client is local.
2. **One exception: the workflow webhook.** `POST /api/hooks/workflow` (exact method and path) stays reachable from other computers because it has its own `X-Workflow-Secret` check, which is unchanged. No other path or method is exempt. The dashboard itself is local-only.
3. **Local operator identity.** A local request acts as the first active administrator record (`auth.local_operator()`), with administrator permissions, so permission checks, audit attribution and article ownership keep working. There is no email, password, session cookie or login call.
4. **Obsolete endpoints.** `POST /api/auth/login` and `POST /api/auth/password` answer HTTP 410 and verify or change nothing. `POST /api/auth/logout` is harmless: it clears a leftover cookie and deletes no session record. `GET /api/auth/me` returns the operator context and permissions the UI needs.
5. **First-run bootstrap** creates an administrator record if no active administrator exists, even when other users exist. It never generates, shows, logs or writes a password: the record stores a placeholder hash that can never verify, and `ADMIN_PASSWORD` is ignored. An existing record is never modified (if the default email is taken, `local-operator@flowmerce.local` is used).
6. **Unchanged:** the CSRF header requirement (`X-Requested-With: blog-ops`) for ordinary mutating requests, all server-side permission checks, the audit log, and the live-publishing safeguards (the `PUBLISH` confirmation phrase, `ALLOW_LIVE_PUBLISH`, the stale-content check). The SQLite schema and all existing data are untouched.

## Rationale
The owner uses Flowmerce alone, on their own computer. Sign-in adds friction and a password to lose without protecting anything that being on the same machine does not already control. Refusing every non-local connection keeps the useful protection (nothing on the network can reach the dashboard) while removing the credential.

## Alternatives considered
- Keep sign-in (status quo): safe for a shared or hosted deployment, but unnecessary friction for one local user.
- Remove authentication and keep the server reachable on the network: rejected, it would let anyone on the same network publish and read business data.
- Bind only to 127.0.0.1 and add no application check: simpler, but one `--host 0.0.0.0` (or a local proxy or tunnel) would silently open everything.
- A single shared secret or token in the browser: still a credential to manage; not requested.

## Advantages
- No password to forget or leak; the dashboard opens directly.
- Fail-closed boundary applied before any content, so a misconfigured bind address exposes nothing.
- Audit attribution, record ownership, assignments and permission checks keep working unchanged.
- No schema change, no data migration, nothing deleted.

## Disadvantages and security boundary
- **The whole protection is "being on this computer".** Any program running on it, and any other account logged in to it, acts as the administrator.
- **Local reverse proxies and tunnels defeat the boundary.** A proxy or tunnel on this computer connects from loopback; unless it sends a forwarded address that uvicorn applies, remote traffic would look local. Do not run Flowmerce behind one.
- **DNS rebinding is not covered.** A malicious web page could try to make a browser on this computer send requests to Flowmerce with the required custom header. A check of the `Host` header would close this; it was not part of this phase (see the roadmap).
- **Not suitable for the planned multi-user cloud deployment** (about 50 users). That needs real authentication; this decision must be revisited before hosting.
- Roles and passwords no longer restrict access; the Users page says so and is read-only.
- Remote clients are refused by the application, not by the network: the server should still be started on 127.0.0.1 (the default).

## Consequences and dependencies
- `src/flowmerce/modules/seo/auth.py` gains `is_loopback_client` and `local_operator`; `app.py` enforces the boundary and runs the new bootstrap; `api.py` changes the four auth endpoints; the UI no longer has a sign-in page (`pages/Login.tsx` is left unused), account menu, password dialog or sign-out; the Users page is read-only.
- Old data is kept: an existing `data/initial-admin.txt`, password hashes, session rows and user records are not deleted or used. The old file is ignored by Git and can be removed by the owner.
- **`scripts/ci_smoke.py` and the CI `Smoke test` job depend on the old sign-in** (they read `initial-admin.txt` and log in) and will fail until updated. That file was outside this phase's approved scope; see the roadmap.
- Other documents that mention signing in or the first-run password (`docs/operations/troubleshooting.md`, `docs/operations/ci-cd.md`, `.env.example`) are now out of date and need a follow-up edit.
- Moving to a hosted deployment later needs a new decision (real authentication, a trusted-proxy policy and a `Host` check).

## Update: phase 2 (2026-10-29)
- The frontend is now a Next.js server bound to `127.0.0.1:3000` (ADR 0006); FastAPI serves no frontend files and the API listens on `127.0.0.1:8787` by default. The Next.js proxy reaches the API from loopback, so the API's boundary and the CSRF header work unchanged. The loopback check still runs inside the API for every path except the webhook, so exposing the API by changing `HOST` exposes nothing but the secret-protected webhook.
- `scripts/ci_smoke.py` and the CI `Smoke test` job were rewritten for local operator mode (no sign-in). `docs/operations/ci-cd.md` and `troubleshooting.md` were updated. `.env.example` may still mention `ADMIN_PASSWORD`, which is ignored.
- Users and passwords: the Users page is not mounted; user records stay in the database for audit and assignments.

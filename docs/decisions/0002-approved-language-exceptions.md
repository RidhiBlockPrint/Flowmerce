# ADR 0002: Approved language exceptions

- Status: approved (owner answers, 2026-10-29)
- Date: 2026-10-29

## Decision
1. **TypeScript/JavaScript (React) is approved for the web UI only.** This covers the existing `blog-ops/web` app. It does not cover backend, integration or business logic.
2. **Plain `.sql` files are approved for database schema only**, kept under `db/` (currently `db/schema.sql`). Business logic stays in Python.

## Rationale
The existing UI is working code written in TypeScript/React; the planned PostgreSQL schema is a 67 KB SQL file. The owner chose to approve both rather than rewrite them.

## Alternatives considered
Freeze the UI as legacy; plan a Python (Jinja2) UI; translate the schema to SQLAlchemy/Alembic; keep SQL as a planning document only.

## Advantages
No rewrite cost; keeps working software.

## Disadvantages
A second toolchain (Node, npm, Vite) for UI work; schema changes happen in SQL rather than Python.

## Consequences and dependencies
- Open: the planning docs name **Next.js** for the new dashboard. The approval covers "TS/JS for the UI" but the choice of framework (Next.js vs the existing Vite/React app) is not yet decided. Ask before starting new UI code.
- Where the UI folder will live after migration is proposed in ADR 0003.
- Any further language (Go, PHP, shell/batch scripts beyond the existing `run.bat`, etc.) still needs approval.

## Update (2026-10-29)
The owner decided the web UI is **Next.js + React in JavaScript/JSX only, with no TypeScript**, replacing Vite and TypeScript: see [ADR 0006](0006-nextjs-javascript-frontend.md). This closes the open framework question above.

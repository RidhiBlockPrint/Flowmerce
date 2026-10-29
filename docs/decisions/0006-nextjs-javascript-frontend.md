# ADR 0006: Next.js + React in JavaScript/JSX for the frontend (no TypeScript, no Vite)

- Status: approved (owner instruction, 2026-10-29); implemented
- Date: 2026-10-29

## Decision
1. **Backend: Python (FastAPI) with the existing SQLite database.** Unchanged.
2. **Frontend: Next.js (App Router) + React, written in JavaScript/JSX only.** `frontend/` contains no `.ts`/`.tsx` files, no TypeScript configuration, no `typescript` or `@types/*` packages, no type annotations and no `as` assertions. Vite, `@vitejs/plugin-react` and React Router are removed. Dependencies: `next` (15.x), `react`, `react-dom` (19.x). Python type hints remain allowed because they are Python.
3. **Two local services.** The Python API runs on `127.0.0.1:8787` and the Next.js server on `127.0.0.1:3000`. The frontend calls `/api/...` and a Next.js rewrite (`frontend/next.config.mjs`) forwards it to the API. FastAPI no longer serves the built UI.
4. **No credentials in the frontend.** Shopify, Google, Claude and database access stay in Python. The browser only talks to `/api/...`.
5. **One launcher.** `scripts/run_flowmerce.py` starts both services, opens the browser and stops both on Ctrl+C; `scripts/run_seo.py` forwards to it.
6. **Only working features are visible.** Navigation and Home list Home and the implemented SEO & Blog pages. Unbuilt projects, shared "planned" pages, future-scope entries and the demonstration-data mode were removed from the UI; their old addresses show a normal not-found page. Source for `Login`, `Planned` and `Users` pages is kept, unmounted. No database rows were touched.
7. **Routing.** Real App Router folders (`frontend/src/app/...`, with dynamic `blogs/[id]` and `workspace/[brand]`); no catch-all route and no second router. Page implementations live in `frontend/src/views/`.

## Rationale
The owner chose Next.js and JavaScript over Vite and TypeScript. This also resolves the framework question left open in ADR 0002 and ADR 0003 (roadmap B5).

## Alternatives considered
- Keep Vite + TypeScript (status quo): rejected by the owner.
- Next.js with TypeScript, or a Next.js catch-all wrapper around the old React Router app: rejected (TypeScript is not allowed; two routers would compete).
- Serve a static Next.js export from FastAPI: rejected; the owner wants Next.js to render the pages and FastAPI to stay an API.

## Advantages
- Real file-based routing, one framework, no TypeScript toolchain; the Python backend and database are untouched.
- Loopback binding of both services plus the API's own check keeps the local-only model (ADR 0005).

## Disadvantages and risks
- Node.js and npm are required on the owner's computer, in addition to Python.
- Without TypeScript there is no compile-time type check; the pages were converted mechanically from typed source and verified by the Next.js build, a route smoke test and a manual browser check, not by a frontend unit-test suite (none exists).
- The proxy target is fixed at build time (`FLOWMERCE_API_ORIGIN`, default `http://127.0.0.1:8787`), so the ports are fixed.
- Next.js 15 is a pinned major version; Next.js 16 exists and was not adopted.

## Consequences
- `PROJECT_RULES.md` section 1 was updated. `tests/unit/test_frontend_javascript_only.py` fails if TypeScript or Vite files or dependencies return, or if unfinished pages are mounted.
- CI runs `npm ci` and `npm run build` (no type-check step) and a smoke test that starts the built frontend.

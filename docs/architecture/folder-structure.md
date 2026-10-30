# Folder structure

Current tree (new foundation; legacy folders shown for completeness):

```text
Flowmerce/
├── README.md  CHANGELOG.md  pyproject.toml  .gitignore  .env.example
├── .vscode/                  editor launch/test config (from blog-ops)
├── src/flowmerce/
│   ├── __init__.py  __main__.py  main.py     version + CLI entry point
│   ├── config/               settings loading and validation
│   ├── core/                 cross-cutting foundations (logging)
│   └── modules/
│       ├── shipping/         Shipping module: repo, schema, aging, normalize, carriers, shopify, sync, service, importer, api
│       └── seo/              SEO & Blog module (migrated from blog-ops)
│           ├── api.py app.py main.py cli.py config.py db.py auth.py permissions.py audit.py util.py
│           ├── services/     business logic (articles, publishing, workflow, sync, analytics, excel, ...)
│           └── integrations/ Shopify, Google (GSC+GA4), Claude clients and integration status
├── frontend/                 Next.js + React UI, JavaScript/JSX only (ADR 0006). Listens on 127.0.0.1:3000
│   ├── package.json  package-lock.json  next.config.mjs  jsconfig.json
│   ├── public/               static files (favicon)
│   └── src/
│       ├── app/              App Router: layout.jsx, page.jsx (Home), not-found.jsx, one folder per route, globals.css
│       ├── views/            page implementations (Home, Overview, Blogs, ArticleEditor, ...; Login/Planned/Users are not mounted)
│       ├── components/       Providers, Shell, ui, overlays, charts, home, metrics, publish, Icon
│       └── lib/              api (calls /api/...), app (context), nav (Next.js routing helpers), routes (navigation), home, format, ...
├── tests/
│   ├── unit/  (+ seo/)       isolated logic tests
│   ├── integration/ (+ seo/) process / HTTP interaction tests
│   └── fixtures/seo.py       shared fixtures for the seo suites
├── scripts/                  run_flowmerce.py (one-command launcher), run_seo.py / run_seo.bat (compatible entry points), ci_smoke.py
├── docs/
│   ├── architecture/  development/  operations/  decisions/
│   ├── FILE_REGISTRY.md
│   └── 01-architecture.md 02-connectors-and-apis.md 03-data-model.md   (planning v0.1, pre-existing)
├── logs/                     runtime logs (contents git-ignored)
├── data/                     runtime data, git-ignored (not yet created on this machine)
├── db/schema.sql             planning-stage PostgreSQL schema (pre-existing, SQL approved for schema only)
├── architecture-map.html     interactive map (pre-existing)
├── data/, backups/           SQLite database and backups (git-ignored, live data)
└── .env                      local secrets (git-ignored)
```

## Where new code goes

| You are adding | Put it in |
|---|---|
| A business feature (ads, seo, ship, ...) | `src/flowmerce/modules/<module>/` with tests in `tests/unit/<module>/` |
| A connection to Shopify, Meta, etc. | `src/flowmerce/integrations/<platform>/` for new platforms (create when needed); SEO-specific clients currently live in `modules/seo/integrations/` |
| UI code | `frontend/` (JavaScript/JSX only, no TypeScript; ADR 0006). A new page: implementation in `src/views/`, a route folder with `page.jsx` in `src/app/`, its entry in `src/lib/routes.js` (only when it works), reusable parts in `src/components/` |
| Settings or new environment variables | `src/flowmerce/config/`, plus `.env.example` and setup docs |
| Logging, error types, base services | `src/flowmerce/core/` |
| Code used by 2+ modules | `src/flowmerce/shared/` (create when the second user appears) |
| Small generic helpers | `src/flowmerce/utilities/` (create when needed) |
| A repeatable Python maintenance script | `scripts/` (register in FILE_REGISTRY) |
| Database schema SQL | `db/` only (see ADR 0002) |

Folders `shared/`, `integrations/` and `utilities/` are intentionally not created yet, to avoid empty placeholders.

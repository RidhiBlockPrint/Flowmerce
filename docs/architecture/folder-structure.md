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
│       └── seo/              SEO & Blog module (migrated from blog-ops)
│           ├── api.py app.py main.py cli.py config.py db.py auth.py permissions.py audit.py util.py
│           ├── services/     business logic (articles, publishing, workflow, sync, analytics, excel, ...)
│           └── integrations/ Shopify, Google (GSC+GA4), Claude clients and integration status
├── frontend/                 React/TypeScript UI (approved exception, ADR 0002)
│   ├── package.json  package-lock.json  vite.config.ts  .npmrc
│   └── web/                  src/, public/, index.html, tsconfig.json, dist/ (built copy served by the backend)
├── tests/
│   ├── unit/  (+ seo/)       isolated logic tests
│   ├── integration/ (+ seo/) process / HTTP interaction tests
│   └── fixtures/seo.py       shared fixtures for the seo suites
├── scripts/                  run_seo.py (launcher), run_seo.bat (Windows double-click wrapper)
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
| UI code | `frontend/` (TypeScript/React only, see ADR 0002) |
| Settings or new environment variables | `src/flowmerce/config/`, plus `.env.example` and setup docs |
| Logging, error types, base services | `src/flowmerce/core/` |
| Code used by 2+ modules | `src/flowmerce/shared/` (create when the second user appears) |
| Small generic helpers | `src/flowmerce/utilities/` (create when needed) |
| A repeatable Python maintenance script | `scripts/` (register in FILE_REGISTRY) |
| Database schema SQL | `db/` only (see ADR 0002) |

Folders `shared/`, `integrations/` and `utilities/` are intentionally not created yet, to avoid empty placeholders.

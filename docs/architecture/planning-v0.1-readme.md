# Flowmerce

A unified e-commerce platform to track, manage and act on what happens in the business.

Six modules on one shared foundation:

1. Meta & Google Ads
2. SEO & Blog Automation
3. Shipping Tracking & Alerts
4. Creative Strategist
5. Landing Page Builder
6. CRO (Conversion Rate Optimization)

## What is in this folder

| Path | What it is |
|---|---|
| `docs/01-architecture.md` | Platform architecture: principles, backend structure, sync, module interlinking, event catalogue, approval engine, module blueprints, security, build phases, open decisions |
| `docs/02-connectors-and-apis.md` | Every external API: what it is used for, auth, endpoints, sync mode, write actions, limits |
| `docs/03-data-model.md` | Master data model: schemas, ER diagrams, identity rules, metric definitions, retention |
| `db/schema.sql` | PostgreSQL 16 schema: 11 schemas, master data, module tables, shared ops engine, cross-module views, seed data |
| `architecture-map.html` | Interactive map of modules, connectors and data flows. Open it in a browser |

## Status

Planning draft v0.1 (2026-10-28). Nothing is built yet. SEO & Blog and Shipping exist as prototypes outside this platform and move onto it in phase 1.

Stack: Python 3.12 + FastAPI, PostgreSQL 16, Celery + Redis, Next.js dashboard, Claude API, S3-compatible storage.

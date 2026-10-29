> Verbatim copy of the original `blog-ops/README.md` (pre-migration). Paths and commands in it (`run.py`, `backend/`, `web/`) refer to the old layout; see docs/development/setup.md for current ones.

# Blog Ops — Ridhi Block Print & Cotton Print Club

One dashboard to run the blogging pipeline and SEO reporting for both Shopify stores:
topic research → keyword validation → topic approval → content generation → content approval →
image selection → Shopify draft → publication approval → performance tracking.

**Backend: Python (FastAPI + SQLite).** The React UI ships pre-built in `web/dist` and is served by the
Python server, so you only need Python to run it.

| | Ridhi Block Print | Cotton Print Club |
|---|---|---|
| Storefront | https://ridhiblockprint.com | https://cottonprintclub.com |
| Shopify shop | `guz0he-21.myshopify.com` | `liquidationfashion.myshopify.com` |
| Blog | `/blogs/news` | `/blogs/blogs` |
| Search Console property (default) | `sc-domain:ridhiblockprint.com` | `sc-domain:cottonprintclub.com` |

## Run it

**Double-click `run.bat`**, or in a terminal:

```bash
python run.py
```

The first run creates `.venv` and installs `requirements.txt` (needs Python 3.10+ and internet), then
opens http://localhost:8787. Later runs start in seconds.

**In VS Code:** open the `blog-ops` folder, install the recommended Python extension when prompted, then
Run and Debug (Ctrl+Shift+D) → **"Blog Ops: run dashboard"** → F5. Breakpoints in `backend/` work.
"Blog Ops: run with auto-reload" restarts the server whenever you save a backend file.
"Blog Ops: tests" runs the test suite.

First sign-in: the admin password is in `data/initial-admin.txt` (unless `ADMIN_EMAIL` / `ADMIN_PASSWORD`
are set in `.env`). Add named users under **Users & roles**, then delete that file. You can also create
users from a terminal:

```bash
.venv\Scripts\python -m backend.cli --email name@company.com --name "Name" --role reviewer
```

## Connecting your real business data

Copy `.env.example` to `.env` and fill in what you have. Restart after editing. Every value stays on the
server; nothing secret reaches the browser, Excel files or browser storage.

1. **Shopify Admin API** (per brand) — Shopify admin → Settings → Apps and sales channels → Develop apps →
   create an app with Admin API scopes `read_content`, `write_content`, `read_products`; install it and put
   the `shpat_…` token in `RIDHI_SHOPIFY_ADMIN_TOKEN` / `CPC_SHOPIFY_ADMIN_TOKEN`. Enables drafts, SEO
   fields, hidden Shopify drafts and authorized publishing. Without it, live articles and products are read
   from each storefront's public feed.
2. **Google Search Console + GA4** — create a Google Cloud service account, download its JSON key into
   `secrets/` (git-ignored), set `GOOGLE_SERVICE_ACCOUNT_FILE=secrets/your-key.json`. Add the
   service-account email as a user on each Search Console property and as Viewer on each GA4 property; set
   `RIDHI_GA4_PROPERTY_ID` / `CPC_GA4_PROPERTY_ID`. Enable "Google Search Console API" and "Google Analytics
   Data API" in that Cloud project.
3. **Claude** — set `ANTHROPIC_API_KEY` for topic research and first drafts (`claude-opus-5-5`).
4. **External agents** (optional) — set `WORKFLOW_WEBHOOK_SECRET`; agents running elsewhere report status
   with `POST /api/hooks/workflow`, header `X-Workflow-Secret`.

Then open **Integrations → Test connection** for each one. The page shows last success, last attempt and
the error message.

### Adding another data source

The code is laid out so a new source is one module plus two small registrations:

1. `backend/integrations/<name>.py` — the API client. Read credentials with `env("MY_KEY")` from
   `backend/config.py`.
2. `backend/services/sync.py` — a `sync_<name>(brand_id)` function that calls the client, writes rows to a
   table (add one as a new entry in `MIGRATIONS` in `backend/db.py` — never edit an old entry) and wraps the
   work in `mark_attempt` / `mark_success` / `mark_error` so the dashboard shows its health.
3. Call it from `_performance_tracking` in `backend/services/workflow.py` (so the scheduler refreshes it
   every 6 hours) and, if you want a card, add it to `_integration_list` in `backend/api.py`.

The interactive API reference is at http://localhost:8787/api/docs while the server runs.

## Publishing safety

An article becomes visible only when **all** of these hold, checked on the server:

1. a reviewer approved the exact current text (any edit voids the approval and cancels open requests);
2. an SEO Manager or Admin made a publish request (now / schedule / update live);
3. a *different* Reviewer or Admin authorizes it (admins may authorize their own);
4. the authorizer types `PUBLISH` in the confirmation dialog;
5. the server has `ALLOW_LIVE_PUBLISH=true` — **off by default**. Leave it off on test copies.

Hidden Shopify drafts never touch a live article. Failed publishes keep the Shopify error and can be
retried safely. The background refresh only reads data — it never generates, drafts or publishes.

## Roles

| | Admin | SEO Manager | Reviewer |
|---|---|---|---|
| Topics, keywords, writing, imports | ✓ | ✓ | – |
| Approve content | ✓ | – | ✓ |
| Hidden Shopify drafts, publish requests | ✓ | ✓ | – |
| Authorize / reject publishing | ✓ | – | ✓ |
| Integrations, brand settings, users, demo data | ✓ | – | – |

## Data sources and labels

Every metric shows where it came from — **Live API**, **Public feed**, **Excel import**, **Demo** or **No
data** — with sync time and period. Search Console and GA4 are kept separate. Data that cannot be fetched
live goes through Excel workbooks (Data & reports): topics, keyword research, blog records, offline review
notes (notes only — they never approve anything) and Search Console / GA4 exports. Imports validate every
row, detect duplicates, and need a second click to commit.

## Changing the UI (optional, needs Node.js)

```bash
npm install
```

```bash
npm run dev
```

Vite serves the UI on http://localhost:5173 and forwards `/api` to the Python server on 8787 (start that
with `python run.py --no-browser`). When done, `npm run build` refreshes `web/dist`. On this office network
npm's default registry is blocked, so `.npmrc` points at registry.yarnpkg.com.

## Deploying

Run `python run.py --no-browser --host 0.0.0.0` (or `uvicorn backend.main:app`) behind HTTPS with
`APP_ENV=production` so cookies are `Secure`. Keep `data/` on a persistent disk and back it up (users,
content, revisions, audit log). Put secrets in the host's secret store. Set `ALLOW_LIVE_PUBLISH=true` only
on the production instance, once the team is ready.

## Layout

```
run.py / run.bat     one-click launcher (creates .venv, installs packages, starts the server)
backend/
  config.py          all settings, read from .env
  db.py              SQLite schema and migrations
  api.py             every HTTP endpoint, each guarded by a permission check
  integrations/      shopify, shopify_public, google (GSC + GA4), claude, status
  services/          articles, publishing, workflow, sync, analytics, excel, demo, scheduler
web/                 React UI source; web/dist is the built copy the server serves
tests/               pytest suites (no network)
```

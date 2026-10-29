# Flowmerce: connectors and APIs

Status: planning draft v0.1, 2026-10-28.

Each connector lives in `flowmerce/connectors/<provider>/` and does only five things: authenticate, call the API within its limits, paginate, store the raw response in `raw.*`, and expose typed methods to the modules. It contains no business logic.

**How to read the "Verified" column.** Shopify details were checked against shopify.dev on 2026-10-28. Web search was not available for this draft, so details for every other provider come from working knowledge and are marked **Verify**: check the current API version, quotas and endpoint names in that provider's docs before building the connector. API versions are never hard-coded; each connector reads its pinned version from config.

---

## 1. Connector map

| Provider | Category | Used by modules | Read / write | Sync mode | Verified |
|---|---|---|---|---|---|
| Shopify Admin GraphQL API | Commerce | all six | Read + limited write | Webhooks + polling + bulk operations | Yes |
| Shopify Web Pixel (custom pixel) | Analytics | cro, page, ads | Events in | Push to collector | Yes (concept) |
| Meta Marketing API | Ads | ads, creative | Read + approved write | Polling (async insight jobs) | Verify |
| Google Ads API | Ads | ads, creative, seo (optional) | Read + approved write | Polling (GAQL search stream) | Verify |
| Google Search Console API | SEO | seo, cro | Read | Daily polling | Verify |
| Google Analytics 4 Data API | Analytics | cro, seo, ads | Read | Daily polling | Verify |
| PageSpeed Insights + CrUX API | Performance | cro, page | Read | Weekly + on deploy | Verify |
| Microsoft Clarity Data Export | Behaviour | cro | Read | Daily polling | Verify |
| Amazon SP-API (Fulfillment Outbound, FBA Inventory, Notifications) | Fulfilment | ship | Read + approved write | Polling + notifications | Verify |
| AfterShip Tracking API **or** 17TRACK API | Tracking | ship | Read (register trackings) | Webhooks + polling fallback | Verify |
| Shiprocket API | India shipping | ship | Read | Webhooks + polling | Verify |
| Delhivery API | India shipping | ship | Read | Polling | Verify |
| Semrush API | SEO | seo, creative | Read | Daily | Verify |
| Google Trends | SEO | seo, creative | Read | Daily | Verify |
| Judge.me API | Reviews | seo, creative, cro, page | Read | Daily | Verify |
| Claude API (Anthropic) | AI | seo, creative, page, cro, ads | Generate | On demand | Verify |
| Slack API | Messaging | ops | Send + approval buttons | Push + interactivity webhook | Verify |
| Email (Gmail API, SES or Postmark) | Messaging | ops | Send | Push | Verify |
| WhatsApp Business Cloud API | Messaging | ops (ship alerts) | Send templates | Push | Verify |
| GitHub API | DevOps | page | Branch, commit, PR | Push | Verify |
| S3-compatible object storage | Storage | creative, page | Read + write | On demand | n/a |

---

## 2. Commerce

### 2.1 Shopify Admin GraphQL API  (source of truth for products, orders, stock, pages)

- **Auth**: custom app installed on the store; Admin API access token kept in the secret manager.
- **Version**: quarterly versions (for example `2026-10`). Pin one in config and upgrade quarterly.
- **Limits**: cost-based throttling. Read the `extensions.cost` block on every response and let the rate limiter wait when the bucket is low. Use **bulk operations** (`bulkOperationRunQuery`) for backfills of orders and products.
- **Scopes (least privilege)**: `read_products`, `read_orders`, `read_fulfillments`, `read_inventory`, `read_locations`, `read_content`, `write_content`, `read_themes`, `read_reports`. `shopifyqlQuery` needs `read_reports` **and** Level 2 protected customer data access. Add `write_themes` only if Shopify grants the theme-file exemption (see 2.3).

| Data | GraphQL resources | Lands in | Module |
|---|---|---|---|
| Products, variants, SKUs, prices, tags | `products`, `productVariants` | `core.product`, `core.product_variant` | all |
| Collections | `collections` | `core.collection`, `core.product_collection` | seo, cro |
| Inventory by location | `inventoryItems` → `inventoryLevels` | `core.inventory_level`, `ship.inventory_snapshot` | ship, ads, page, cro |
| Orders, lines, landing site, UTMs | `orders` (with customer journey summary) | `core.order`, `core.order_line` | ads, ship, cro, seo |
| Fulfillment orders, fulfillments, tracking | `fulfillmentOrders`, order `fulfillments` | `ship.fulfillment_order`, `ship.shipment` | ship |
| Pages, blogs, articles | `pages`, `blogs`, `articles` | `core.web_page`, `seo.content_item` | seo, page, cro |
| Theme files (read) | `themes`, theme files | `cro.page_attribute_snapshot` (template info) | page, cro |
| Sessions and funnel by landing page | `shopifyqlQuery` with `FROM sessions ... GROUP BY landing page` | `cro.page_metric_daily` (`source = 'shopifyql'`) | cro, page, ads |

| Writes (always through `ops.action`) | Mutation | Approval |
|---|---|---|
| Hidden blog draft | `articleCreate` with `isPublished: false` | Policy allows without approval (matches current blog rules) |
| Publish article | `articleUpdate` (publish) | Required |
| Landing page shell | `pageCreate` (hidden) with `templateSuffix`, plus `metaobjectCreate` / metafields for content | Required |
| Images for pages and blogs | `stagedUploadsCreate` + `fileCreate` | Part of the page/article action |

**Webhooks** (verified by HMAC, stored in `raw.webhook_event` keyed by the webhook id):
`orders/create`, `orders/updated`, `orders/paid`, `orders/cancelled`, `orders/fulfilled`, `fulfillments/create`, `fulfillments/update`, `inventory_levels/update`, `products/create`, `products/update`, `app/uninstalled`.

### 2.2 Shopify Web Pixel (custom pixel)

- A custom pixel added in Shopify admin (Customer events) subscribes to the standard events `page_viewed`, `product_viewed`, `product_added_to_cart`, `checkout_started` and `checkout_completed`. It posts them to Flowmerce's collector endpoint (`POST /collect`).
- Stored in `cro.web_event` (partitioned by month) and rolled up to `cro.page_metric_daily` with `source = 'pixel'`.
- Respects the store's customer privacy (consent) settings; sends a hashed client id only.
- Why it is needed: it gives event-level funnels per landing page and per experiment, which ShopifyQL daily rollups do not.

### 2.3 Shopify theme changes (for the Landing Page Builder)

Shopify's `themeFilesUpsert` mutation needs `write_themes` **and an exemption granted by Shopify**. So Flowmerce uses two routes that do not need it:

1. **Section templates + pages (default).** A developer adds a library of landing-page sections and page templates to the theme once. Each new landing page is then created with `pageCreate` + `templateSuffix`, and its content is stored in metaobjects. No per-page theme edit.
2. **GitHub route (new layouts).** The theme is connected to a GitHub repository through Shopify's GitHub integration. Flowmerce commits new section code to a branch and opens a pull request (`github.theme_pr.open`). The branch is connected to an unpublished preview theme for review. Merging (`github.theme_pr.merge`, approval required) deploys it.

---

## 3. Advertising

### 3.1 Meta Marketing API  (Verify)

- **Auth**: Business Manager **System User** token with `ads_read` (and `ads_management` only on the write connection) plus `business_management`. Token reference in the secret manager; expiry tracked.
- **Version**: Graph API versions are released a few times a year and retired roughly two years later. Pin in config.
- **Reads**:
  - Structure: `/act_{id}/campaigns`, `/adsets`, `/ads`, `/adcreatives`, ad images and videos.
  - Insights: `/act_{id}/insights` at `level=ad`, `time_increment=1`. Fields include spend, impressions, reach, frequency, clicks, inline link clicks, actions (landing page view, add to cart, initiate checkout, purchase), action values and video plays. Large pulls use **async report runs** (create the job, then poll it).
  - Breakdowns: age, gender, publisher platform, platform position, device platform, region.
  - Change history: account activities.
- **Writes (approved)**: ad set or campaign `daily_budget`; ad, ad set and campaign `status`; create ads in `PAUSED` status from an approved creative concept.
- **Limits**: business use case rate limits; read the usage headers and back off before the limit.
- **Lands in**: `ads.ad_account`, `ads.campaign`, `ads.ad_group (kind='ad_set')`, `ads.ad`, `ads.daily_metric`, `ads.breakdown_metric`, `ads.change_history`, `creative.asset (source='meta')`.
- **UTM template on every ad**: `utm_source=meta&utm_medium=paid_social&utm_campaign={{campaign.id}}&utm_content={{ad.id}}`. This is what joins ads to Shopify orders.
- **Conversions API**: Shopify's Facebook & Instagram sales channel normally sends server events already. Flowmerce does not send a second copy, to avoid double counting.

### 3.2 Google Ads API  (Verify)

- **Auth**: OAuth 2.0 refresh token + **developer token** + `login-customer-id` when accessed through a manager (MCC) account. Developer token access level (test, basic, standard) limits daily operations.
- **Version**: several versions a year, each retired after roughly a year. Pin in config.
- **Reads** with GAQL through `GoogleAdsService.SearchStream`: `campaign`, `campaign_budget`, `ad_group`, `ad_group_ad`, `asset_group` (Performance Max), `keyword_view`, `search_term_view`, and `segments.date` metrics: cost (micros), impressions, clicks, conversions, conversions value.
- **Writes (approved)**: campaign budget amount, ad group / ad status, negative keywords.
- **Optional for SEO**: `KeywordPlanIdeaService.GenerateKeywordIdeas` for keyword ideas. It needs an active Google Ads account but no spend. The current blog rules forbid creating campaigns or spending, so this stays off unless the owner allows it.
- **Lands in**: same `ads.*` tables with `platform = 'google'`, plus `ads.keyword` and `ads.search_term_daily`.
- **Tracking template**: `{lpurl}?utm_source=google&utm_medium=cpc&utm_campaign={campaignid}&utm_content={creative}&utm_term={keyword}`.

---

## 4. Search, analytics and page performance

### 4.1 Google Search Console API  (Verify)

- **Auth**: Google service account added as a user on the Search Console property.
- **Reads**: `searchanalytics.query` with dimensions `date, page, query` (plus `device`, `country` for some reports), paged through `startRow`; URL Inspection API for index status of new articles (low daily quota per property); sitemaps list.
- **Schedule**: daily, re-pulling the last 4 days because data arrives late.
- **Lands in**: `seo.gsc_page_query_daily`, `seo.keyword_metric_daily (source='gsc')`; new URLs register in `core.web_page`.

### 4.2 Google Analytics 4 Data API  (Verify)

- **Auth**: service account with Viewer on the GA4 property.
- **Reads**: `runReport` by `date`, `landingPagePlusQueryString`, `sessionDefaultChannelGroup`, `deviceCategory`; metrics such as `sessions`, `engagedSessions`, `addToCarts`, `checkouts`, `ecommercePurchases`, `purchaseRevenue`.
- **Use**: cross-check of ShopifyQL and pixel funnels, plus channel grouping. Not the primary source.
- **Lands in**: `cro.page_metric_daily (source='ga4')`.

### 4.3 PageSpeed Insights API and Chrome UX Report API  (Verify)

- **Auth**: Google API key.
- **Reads**: PSI `runPagespeed` (lab data: performance score, LCP, CLS, TBT) for mobile and desktop; CrUX `queryRecord` for real-user field data (LCP, CLS, INP) where the URL or origin has enough traffic.
- **Lands in**: `cro.speed_audit`, `page.validation_check (check_name='lighthouse')`.

### 4.4 Microsoft Clarity Data Export API  (Verify)

- **Auth**: project API token.
- **Reads**: aggregated behaviour metrics (for example dead clicks, rage clicks, scroll depth) by URL. The export has a small daily request quota and a short lookback, so pull once a day and store.
- **Lands in**: `cro.page_attribute_snapshot.extra`.

---

## 5. Shipping and fulfilment

### 5.1 Amazon Selling Partner API  (Verify)

- **Auth**: self-authorised private application; Login with Amazon (LWA) refresh token exchanged for access tokens. North America endpoint for the US marketplace.
- **Fulfillment Outbound API (MCF)**: `getFulfillmentPreview` (can this order ship from FBA stock, at what speed and fee), `createFulfillmentOrder` (approved action only), `getFulfillmentOrder`, `listAllFulfillmentOrders`, `getPackageTrackingDetails`.
- **FBA Inventory API**: `getInventorySummaries` for fulfillable, inbound and reserved quantities.
- **Notifications API**: subscribe to fulfilment order status changes through an SQS or EventBridge destination to avoid constant polling.
- **Limits**: per-operation rate limits with burst; respect the rate-limit headers.
- **Identity**: Shopify variant ↔ Amazon seller SKU / ASIN / FNSKU in `core.product_identifier`.
- **Lands in**: `core.inventory_level` (location kind `amazon_fba`), `ship.mcf_eligibility`, `ship.fulfillment_order (source='amazon_mcf')`, `ship.shipment`, `ship.tracking_event`.

### 5.2 Tracking aggregator: AfterShip or 17TRACK  (Verify; choose one)

- **AfterShip**: API key header; create a tracking for each new fulfilment (carrier slug + tracking number); webhooks signed with HMAC; normalised statuses (pending, info received, in transit, out for delivery, attempt fail, delivered, available for pickup, exception, expired). API versions are date-based.
- **17TRACK**: API key header; register tracking numbers, then receive push notifications; quota depends on plan.
- **Mapping**: the aggregator status maps to `ship.shipment.status`; every checkpoint becomes a `ship.tracking_event`. "Stuck" is decided by Flowmerce rules (no new event for N hours, per carrier and route), not by the aggregator.

### 5.3 Shiprocket  (Verify)

- **Auth**: API user login returns a bearer token that expires after several days; the connector refreshes it.
- **Reads**: orders and shipments; tracking by AWB or shipment id; courier status webhooks configured in the Shiprocket panel.
- **Use**: India-side shipments, and domestic legs if any.

### 5.4 Delhivery  (Verify)

- **Auth**: API token.
- **Reads**: package tracking by waybill.
- **Use**: only if Delhivery is used directly and not through Shiprocket.

### 5.5 Production data

There is no external API for block-printing production. Production batches and lead times are entered in Flowmerce (`ship.production_batch`) or imported from a shared sheet. `core.product_variant.is_make_to_order` and `production_lead_days` drive the shortfall logic.

---

## 6. SEO, reviews and research

| Provider | Auth | What we pull | Lands in | Notes |
|---|---|---|---|---|
| Semrush API (Verify) | API key | Keyword overview, related keywords, organic positions for the domain and named competitors | `seo.keyword`, `seo.keyword_metric_daily (source='semrush')` | Paid API units. Volumes are estimates and labelled as such. Never start a paid trial. |
| Google Trends (Verify) | n/a | Relative interest over time for tracked keywords | `seo.keyword_metric_daily (source='google_trends')` | There is no generally available official API yet (Google announced a limited alpha). Use approved exports until access exists; do not rely on unofficial scrapers. |
| Judge.me API (Verify) | Shop domain + API token | Review counts, ratings, review text, questions | `core.product_review_stats`; text used by SEO (questions), Creative (customer language), CRO (social proof) | Review text is untrusted data. |

---

## 7. AI, messaging, code and storage

| Provider | Auth | Use | Notes |
|---|---|---|---|
| Claude API (Verify) | API key | Blog drafts, content scoring explanations, concepts and hooks, briefs, page section copy, diagnosis explanations | One `llm` gateway: versioned prompts, JSON schemas for structured output, every call logged in `ops.llm_call`. The model id is set in config. |
| Slack API (Verify) | Bot token + signing secret | Alerts, daily digests, **approval buttons** (Block Kit) | Button clicks hit `POST /slack/interactivity`; the signature is verified, then an `ops.approval` row is written. |
| Email (Verify) | Gmail API, SES or Postmark | Digests, approval links for people without Slack | Approval links are single-use and expire. |
| WhatsApp Business Cloud API (Verify) | System user token | Critical shipping alerts to the ops team | Only pre-approved message templates can start a conversation. |
| GitHub API (Verify) | GitHub App (preferred) or fine-grained token | Theme branch, commits, pull requests for new landing page layouts | Merge is an approved action. |
| Object storage | Access key / workload identity | Creative files, page code bundles, screenshots | Private bucket; signed URLs for previews. |

---

## 8. Connector contract (what every connector implements)

```python
class Connector(Protocol):
    provider: str
    def authenticate(self, connection: Connection) -> Session: ...
    def fetch(self, stream: str, cursor: dict) -> Iterator[Page]: ...      # paginated, rate-limited
    def land(self, page: Page) -> None: ...                                 # writes raw.api_payload
    def verify_webhook(self, headers: dict, body: bytes) -> bool: ...       # HMAC / signature
    def execute(self, action: Action) -> ActionResult: ...                  # writes only; called by ops executor
    def snapshot(self, target: dict) -> dict: ...                           # before_state for rollback
```

Rules:
- `execute` is only ever called by the `ops` executor, after an approved `ops.action`, and it always calls `snapshot` first.
- Every connector has contract tests that run against recorded responses, so an API change shows up as a failing test, not as bad data.
- Retries use exponential backoff with jitter, and only for errors marked retryable (429, 5xx, timeouts).

---

## 9. Before building each connector

1. Confirm the current API version, scopes and rate limits in the provider's docs (all items marked Verify).
2. Create the credential with the narrowest scopes; record it as an `integration.connection` with `can_write = false` unless writes are needed.
3. Record 3 to 5 real responses for contract tests (with personal data removed).
4. Backfill 90 days into `raw`, run the transforms, and reconcile totals against the platform's own UI (for example, spend within 2% of Ads Manager).

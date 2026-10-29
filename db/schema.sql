-- =====================================================================
-- Flowmerce master data schema  (PostgreSQL 16)
-- One database, one schema per bounded area:
--   auth         users and roles
--   core         master data every module shares (store, product, order, page, taxonomy, brand rules)
--   integration  connections, sync jobs, webhook subscriptions
--   raw          untouched API and webhook payloads (replayable)
--   ads          Meta + Google Ads
--   seo          SEO and blog automation
--   ship         shipping tracking, inventory readiness, MCF, production
--   creative     creative strategist
--   page         landing page building automation
--   cro          conversion rate optimization
--   ops          shared engine: events, alerts, recommendations, approvals, actions, audit
--
-- Conventions
--   * uuid primary keys (gen_random_uuid), timestamptz everywhere, money as numeric(14,2)
--   * external ids are stored as text next to our own id; (provider, external_id) is unique
--   * status/kind columns use CHECK lists, so new values are a one-line migration
--   * secrets are NEVER stored here: integration.connection.secret_ref points to the secret manager
--   * customer PII is minimised: hashed email only
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
-- Optional, for content/creative similarity search. Enable when pgvector is installed:
-- CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS integration;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS ads;
CREATE SCHEMA IF NOT EXISTS seo;
CREATE SCHEMA IF NOT EXISTS ship;
CREATE SCHEMA IF NOT EXISTS creative;
CREATE SCHEMA IF NOT EXISTS page;
CREATE SCHEMA IF NOT EXISTS cro;
CREATE SCHEMA IF NOT EXISTS ops;

-- =====================================================================
-- AUTH
-- =====================================================================
CREATE TABLE auth.app_user (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext NOT NULL UNIQUE,
  full_name     text NOT NULL,
  role          text NOT NULL CHECK (role IN ('owner','admin','marketer','ops','content','viewer')),
  is_active     boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- =====================================================================
-- CORE  (master data: the shared keys that interlink every module)
-- =====================================================================
CREATE TABLE core.store (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  shopify_domain  text UNIQUE,                 -- e.g. example.myshopify.com
  primary_domain  text,                        -- e.g. www.example.com
  currency        char(3) NOT NULL DEFAULT 'USD',
  timezone        text NOT NULL DEFAULT 'America/New_York',
  ops_timezone    text NOT NULL DEFAULT 'Asia/Kolkata',
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.sales_channel (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id  uuid NOT NULL REFERENCES core.store(id),
  code      text NOT NULL CHECK (code IN ('shopify_online','amazon','meta_shop','google_shopping','wholesale','other')),
  name      text NOT NULL,
  UNIQUE (store_id, code)
);

CREATE TABLE core.product (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id        uuid NOT NULL REFERENCES core.store(id),
  shopify_gid     text UNIQUE,                 -- gid://shopify/Product/123
  handle          text NOT NULL,
  title           text NOT NULL,
  product_type    text,
  vendor          text,
  status          text NOT NULL CHECK (status IN ('active','draft','archived')),
  tags            text[] NOT NULL DEFAULT '{}',
  src_created_at  timestamptz,
  src_updated_at  timestamptz,
  synced_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (store_id, handle)
);

CREATE TABLE core.product_variant (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id          uuid NOT NULL REFERENCES core.product(id) ON DELETE CASCADE,
  shopify_gid         text UNIQUE,
  inventory_item_gid  text UNIQUE,
  sku                 text,
  title               text NOT NULL,
  price               numeric(14,2) NOT NULL,
  compare_at_price    numeric(14,2),
  barcode             text,
  weight_g            integer,
  is_make_to_order    boolean NOT NULL DEFAULT false,  -- block printed on demand
  production_lead_days integer,
  synced_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON core.product_variant (sku);

-- One variant, many outside identities: Amazon SKU/ASIN/FNSKU, Meta catalog id, Google offer id
CREATE TABLE core.product_identifier (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  variant_id   uuid NOT NULL REFERENCES core.product_variant(id) ON DELETE CASCADE,
  system       text NOT NULL CHECK (system IN ('amazon_seller_sku','asin','fnsku','meta_retailer_id','google_offer_id','barcode','other')),
  external_id  text NOT NULL,
  UNIQUE (system, external_id)
);

CREATE TABLE core.product_cost (
  variant_id   uuid NOT NULL REFERENCES core.product_variant(id) ON DELETE CASCADE,
  valid_from   date NOT NULL,
  unit_cost    numeric(14,2) NOT NULL,         -- COGS, used for break-even ROAS
  currency     char(3) NOT NULL,
  PRIMARY KEY (variant_id, valid_from)
);

CREATE TABLE core.collection (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id     uuid NOT NULL REFERENCES core.store(id),
  shopify_gid  text UNIQUE,
  handle       text NOT NULL,
  title        text NOT NULL,
  UNIQUE (store_id, handle)
);

CREATE TABLE core.product_collection (
  product_id     uuid NOT NULL REFERENCES core.product(id) ON DELETE CASCADE,
  collection_id  uuid NOT NULL REFERENCES core.collection(id) ON DELETE CASCADE,
  PRIMARY KEY (product_id, collection_id)
);

-- Anywhere stock can sit: Shopify location, Amazon FBA pool (for MCF), production unit, 3PL
CREATE TABLE core.location (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id     uuid NOT NULL REFERENCES core.store(id),
  kind         text NOT NULL CHECK (kind IN ('shopify_location','amazon_fba','production_unit','3pl','other')),
  name         text NOT NULL,
  external_id  text,
  country      char(2),
  UNIQUE (store_id, kind, external_id)
);

CREATE TABLE core.inventory_level (
  variant_id   uuid NOT NULL REFERENCES core.product_variant(id) ON DELETE CASCADE,
  location_id  uuid NOT NULL REFERENCES core.location(id) ON DELETE CASCADE,
  available    integer NOT NULL DEFAULT 0,
  reserved     integer NOT NULL DEFAULT 0,
  inbound      integer NOT NULL DEFAULT 0,
  on_hand      integer NOT NULL DEFAULT 0,
  as_of        timestamptz NOT NULL,
  PRIMARY KEY (variant_id, location_id)
);

CREATE TABLE core.customer (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id        uuid NOT NULL REFERENCES core.store(id),
  shopify_gid     text UNIQUE,
  email_sha256    text,                         -- hashed only; never the raw email
  country         char(2),
  first_order_at  timestamptz,
  orders_count    integer NOT NULL DEFAULT 0
);

-- The URL registry. Every page any module touches gets ONE row here:
-- product pages, collections, blog articles (SEO), landing pages, home, ad destinations.
CREATE TABLE core.web_page (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id        uuid NOT NULL REFERENCES core.store(id),
  url_normalized  text NOT NULL,               -- lower-case host+path, no query string, no trailing slash
  path            text NOT NULL,
  page_type       text NOT NULL CHECK (page_type IN ('home','product','collection','blog_article','landing','page','policy','search','other')),
  product_id      uuid REFERENCES core.product(id),
  collection_id   uuid REFERENCES core.collection(id),
  shopify_gid     text,                        -- Page / Article / Product gid where applicable
  template_name   text,                        -- e.g. product.default, page.lp-diwali
  title           text,
  status          text NOT NULL DEFAULT 'live' CHECK (status IN ('live','hidden','draft','redirected','removed')),
  owner_module    text NOT NULL DEFAULT 'core' CHECK (owner_module IN ('core','seo','page')),
  first_seen_at   timestamptz NOT NULL DEFAULT now(),
  last_seen_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (store_id, url_normalized)
);
CREATE INDEX ON core.web_page (page_type);
CREATE INDEX ON core.web_page (product_id);

CREATE TABLE core."order" (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id            uuid NOT NULL REFERENCES core.store(id),
  channel_id          uuid REFERENCES core.sales_channel(id),
  shopify_gid         text UNIQUE,
  order_name          text,                     -- #1234
  customer_id         uuid REFERENCES core.customer(id),
  src_created_at      timestamptz NOT NULL,
  processed_at        timestamptz,
  cancelled_at        timestamptz,
  financial_status    text,
  fulfillment_status  text,
  currency            char(3) NOT NULL,
  subtotal            numeric(14,2) NOT NULL DEFAULT 0,
  discounts           numeric(14,2) NOT NULL DEFAULT 0,
  shipping            numeric(14,2) NOT NULL DEFAULT 0,
  tax                 numeric(14,2) NOT NULL DEFAULT 0,
  total               numeric(14,2) NOT NULL DEFAULT 0,
  shipping_country    char(2),
  -- attribution keys (from Shopify customer journey / landing site)
  landing_url         text,
  landing_page_id     uuid REFERENCES core.web_page(id),
  referrer_url        text,
  utm_source          text,
  utm_medium          text,
  utm_campaign        text,
  utm_content         text,
  utm_term            text,
  synced_at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON core."order" (src_created_at);
CREATE INDEX ON core."order" (utm_campaign, utm_content);

CREATE TABLE core.order_line (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id            uuid NOT NULL REFERENCES core."order"(id) ON DELETE CASCADE,
  shopify_gid         text UNIQUE,
  variant_id          uuid REFERENCES core.product_variant(id),
  product_id          uuid REFERENCES core.product(id),
  quantity            integer NOT NULL,
  unit_price          numeric(14,2) NOT NULL,
  discount            numeric(14,2) NOT NULL DEFAULT 0,
  fulfillable_qty     integer NOT NULL DEFAULT 0
);
CREATE INDEX ON core.order_line (variant_id);

CREATE TABLE core.product_review_stats (
  product_id    uuid NOT NULL REFERENCES core.product(id) ON DELETE CASCADE,
  as_of         date NOT NULL,
  review_count  integer NOT NULL,
  avg_rating    numeric(3,2),
  source        text NOT NULL DEFAULT 'judgeme',
  PRIMARY KEY (product_id, as_of, source)
);

-- Shared taxonomy: one vocabulary for hooks, angles, formats, funnel stages, personas, themes.
-- Creative, Ads, Landing pages, SEO and CRO all tag their records with the same terms,
-- which is what lets "this hook" be compared across an ad, a page and a blog.
CREATE TABLE core.taxonomy_term (
  id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scheme  text NOT NULL CHECK (scheme IN ('hook','angle','format','funnel_stage','persona','theme','occasion','offer_type','page_section')),
  value   text NOT NULL,
  UNIQUE (scheme, value)
);

CREATE TABLE core.entity_tag (
  term_id      uuid NOT NULL REFERENCES core.taxonomy_term(id) ON DELETE CASCADE,
  entity_type  text NOT NULL CHECK (entity_type IN ('creative.asset','creative.concept','ads.ad','page.landing_page','seo.content_item','core.web_page','core.product')),
  entity_id    uuid NOT NULL,
  tagged_by    text NOT NULL DEFAULT 'system' CHECK (tagged_by IN ('system','ai','human')),
  PRIMARY KEY (term_id, entity_type, entity_id)
);
CREATE INDEX ON core.entity_tag (entity_type, entity_id);

-- Brand voice, approved and banned claims. Read by SEO, Creative and Landing pages before writing.
CREATE TABLE core.brand_rule (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id      uuid NOT NULL REFERENCES core.store(id),
  kind          text NOT NULL CHECK (kind IN ('voice','approved_claim','banned_claim','visual','legal')),
  rule_text     text NOT NULL,
  evidence_ref  text,
  is_active     boolean NOT NULL DEFAULT true,
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- =====================================================================
-- INTEGRATION  (connectors)
-- =====================================================================
CREATE TABLE integration.provider (
  code         text PRIMARY KEY,               -- 'shopify','meta_ads','google_ads','gsc','ga4','amazon_spapi','aftership','track17','shiprocket','delhivery','semrush','judgeme','clarity','psi','anthropic','slack','github','object_store'
  category     text NOT NULL CHECK (category IN ('commerce','ads','analytics','seo','shipping','reviews','ai','messaging','devops','storage')),
  display_name text NOT NULL
);

CREATE TABLE integration.connection (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id         uuid NOT NULL REFERENCES core.store(id),
  provider_code    text NOT NULL REFERENCES integration.provider(code),
  account_ref      text NOT NULL,              -- ad account id, GSC property, seller id, shop domain
  display_name     text NOT NULL,
  auth_type        text NOT NULL CHECK (auth_type IN ('oauth2','api_key','system_user_token','lwa','basic','hmac')),
  secret_ref       text NOT NULL,              -- pointer into the secret manager, never the secret
  scopes           text[] NOT NULL DEFAULT '{}',
  can_write        boolean NOT NULL DEFAULT false,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','error','revoked')),
  last_success_at  timestamptz,
  last_error       text,
  token_expires_at timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider_code, account_ref)
);

CREATE TABLE integration.sync_job (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id  uuid NOT NULL REFERENCES integration.connection(id) ON DELETE CASCADE,
  stream         text NOT NULL,                -- e.g. 'meta.insights.ad.daily', 'shopify.orders'
  mode           text NOT NULL CHECK (mode IN ('incremental','backfill','webhook','snapshot')),
  schedule_cron  text,
  lookback_days  integer NOT NULL DEFAULT 0,   -- re-pull window for late-arriving data (ads, GSC)
  cursor         jsonb NOT NULL DEFAULT '{}',
  is_enabled     boolean NOT NULL DEFAULT true,
  last_run_at    timestamptz,
  next_run_at    timestamptz,
  UNIQUE (connection_id, stream, mode)
);

CREATE TABLE integration.sync_run (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sync_job_id       uuid NOT NULL REFERENCES integration.sync_job(id) ON DELETE CASCADE,
  started_at        timestamptz NOT NULL DEFAULT now(),
  finished_at       timestamptz,
  status            text NOT NULL DEFAULT 'running' CHECK (status IN ('running','succeeded','partial','failed')),
  records_received  integer NOT NULL DEFAULT 0,
  records_upserted  integer NOT NULL DEFAULT 0,
  api_calls         integer NOT NULL DEFAULT 0,
  error             text
);
CREATE INDEX ON integration.sync_run (sync_job_id, started_at DESC);

CREATE TABLE integration.webhook_subscription (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id  uuid NOT NULL REFERENCES integration.connection(id) ON DELETE CASCADE,
  topic          text NOT NULL,                -- 'orders/create', 'fulfillments/update', 'tracking_update'
  external_id    text,
  endpoint_path  text NOT NULL,
  status         text NOT NULL DEFAULT 'active' CHECK (status IN ('active','failing','disabled')),
  UNIQUE (connection_id, topic)
);

-- =====================================================================
-- RAW  (land first, transform second: every payload can be replayed)
-- =====================================================================
CREATE TABLE raw.api_payload (
  id             bigint GENERATED ALWAYS AS IDENTITY,
  received_at    timestamptz NOT NULL DEFAULT now(),
  connection_id  uuid NOT NULL,
  stream         text NOT NULL,
  external_id    text,
  payload_hash   text NOT NULL,
  payload        jsonb NOT NULL,
  processed_at   timestamptz,
  PRIMARY KEY (id, received_at)
) PARTITION BY RANGE (received_at);
CREATE TABLE raw.api_payload_default PARTITION OF raw.api_payload DEFAULT;
CREATE INDEX ON raw.api_payload (stream, external_id);

CREATE TABLE raw.webhook_event (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  provider_code    text NOT NULL,
  topic            text NOT NULL,
  idempotency_key  text NOT NULL UNIQUE,       -- e.g. X-Shopify-Webhook-Id
  signature_valid  boolean NOT NULL,
  headers          jsonb NOT NULL DEFAULT '{}',
  payload          jsonb NOT NULL,
  received_at      timestamptz NOT NULL DEFAULT now(),
  processed_at     timestamptz,
  error            text
);

-- =====================================================================
-- ADS  (Meta Ads + Google Ads in one model)
-- =====================================================================
CREATE TABLE ads.ad_account (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id  uuid NOT NULL REFERENCES integration.connection(id),
  platform       text NOT NULL CHECK (platform IN ('meta','google')),
  external_id    text NOT NULL,                -- act_123 / customer id 123-456-7890
  name           text NOT NULL,
  currency       char(3) NOT NULL,
  timezone       text NOT NULL,
  status         text NOT NULL,
  UNIQUE (platform, external_id)
);

CREATE TABLE ads.campaign (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ad_account_id    uuid NOT NULL REFERENCES ads.ad_account(id),
  platform         text NOT NULL CHECK (platform IN ('meta','google')),
  external_id      text NOT NULL,
  name             text NOT NULL,
  objective        text,                        -- Meta objective / Google channel type (SEARCH, PMAX, ...)
  status           text NOT NULL,
  daily_budget     numeric(14,2),
  lifetime_budget  numeric(14,2),
  bid_strategy     text,
  campaign_key     text,                        -- normalised utm_campaign used to join orders
  start_at         timestamptz,
  end_at           timestamptz,
  src_updated_at   timestamptz,
  UNIQUE (platform, external_id)
);
CREATE INDEX ON ads.campaign (campaign_key);

-- Meta ad set / Google ad group or asset group
CREATE TABLE ads.ad_group (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id        uuid NOT NULL REFERENCES ads.campaign(id) ON DELETE CASCADE,
  platform           text NOT NULL CHECK (platform IN ('meta','google')),
  external_id        text NOT NULL,
  kind               text NOT NULL DEFAULT 'ad_group' CHECK (kind IN ('ad_set','ad_group','asset_group')),
  name               text NOT NULL,
  status             text NOT NULL,
  daily_budget       numeric(14,2),
  optimization_goal  text,
  targeting          jsonb NOT NULL DEFAULT '{}',
  in_learning_phase  boolean,
  UNIQUE (platform, external_id)
);

CREATE TABLE ads.ad (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ad_group_id          uuid NOT NULL REFERENCES ads.ad_group(id) ON DELETE CASCADE,
  platform             text NOT NULL CHECK (platform IN ('meta','google')),
  external_id          text NOT NULL,
  name                 text NOT NULL,
  status               text NOT NULL,
  ad_format            text,                    -- image, video, carousel, rsa, pmax_asset
  headline             text,
  primary_text         text,
  call_to_action       text,
  destination_url      text,
  destination_page_id  uuid REFERENCES core.web_page(id),          -- link to Landing pages / CRO
  creative_asset_id    uuid,                                       -- FK added after creative schema
  creative_concept_id  uuid,                                       -- FK added after creative schema
  url_tags             text,                    -- UTM template on the ad
  promoted_product_ids uuid[] NOT NULL DEFAULT '{}',               -- link to Shipping stock checks
  src_created_at       timestamptz,
  UNIQUE (platform, external_id)
);
CREATE INDEX ON ads.ad (destination_page_id);

CREATE TABLE ads.keyword (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ad_group_id  uuid NOT NULL REFERENCES ads.ad_group(id) ON DELETE CASCADE,
  external_id  text NOT NULL,
  text         text NOT NULL,
  match_type   text NOT NULL CHECK (match_type IN ('exact','phrase','broad')),
  status       text NOT NULL,
  UNIQUE (ad_group_id, external_id)
);

-- Platform-reported daily metrics at campaign, ad_group and ad level
CREATE TABLE ads.daily_metric (
  metric_date         date NOT NULL,
  level               text NOT NULL CHECK (level IN ('campaign','ad_group','ad')),
  entity_id           uuid NOT NULL,
  platform            text NOT NULL CHECK (platform IN ('meta','google')),
  spend               numeric(14,2) NOT NULL DEFAULT 0,
  impressions         bigint NOT NULL DEFAULT 0,
  reach               bigint,
  frequency           numeric(8,3),
  clicks              bigint NOT NULL DEFAULT 0,
  link_clicks         bigint,
  landing_page_views  bigint,
  add_to_cart         numeric(14,2),
  initiate_checkout   numeric(14,2),
  purchases           numeric(14,2),            -- platform conversions can be fractional (Google)
  purchase_value      numeric(14,2),
  video_3s_views      bigint,
  video_thruplays     bigint,
  pulled_at           timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (metric_date, level, entity_id)
);

CREATE TABLE ads.breakdown_metric (
  metric_date  date NOT NULL,
  entity_id    uuid NOT NULL,                   -- usually ad_group or ad
  dimension    text NOT NULL CHECK (dimension IN ('age','gender','placement','device','region','platform_position','hour')),
  dim_value    text NOT NULL,
  spend        numeric(14,2) NOT NULL DEFAULT 0,
  impressions  bigint NOT NULL DEFAULT 0,
  clicks       bigint NOT NULL DEFAULT 0,
  purchases    numeric(14,2),
  purchase_value numeric(14,2),
  PRIMARY KEY (metric_date, entity_id, dimension, dim_value)
);

CREATE TABLE ads.search_term_daily (
  metric_date  date NOT NULL,
  ad_group_id  uuid NOT NULL REFERENCES ads.ad_group(id) ON DELETE CASCADE,
  search_term  text NOT NULL,
  impressions  bigint NOT NULL DEFAULT 0,
  clicks       bigint NOT NULL DEFAULT 0,
  cost         numeric(14,2) NOT NULL DEFAULT 0,
  conversions  numeric(14,2),
  PRIMARY KEY (metric_date, ad_group_id, search_term)
);

-- Store-side truth: Shopify orders joined to ads through UTMs
CREATE TABLE ads.attribution_daily (
  metric_date   date NOT NULL,
  model         text NOT NULL CHECK (model IN ('utm_last_click','platform_reported','blended')),
  campaign_id   uuid NOT NULL REFERENCES ads.campaign(id) ON DELETE CASCADE,
  ad_id         uuid REFERENCES ads.ad(id) ON DELETE CASCADE,
  orders        integer NOT NULL DEFAULT 0,
  revenue       numeric(14,2) NOT NULL DEFAULT 0,
  new_customers integer NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX attribution_daily_uq ON ads.attribution_daily (metric_date, model, campaign_id, COALESCE(ad_id, '00000000-0000-0000-0000-000000000000'::uuid));

CREATE TABLE ads.target (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id         uuid NOT NULL REFERENCES core.store(id),
  scope_type       text NOT NULL CHECK (scope_type IN ('store','platform','campaign','product')),
  scope_id         text,
  metric           text NOT NULL CHECK (metric IN ('roas','cpa','cpm','ctr','daily_spend_cap')),
  target_value     numeric(14,4) NOT NULL,
  breakeven_value  numeric(14,4),
  valid_from       date NOT NULL DEFAULT current_date
);

CREATE TABLE ads.change_history (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type  text NOT NULL CHECK (entity_type IN ('campaign','ad_group','ad')),
  entity_id    uuid NOT NULL,
  changed_at   timestamptz NOT NULL,
  source       text NOT NULL CHECK (source IN ('platform_ui','flowmerce','platform_auto')),
  field        text NOT NULL,
  old_value    text,
  new_value    text,
  action_id    uuid                                -- FK to ops.action added later
);

-- =====================================================================
-- SEO  (SEO and blog automation)
-- =====================================================================
CREATE TABLE seo.keyword_cluster (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id            uuid NOT NULL REFERENCES core.store(id),
  name                text NOT NULL,
  primary_keyword_id  uuid,                          -- FK added below
  intent              text CHECK (intent IN ('informational','commercial','transactional','navigational','mixed'))
);

CREATE TABLE seo.keyword (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id      uuid NOT NULL REFERENCES core.store(id),
  text          text NOT NULL,
  locale        text NOT NULL DEFAULT 'en-US',
  cluster_id    uuid REFERENCES seo.keyword_cluster(id),
  intent        text CHECK (intent IN ('informational','commercial','transactional','navigational','mixed')),
  is_brand      boolean NOT NULL DEFAULT false,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (store_id, text, locale)
);
ALTER TABLE seo.keyword_cluster
  ADD CONSTRAINT keyword_cluster_primary_fk FOREIGN KEY (primary_keyword_id) REFERENCES seo.keyword(id);

-- Estimates are labelled by source: Semrush volume is an estimate, Trends is relative interest
CREATE TABLE seo.keyword_metric_daily (
  keyword_id    uuid NOT NULL REFERENCES seo.keyword(id) ON DELETE CASCADE,
  metric_date   date NOT NULL,
  source        text NOT NULL CHECK (source IN ('semrush','google_trends','keyword_planner','gsc')),
  volume_est    integer,
  trend_index   integer,                              -- 0-100 relative interest
  difficulty    integer,
  cpc_est       numeric(10,2),
  serp_features text[],
  PRIMARY KEY (keyword_id, metric_date, source)
);

CREATE TABLE seo.gsc_page_query_daily (
  metric_date  date NOT NULL,
  page_id      uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  query        text NOT NULL,
  device       text NOT NULL DEFAULT 'all',
  country      text NOT NULL DEFAULT 'all',
  clicks       integer NOT NULL DEFAULT 0,
  impressions  integer NOT NULL DEFAULT 0,
  position     numeric(6,2),
  PRIMARY KEY (metric_date, page_id, query, device, country)
);

CREATE TABLE seo.topic (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id          uuid NOT NULL REFERENCES core.store(id),
  title             text NOT NULL,
  cluster_id        uuid REFERENCES seo.keyword_cluster(id),
  score             integer CHECK (score BETWEEN 0 AND 100),
  score_breakdown   jsonb NOT NULL DEFAULT '{}',      -- relevance, demand, ranking chance, intent, product potential, gap, timing
  funnel_stage      text CHECK (funnel_stage IN ('tof','mof','bof')),
  target_product_ids uuid[] NOT NULL DEFAULT '{}',
  must_publish_by   date,
  status            text NOT NULL DEFAULT 'idea' CHECK (status IN ('idea','approved','drafting','drafted','published','rejected','parked')),
  created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE seo.content_item (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id            uuid NOT NULL REFERENCES core.store(id),
  topic_id            uuid REFERENCES seo.topic(id),
  content_type        text NOT NULL CHECK (content_type IN ('blog_article','collection_copy','product_copy','faq','buying_guide')),
  title               text NOT NULL,
  slug                text,
  meta_title          text,
  meta_description    text,
  body_html           text,
  schema_jsonld       jsonb,
  word_count          integer,
  version_no          integer NOT NULL DEFAULT 1,
  status              text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','in_review','approved','hidden_draft','published','archived')),
  page_id             uuid REFERENCES core.web_page(id),
  shopify_article_gid text,
  author_kind         text NOT NULL DEFAULT 'agent' CHECK (author_kind IN ('agent','human','mixed')),
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE seo.content_score (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_item_id  uuid NOT NULL REFERENCES seo.content_item(id) ON DELETE CASCADE,
  scored_at        timestamptz NOT NULL DEFAULT now(),
  overall          integer CHECK (overall BETWEEN 0 AND 100),
  seo_score        integer,
  readability      integer,
  relevance        integer,
  aeo_geo          integer,
  brand_compliance integer,
  issues           jsonb NOT NULL DEFAULT '[]'
);

CREATE TABLE seo.internal_link (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  from_page_id  uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  to_page_id    uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  anchor_text   text NOT NULL,
  status        text NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested','approved','live','rejected')),
  UNIQUE (from_page_id, to_page_id, anchor_text)
);

-- AI search visibility, only where it can actually be checked
CREATE TABLE seo.ai_visibility_check (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword_id      uuid NOT NULL REFERENCES seo.keyword(id) ON DELETE CASCADE,
  engine          text NOT NULL CHECK (engine IN ('google_ai_overview','chatgpt','perplexity','claude','gemini','copilot')),
  checked_at      timestamptz NOT NULL DEFAULT now(),
  brand_mentioned boolean,
  cited_page_id   uuid REFERENCES core.web_page(id),
  method          text NOT NULL CHECK (method IN ('manual','api','third_party')),
  notes           text
);

-- =====================================================================
-- SHIP  (shipping tracking & alerts, readiness, MCF, production)
-- =====================================================================
CREATE TABLE ship.fulfillment_order (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id     uuid NOT NULL REFERENCES core."order"(id) ON DELETE CASCADE,
  source       text NOT NULL CHECK (source IN ('shopify','amazon_mcf','shiprocket','manual')),
  external_id  text,
  location_id  uuid REFERENCES core.location(id),
  status       text NOT NULL,
  requested_at timestamptz,
  ship_by      timestamptz,
  UNIQUE (source, external_id)
);

CREATE TABLE ship.shipment (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id               uuid NOT NULL REFERENCES core."order"(id) ON DELETE CASCADE,
  fulfillment_order_id   uuid REFERENCES ship.fulfillment_order(id),
  shopify_fulfillment_gid text UNIQUE,
  carrier                text,
  service                text,
  tracking_number        text,
  tracking_url           text,
  tracker                text NOT NULL DEFAULT 'none' CHECK (tracker IN ('aftership','track17','shiprocket','delhivery','amazon','none')),
  tracker_ref            text,
  status                 text NOT NULL DEFAULT 'unknown' CHECK (status IN ('label_created','in_transit','out_for_delivery','delivered','exception','failed_attempt','returning','returned','stuck','unknown')),
  shipped_at             timestamptz,
  estimated_delivery_at  timestamptz,
  delivered_at           timestamptz,
  last_event_at          timestamptz,
  last_checkpoint        text,
  destination_country    char(2),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  UNIQUE (carrier, tracking_number)
);
CREATE INDEX ON ship.shipment (status, last_event_at);

CREATE TABLE ship.tracking_event (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shipment_id  uuid NOT NULL REFERENCES ship.shipment(id) ON DELETE CASCADE,
  occurred_at  timestamptz NOT NULL,
  status       text NOT NULL,
  sub_status   text,
  location     text,
  message      text,
  source       text NOT NULL,
  UNIQUE (shipment_id, occurred_at, status)
);

CREATE TABLE ship.inventory_snapshot (
  snapshot_date  date NOT NULL,
  variant_id     uuid NOT NULL REFERENCES core.product_variant(id) ON DELETE CASCADE,
  location_id    uuid NOT NULL REFERENCES core.location(id) ON DELETE CASCADE,
  available      integer NOT NULL,
  reserved       integer NOT NULL DEFAULT 0,
  inbound        integer NOT NULL DEFAULT 0,
  PRIMARY KEY (snapshot_date, variant_id, location_id)
);

-- Result of an Amazon MCF fulfilment preview for a variant / order
CREATE TABLE ship.mcf_eligibility (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  variant_id         uuid NOT NULL REFERENCES core.product_variant(id) ON DELETE CASCADE,
  order_id           uuid REFERENCES core."order"(id) ON DELETE CASCADE,
  checked_at         timestamptz NOT NULL DEFAULT now(),
  fba_available_qty  integer,
  is_eligible        boolean NOT NULL,
  reason             text,
  shipping_speed     text,
  estimated_fee      numeric(14,2),
  preview            jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE ship.production_requirement (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  variant_id     uuid NOT NULL REFERENCES core.product_variant(id),
  order_line_id  uuid REFERENCES core.order_line(id) ON DELETE SET NULL,
  qty_required   integer NOT NULL,
  qty_available  integer NOT NULL,
  shortfall_qty  integer GENERATED ALWAYS AS (GREATEST(qty_required - qty_available, 0)) STORED,
  due_by         date,
  status         text NOT NULL DEFAULT 'open' CHECK (status IN ('open','scheduled','in_production','ready','cancelled')),
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ship.production_batch (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  variant_id         uuid NOT NULL REFERENCES core.product_variant(id),
  location_id        uuid REFERENCES core.location(id),
  qty                integer NOT NULL,
  started_at         timestamptz,
  expected_ready_at  timestamptz,
  completed_at       timestamptz,
  status             text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','in_progress','done','cancelled'))
);

CREATE TABLE ship.allocation (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_line_id  uuid NOT NULL REFERENCES core.order_line(id) ON DELETE CASCADE,
  location_id    uuid REFERENCES core.location(id),
  qty            integer NOT NULL,
  method         text NOT NULL CHECK (method IN ('shopify_stock','amazon_mcf','make_to_order','3pl')),
  decided_by     text NOT NULL CHECK (decided_by IN ('rule','human')),
  decided_at     timestamptz NOT NULL DEFAULT now()
);

-- =====================================================================
-- CREATIVE  (creative strategist)
-- =====================================================================
CREATE TABLE creative.asset (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id      uuid NOT NULL REFERENCES core.store(id),
  kind          text NOT NULL CHECK (kind IN ('image','video','copy','carousel','ugc','gif')),
  storage_uri   text NOT NULL,                     -- object store key
  sha256        text NOT NULL UNIQUE,              -- dedupes the same file across Meta and Google
  width         integer,
  height        integer,
  duration_s    numeric(8,2),
  source        text NOT NULL CHECK (source IN ('upload','meta','google','generated','drive','dropbox')),
  rights_note   text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE creative.asset_product (
  asset_id    uuid NOT NULL REFERENCES creative.asset(id) ON DELETE CASCADE,
  product_id  uuid NOT NULL REFERENCES core.product(id) ON DELETE CASCADE,
  PRIMARY KEY (asset_id, product_id)
);

CREATE TABLE creative.concept (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id      uuid NOT NULL REFERENCES core.store(id),
  title         text NOT NULL,
  hook          text,
  angle         text,
  message       text,
  offer         text,
  funnel_stage  text CHECK (funnel_stage IN ('tof','mof','bof')),
  persona       text,
  evidence      jsonb NOT NULL DEFAULT '[]',        -- references to ad metrics, keywords, reviews behind the idea
  origin        text NOT NULL DEFAULT 'ai' CHECK (origin IN ('ai','human','mixed')),
  status        text NOT NULL DEFAULT 'idea' CHECK (status IN ('idea','approved','in_production','live','retired','rejected')),
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE creative.concept_asset (
  concept_id  uuid NOT NULL REFERENCES creative.concept(id) ON DELETE CASCADE,
  asset_id    uuid NOT NULL REFERENCES creative.asset(id) ON DELETE CASCADE,
  role        text NOT NULL DEFAULT 'variant',
  PRIMARY KEY (concept_id, asset_id)
);

CREATE TABLE creative.brief (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  concept_id      uuid NOT NULL REFERENCES creative.concept(id) ON DELETE CASCADE,
  brief_type      text NOT NULL CHECK (brief_type IN ('ad','landing_page','content','email')),
  target_platform text,                              -- meta, google, shopify
  body_md         text NOT NULL,
  requirements    jsonb NOT NULL DEFAULT '{}',
  status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','in_use','done','rejected')),
  approved_by     uuid REFERENCES auth.app_user(id),
  approved_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Ad performance rolled up to asset/concept level (computed from ads.*)
CREATE TABLE creative.performance_rollup (
  subject_type  text NOT NULL CHECK (subject_type IN ('asset','concept','taxonomy_term')),
  subject_id    uuid NOT NULL,
  platform      text NOT NULL CHECK (platform IN ('meta','google','all')),
  period_start  date NOT NULL,
  period_end    date NOT NULL,
  spend         numeric(14,2) NOT NULL DEFAULT 0,
  impressions   bigint NOT NULL DEFAULT 0,
  ctr           numeric(8,5),
  hook_rate     numeric(8,5),                       -- 3s views / impressions
  hold_rate     numeric(8,5),                       -- thruplays / 3s views
  cpa           numeric(14,2),
  roas          numeric(10,4),
  sample_ok     boolean NOT NULL DEFAULT false,     -- enough spend/impressions to trust
  PRIMARY KEY (subject_type, subject_id, platform, period_start, period_end)
);

CREATE TABLE creative.test_plan (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  concept_id      uuid NOT NULL REFERENCES creative.concept(id) ON DELETE CASCADE,
  hypothesis      text NOT NULL,
  variable        text NOT NULL CHECK (variable IN ('hook','angle','format','offer','visual','copy','audience')),
  variants        jsonb NOT NULL DEFAULT '[]',
  success_metric  text NOT NULL,
  min_spend       numeric(14,2),
  status          text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','approved','running','concluded','cancelled')),
  result          jsonb
);

CREATE TABLE creative.trend_signal (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id      uuid NOT NULL REFERENCES core.store(id),
  source        text NOT NULL,                      -- approved sources only
  captured_at   timestamptz NOT NULL DEFAULT now(),
  topic         text NOT NULL,
  strength      integer CHECK (strength BETWEEN 0 AND 100),
  url           text,
  notes         text
);

CREATE TABLE creative.competitor_reference (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id     uuid NOT NULL REFERENCES core.store(id),
  brand        text NOT NULL,
  url          text,
  captured_at  timestamptz NOT NULL DEFAULT now(),
  asset_uri    text,
  notes        text
);

ALTER TABLE ads.ad
  ADD CONSTRAINT ad_creative_asset_fk   FOREIGN KEY (creative_asset_id)   REFERENCES creative.asset(id),
  ADD CONSTRAINT ad_creative_concept_fk FOREIGN KEY (creative_concept_id) REFERENCES creative.concept(id);

-- =====================================================================
-- PAGE  (landing page building automation)
-- =====================================================================
CREATE TABLE page.landing_page (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id            uuid NOT NULL REFERENCES core.store(id),
  web_page_id         uuid UNIQUE REFERENCES core.web_page(id),      -- set once a URL exists
  brief_id            uuid REFERENCES creative.brief(id),            -- link from Creative
  campaign_id         uuid REFERENCES ads.campaign(id),              -- link to Ads
  name                text NOT NULL,
  objective           text NOT NULL,
  audience            text,
  brief_text          text,                                          -- the plain-language brief
  design_direction    jsonb NOT NULL DEFAULT '{}',
  status              text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','generating','in_review','approved','deploying','live','paused','archived')),
  current_version_id  uuid,                                          -- FK added below
  shopify_page_gid    text,
  template_suffix     text,
  created_by          uuid REFERENCES auth.app_user(id),
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE page.landing_page_product (
  landing_page_id  uuid NOT NULL REFERENCES page.landing_page(id) ON DELETE CASCADE,
  product_id       uuid NOT NULL REFERENCES core.product(id),
  role             text NOT NULL DEFAULT 'featured',
  PRIMARY KEY (landing_page_id, product_id)
);

CREATE TABLE page.reference (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  landing_page_id  uuid NOT NULL REFERENCES page.landing_page(id) ON DELETE CASCADE,
  kind             text NOT NULL CHECK (kind IN ('competitor','inspiration','own_page','brand_guide')),
  url              text,
  asset_uri        text,
  extracted_patterns jsonb NOT NULL DEFAULT '[]',    -- layout patterns noted, never copied content
  notes            text
);

CREATE TABLE page.page_version (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  landing_page_id   uuid NOT NULL REFERENCES page.landing_page(id) ON DELETE CASCADE,
  version_no        integer NOT NULL,
  section_spec      jsonb NOT NULL,                  -- ordered sections + content, the source of truth
  code_bundle_uri   text,                            -- liquid/json/css/js bundle in object store
  preview_url       text,
  screenshot_uris   text[] NOT NULL DEFAULT '{}',
  change_reason     text,                            -- e.g. 'CRO experiment 12: move reviews above fold'
  source_experiment_id uuid,                         -- FK added after cro schema
  status            text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','preview','approved','deployed','superseded','rolled_back','rejected')),
  created_by_kind   text NOT NULL DEFAULT 'agent' CHECK (created_by_kind IN ('agent','human')),
  created_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (landing_page_id, version_no)
);
ALTER TABLE page.landing_page
  ADD CONSTRAINT landing_page_current_version_fk FOREIGN KEY (current_version_id) REFERENCES page.page_version(id);

CREATE TABLE page.validation_check (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_version_id  uuid NOT NULL REFERENCES page.page_version(id) ON DELETE CASCADE,
  check_name       text NOT NULL CHECK (check_name IN ('links','mobile_layout','lighthouse','tracking_events','brand_claims','accessibility','liquid_render')),
  passed           boolean NOT NULL,
  details          jsonb NOT NULL DEFAULT '{}',
  checked_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE page.deployment (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_version_id  uuid NOT NULL REFERENCES page.page_version(id),
  target           text NOT NULL CHECK (target IN ('preview_theme','live')),
  method           text NOT NULL CHECK (method IN ('page_and_metaobjects','github_pr','theme_files_upsert')),
  external_ref     text,                             -- PR url, page gid, theme id
  action_id        uuid,                             -- FK to ops.action added later (the approved action)
  status           text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','deployed','failed','rolled_back')),
  deployed_at      timestamptz,
  rolled_back_at   timestamptz
);

-- =====================================================================
-- CRO  (conversion rate optimization)
-- =====================================================================
-- First-party events from a Shopify Web Pixel (custom pixel) posting to our collector
CREATE TABLE cro.web_event (
  id           bigint GENERATED ALWAYS AS IDENTITY,
  received_at  timestamptz NOT NULL DEFAULT now(),
  event_name   text NOT NULL,                          -- page_viewed, product_viewed, product_added_to_cart, checkout_started, checkout_completed
  client_hash  text,
  session_key  text,
  page_url     text,
  page_id      uuid,
  product_id   uuid,
  utm          jsonb NOT NULL DEFAULT '{}',
  device       text,
  payload      jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY (id, received_at)
) PARTITION BY RANGE (received_at);
CREATE TABLE cro.web_event_default PARTITION OF cro.web_event DEFAULT;
CREATE INDEX ON cro.web_event (page_id, received_at);

-- Daily page funnel from ShopifyQL sessions, GA4 or our own pixel
CREATE TABLE cro.page_metric_daily (
  metric_date       date NOT NULL,
  page_id           uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  source            text NOT NULL CHECK (source IN ('shopifyql','ga4','pixel')),
  device            text NOT NULL DEFAULT 'all',
  traffic_channel   text NOT NULL DEFAULT 'all',        -- paid_social, paid_search, organic, email, direct, referral
  sessions          integer NOT NULL DEFAULT 0,
  landing_sessions  integer NOT NULL DEFAULT 0,          -- LPV when the page was the entry page
  atc_sessions      integer NOT NULL DEFAULT 0,
  checkout_sessions integer NOT NULL DEFAULT 0,
  purchases         integer NOT NULL DEFAULT 0,
  revenue           numeric(14,2) NOT NULL DEFAULT 0,
  avg_engaged_s     numeric(10,2),
  PRIMARY KEY (metric_date, page_id, source, device, traffic_channel)
);

-- What a page looks like at a point in time: the feature vector used to compare peers
CREATE TABLE cro.page_attribute_snapshot (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id           uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  captured_at       timestamptz NOT NULL DEFAULT now(),
  template_name     text,
  price             numeric(14,2),
  compare_at_price  numeric(14,2),
  in_stock          boolean,
  image_count       integer,
  has_video         boolean,
  review_count      integer,
  avg_rating        numeric(3,2),
  shipping_message  boolean,
  returns_message   boolean,
  cta_above_fold    boolean,
  lcp_ms            integer,
  cls               numeric(6,3),
  inp_ms            integer,
  word_count        integer,
  sections          text[] NOT NULL DEFAULT '{}',
  extra             jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX ON cro.page_attribute_snapshot (page_id, captured_at DESC);

CREATE TABLE cro.speed_audit (
  page_id      uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  audited_at   timestamptz NOT NULL,
  strategy     text NOT NULL CHECK (strategy IN ('mobile','desktop')),
  perf_score   integer,
  lcp_ms       integer,
  cls          numeric(6,3),
  inp_ms       integer,
  source       text NOT NULL CHECK (source IN ('psi_lab','crux_field')),
  PRIMARY KEY (page_id, audited_at, strategy, source)
);

CREATE TABLE cro.peer_group (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id   uuid NOT NULL REFERENCES core.store(id),
  name       text NOT NULL,
  page_type  text NOT NULL,
  rule       jsonb NOT NULL DEFAULT '{}'           -- e.g. same template + same collection + price band
);

CREATE TABLE cro.peer_group_member (
  peer_group_id  uuid NOT NULL REFERENCES cro.peer_group(id) ON DELETE CASCADE,
  page_id        uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  PRIMARY KEY (peer_group_id, page_id)
);

-- Diagnosis: category is a hypothesis with confidence, never an automatic conclusion
CREATE TABLE cro.diagnosis (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id         uuid NOT NULL REFERENCES core.web_page(id) ON DELETE CASCADE,
  peer_group_id   uuid REFERENCES cro.peer_group(id),
  period_start    date NOT NULL,
  period_end      date NOT NULL,
  category        text NOT NULL CHECK (category IN ('page','product','pricing_offer','traffic_audience','customer_journey','insufficient_evidence')),
  confidence      text NOT NULL CHECK (confidence IN ('low','medium','high')),
  sample_sessions integer NOT NULL,
  evidence        jsonb NOT NULL DEFAULT '[]',
  explanation     text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cro.pattern (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id     uuid NOT NULL REFERENCES core.store(id),
  name         text NOT NULL,
  description  text NOT NULL,
  page_type    text NOT NULL,
  evidence     jsonb NOT NULL DEFAULT '[]',
  status       text NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','validated','rejected'))
);

CREATE TABLE cro.experiment (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id               uuid NOT NULL REFERENCES core.web_page(id),
  diagnosis_id          uuid REFERENCES cro.diagnosis(id),
  pattern_id            uuid REFERENCES cro.pattern(id),
  hypothesis            text NOT NULL,
  change_spec           jsonb NOT NULL,
  method                text NOT NULL CHECK (method IN ('before_after','split_url','ab_tool')),
  primary_metric        text NOT NULL CHECK (primary_metric IN ('atc_rate','checkout_rate','conversion_rate','revenue_per_session')),
  min_sessions          integer NOT NULL,
  variant_version_id    uuid REFERENCES page.page_version(id),     -- the page version built for the test
  status                text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','approved','running','concluded','cancelled')),
  started_at            timestamptz,
  ended_at              timestamptz,
  result                jsonb,
  decision              text CHECK (decision IN ('ship','revert','inconclusive'))
);
ALTER TABLE page.page_version
  ADD CONSTRAINT page_version_experiment_fk FOREIGN KEY (source_experiment_id) REFERENCES cro.experiment(id);

-- =====================================================================
-- OPS  (shared engine: events, alerts, recommendations, approvals, actions, outcomes, audit)
-- =====================================================================
-- Transactional outbox: modules write domain events in the same transaction as their data
CREATE TABLE ops.event_outbox (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  occurred_at    timestamptz NOT NULL DEFAULT now(),
  source_module  text NOT NULL CHECK (source_module IN ('core','ads','seo','ship','creative','page','cro','ops')),
  event_type     text NOT NULL,                    -- e.g. 'ship.stock_low', 'cro.diagnosis_created'
  entity_type    text NOT NULL,
  entity_id      uuid,
  payload        jsonb NOT NULL DEFAULT '{}',
  published_at   timestamptz,
  attempts       integer NOT NULL DEFAULT 0
);
CREATE INDEX event_outbox_unpublished ON ops.event_outbox (id) WHERE published_at IS NULL;

CREATE TABLE ops.event_subscription (
  event_type       text NOT NULL,
  consumer_module  text NOT NULL,
  handler          text NOT NULL,                  -- python dotted path
  is_active        boolean NOT NULL DEFAULT true,
  PRIMARY KEY (event_type, consumer_module, handler)
);

CREATE TABLE ops.alert_rule (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  module       text NOT NULL,
  code         text NOT NULL UNIQUE,              -- e.g. 'ship.stuck_72h', 'ads.spend_no_purchase'
  description  text NOT NULL,
  condition    jsonb NOT NULL,
  severity     text NOT NULL CHECK (severity IN ('info','warning','critical')),
  channels     text[] NOT NULL DEFAULT '{dashboard}',
  is_active    boolean NOT NULL DEFAULT true
);

CREATE TABLE ops.alert (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id     uuid NOT NULL REFERENCES core.store(id),
  rule_id      uuid REFERENCES ops.alert_rule(id),
  module       text NOT NULL,
  severity     text NOT NULL CHECK (severity IN ('info','warning','critical')),
  entity_type  text NOT NULL,
  entity_id    uuid,
  title        text NOT NULL,
  details      jsonb NOT NULL DEFAULT '{}',
  dedupe_key   text NOT NULL,
  status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','snoozed','resolved')),
  opened_at    timestamptz NOT NULL DEFAULT now(),
  resolved_at  timestamptz
);
CREATE UNIQUE INDEX alert_one_open_per_key ON ops.alert (dedupe_key) WHERE status IN ('open','acknowledged','snoozed');

CREATE TABLE ops.recommendation (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id         uuid NOT NULL REFERENCES core.store(id),
  module           text NOT NULL,
  kind             text NOT NULL,                  -- e.g. 'ads.pause_ad', 'cro.test_pattern', 'ship.use_mcf'
  entity_type      text NOT NULL,
  entity_id        uuid,
  title            text NOT NULL,
  rationale        text NOT NULL,
  evidence         jsonb NOT NULL DEFAULT '[]',
  evidence_level   text NOT NULL CHECK (evidence_level IN ('observed','probable','hypothesis')),
  priority_score   numeric(6,2) NOT NULL DEFAULT 0,
  proposed_action  jsonb,                          -- becomes ops.action.params when approved
  dedupe_key       text NOT NULL,
  status           text NOT NULL DEFAULT 'new' CHECK (status IN ('new','approved','rejected','expired','executed','superseded')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  expires_at       timestamptz
);
CREATE UNIQUE INDEX recommendation_one_live_per_key ON ops.recommendation (dedupe_key) WHERE status IN ('new','approved');

CREATE TABLE ops.approval_policy (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_type            text NOT NULL UNIQUE,     -- matches ops.action.action_type
  requires_approval      boolean NOT NULL DEFAULT true,
  approver_roles         text[] NOT NULL DEFAULT '{owner,admin}',
  max_change_pct         numeric(6,2),             -- e.g. budget +/-20% per 24h
  auto_approve_condition jsonb,                    -- only for explicitly safe actions
  is_forbidden           boolean NOT NULL DEFAULT false   -- e.g. deletes: never executable
);

CREATE TABLE ops.action (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id           uuid NOT NULL REFERENCES core.store(id),
  module             text NOT NULL,
  recommendation_id  uuid REFERENCES ops.recommendation(id),
  action_type        text NOT NULL,                -- 'meta.adset.set_budget', 'shopify.page.create', 'github.pr.open', 'amazon.mcf.create_order'
  connection_id      uuid REFERENCES integration.connection(id),
  target             jsonb NOT NULL,               -- external ids being changed
  params             jsonb NOT NULL DEFAULT '{}',
  idempotency_key    text NOT NULL UNIQUE,
  is_dry_run         boolean NOT NULL DEFAULT false,
  status             text NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval','approved','queued','executing','succeeded','failed','rolled_back','cancelled','rejected')),
  before_state       jsonb,                        -- snapshot used for rollback
  after_state        jsonb,
  requested_by       uuid REFERENCES auth.app_user(id),
  requested_at       timestamptz NOT NULL DEFAULT now(),
  executed_at        timestamptz,
  error              text,
  rollback_of        uuid REFERENCES ops.action(id)
);
CREATE INDEX ON ops.action (status);

CREATE TABLE ops.approval (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_id    uuid NOT NULL REFERENCES ops.action(id) ON DELETE CASCADE,
  approver_id  uuid NOT NULL REFERENCES auth.app_user(id),
  decision     text NOT NULL CHECK (decision IN ('approved','rejected','changes_requested')),
  channel      text NOT NULL CHECK (channel IN ('web','slack','email')),
  comment      text,
  decided_at   timestamptz NOT NULL DEFAULT now()
);

-- Did the action work? Measured after a window, compared to a baseline
CREATE TABLE ops.outcome (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  action_id    uuid NOT NULL REFERENCES ops.action(id) ON DELETE CASCADE,
  metric       text NOT NULL,
  window_days  integer NOT NULL,
  baseline     numeric(18,6),
  observed     numeric(18,6),
  measured_at  timestamptz NOT NULL DEFAULT now(),
  verdict      text NOT NULL CHECK (verdict IN ('improved','no_change','worse','inconclusive'))
);

CREATE TABLE ops.task (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id     uuid NOT NULL REFERENCES core.store(id),
  module       text NOT NULL,
  title        text NOT NULL,
  entity_type  text,
  entity_id    uuid,
  assignee_id  uuid REFERENCES auth.app_user(id),
  due_at       timestamptz,
  status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','done','cancelled'))
);

CREATE TABLE ops.notification (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel     text NOT NULL CHECK (channel IN ('slack','email','whatsapp','dashboard')),
  recipient   text NOT NULL,
  subject     text,
  body        text NOT NULL,
  ref_type    text,
  ref_id      uuid,
  status      text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','sent','failed')),
  sent_at     timestamptz
);

CREATE TABLE ops.audit_log (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  at           timestamptz NOT NULL DEFAULT now(),
  actor_type   text NOT NULL CHECK (actor_type IN ('user','system','agent')),
  actor_id     text,
  verb         text NOT NULL,
  entity_type  text NOT NULL,
  entity_id    text,
  diff         jsonb NOT NULL DEFAULT '{}'
);

-- LLM usage, so every AI output can be traced to a prompt version and cost
CREATE TABLE ops.llm_call (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  module          text NOT NULL,
  purpose         text NOT NULL,                  -- 'seo.draft_article', 'creative.generate_hooks', 'cro.explain_diagnosis'
  model           text NOT NULL,
  prompt_version  text NOT NULL,
  input_tokens    integer,
  output_tokens   integer,
  cost_usd        numeric(10,4),
  ref_type        text,
  ref_id          uuid,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- late foreign keys into ops
ALTER TABLE ads.change_history ADD CONSTRAINT change_history_action_fk FOREIGN KEY (action_id) REFERENCES ops.action(id);
ALTER TABLE page.deployment     ADD CONSTRAINT deployment_action_fk     FOREIGN KEY (action_id) REFERENCES ops.action(id);

-- =====================================================================
-- CROSS-MODULE VIEWS  (the interlinking, made queryable)
-- =====================================================================

-- Ads -> Landing page -> CRO: every ad with the funnel of the page it sends traffic to (last 7 days)
CREATE VIEW cro.v_ad_destination_funnel AS
SELECT a.id                AS ad_id,
       a.platform,
       a.name              AS ad_name,
       p.id                AS page_id,
       p.url_normalized,
       p.page_type,
       COALESCE(SUM(m.spend), 0)              AS spend_7d,
       COALESCE(SUM(m.link_clicks), 0)        AS link_clicks_7d,
       COALESCE(SUM(m.landing_page_views), 0) AS lpv_7d,
       f.landing_sessions_7d,
       f.atc_sessions_7d,
       f.purchases_7d,
       CASE WHEN f.landing_sessions_7d > 0 THEN f.atc_sessions_7d::numeric / f.landing_sessions_7d END AS atc_rate_7d
FROM ads.ad a
JOIN core.web_page p ON p.id = a.destination_page_id
LEFT JOIN ads.daily_metric m
       ON m.level = 'ad' AND m.entity_id = a.id AND m.metric_date >= current_date - 7
LEFT JOIN LATERAL (
       SELECT SUM(d.landing_sessions) AS landing_sessions_7d,
              SUM(d.atc_sessions)     AS atc_sessions_7d,
              SUM(d.purchases)        AS purchases_7d
       FROM cro.page_metric_daily d
       WHERE d.page_id = p.id AND d.metric_date >= current_date - 7
         AND d.source = 'shopifyql' AND d.device = 'all' AND d.traffic_channel = 'paid_social'
     ) f ON true
GROUP BY a.id, a.platform, a.name, p.id, p.url_normalized, p.page_type,
         f.landing_sessions_7d, f.atc_sessions_7d, f.purchases_7d;

-- Shipping -> Ads: live ads promoting products whose sellable stock is low (feeds 'pause or switch' recommendations)
CREATE VIEW ship.v_ads_on_low_stock AS
WITH stock AS (
  SELECT v.product_id,
         SUM(il.available) AS available_units,
         bool_or(v.is_make_to_order) AS has_make_to_order
  FROM core.product_variant v
  LEFT JOIN core.inventory_level il ON il.variant_id = v.id
  GROUP BY v.product_id
)
SELECT a.id AS ad_id, a.platform, a.name AS ad_name, a.status AS ad_status,
       pr.id AS product_id, pr.title AS product_title,
       s.available_units, s.has_make_to_order
FROM ads.ad a
CROSS JOIN LATERAL unnest(a.promoted_product_ids) AS pp(product_id)
JOIN core.product pr ON pr.id = pp.product_id
JOIN stock s ON s.product_id = pr.id
WHERE a.status IN ('ACTIVE','ENABLED')
  AND COALESCE(s.available_units, 0) <= 5
  AND NOT s.has_make_to_order;

-- Creative -> Ads: performance of each shared taxonomy term (hook, angle, format) across all ads
CREATE VIEW creative.v_term_performance_30d AS
SELECT t.scheme, t.value,
       COUNT(DISTINCT a.id)                  AS ads,
       SUM(m.spend)                          AS spend,
       SUM(m.impressions)                    AS impressions,
       SUM(m.purchases)                      AS purchases,
       CASE WHEN SUM(m.impressions) > 0 THEN SUM(m.video_3s_views)::numeric / SUM(m.impressions) END AS hook_rate,
       CASE WHEN SUM(m.purchases)   > 0 THEN SUM(m.spend) / SUM(m.purchases) END                     AS cpa,
       CASE WHEN SUM(m.spend)       > 0 THEN SUM(m.purchase_value) / SUM(m.spend) END                AS roas
FROM core.taxonomy_term t
JOIN core.entity_tag et ON et.term_id = t.id AND et.entity_type = 'ads.ad'
JOIN ads.ad a ON a.id = et.entity_id
JOIN ads.daily_metric m ON m.level = 'ad' AND m.entity_id = a.id AND m.metric_date >= current_date - 30
GROUP BY t.scheme, t.value;

-- Product 360: one row per product with signals from every module
CREATE VIEW core.v_product_360 AS
SELECT p.id, p.title, p.status,
       (SELECT SUM(il.available) FROM core.product_variant v JOIN core.inventory_level il ON il.variant_id = v.id WHERE v.product_id = p.id) AS available_units,
       (SELECT COUNT(*) FROM ship.production_requirement r JOIN core.product_variant v ON v.id = r.variant_id
         WHERE v.product_id = p.id AND r.status IN ('open','scheduled','in_production'))                                               AS open_production_reqs,
       (SELECT COUNT(*) FROM ads.ad a WHERE p.id = ANY (a.promoted_product_ids) AND a.status IN ('ACTIVE','ENABLED'))                AS live_ads,
       (SELECT COUNT(*) FROM page.landing_page_product lp WHERE lp.product_id = p.id)                                                  AS landing_pages,
       (SELECT COUNT(*) FROM seo.topic t WHERE p.id = ANY (t.target_product_ids) AND t.status IN ('drafted','published'))              AS seo_topics,
       (SELECT d.category FROM cro.diagnosis d JOIN core.web_page w ON w.id = d.page_id
         WHERE w.product_id = p.id ORDER BY d.created_at DESC LIMIT 1)                                                                 AS latest_cro_diagnosis,
       (SELECT r.avg_rating FROM core.product_review_stats r WHERE r.product_id = p.id ORDER BY r.as_of DESC LIMIT 1)                 AS avg_rating
FROM core.product p;

-- =====================================================================
-- SEED: providers and default approval policies
-- =====================================================================
INSERT INTO integration.provider (code, category, display_name) VALUES
 ('shopify','commerce','Shopify Admin API'),
 ('meta_ads','ads','Meta Marketing API'),
 ('google_ads','ads','Google Ads API'),
 ('gsc','analytics','Google Search Console API'),
 ('ga4','analytics','Google Analytics 4 Data API'),
 ('psi','analytics','PageSpeed Insights / CrUX API'),
 ('clarity','analytics','Microsoft Clarity Data Export'),
 ('amazon_spapi','shipping','Amazon Selling Partner API (MCF, FBA inventory)'),
 ('aftership','shipping','AfterShip Tracking API'),
 ('track17','shipping','17TRACK API'),
 ('shiprocket','shipping','Shiprocket API'),
 ('delhivery','shipping','Delhivery API'),
 ('semrush','seo','Semrush API'),
 ('google_trends','seo','Google Trends (export or API if access granted)'),
 ('judgeme','reviews','Judge.me API'),
 ('anthropic','ai','Claude API'),
 ('slack','messaging','Slack API'),
 ('whatsapp','messaging','WhatsApp Business Cloud API'),
 ('github','devops','GitHub API (theme repository)'),
 ('object_store','storage','S3-compatible object storage');

INSERT INTO ops.approval_policy (action_type, requires_approval, approver_roles, max_change_pct, is_forbidden) VALUES
 ('meta.campaign.set_budget',     true,  '{owner,admin,marketer}', 20, false),
 ('meta.adset.set_budget',        true,  '{owner,admin,marketer}', 20, false),
 ('meta.ad.set_status',           true,  '{owner,admin,marketer}', NULL, false),
 ('meta.ad.create_paused',        true,  '{owner,admin,marketer}', NULL, false),
 ('google.campaign.set_budget',   true,  '{owner,admin,marketer}', 20, false),
 ('google.keyword.add_negative',  true,  '{owner,admin,marketer}', NULL, false),
 ('shopify.article.create_hidden',false, '{owner,admin,content}',  NULL, false),
 ('shopify.article.publish',      true,  '{owner,admin}',          NULL, false),
 ('shopify.page.create_hidden',   true,  '{owner,admin,marketer}', NULL, false),
 ('shopify.page.publish',         true,  '{owner,admin}',          NULL, false),
 ('github.theme_pr.open',         true,  '{owner,admin}',          NULL, false),
 ('github.theme_pr.merge',        true,  '{owner,admin}',          NULL, false),
 ('amazon.mcf.create_order',      true,  '{owner,admin,ops}',      NULL, false),
 ('notify.send',                  false, '{owner,admin,ops,marketer}', NULL, false),
 ('any.delete',                   true,  '{}',                     NULL, true);

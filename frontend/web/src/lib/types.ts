export type BrandId = 'ridhi' | 'cpc';
export type BrandFilter = BrandId | 'all';

export interface BrandSettings {
  voice: string;
  audience: string;
  avoid: string;
  defaultAuthor: string;
  topicsPerRun: number;
  draftsPerRun: number;
  researchFocus: string;
}

export interface Brand {
  id: BrandId;
  name: string;
  short: string;
  storefrontUrl: string;
  blogUrl: string;
  shopDomain: string;
  blogHandle: string;
  gscProperty: string;
  ga4PropertyId: string;
  configured: { shopifyAdmin: boolean; gsc: boolean; ga4: boolean };
  settings: BrandSettings;
}

export interface Me {
  user: { id: number; email: string; name: string; role: 'admin' | 'seo_manager' | 'reviewer'; roleLabel: string };
  permissions: string[];
  brands: Brand[];
  livePublishing: boolean;
  demoLoaded: boolean;
}

export interface Article {
  id: number;
  brand_id: BrandId;
  topic_id: number | null;
  title: string;
  handle: string;
  primary_keyword: string;
  meta_title: string;
  meta_description: string;
  summary_html: string;
  body_html: string;
  tags: string;
  author: string;
  image_url: string;
  image_alt: string;
  status: string;
  version: number;
  content_hash: string;
  approved_hash: string | null;
  approved_at: string | null;
  review_note: string;
  shopify_article_id: string | null;
  shopify_published: boolean;
  live_url: string | null;
  publish_at: string | null;
  published_at: string | null;
  shopify_synced_at: string | null;
  origin: string;
  last_error: string | null;
  assignee_id: number | null;
  assignee_name?: string;
  updated_at: string;
  created_at: string;
  has_shopify_draft: boolean;
  live_differs: boolean;
  approval_current: boolean;
  next_action: { role: string; label: string };
}

export interface SourceInfo {
  kind: 'api' | 'excel' | 'demo' | null;
  label: string;
  syncedAt: string | null;
  coverage: { from: string | null; to: string | null };
}

export interface Topic {
  id: number;
  brand_id: BrandId;
  title: string;
  primary_keyword: string;
  secondary_keywords: string;
  intent: string;
  search_volume: number | null;
  keyword_difficulty: number | null;
  volume_source: string | null;
  rationale: string;
  notes: string;
  validation_note: string;
  status: string;
  source: string;
  article_id: number | null;
  updated_at: string;
}

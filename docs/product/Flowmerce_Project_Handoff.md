# Flowmerce: Product, Flow and Build Specification

*Handoff document for an AI agent or a new team member. It describes WHAT we are building, in what ORDER, how data and decisions FLOW, and how the work is STRUCTURED. It was compiled from the presentation decks and prototype built in this project. Anything marked “to confirm” is not yet verified.*

---

## 0. How to read this document

| Part | What it covers |
| --- | --- |
| 1 | Vision, principles and vocabulary |
| 2 | The platform structure: six core projects plus one future-scope project |
| 3 | Each project in detail: purpose, flow steps, inputs, outputs |
| 4 | Build order and how projects are joined |
| 5 | Information flows (which data helps which project decide) |
| 6 | The ten-step delivery process and progress tracking |
| 7 | Expected business outcomes |
| 8 | Merchandising Automation (future scope) in full |
| 9 | Decisions already made, and open items to confirm |
| 10 | The presentation deck and the app prototype (what exists today) |
| Appendix A | Brand Ops Hub: the related operations app (nightly jobs, pages, access, time, stack, budget) |

**Names.** The platform is called **Flowmerce** (tagline: *Ecommerce in a Flow*). It was earlier called “Sutra”; treat the two as the same thing. Two stores are in scope: **Ridhi** (US Eastern time) and **CPC** (US Mountain time).

**Team.** Developers: Ashutosh Pandey and Aditya Kumavat. Project under Aryan Sarang.

---

## 1. Vision, principles and vocabulary

### 1.1 Vision

Flowmerce is one unified e-commerce platform built from **six core projects**. Each project solves a different business problem and is **standalone**. Together they aim to change how the business acquires customers, converts demand, delivers a good customer experience, makes decisions, and scales.

The five outcomes the platform is meant to move are: customer acquisition, conversion, customer experience, decision speed, and ability to scale (see section 7).

### 1.2 Principles that apply everywhere

1. **Projects are standalone.** No project must wait for another one to operate. Data can be shared between projects, but sharing data does not make one project depend on another.
2. **Two different relationships.** The *build order* (section 4) is the planned implementation sequence. The *information flows* (section 5) show which data helps which project decide better. Never present information flows as project dependencies.
3. **Approval first.** Any action that changes something on a platform (ad budgets, live pages, theme pushes, replacement orders, product placement) needs a person’s approval. Suggestions are free; changes are gated.
4. **Honesty about data.** Do not claim a precise parcel location or delay reason when the carrier does not supply it. A *suspected* lost parcel is an alert, not a confirmed loss. Mark proposed or unverified integrations as “proposed” or “to confirm”.
5. **No invented results.** No guaranteed rankings, AI citations, traffic, revenue or percentage gains. Outcomes are *intended* and are evaluated after deployment. Example numbers in demos are labelled hypothetical.
6. **Measure, don’t assume.** Changes are checked against a control group or an earlier period.
7. **Reuse before rebuilding.** Use the platform’s own tools where they work (for example Shopify search and reports) and add what is missing.

### 1.3 Vocabulary

| Term | Meaning |
| --- | --- |
| CRO | Conversion Rate Optimization |
| AEO / GEO / LLMO | Answer-engine, generative-engine and LLM optimization: making content understandable and usable by AI-assisted search |
| LPV / ATC | Landing page views / add to cart |
| CTR / CPC / CVR / CPA / ROAS | Click-through rate / cost per click / conversion rate / cost per acquisition / return on ad spend |
| ERP | The main e-commerce ERP that each finished project is integrated into |
| A/B test | A controlled experiment with one variable, a comparison group and a pre-chosen success metric |

---

## 2. Platform structure

### 2.1 The projects at a glance

| Build position | Project | One-line purpose |
| --- | --- | --- |
| 1 | SEO & Blog Content | Help customers discover us through organic search and AI-assisted search |
| 2 | Shipping & Customer Experience | Shipment visibility, exception alerts and the full return and replacement experience |
| 3 | Meta & Google Ads Performance | Ad performance, controlled experiments and approved, evidence-based budget decisions |
| 4 | Creative Strategist | Research, concepts and briefs, tested and improved in a repeatable loop |
| 5 | Landing Page Automation | Brand-consistent, Shopify-ready campaign pages |
| 6 | Conversion Rate Optimization (CRO) | Improve the journey from landing-page entry to conversion |
| Future scope | Merchandising Automation | A possible next stage: season sales, inventory, campaign products, colours, mix-and-match |

**Baseline status** (as shown on the progress page; the only place statuses appear): SEO & Blog Content and Shipping & Customer Experience are in **Prototype testing (step 5 of 10)**. Meta & Google Ads, Creative Strategist, Landing Page Automation, CRO and Merchandising are **Not started**.

### 2.2 Grouping and links

- **Standalone, no links:** SEO & Blog Content; Shipping & Customer Experience.
- **Advertising pair:** Meta & Google Ads ↔ Creative Strategist. Ad results inform creative; Creative’s variants are tested through the ads project.
- **Pages pair:** Landing Page Automation ↔ CRO. Conversion insights inform future pages and approved updates.
- **Creative → Landing Pages:** message, offer and style flow forward. **Landing Pages → Ads and Creative:** conversion data flows back.
- **Merchandising Automation:** future scope; links to other projects are to be confirmed.

---

## 3. The projects in detail

### 3.1 SEO & Blog Content

**Focus areas:** Organic discovery · AI-search visibility

**Purpose:** Help customers discover us through organic search and AI-assisted search.

**Today:**
- Manual content planning
- Disconnected SEO tools
- Customer-question gaps unclear
- AI-answer visibility unknown

**Intended platform:**
- Stronger organic discovery
- Visible in AI answers
- Fact-checked FAQs and content
- Search linked to conversions

**Flow (what it does, step by step):**

1. **Research demand**: Keywords, intent, real questions
   - Find organic search and relevant keyword opportunities
   - Research search intent from genuine customer questions
2. **Plan content**: Topics, pages, FAQs
   - Generate blog topics aligned to brand and products
   - Plan SEO-focused product pages, landing pages and blogs
   - Plan FAQs that directly answer customer questions
3. **Create and fact-check**: Clear, structured, reliable
   - Write fact-checked, reliable content
   - Structure information so search engines and AI systems can understand it
4. **Optimize for AI search**: AEO, GEO, LLMO
   - Apply AEO, GEO and LLMO principles where relevant
   - Aim for visibility in AI-assisted search answers
5. **Score and publish**: Quality and relevance
   - Score existing and new blogs for quality and relevance
   - Manage blogs in one dashboard
6. **Track and improve**: Discovery to conversion
   - Track organic discovery and AI-search visibility
   - Connect search performance to engagement and conversions
   - Flag underperforming content with specific fixes

**Notes and limits:** Rankings, AI citations and traffic growth are not guaranteed.

**Inputs:**
- Brand and product information
- Search intent and customer questions
- Search Console data
- Existing blogs

**Outputs:**
- Keyword and blog priorities
- Drafts, FAQs and scores
- Recommendations
- Organic discovery reports

**Exists today → Information Extraction (being built) → Platform enables** (the middle column is titled “Information Extraction” in the deck):
- Exists today: SEO prototype; Search Console data; Existing blogs
- Information Extraction (being built): Search Console + Shopify links; FAQ and structured content; AI-search tracking; ERP integration
- Platform enables: Organic discovery; AI-search visibility; Content tied to conversions

**Connects with:** Standalone. No other project waits for its data.
**Build position rationale:** Already in prototype. Its data is not needed by any other project, so it can mature on its own timeline.  
**Needs:** Nothing from other projects.  
**Passes on:** No other project waits for it.

### 3.2 Shipping & Customer Experience

**Focus areas:** Shipment visibility · Exceptions and alerts · Returns, refunds and replacements

**Purpose:** Shipment visibility, exception alerts and the full return and replacement experience.

**Today:**
- No single shipment view
- Delays hard to spot
- Unclear exception ownership
- Return status scattered

**Intended platform:**
- Shipments tracked centrally
- Early exception alerts
- Clear issue ownership
- Traceable returns, replacements

**Flow (what it does, step by step):**

1. **Track shipments**: Carrier APIs, tracking IDs
   - Connect supported delivery-partner APIs using tracking IDs
   - Show location, status and history as reported by the carrier
   - Highlight shipments without usable tracking
2. **Detect exceptions**: Not moving, stuck, delayed
   - Spot shipments not moving from dispatch: Jaipur warehouse, or Amazon fulfilment where applicable
   - Detect shipments stuck at one location beyond a configurable threshold
   - Explain the delay reason when the carrier provides it
3. **Raise critical alerts**: Inactivity, exceptions, suspected loss
   - Alert on prolonged inactivity and delivery exceptions
   - Flag suspected lost parcels: an alert, not a confirmed loss
4. **Returns and refunds**: Wrong product, returns, refunds
   - Manage reports of incorrect products delivered
   - Manage return requests and return status
   - Coordinate refunds under the applicable policy
   - Update return inventory through the existing integration
5. **Replace and deliver**: Replacement to doorstep
   - Generate replacement orders when authorized and supported
   - Track the replacement shipment through delivery
6. **Resolve and record**: Complaint to resolution
   - Track each case from complaint to resolution
   - Keep one record: order, return, replacement and outcome

**Notes and limits:** Location and delay reasons appear only when the carrier reports them. An operations prototype for inventory and order checks already exists and is not being rebuilt.

**Inputs:**
- Delivery-partner tracking data (supported APIs)
- Orders and tracking IDs
- Return and replacement requests
- Refund status
- Existing inventory or commerce integration

**Outputs:**
- Shipment status and history
- Exception and critical alerts
- Return and refund status
- Replacement orders
- Case record from complaint to resolution

**Exists today → Information Extraction (being built) → Platform enables** (the middle column is titled “Information Extraction” in the deck):
- Exists today: Operations prototype (built); Orders and tracking IDs; Jaipur warehouse, Amazon fulfilment
- Information Extraction (being built): Carrier API connections; Exception alerts; Returns and replacement workflow
- Platform enables: Shipment visibility; Faster issue resolution; Reliable customer experience

**Connects with:** Standalone. No other project waits for its data.
**Build position rationale:** An operations prototype already exists. The next focus is shipment tracking and customer experience, with no critical dependency in either direction.  
**Needs:** Nothing from other projects.  
**Passes on:** No other project waits for it.

### 3.3 Meta & Google Ads Performance

**Focus areas:** Performance · Experimentation · Evidence-based budget decisions

**Purpose:** Ad performance, controlled experiments and approved, evidence-based budget decisions.

**Today:**
- Time-consuming analysis
- Problems found late
- Budget calls need evidence

**Intended platform:**
- Evidence-based budget decisions
- Controlled A/B tests
- Approved, tracked optimizations
- Meta and Google together

**Flow (what it does, step by step):**

1. **Collect campaign data**: Meta and Google Ads
   - Monitor campaign, ad set, ad, audience and spend across Meta and Google Ads
   - Google Ads connection to be confirmed
2. **Diagnose performance**: Winners, losers, causes
   - Find underperformers and winners worth scaling
   - Diagnose possible causes, separating fact from hypothesis
3. **Design the experiment**: One hypothesis, one variable
   - Primary objective and hypothesis
   - Test variable and comparison group
   - Audience allocation and budget
   - A defined testing period with sufficient data
4. **Run the A/B test**: Creatives, audiences, pages, offers
   - Creatives: images, videos, hooks, formats, copy
   - Audiences: segments, targeting, prospecting vs retargeting
   - Landing pages: layout, content, product presentation, CTAs
   - Offers: promotions, incentives, how the offer is presented
   - One variable per test, unless a proper experimental design is used
5. **Compare results**: CTR, CPC, CVR, CPA, ROAS
   - Compare each variant against the comparison group
   - Judge on the primary metric chosen before launch
   - Metrics: CTR, CPC, CVR, CPA, ROAS
6. **Recommend and optimize**: Approved budget moves
   - Recommend budget, targeting and creative actions
   - Run approved actions from the platform
   - Log recommendations, approvals and results

**Notes and limits:** ROAS where relevant. No campaign change without approval.

**Inputs:**
- Meta campaign and spend data
- Google Ads campaign data (connection to be confirmed)
- Conversion tracking
- Budgets and targets
- Creative, page and offer variants

**Outputs:**
- Performance reports
- A/B test plans and results
- Prioritized recommendations
- Approved actions and history

**Exists today → Information Extraction (being built) → Platform enables** (the middle column is titled “Information Extraction” in the deck):
- Exists today: Meta and Google Ads accounts; Manual performance reviews
- Information Extraction (being built): Meta connection; Google Ads connection (TBC); A/B test tracking; Approval step
- Platform enables: Evidence-based budgets; Controlled experiments; Faster optimizations

**Connects with:** Works with Creative Strategist: ad results inform creative, and Creative’s variants are tested here.
**Build position rationale:** Third, because its campaign results are the input Creative Strategist uses.  
**Needs:** Meta and Google Ads account data and access.  
**Passes on:** Campaign performance for Creative Strategist.

### 3.4 Creative Strategist

**Focus areas:** Research · Concepts · Creative testing

**Purpose:** Research, concepts and briefs, tested and improved in a repeatable loop.

**Today:**
- Ad hoc creative ideas
- Not always performance-informed
- No repeatable loop

**Intended platform:**
- Repeatable creative loop
- Performance-informed concepts
- Full-funnel briefs
- Tested creative variants

**Flow (what it does, step by step):**

1. **Research** _[Research]_: Performance, trends, competitors
   - Analyze which creatives, hooks and angles perform
   - Research trends from approved sources
   - Research competitors in our category
   - Research big D2C brands and how they attract customers
2. **Insight** _[Research]_: Customer interests, angles
   - Use search intent to find customer interests
   - Turn audience and customer-review insights into creative angles
3. **Concept and hook** _[Create]_: Ideas, hooks, messaging
   - Generate concepts, hooks and messaging
4. **Brief** _[Create]_: Top, middle, bottom of funnel
   - Write briefs for top, middle and bottom of funnel
   - Link briefs to landing pages
5. **Creative test** _[Learn]_: Variants and hypothesis
   - Creative writes the variants and the hypothesis
   - Meta & Google Ads runs and measures the A/B test
6. **Learnings** _[Learn]_: Feed the next round
   - Test results feed the next research round

**Inputs:**
- Ad performance
- Search intent
- Audience and review insights (proposed)
- Brand guidelines
- Trends
- Competitor and D2C brand research

**Outputs:**
- Concepts
- Hooks
- Briefs
- Funnel content plans
- Creative variants for testing

**Exists today → Information Extraction (being built) → Platform enables** (the middle column is titled “Information Extraction” in the deck):
- Exists today: Ad performance data; Brand guidelines; Competitor references
- Information Extraction (being built): Ads performance feedback; Research and brief generation
- Platform enables: Performance-informed briefs; Repeatable creative loop

**Connects with:** Gets campaign performance from Meta & Google Ads, and hands message, offer and style to Landing Pages.
**Build position rationale:** Fourth, because it relies on real ad performance from Meta & Google Ads.  
**Needs:** Campaign performance from Meta & Google Ads.  
**Passes on:** Message, offer and style for Landing Pages.

### 3.5 Landing Page Automation

**Purpose:** Brand-consistent, Shopify-ready campaign pages.

**Today:**
- Manual page design
- Built per campaign

**Intended platform:**
- Pages from a brief
- On-brand, Shopify-ready
- Live only after approval
- Conversions tracked

**Flow (what it does, step by step):**

1. **Understand the brief**: Brand, product, references
   - Understand brand, product and brief
   - Study supplied references without copying them
2. **Design and build**: Shopify-ready code
   - Design the page and generate Shopify-compatible code
3. **Validate**: Content, links, mobile
   - Validate content, links and mobile layout
4. **Preview and approve**: Nothing live without approval
   - Preview, then approve before anything goes live
5. **Deploy**: Prior version kept
   - Deploy the approved page and keep the prior version
6. **Measure and improve**: LPV, ATC, purchases
   - Track LPV, ATC, purchases and conversion rates
   - Diagnose, recommend, approve, implement, measure again

**Inputs:**
- Brand and product information
- References
- Objective
- Creative assets

**Outputs:**
- Designed page and preview
- Shopify code
- Approved deployment
- Tracking

**Exists today → Information Extraction (being built) → Platform enables** (the middle column is titled “Information Extraction” in the deck):
- Exists today: Brand and product info; Creative assets; Shopify store
- Information Extraction (being built): Brief-to-page generation; Preview and approval; Conversion tracking
- Platform enables: Fast, on-brand campaign pages

**Connects with:** Gets message, offer and style from Creative; CRO insights inform future pages.
**Build position rationale:** Fifth, because it needs the creative output to build a matching page.  
**Needs:** Message, offer and style from Creative.  
**Passes on:** Conversion data back to Meta & Google Ads and Creative.

### 3.6 Conversion Rate Optimization (CRO)

**Focus areas:** Page Optimization · Traffic Tracking · Customer Experience

**Purpose:** Improve the journey from landing-page entry to conversion.

**Today:**
- Guesswork on conversion gaps
- Drop-off reasons unclear

**Intended platform:**
- Friction pinpointed
- Traffic linked to pages
- Tested page improvements
- Better customer journey

**Flow (what it does, step by step):**

1. **Track traffic** _[Traffic Tracking]_: Source and campaign context
   - Connect traffic source and campaign context to page performance
2. **Map the journey** _[Customer Experience]_: Entry to conversion
   - Understand how visitors move through key pages
   - Visitor-tracking source to be confirmed
3. **Find friction** _[Customer Experience]_: Where visitors drop off
   - Find friction from landing-page entry to conversion
   - Separate page, product, pricing, audience and journey issues
4. **Compare pages** _[Page Optimization]_: What stronger pages do
   - Compare similar pages, templates and campaigns
   - Identify what stronger pages do better
   - Show confidence, or flag insufficient evidence
5. **Test improvements** _[Page Optimization]_: Prioritized experiments
   - Recommend prioritized experiments
   - Changes go live only with approval
6. **Measure impact** _[Page Optimization]_: Before vs after
   - Compare before and after approved changes

**Notes and limits:** CRO explains why visitors do or do not convert. It is not a purely visual redesign.

**Inputs:**
- Page performance and structure
- Traffic and campaign context
- Pricing and inventory
- Visitor-behaviour data (source to be confirmed)

**Outputs:**
- Page comparisons
- Friction points with confidence
- Reusable patterns
- Experiments

**Exists today → Information Extraction (being built) → Platform enables** (the middle column is titled “Information Extraction” in the deck):
- Exists today: Page performance data; Traffic and campaign context
- Information Extraction (being built): Page comparison; Visitor tracking (TBC); Approved experiments
- Platform enables: Less friction; Evidence on drop-offs

**Connects with:** Works with Landing Page Automation: insights inform future pages and approved updates.
**Build position rationale:** Sixth, after Landing Page Automation, because it improves the pages that exist.  
**Needs:** Page performance and traffic context.  
**Passes on:** Insights for Landing Page Automation.

### 3.7 Merchandising Automation (FUTURE SCOPE)

**Focus areas:** Future scope

**Purpose:** A possible next stage: season sales, inventory, campaign products, colours, mix-and-match.

**Today:**
- Manual product picks
- Sales reviewed by hand
- Stock not tied to placement

**Intended platform:**
- Data-led collection order
- Stock-aware placement
- Bundles from real orders
- Search gaps closed

**Flow (what it does, step by step):**

1. **Analyse season sales**: Previous season, ABC grades
   - Analyse previous season sales
   - Grade products A, B or C by revenue share and spot seasonal patterns
2. **Review inventory**: By inventory type, cover
   - Review inventory by type
   - Check days of cover, and flag low and overstocked products
3. **Pick campaign products**: Per marketing campaign
   - Suggest products for each marketing campaign
   - Rank on conversion, margin and stock, with the campaign calendar
4. **Suggest colours**: What to feature
   - Suggest colours to feature
   - Use colour-level sales and stock by variant
5. **Mix and match**: Combinations that sell
   - Suggest mix-and-match combinations
   - Use co-purchase rates, and check margin after any bundle discount
6. **Approve and measure**: A person decides
   - A person approves every suggestion
   - Compare with a control group or an earlier period

**Notes and limits:** Future scope. Not operational and not scheduled for immediate implementation. It builds on Shopify’s own search, recommendation and reporting tools rather than replacing them.

**Inputs:**
- Previous season sales
- Inventory by type
- Campaign plans
- Product, colour and cost data
- Search and view data (to confirm)

**Outputs:**
- Ranked collections
- Campaign product suggestions
- Colour suggestions
- Bundle and mix-and-match sets
- Search fixes
- Impact measurement

**Exists today → Information Extraction (being built) → Platform enables** (the middle column is titled “Information Extraction” in the deck):
- Exists today: Previous season sales; Inventory by type; Shopify store data
- Information Extraction (not scheduled, future scope): Not scheduled
- Platform enables: Campaign product suggestions; Colour and mix-and-match ideas; Measured results

**Connects with:** Links to other projects are to be confirmed.
**Build position rationale:** Last: future scope, after the core projects.  
**Needs:** Previous season sales and inventory data.  
**Passes on:** To be confirmed.

---

## 4. Build order and how projects are joined

The intended implementation sequence is below. It is a **plan for building**, not an operating dependency: every project is standalone.

| Step | Project | Why here | Needs | Passes on |
| --- | --- | --- | --- | --- |
| 1 | SEO & Blog Content | Already in prototype. Its data is not needed by any other project, so it can mature on its own timeline. | Nothing from other projects. | No other project waits for it. |
| 2 | Shipping & Customer Experience | An operations prototype already exists. The next focus is shipment tracking and customer experience, with no critical dependency in either direction. | Nothing from other projects. | No other project waits for it. |
| 3 | Meta & Google Ads Performance | Third, because its campaign results are the input Creative Strategist uses. | Meta and Google Ads account data and access. | Campaign performance for Creative Strategist. |
| 4 | Creative Strategist | Fourth, because it relies on real ad performance from Meta & Google Ads. | Campaign performance from Meta & Google Ads. | Message, offer and style for Landing Pages. |
| 5 | Landing Page Automation | Fifth, because it needs the creative output to build a matching page. | Message, offer and style from Creative. | Conversion data back to Meta & Google Ads and Creative. |
| 6 | Conversion Rate Optimization (CRO) | Sixth, after Landing Page Automation, because it improves the pages that exist. | Page performance and traffic context. | Insights for Landing Page Automation. |
| Future scope | Merchandising Automation | Last: future scope, after the core projects. | Previous season sales and inventory data. | To be confirmed. |

Connector labels used on the build-order diagram: SEO → Shipping (“then”), Shipping → Meta & Google Ads (“then”), Meta & Google Ads → Creative (“campaign performance”), Creative → Landing Pages (“message, offer, style”), Landing Pages → CRO (“page performance”), CRO → Merchandising (“future scope”, dashed). A dashed return path shows **conversion data returning** from Landing Pages to Meta & Google Ads and Creative.

### 4.1 Rules for joining projects

- **One project at a time.** Each project completes all ten steps, including tested ERP integration, before another project relies on its output.
- **Connect only what is critical.** SEO and Shipping run standalone. A link exists only where one project cannot work without another’s output.
- **Plan the order around data.** Meta & Google Ads comes first of the linked projects, because Creative uses its results, and Landing Pages use the creative output.

### 4.2 Path of every project into the ERP

1. **Prototype**: A small working version proves the idea on real data.
2. **Tested prototype**: Tested with the team against known results.
3. **MVP**: The first version the team can use day to day.
4. **Tested MVP**: Run in real conditions; changes applied and retested.
5. **Main e-commerce ERP**: Integrated and debugged, linking to another project only where critical.

---

## 5. Information flows

Flow of data through four layers: **Sources → Data signals → Projects (agents) → Decisions and outputs**. This is information movement, not project dependency.

**Sources:** Google Search Console; Customer reviews & questions; Shopify store; Meta Ads · Google Ads; Landing pages & site tracking; Delivery-partner APIs.

| Data signal | Source | Used by | Status |
| --- | --- | --- | --- |
| Queries, impressions, clicks, landing-page performance | Google Search Console | SEO & Blog | Confirmed in the project specification |
| Customer questions | Customer reviews & questions | SEO & Blog | Confirmed in the project specification |
| Product data & descriptions | Shopify store | SEO & Blog, Landing Pages | Confirmed in the project specification |
| Reviews & feedback | Customer reviews & questions | Creative, CRO, Shipping & CX | Proposed, to be validated |
| Campaign performance & spend | Meta Ads · Google Ads | Meta & Google Ads, Creative | Confirmed in the project specification |
| Creative experiment results | Meta Ads · Google Ads | Creative, Meta & Google Ads | Confirmed in the project specification |
| Traffic & conversions (LPV, ATC, purchases) | Landing pages & site tracking | CRO, Landing Pages, Meta & Google Ads, Creative | Confirmed in the project specification |
| Orders & tracking IDs | Shopify store | Shipping & CX | Confirmed in the project specification |
| Tracking events & exceptions | Delivery-partner APIs | Shipping & CX | Confirmed in the project specification |
| Return & replacement outcomes | Shopify store | Shipping & CX | Proposed, to be validated |

**Decisions and outputs per project:**

- **SEO & Blog** → Content, FAQ & AI-search opportunities
- **Creative** → Concepts, hooks & briefs
- **Meta & Google Ads** → Budget moves & A/B test recommendations
- **Landing Pages** → Campaign landing pages
- **CRO** → Friction fixes & page experiments
- **Shipping & CX** → Alerts & resolution workflows

Notes: Google Ads data has a connection **to be confirmed**. “Reviews & feedback” and “Return & replacement outcomes” are **proposed** flows.

---

## 6. The ten-step delivery process and progress tracking

Every project, with no exceptions, goes through the same ten steps. No project skips a stage.

1. **Information collection**: Gather the business rules, data sources, questions the project must answer and the people who own them.  
   *Done when:* A written brief that the project owner has confirmed.
2. **Understanding platform**: Study how the source platform works: its data, limits, terms and how it connects to the rest of the business.  
   *Done when:* Documented findings on what can be read, and what can be changed.
3. **Access**: Obtain the accounts, permissions and keys the project needs, with approval limits for any action that changes something.  
   *Done when:* Working, permissioned access with clear owners.
4. **Prototype build**: Build a small working version that proves the idea against real data.  
   *Done when:* A prototype that runs end to end on real data.
5. **Prototype testing**: Test the prototype with the team and compare its output against known results.  
   *Done when:* A list of what works, what does not, and what to change.
6. **MVP build**: Build the first version the team can use day to day, including its dashboard.  
   *Done when:* A usable MVP with the agreed dashboard views.
7. **MVP testing**: Run the MVP in real conditions with the people who will use it.  
   *Done when:* Owner sign-off, or a clear list of fixes.
8. **Changes**: Apply what testing showed: fixes, missing features and tuning.  
   *Done when:* All agreed changes made and retested.
9. **ERP integration**: Connect the project to the main e-commerce ERP, linking to another project only where a dependency is critical.  
   *Done when:* The project runs inside the main ERP.
10. **Debugging**: Resolve issues found after integration and stabilise the project for daily use.  
   *Done when:* Stable operation with no open blocking issues.

**Progress page behaviour (in the deck):**
- Shows each project against the ten steps, with a status (Not started, a step name, or Complete) and progress within the current step.
- A user can play through the ten steps, select a project to see its own flow on the steps, and (with “Edit progress” switched on) change a project’s current step, status and in-step progress.
- Overall progress counts completed steps plus progress inside the current step, across the six core projects.
- Edits are **local to the viewer’s browser** (no server, no sign-in). Baseline is restorable with “Reset”. Statuses must appear only on this page and nowhere else in the deck.

---

## 7. Expected business outcomes

These are intended outcomes to evaluate after deployment. No financial returns or percentage improvements are assumed.

- **Better customer acquisition**: Organic and AI-search discovery, performance-informed creative and tested ad decisions. *(projects: SEO & Blog, Meta & Google Ads, Creative)*
- **Improved conversion**: Faster branded pages and evidence on where visitors drop off. *(projects: Landing Pages, CRO, Meta & Google Ads)*
- **Reliable customer experience**: Shipment visibility, early exception alerts and traceable returns and replacements. *(projects: Shipping & CX, CRO)*
- **Faster decisions**: Prioritized, evidence-based recommendations replace manual reviews and guesswork. *(projects: Meta & Google Ads, CRO, Shipping & CX, SEO & Blog)*
- **Ability to scale**: Less manual effort per campaign, page and order as the business grows. *(projects: SEO & Blog, Shipping & CX, Meta & Google Ads, Creative, Landing Pages, CRO)*

---

## 8. Merchandising Automation (future scope) in full

**Status:** a possible next stage after the six core projects. Not operational and not scheduled for immediate implementation. It builds on Shopify’s own search, recommendation and reporting tools rather than replacing them: Flowmerce adds scoring on margin and stock together, business rules, approvals and measurement.

### 8.1 What it improves

- **Product discovery and visibility.** Customers see the products most likely to sell first, not whatever was added last. *How:* Scores every product on revenue grade, conversion, margin, stock and season, then proposes a collection order. *Example:* A drawer organizer with strong conversion sits on page 3. It is proposed for the top row. *Metric:* Share of product views reaching high-potential products.
- **Product collection organization.** Group products by shared attributes such as material, function or collection, and keep each collection’s order current. *How:* Reviews each collection on a schedule, then proposes which products lead and which step back. *Example:* “Kitchen Organizers” is reviewed weekly: trending items move up, stale ones step back. *Metric:* Collection conversion rate.
- **Cross-selling and product bundling.** Offer relevant add-ons and bundles at the moment customers decide. *How:* Finds pairs in real orders, checks relevance, compatibility and margin after discount, then proposes bundles and “frequently bought together” items. *Example:* Storage containers and drawer dividers shown with a kitchen organizer. *Metric:* Attach rate and average order value.
- **On-site search experience.** Close the gap between what customers type and what the catalog says. *How:* Reads zero-result searches, finds the cause (wording, a missing attribute, or a real catalog gap) and proposes the fix. *Example:* “kitchen storage rack” should also lead to “kitchen organizers”. *Metric:* Zero-result search rate.
- **Inventory-aware recommendations.** Do not push what cannot be bought, and do not let slow stock sit unseen. *How:* Uses stock and days of cover to step products back early, and pairs slow stock with strong sellers. *Example:* A nearly sold-out item steps back while in-stock alternatives lead the collection. *Metric:* Share of top-row views on in-stock products.
- **Sales conversion and profit margins.** Balance what sells with what earns. *How:* Ranks on gross margin as well as sales, and checks every bundle or promotion against a margin floor. *Example:* Between two similar items, the one with a healthy margin and good conversion leads. *Metric:* Conversion rate and gross margin.

### 8.2 Features

#### A. Smart Product Ranking
Rank every product on measurable signals, then propose which products lead each collection.

- Grade products A, B or C by revenue share (ABC analysis) and use the grade as a signal
- Blend conversion rate, gross margin, sell-through and availability with seasonal demand
- Propose the first-row products for each collection, by business objective
- Surface high-potential, low-visibility products: good conversion, few views
- Give new products a minimum exposure period before judging them

*Example:* In “Kitchen Organizers”, a drawer organizer with strong conversion and a healthy margin sits on page 3. The ranking proposes moving it into the top row.
*Industry basis:* ABC analysis: A-grade products drive most revenue and deserve stock priority and prominent placement. Grades are re-checked as sell-through and margin change.

#### B. Automated Product Bundling
Learn from past orders which products go together, and protect margin while doing it.

- Find products bought together in past orders (co-purchase rate)
- Propose bundles of items used together, items from one category, and value packs
- Pair slow-moving stock with strong sellers to lift its demand
- Check margin after the bundle discount before proposing it
- Recommend complements on product pages, in the cart and at checkout, within a limit on prompts

Guardrails: Relevant and compatible items only; One recommendation block per step; Margin floor holds after the discount

*Example:* A kitchen organizer is recommended alongside storage containers and drawer dividers.
*Industry basis:* Price bundling and cross-selling: bundles lift order value and can move slower stock, but can erode margin or limit choice. Relevance is what makes a cross-sell feel helpful.

#### C. Inventory-Aware Merchandising
Keep what is visible aligned with what can actually be bought.

- Watch stock and days of cover for each product and variant
- Step products back when cover falls below a configurable threshold, before they sell out
- Keep out-of-stock products out of the top rows; hide them only under a business rule
- Put in-stock, healthy-margin, high-converting products in the lead
- Alert the team early, and suggest a bundle or promotion for overstock

*Example:* A bestseller is down to a few days of cover. It steps back from the first row until restocked, and in-stock products with good margins take its place.
*Industry basis:* Inventory management: low-stock thresholds and alerts let teams act before a stockout, while overstock adds holding costs.

#### D. Smart Search Optimization
Close the gap between the words customers type and the words in the catalog.

- Rank the most common search terms, with their conversion
- List zero-result searches and find the cause: wording gap, missing tag or title, or true catalog gap
- Propose synonyms, mappings, and title and tag edits
- Pass true catalog gaps to buying: customers want something we do not sell
- Rely on the store’s own search for typo tolerance and predictive search

*Example:* Searching “kitchen storage rack” should also help customers discover relevant “kitchen organizers”.
*Industry basis:* Shopify storefront search already includes predictive search and typo tolerance, so the gap Flowmerce fills is vocabulary, attributes and catalog coverage. Synonym controls are to be confirmed in the store’s search settings.

#### E. Seasonal Merchandising
Prepare collections before demand rises, using past patterns and the campaign calendar.

- Build a seasonality index per category from past years of orders
- Mark campaign and festival windows from a shared calendar
- Flag one-off spikes, such as a single campaign, so they do not distort the pattern
- Propose collection and campaign product changes ahead of the window, with a stock check
- With under about two years of history, plan from the calendar and team input, not from forecasts

*Example:* Gifting and decor products have historically sold more before festival periods, so a festive collection is proposed ahead of time, once stock is confirmed.
*Industry basis:* Demand forecasting: seasonality is driven by holidays, weather and events such as wedding or festival season. Trend projection works best with about two years or more of history, and one-off anomalies must be accounted for.

#### F. Low-Performing Product Detection
Find products that are not working, and try the gentler fixes first.

- Find products with traffic but few sales, and products with falling demand or poor margin
- Place each on a traffic × conversion map with its ABC grade and days of cover
- Propose an action ladder: improve the page, raise visibility, bundle with A or B items, run a timed promotion, reduce exposure
- Wait for enough views and orders before judging a product
- Only a person can mark a product for discontinuation

*Example:* A decor shelf gets plenty of views but few orders. The proposal is to review its page and test a promotion before reducing its exposure.
*Industry basis:* ABC analysis: C-grade products need not be dropped. Bundling them with A or B items, giving them more visibility, or discounting them can recover value.

**Rule:** A product is never removed automatically because of low sales alone. Traffic, inventory and business rules are checked first.

### 8.3 Scoring and rules

1. **Grade every product A, B or C by revenue share (ABC analysis).** 80 / 15 / 5 is a widely used guideline, not a fixed rule, so thresholds are adjustable. Re-grade as sell-through and margin change.

   - Grade A: Keep in stock: protect availability; Feature in top rows and on the homepage; Protect margin; avoid deep discounts
   - Grade B: Monitor: items move between A and C; Re-grade as sell-through and margin change; Raise visibility if conversion is strong
   - Grade C: Bundle with A or B items to lift demand; Give more visibility before judging; Test a timed promotion; never remove automatically

2. **Score on measurable signals** (weight × signal, added up; weights follow the business objective such as grow sales, protect margin, seasonal push):

   - Revenue grade: Share of revenue and its A, B or C grade
   - Conversion rate: Orders ÷ visits, for the product or collection
   - Gross margin: (Revenue − cost of goods) ÷ revenue
   - Sell-through and velocity: How fast stock is selling, by variant
   - Availability: Units and days of cover
   - Seasonal index: Expected demand for the coming weeks

3. **Rules always win over the score:**

   - Out of stock: Never in the top rows
   - Low stock: Steps back below the cover threshold
   - Margin floor: No bundle or promotion below it
   - Pinned products: Campaign or brand-critical items stay put
   - Minimum evidence: No judgement before enough views and orders
   - New products: Minimum exposure period first
   - Approval: Nothing goes live without a person

### 8.4 Data sources

| Data | What | Availability | How |
| --- | --- | --- | --- |
| Product catalog | Products, variants, prices, collections, tags | Platform API or report | Shopify Admin API |
| Orders and line items | What was bought, and with what | Platform API or report | Admin API. Complete history may need the read_all_orders scope. |
| Inventory and stock availability | Units per product and location | Platform API or report | Admin API inventory levels, kept in sync with webhooks |
| ABC grades by product | Revenue share and grade | Platform API or report | Shopify has an ABC analysis by product report. Flowmerce can also calculate it from orders. |
| Historical sales and seasonal trends | Built from past orders | Platform API or report | Derived from order history. More reliable with about two years or more. |
| Product prices and profit margins | Margin needs a cost for every product | Needs extra setup or permissions | Shopify profit reports cover items with a cost per item recorded at the time of sale. Keep costs current, or upload them. |
| Customer search queries | Including searches with no results | Needs extra setup or permissions | Not part of standard order and product data. Needs store search analytics or site tracking. To confirm. |
| Product views and conversion | Views, add-to-cart and purchases by product | Needs extra setup or permissions | Needs analytics access, such as store analytics or GA4. Conversion rate is orders ÷ visits. |
| Campaign and festival calendar | When promotions and seasons start | Needs extra setup or permissions | A shared calendar from the marketing team. It is not in any platform API. |
| Amazon and Etsy listings | Listings, prices, availability | Where supported | Only where a supported integration is available. Not confirmed for this project. |

### 8.5 Automation workflow (eight steps)

*In the MVP, no change reaches a store without human approval.*

1. **Data Collection** _[Automated]_: Catalog, orders, stock
   - Pull products, prices, inventory and orders through supported platform APIs
   - Keep stock and orders in sync with webhooks
   - Bring in search, view and cost data only where it is available
2. **Data Cleaning** _[Automated]_: Match and tidy
   - Match products and variants, and treat bundles correctly
   - Remove duplicates and test orders
   - Flag one-off spikes, and flag missing costs or stock data for a person
3. **Performance Analysis** _[Automated]_: Metrics per product
   - Calculate revenue share, conversion, margin, sell-through and days of cover
   - Find co-purchased products and failed searches
4. **Product Scoring** _[Automated]_: Metrics plus rules
   - Grade products A, B or C and score them on measurable signals
   - Apply the business rules: stock thresholds, margin floor, pinned products, minimum evidence
5. **Merchandising Recommendations** _[Automated]_: Action, reason, impact
   - Draft collection order, bundles, search fixes and low-performer actions
   - Attach the reason, estimated impact, confidence and the rules it passed
6. **Human Approval** _[Human approval]_: A person decides
   - A person reviews every recommendation: approve, edit or dismiss
   - Ranking and bundles go to marketing; pricing and reduced exposure go to the owner
   - Nothing is applied before this step
7. **Platform Updates** _[After approval]_: Only what was approved
   - Apply approved changes through supported APIs
   - Keep the previous version so a change can be undone
8. **Performance Monitoring** _[Automated + review]_: Did it help?
   - Track conversion, revenue and margin after each change
   - Compare with a control group or an earlier period
   - Feed accepted and dismissed recommendations back into scoring

### 8.6 AI and technology

- **Python:** cleaning, ABC grading, scoring and co-purchase analysis.
- **PostgreSQL (SQL):** products, orders, stock snapshots, scores, recommendations, approvals and outcomes.
- **APIs and webhooks:** Shopify Admin API and webhooks keep orders, products and stock in sync; other platforms only where supported.
- **Rule-based automation:** stock thresholds, margin floor, pinned products, minimum evidence.
- **Machine learning:** demand forecasting and recommendations, only with enough history, validated on held-out data first.
- **LLMs:** interpret search wording, draft titles, tags and synonyms for review, and explain each recommendation in plain language.

Decision pipeline: **numbers decide** (metrics and validated algorithms) → **rules constrain** → **an LLM explains** → **a person approves**. An LLM alone is not used to forecast demand or optimize rankings.

### 8.7 Conceptual dashboard

Top-performing products; products recommended for higher visibility; low-stock alerts (with days of cover); frequently purchased combinations; zero-result searches (with cause); collection performance; conversion-rate and gross-margin trend; recommended actions, each with estimated impact, confidence and the rules it passed, and Approve / Dismiss.

### 8.8 Example scenario (store selling kitchen organizers and home decor; all numbers hypothetical)

1. **Analyze the store**: Import products, orders, stock and costs. Grade products A, B or C, and calculate conversion, margin and days of cover.
2. **Find the winners**: Spot high-margin kitchen organizers with good conversion rates. Check visibility: some A-grade items sit low in their collection.
3. **Find the pairs**: Storage containers are frequently purchased with organizers. Hypothetical: about 1 in 3 organizer orders also includes containers.
4. **Suggest a bundle**: Propose organizer + storage containers + drawer dividers. Checks: items are compatible, stock is sufficient, margin holds after the discount. Pair one slow-moving C-grade item with the bundle to lift its demand.
5. **Catch failed searches**: Detect searches that return no relevant products. Hypothetical: “kitchen storage rack”, “drawer separator”. Classify each: wording gap, missing tag, or true catalog gap.
6. **Fix search**: Propose the synonym: kitchen storage rack → kitchen organizers. Propose title and tag edits for the matching products. Pass real catalog gaps to buying.
7. **Reorder the collection**: Propose an order from the chosen objective and available stock. Low-stock items step back; in-stock, healthy-margin items lead; pinned items stay.
8. **Approve and measure**: A person approves the changes. Compare conversion, revenue and margin with a control group or an earlier period. Keep, adjust or roll back based on what was measured.

### 8.9 Expected benefits and how each is measured

- **Reduced manual merchandising work**: measured by Hours per week spent re-sorting collections and building bundles by hand.
- **Improved product discovery**: measured by Share of product views reaching high-potential products, and the zero-result search rate.
- **More relevant cross-selling**: measured by Attach rate, average order value (order revenue ÷ orders), and recommendation click-through.
- **Better inventory-aware placement**: measured by Share of top-row views on in-stock products, and stockout days for top sellers.
- **Faster identification of underperformers**: measured by Time from a product slipping to it being flagged.
- **Improved conversion opportunities**: measured by Online store conversion rate (orders ÷ visits) against a control group or an earlier period.
- **More consistent merchandising decisions**: measured by Share of decisions that follow the agreed scores and rules.

Actual impact must be measured through experiments and performance tracking against a control group or an earlier period. Benefits are potential, not promised.

### 8.10 MVP plan

**Phase 1: Rule-Based MVP** (gate: Human approval before any change)
- Import product and order data
- Calculate product performance metrics, including ABC grade, margin and days of cover
- Generate collection-order recommendations
- Flag low-stock and low-performing products
- Recommend basic product bundles, with a margin check
- Display recommendations in a dashboard
- Require human approval before making changes
*Done when:* Recommendations match the team’s own judgement on a sample of collections, and the approval flow works end to end.

**Phase 2: Intelligent Automation** (gate: Approved changes applied through supported APIs)
- Add search-query analysis and synonym mapping
- Automate approved merchandising updates through supported APIs
- Add configurable business rules and notifications
- Track recommendation acceptance and outcomes
*Done when:* Approved changes apply cleanly and can be undone, and each one is measured against a control.

**Phase 3: Advanced AI** (gate: Only on validated performance data)
- Add machine-learning-based recommendations
- Introduce demand forecasting and seasonal analysis
- Improve product ranking using validated performance data
- Add feedback loops and controlled experiments
*Done when:* A model beats the rule-based baseline on held-out data before it is used. The rules stay on as a safety layer.

### 8.11 Sources and limits

Practices were checked against Shopify blog articles (read in this project):

- Ecommerce Merchandising: What It Is and Strategies: Four components of merchandising, curation, predictive search and recommendations. https://www.shopify.com/blog/ecommerce-merchandising
- Price Bundling: How Price Bundling Helps Increase Sales: Bundle types, benefits for order value and slow stock, and the margin risk. https://www.shopify.com/blog/product-bundling
- Cross Selling: Definition, Examples, and Strategies: Where cross-sells appear, and why relevance, prompt limits and compatibility matter. https://www.shopify.com/blog/cross-selling
- ABC Analysis: Categorize and Optimize Inventory: A, B and C grades by revenue share, and what to do with each grade. https://www.shopify.com/blog/abc-analysis
- Demand Forecasting: Methods and Retail Examples: Seasonality drivers, trend projection and how much history it needs. https://www.shopify.com/blog/demand-forecasting
- Inventory Management: Low-stock thresholds, safety stock and alerts. https://www.shopify.com/blog/inventory-management
- What Is Gross Margin?: Gross margin definition, used for the margin signal and the margin floor. https://www.shopify.com/blog/gross-margin
- Ecommerce Conversion Rate: Conversion rate as orders ÷ visits, and how tools name it. https://www.shopify.com/blog/ecommerce-conversion-rate

Only Shopify pages could be read. Amazon and Etsy integration details, Shopify developer API limits, and store-specific search and analytics access were **not verified**.

---

## 9. Decisions already made, and open items

### 9.1 Decisions made

- Platform renamed **Flowmerce**; tagline **Ecommerce in a Flow**.
- SEO became **SEO & Blog Content**, with organic discovery and AI-search visibility (AEO, GEO, LLMO) as its two central goals.
- Shipping became **Shipping & Customer Experience**: focus on shipment visibility, exception detection, returns, refunds and the full replacement experience. An operations prototype for inventory and order checks already exists and is **not** being rebuilt; inventory and general order management are not primary objectives (only return-inventory for the returns process).
- Ads module became **Meta & Google Ads Performance**, with controlled A/B testing (creatives, audiences, landing pages, offers) inside its flow.
- **CRO = Conversion Rate Optimization**, subtitle “Page Optimization · Traffic Tracking · Customer Experience”.
- **Creative Strategist** was reviewed and updated: subtitle “Research · Concepts · Creative testing”; a six-step loop; Creative writes variants and hypothesis, the ads project runs and measures the test; audience and review insights added (data source proposed).
- **Build order:** SEO → Shipping → Meta & Google Ads → Creative → Landing Pages → CRO → Merchandising (future scope, last).
- Merchandising Automation is **future scope**, not a current priority.
- Repeated status labels were removed everywhere except the progress page.
- The deck has a reversible visual theme (Refined default, Original restorable).

### 9.2 Open items and “to confirm”

- Google Ads connection and data access.
- GA4 or Microsoft Clarity for conversion data (in the related Brand Ops Hub plan this is an open decision).
- Source of visitor-behaviour tracking for CRO.
- Carrier or aggregator for tracking APIs (Shipping).
- Proposed information flows: reviews and feedback; return and replacement outcomes.
- Search-query and product-level view data for Merchandising (needs analytics access).
- Amazon and Etsy integrations (only where supported; not confirmed).
- Where CRO and Merchandising exact timing sits in practice (order is set; dates are not).

---

## 10. What exists today

### 10.1 The Flowmerce presentation deck

Published as an interactive HTML deck (React, CSS and HTML). Seven slides:

1. **Intro:** name, tagline, stats (6 core projects, 10 delivery steps, 1 future-scope area), project beads that open each project.
2. **Project modules:** pick a project, then three tabs: *Today → Intended platform* (before/after as short bullets, plus an “Exists today → Information Extraction → Platform enables” flow with animated connectors), *What it does* (5 to 6 connected steps with a play control), *Inputs → Outputs* (animated curves from each input to the project icon and on to each output).
3. **Build order:** the seven-project sequence with Now and Next highlighting, labelled connectors and the conversion-data return path.
4. **Data flows:** the four-layer diagram; hover or click traces a path; proposed links are dashed.
5. **Building process and progress:** ten-step playback with floating explanation, project focus, and the editable progress table; second tab “Joined carefully” (rules and the path into the ERP).
6. **Merchandising (future scope):** the full section in section 8, as eleven tabs with interactive demos.
7. **Outcomes:** five outcomes linked to the projects behind them, plus the closing wordmark.

Other features: Original/Refined theme switch, light/dark mode, keyboard and swipe navigation, slide list, fullscreen, reduced-motion support, responsive layouts for desktop, tablet and phone.

### 10.2 Published links

| Item | Link |
| --- | --- |
| Flowmerce deck | https://claude.ai/artifact/Fke62GUtZ1CBT6eQHhBT2p |
| Brand Ops Hub deck | https://claude.ai/artifact/CE5EStbRqcELUPiAxVCFfC |
| Brand Ops Hub app prototype | https://claude.ai/artifact/PQqqAk4TWRJHscrFjd8Sek |

---

## Appendix A: Brand Ops Hub (the related operations app)

*Source: the PDF “Brand Ops Hub: Pages, Flow and Access” (Oct 26, 2026, @yash). Its six modules (SEO, Shipping, Conversion, Meta ads, Creative, Landing) mirror the Flowmerce core projects; it appears to be the operations interface for them. Confirm this relationship with the owner.*

### A.1 How the hub runs

The hub works a **night shift**: data syncs and Claude analysis run overnight on a schedule; the team spends the day reading reports, approving suggestions and asking for new work (for example a landing page design). On-demand requests skip the night queue and join the same approval step.

**Every night** (automatic, IST):
1. Sync data (Shopify, GSC, Meta, carriers): Fresh data is pulled in for every module before any analysis starts (00:30 IST).
2. Claude jobs (analyse, write reports, drafts): Claude analyses the data and writes reports and drafts, one job after another.
3. Save results (to Supabase for dashboards): Results are saved so that by morning every dashboard holds last night’s report.
4. Urgent alerts (to Slack and email): Urgent issues have already gone to Slack and email before the team is online.

**Next morning** (the team):
1. Dashboards (read last night’s reports): By morning every dashboard holds last night’s report.
2. Approve (or dismiss each suggestion): A suggestion’s Approve button turns it into an action; anything above the low tier then waits in the inbox for someone with the right role.
3. Action runs (then reads back to check): The action runs, then the hub reads it back from the platform to check it worked.
4. Logged (every step in the activity log): Every action is written to the activity log, filterable by brand, module and person.

**Any time** (on request):
1. Request (e.g. describe a new landing page): On-demand requests skip the night queue: Claude works on them right away.
2. Claude job (uses references and guidelines): The job uses references and guidelines from the Library.
3. Design options (preview desktop and mobile): Options preview on desktop and mobile. Ask for changes, or send the chosen one to the same approval step as every suggestion.

### A.2 Night schedule (IST, proposed; editable in Settings)

Jobs run one after another about an hour apart so they do not compete for the Claude plan’s usage limits.

| Time | Job | Cadence | Uses Claude | Output |
| --- | --- | --- | --- | --- |
| 00:30 | Data sync (Shopify, Search Console, Meta, carriers) | Daily | No | Fresh data for every module |
| 01:00 | Shipping delay alert and unfulfilled status check | Daily | Yes | Alerts for late and unfulfilled orders; list in Shipping |
| 01:30 | Meta ads report | Daily | Yes | Report and flags in Meta ads |
| 02:30 | Conversion report and fix suggestions | Daily | Yes | Report and suggestions in Conversion |
| 03:30 | Creative strategist suggestions | Daily | Yes | Concepts and briefs in Creative |
| 04:30 | Landing pages report | Daily | Yes | Page performance report in Landing pages |
| 05:30 | SEO blog automation | Twice a week, Sun and Wed | Yes | One hidden blog draft and SEO report |
| On demand | Landing page design request | When someone asks | Yes | Design options to review |

**Timezone catch:** IST night is US afternoon. A 01:00 IST run sees US data only up to the last full US day (two calendar days back). To include yesterday’s US sales, a job must start after 10:30 IST for Ridhi (US Eastern) and after 12:30 IST for CPC (US Mountain), in US winter time.

### A.3 Pages (ten page types, one shell: modules on the left, brand switcher on top)

| Page | Route | What it holds |
| --- | --- | --- |
| Home (morning brief) | `/[brand]` | Last night’s runs, alerts, approvals waiting, one KPI row per module |
| Module dashboard | `/[brand]/seo , /shipping , /cro , /meta , /creative , /landing` | KPI tiles, trend chart, latest report card, top items table |
| Report | `/[brand]/[module]/reports/[date]` | One night’s report: summary, findings with evidence, suggestions to approve or dismiss |
| Builder (on-demand tool) | `/[brand]/landing/new` | Describe a request, pick references and guidelines, generate options, revise, send for approval |
| Approvals inbox | `/approvals` | Every pending action; detail pane with platform, record, change, reversible, how checked |
| Runs and schedules | `/runs` | Last night’s job timeline, status, logs, run now, edit schedule |
| Alerts | `/alerts` | Alert history, acknowledge or resolve, alert rules |
| Activity log | `/activity` | Every action ever run, filterable by brand, module and person |
| Library | `/[brand]/library` | Brand guidelines, voice docs, design references and past pages that AI jobs read |
| Settings | `/settings` | Brands, team and roles, connections and tokens, schedules |

All six modules share **one dashboard template and one report template**, so a new module adds data, not new pages.

**Approval model:** a report’s Approve button turns a suggestion into an action. Low-tier actions run immediately; anything above Low waits in the Approvals inbox for someone with the right role. The inbox shows five facts: platform, record, change, reversible, how checked. After running, the hub reads the result back to check it, and logs every step in the activity log. (Tier definitions are not specified in the PDF.)

**Landing page builder (first on-demand action tool):** Describe (text, references from the Library, guidelines, products from Shopify) → Generate (Claude builds each option as HTML in the design system with real product data and photos, and screenshots desktop and mobile) → Review (compare options, ask for changes in plain words, send one for approval). Exported theme files are reviewed before any theme push, which stays an owner-approved action. Later tools (ad briefs, email drafts) reuse the same three steps.

### A.4 Tools, APIs and access (15 accounts and grants needed before the first night run)

Shopify, Meta and Google grants take longest and start in week 1. Every token lives in Supabase Vault or the job runner’s secrets, never in code.

| Tool | Used for | What we need | Granted by | Week 1 |
| --- | --- | --- | --- | --- |
| Vercel | Hosting the web app | Pro team linked to GitHub; environment variables; a subdomain such as hub.ridhihome.com | Tech lead; DNS admin for the domain |  |
| Supabase | Database, login, file storage, secrets | Production and staging projects; Google login provider; storage for references and generated designs | Tech lead |  |
| GitHub | Code and reviews | Private repository with a protected main branch | Tech lead |  |
| Job runner (Trigger.dev) | Night and on-demand jobs | A project whose image includes Claude Code and a headless browser (Playwright) for page previews and screenshots | Tech lead |  |
| Claude plan (Pro or Max) | Every AI job | A dedicated seat for automation, and its token from claude setup-token saved as a secret | Claude account owner |  |
| Shopify, Ridhi | All modules | The hub’s custom app in the Ridhi dev org. Protected customer data access for order details. Scopes: read_orders, read_all_orders, read_products, read_content, write_content (hidden drafts and pages only), read_reports, read_merchant_managed_fulfillment_orders, read_themes. | Ridhi store owner installs | Yes |
| Shopify, CPC | All modules | Same app through custom distribution, since CPC is a separate org. read_all_orders needs Shopify’s approval for CPC. | CPC store owner installs | Yes |
| Shopify theme writes | Publishing landing pages | write_themes, added only once the owner approves theme pushes | Store owners |  |
| Google Search Console | SEO | A Google Cloud project with the Search Console API on and a service account, added as a user on each property | Property owner | Yes |
| GA4 or Microsoft Clarity | Conversion | GA4: the same service account as Viewer on each property. Clarity: an API token per project. | Marketing | Yes |
| Meta Marketing API | Meta ads, Creative | A Business-type Meta app and a system user with a long-lived token, assigned to each ad account. Scopes: ads_read (now), business_management (now), ads_management (only when pause or budget actions are approved). | Business Manager admin | Yes |
| Carrier tracking | Shipping delays | An API key from a tracking aggregator or the carriers we use (to choose) | Operations |  |
| Slack | Alerts | A Slack app with chat:write for one alerts channel | Slack admin |  |
| Email | Alerts | A transactional email service with DNS records on the company domain | DNS admin |  |
| Google Workspace | Team sign-in | An internal OAuth client for “Sign in with Google” | Workspace admin | Yes |

Semrush and Google Trends stay manual: their CSV exports are uploaded to the Library page.

### A.5 Running Claude on the plan token

- AI jobs run **Claude Code in headless mode** inside the job runner (Trigger.dev), signed in with a long-lived token from a Claude Pro or Max plan (`claude setup-token`, passed as `CLAUDE_CODE_OAUTH_TOKEN`), instead of a pay-per-call API key.
- Cost is the fixed plan price; the hub logs each run’s duration and token count instead of dollars.
- Usage limits are shared with anyone on the same account: use a dedicated automation seat and keep jobs spread through the night.
- Not on Vercel: Claude Code needs a long-running process, so every AI job lives in the job runner.
- Existing blog-run and brand-voice skill files move into the repo’s `.claude/skills/`; each job gets its own prompt file.
- Claude returns JSON; the hub validates it before saving; anything that writes to a tool still goes through approvals.
- When a limit is hit, the job retries after the reset and the Runs page flags it; any job can switch to an API key in Settings.
- Confirm the plan’s terms cover automated business use before go-live.

### A.6 Tech stack

**Frontend** (What the team sees):
- Next.js + TypeScript [suggested]: The web app: Home, module dashboards, reports, builder, approvals, runs, alerts, library and settings. The PDF names Vercel for hosting but not the framework; Next.js is my suggestion because it fits Vercel.
- Vercel [from the PDF]: Hosts the web app. Pro team linked to GitHub, environment variables, and a subdomain such as hub.ridhihome.com.

**Data and login** (Where everything is stored):
- Supabase Postgres [from the PDF]: Database for reports, suggestions, actions and the activity log. Production and staging projects.
- Supabase Auth + Google sign-in [from the PDF]: Team login through an internal Google Workspace OAuth client ("Sign in with Google").
- Supabase Storage [from the PDF]: Stores references and generated designs.
- Supabase Vault [from the PDF]: Keeps every token secret, never in code (or the job runner’s secrets).

**Jobs and AI** (The night shift):
- Trigger.dev [from the PDF]: Runs the night schedule and on-demand jobs. Claude Code needs a long-running process, so AI jobs live here, not on Vercel.
- Claude Code (headless) [from the PDF]: Every AI job: analysis, reports, drafts and designs, signed in with a Claude Pro or Max plan token (claude setup-token).
- Playwright [from the PDF]: Headless browser for landing-page previews and desktop and mobile screenshots.
- JSON validation [from the PDF]: The hub checks Claude’s JSON before saving. Anything that writes to a tool still goes through approvals.

**Integrations** (Data in, actions out):
- Shopify Admin API [from the PDF]: Custom app for Ridhi, and custom distribution for CPC. Orders, products, content, reports, fulfilment and themes.
- Google Search Console API [from the PDF]: SEO data through a Google Cloud service account on each property.
- GA4 or Microsoft Clarity [from the PDF]: Conversion data. Which one is still an open decision.
- Meta Marketing API [from the PDF]: Meta ads and Creative, through a Business-type app and system user.
- Carrier tracking API [from the PDF]: Shipping delays. Aggregator or direct carriers, still to choose.
- Slack API + email service [from the PDF]: Urgent alerts to one Slack channel and by transactional email.

**Code and delivery** (How we build):
- GitHub [from the PDF]: Private repository with a protected main branch and code reviews.
- Prompt files + .claude/skills [from the PDF]: Blog-run and brand-voice skills move into the repo; each job gets its own prompt file.

### A.7 Time estimate for two developers (an estimate, not in the PDF)

Assumes two full-time developers, open decisions made on time, and access granted in the first weeks. Waits not counted: third-party approvals, DNS, the two-week plan trial.

| Phase | Person-weeks without AI | With heavy AI-tool use |
| --- | --- | --- |
| Foundation and app shell | 2.5 | 1.5 |
| Job runner and Claude harness | 3 | 2 |
| Data syncs | 3.5 | 2.5 |
| Dashboards, reports, Library, Settings | 3.5 | 2 |
| Six module jobs | 5 | 3.5 |
| Alerts: Slack and email | 1.5 | 1 |
| Approvals, actions, activity log | 3.5 | 2.5 |
| Landing page builder | 3.5 | 2.5 |
| CPC, hardening, trial, go-live | 2.5 | 2 |
| **Total** | **28.5** | **19.5** |

- Without AI: 28.5 person-weeks ÷ 2 members ≈ **14 to 15 weeks** to go-live (fast ≈ 12, cautious ≈ 19). With heavy AI-tool use: 19.5 person-weeks ÷ 2 ≈ **10 weeks** (about 2.5 months).
- First MVP (Ridhi only, Shipping and Meta reports, Home and one dashboard, Slack alerts): about **7 to 8 weeks without AI, about 5 with AI**.
- Milestones (expected plan): week 3 shell and job runner ready; week 7 first real night run; week 11.5 six modules, alerts and approvals live; week 14.5 builder, CPC and trial done, go-live.

**Suggested phases and owners (Member A = back-end, jobs, integrations; Member B = front-end, dashboards, builder):**

- **Foundation and app shell** (2.5 person-weeks, weeks 0 to 2.5, owner AB): Private GitHub repo with a protected main branch; Vercel project and the hub subdomain; Supabase production and staging, Google login; Brands, team and roles; App shell: module menu and brand switcher
- **Job runner and Claude harness** (3 person-weeks, weeks 0 to 3, owner A): Trigger.dev project with Claude Code and Playwright in the image; Plan token stored as a secret; One prompt file per job; skills moved to .claude/skills/; JSON validation before saving; Retry after a limit resets; API-key fallback in Settings; Runs page: timeline, status, logs, run now, edit schedule
- **Data syncs** (3.5 person-weeks, weeks 3 to 6.5, owner A): Shopify (Ridhi first, CPC later); Search Console; Meta Marketing API; Carrier tracking; GA4 or Clarity; The 00:30 nightly sync job
- **Dashboards, reports, Library, Settings** (3.5 person-weeks, weeks 2.5 to 6, owner B): One dashboard template and one report template for all six modules; Home (morning brief); Library and Settings pages; Report page with “Ask Claude about this report”
- **Six module jobs** (5 person-weeks, weeks 6 to 11, owner AB): Shipping delay alert and unfulfilled status check; Meta ads report; Conversion report and fix suggestions; Creative strategist suggestions; Landing pages report; SEO blog automation (hidden draft and SEO report)
- **Alerts: Slack and email** (1.5 person-weeks, weeks 6.5 to 8, owner A): Slack app for one alerts channel; Transactional email with DNS records; Alerts page: history, acknowledge, resolve, rules
- **Approvals, actions, activity log** (3.5 person-weeks, weeks 8 to 11.5, owner AB): Approve turns a suggestion into an action; Tiers: above low waits in the inbox for the right role; Action detail: platform, record, change, reversible, how checked; Action runs, then reads back to check; Activity log filterable by brand, module and person
- **Landing page builder** (3.5 person-weeks, weeks 11 to 14.5, owner B): Describe, Generate, Review; Options as HTML in our design system with real product data and photos; Desktop and mobile screenshots; Revise in plain words; version history; Export theme files; theme push stays owner-approved
- **CPC, hardening, trial, go-live** (2.5 person-weeks, weeks 11.5 to 14, owner AB): CPC brand via Shopify custom distribution (read_all_orders needs Shopify’s approval); Two-week trial of the night load to choose Pro or Max; Confirm plan terms cover automated business use; Go-live checks

### A.8 Subscriptions and budget (estimates from list prices known to mid-2026; not live-checked; GST and card fees excluded)

| Tool | Plan | About per month |
| --- | --- | --- |
| Vercel | Pro, 2 members | $40 |
| Supabase | Pro plus staging project | $35 |
| GitHub | Team, 2 members | $8 |
| Trigger.dev | Pro plus compute for night jobs | $75 (range $50 to 120) |
| Claude plan, automation seat | Pro $20 / Max 5× $100 / Max 20× $200 (default Max 5×) | $100 |
| Claude seats for 2 developers | Max 5× × 2, build phase only | $200 |
| Carrier tracking API | to choose | $50 (range $0 to 100) |
| Transactional email | free tier | $0 |
| Semrush | only if not already subscribed | $140 optional |

Free or already available: Shopify custom app, Search Console API, GA4 or Clarity, Meta Marketing API, Slack app, Google Workspace sign-in, hub subdomain, Playwright, Next.js, Google Trends.

Default scenario (₹86 per $, 2.5 months with AI): tools about **$508 per month while building** (₹43,688), about **$1,397 for the whole build including a 10% buffer** (₹1,20,142), and about **$308 per month to run** after go-live (₹26,488; about ₹3.2 lakh in the first year). Developer salaries are not included.

### A.9 Open decisions (from the PDF)

- Night in IST (reports lag one US day) or night in US time (reports include yesterday, ready by early afternoon IST)?  *(needed by about week 2: before jobs are scheduled)*
- Final cadence per job: set the Cadence column  *(needed by about week 2: before jobs are scheduled)*
- Claude plan for the automation seat: Pro or Max, based on a two-week trial of the night load  *(needed by about week 13: after the trial)*
- Carrier tracking source for shipping delays  *(needed by about week 3: before data syncs)*
- GA4 or Microsoft Clarity for conversion data  *(needed by about week 3: before data syncs)*
- How many design options the landing page builder makes per request, and who approves them  *(needed by about week 10: before the builder)*
- Hub subdomain and Slack alerts channel  *(needed by about week 1: subdomain at setup; channel before alerts)*

### A.10 The app prototype

A clickable dummy of the finished hub with **sample data only** (no real accounts). Pages: Home (morning brief), Analytics (KPIs, revenue chart with Ridhi-vs-CPC compare, conversion funnel, channel mix, order heatmap, top products, AI insights), six module dashboards, report pages (Approve and Dismiss, Ask Claude), Approvals inbox (approve with run and read-back, logged), landing page builder (describe, generate, review), Runs and schedules (timeline, tokens, logs, run now, edit schedule), Alerts (acknowledge, resolve, rules), Activity log (filters), Library, and Settings (brands, team, 15 connections, Claude token). Also: brand switcher, light/dark, Ctrl or ⌘+K search, confetti on approval, and a footer with editable contact details (email, phone, address, hours) that are placeholders until real details are supplied.

*End of document.*

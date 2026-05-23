# Project state and roadmap

Status as of end of Day 1.

## Where we are

### Strategic foundation
Five reference docs updated and ready to replace originals in the project:
- `business-overview.md`
- `hosting-strategy.md`
- `automation-pipeline.md`
- `design-system-and-variety.md`
- `prospecting-playbook.md`

Anchor decisions locked in:
- Pricing: $25/mo monthly or $19/mo annually, no build fee
- "No asset lock-in" — annual prepay non-refundable, but website and domain always belong to the customer
- $50 flat for new pages; other extras quoted in writing
- Tech stack: Astro 5 + TypeScript + Tailwind, deployed on Cloudflare Pages
- Email split: Resend for transactional only; real human inbox for cold outreach
- Designed for a ~1,000-customer endgame; first 6–12 months will be visibly scrappier

### Infrastructure
- GitHub repo: `opensign-web-co` (under ReindeerWorks)
- Local working dir: `/dev/mountain-men-tech/open-sign-web-co` (WSL, on `/mnt/c`)
- Domain: `opensignwebco.com` (Cloudflare-managed, SSL active)
- Astro project scaffolded and deployed via Cloudflare Pages
- SSH keys configured for GitHub
- Deploy pipeline live: push to `main` → auto-build → production

### Visual direction (in flight)
Six DNA variations live at https://opensignwebco.com:
- `/clinical` — Clinical Precision
- `/print` — Print-Inspired
- `/brutalist` — Brutalist Indie (original)
- `/brutalist-soft` — calmer, deep teal accent
- `/brutalist-warm` — warmer palette, terracotta accent
- `/brutalist-editorial` — serif headlines, brutalist structure

Status: pending Richard's review. Nick's private lean: **Brutalist Warm**.

## What's next

Phased, in roughly the order to tackle.

### Marketing site polish (next session or two)
- Contact form (replace mailto) — needs Resend integration
- Favicon
- OpenGraph / social meta tags
- Sitemap.xml + robots.txt
- Logo/wordmark refinement (currently text-only)
- Possibly a "portfolio coming soon" placeholder section

### Email + workspace infrastructure — COMPLETE
- Google Workspace: hello@opensignwebco.com (primary), nick@ and richard@ as aliases
- Resend: opensignwebco.com verified and ready to send
- Remaining: "Send mail as" setup in Gmail settings for both aliases (manual, 2 minutes each); RESEND_API_KEY added to .env

## End of May 21, 2026

### Pipeline state
- Airtable Leads: 10 records — 1 Strong (Craft Eats, disqualified), 8 Weak, 1 No Site (Decked Out after manual Site Quality flip)
- All 9 active prospects have populated Site Quality, Site Issues, Site Issues Raw, and Brief fields
- Pipeline tested end-to-end at smoke-test scale (Hanover + 18mi radius, restaurants/cafés/bars vertical)

### Scripts shipped
- `open-sign-web-co/scripts/pull_leads.py` — Google Places (New) → Airtable, vertical-interleaved, idempotent, dedupes on Place ID
- `open-sign-web-co/scripts/evaluate_sites.py` — quality-bar heuristics, populates Site Quality + JSON raw data
- `open-sign-web-co/scripts/generate_briefs.py` — Places Details + reviews → structured markdown brief, Gemini-seeded when available

### Phase status
- Phase 2 (Lead gen + quality bar): substantially complete
- Phase 3 Stage 2 (Brand intake / briefs): complete
- Phase 3 Stage 3 (Mockup generation): next session

### Open items (small, can wait)
- Manual Airtable cleanup: McAllister spelling normalization on Britton Downtown brief; strike "and menu" from La Cucina revival-narrative line
- Human skim of all 9 briefs for drift patterns — looking specifically for parallel-construction filler and frequency-quantifier inflation now that the shapes are named
- 3 prompt-revision TODOs staged inline in `generate_briefs.py`:
  - Website key-info-line interpretive language drift
  - Parallel-construction filler in data-grounded sections
  - Frequency-quantifier inflation in data-grounded sections
- Gettysburg expansion pass (optional, cheap — `pull_leads.py --center "Gettysburg, PA"`, then `evaluate_sites.py` + `generate_briefs.py` on new leads)
- Decked Out URL fix attempt (optional — if a working URL exists, re-evaluate with `--lead-id`)

### Next session: Stage 8 — update automation
Architecture and design first (chat), then build (CC). Required before first paying customer.

### Patterns worth carrying forward
- Audit-before-change paid off concretely today (Google Places field discovery, Airtable schema validation, brief grounding verification)
- Smoke test → review → live run is the right cadence — kept us from shipping bad data three separate times today
- Field IDs not display names for Airtable writes
- "Verify external contracts against reality" surfaces undocumented enrichments (this is how we found `generativeSummary`)
- Audit/propose-then-implement was the highest-leverage habit of the day

### Phase 3 — Brand intake + mockup generation (Stages 2–3)
- Brief generation from public info (Google Business Profile, social, reviews)
- Component bucket implementation (the design system encoded in code)
- DNA preset definitions
- Compatibility rules + voice components
- Overgenerate-and-filter pipeline
- Similarity detection (perceptual hash + LLM-vision check)
- Preview URL deployment infrastructure

### Phase 4 — Outreach (Stage 4)
- Email template per `prospecting-playbook.md`
- Send from real inbox (manual → Gmail API)
- Reply routing to shared inbox

### Phase 5 — Update automation (Stage 8)
**Required before launching paid customers.** The whole $25/mo unit economics depend on this working.
- Inbox monitoring + parsing
- Four-bucket classifier (auto-handle, clarify-then-handle, quote-then-handle, escalate) — *Prompt + eval harness complete (May 22); production worker pending step 2.*
- Preview URL generation per change
- Customer confirmation flow ("Reply YES to push live")
- Audit logging
- Escalation queue

### Phase 6 — Billing
- Stripe integration
- Monthly + annual prepay handling
- Pass-through pricing for domain registration and other extras
- Failed-payment dunning sequence

### Phase 7 — First customers
- Take the cold-outreach pipeline live for one vertical / one geography
- Ship the first paid customer end-to-end
- Track the make-or-break metric: **minutes of human attention per customer per month** (target: under 5; gets tight at 15; breaks at 30)

## End of May 22, 2026

- Mockup generation v0 complete: 9 leads, Warm Hospitality DNA, all live at opensignwebco.com/previews/[slug]
- generate_mockups.py: tail guard, --lead-id flag, max_tokens bumped to 12000, prompt fixes for contrast/imagery/palette
- Contact form live with Resend integration (functions/api/contact.ts)
- OG tags and favicon added to marketing site
- Email infrastructure complete (see earlier section)

## End of May 22, 2026 (continued) — Stage 8 step 1 complete

- Classifier prompt + offline eval harness shipped under
  scripts/stage8/classifier-eval/
- Baseline: 35/35 on synthetic cases across INFORMATIONAL,
  AUTO_HANDLE, CLARIFY, QUOTE, ESCALATE plus 4 EDGE cases
- Tool-use forced output, 8s inter-request throttle, retry-with-
  backoff on 429s
- Prompt is ready to graduate into the production inbound worker
  when step 2 (Postmark webhook → Pages Function → Airtable)
  lands

## Open questions still TBD

- Which DNA direction wins (waiting on Richard)
- First geography + vertical
- Whether to keep all six mockup pages or only the chosen one
- Contact form vs mailto for v1 launch
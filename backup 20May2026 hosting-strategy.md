# Hosting Strategy

The goal: a hosting model that is cheap for us, transparent for the customer, and naturally sticky without trapping anyone.

## Recommended stack: Cloudflare Pages

**Why:**
- Free tier handles small-business traffic easily (most of our clients will be well under any limits)
- Free SSL, free CDN, free custom domains
- We can host hundreds of customer sites under one paid team plan ($20/mo Pro is generous, $200/mo Business is unlikely to be needed for a long time) — there's no per-site cost
- Git-driven deploys mean every customer site is version-controlled and rollback is one click
- Cloudflare also handles DNS, which simplifies domain operations dramatically if customers let us manage theirs

**Alternatives considered:**

| Option | Why we passed |
|---|---|
| Vercel | Per-team pricing gets awkward with many client sites; commercial use of free tier is unclear |
| Netlify | Comparable to Cloudflare; slightly worse free tier; no real advantage |
| VPS (Hetzner, DigitalOcean) | Cheapest at scale but introduces ops overhead we don't want |
| Webflow / Framer / Squarespace | Per-site subscription kills our margins and creates the exact platform lock-in we're selling against |
| Self-hosted WordPress | Maintenance burden, security surface, no |

## Pricing tiers (placeholder — calibrate after first 10 sales)

| Tier | Build fee | Monthly | What's included |
|---|---|---|---|
| Starter | $300 | $25/mo | Hosting, SSL, backups, up to 2 small text/image changes per month, uptime monitoring |
| Standard | $500 | $50/mo | Above + Google Business Profile management + a quarterly content refresh + faster turnaround on changes |
| Pro | $1,000 | $100/mo | Above + form/booking integration + monthly performance review + priority changes (same-day) + minor design tweaks included |

These are starting numbers. The right way to find pricing is to ship the first 5–10 customers at the lower end, see what conversations are like, and adjust.

## What's included vs. what's extra (PUBLISH THIS)

The single most important hosting-related thing we can do is publish this list on our marketing site. The agency industry's biggest sin is hidden monthly creep; the antidote is radical transparency.

**Included in every tier:**
- Hosting, SSL, global CDN
- Daily backups
- Domain transfer help (if they own the domain elsewhere)
- Email-based support for change requests
- Small text and image updates per the tier's allowance
- Uptime monitoring

**Extra, priced clearly upfront:**
- New page additions (flat fee per page, published)
- Major design changes / redesigns (quoted per project)
- Integrations (booking, e-commerce, CRM, custom forms — quoted)
- Domain registration ($X/yr, our cost + a small markup)
- E-commerce setup and ongoing support (separate tier or quoted)
- Anything outside what's listed: we'll quote it in writing before doing it, no surprises

The "no surprises" promise is the marketing.

## Lock-in stance: explicitly opposite to industry

**Our public promise:** if a customer leaves, we export the full static site for them and help them migrate to wherever they want. We'll also hand over their domain ownership if they ever had to keep it with us.

This is on our marketing site, by name, prominently.

**Why this works:**
- Turns the biggest unspoken objection ("am I trapped if this doesn't work out?") into a trust signal
- Cheap to deliver because the sites genuinely are static files
- Discourages no-one from signing up. People who are confident they can leave are more willing to start.

## Operational notes

**One Cloudflare Pages project per customer.** Don't share infrastructure between customers. Isolation is cheap with Pages.

**Domain management.** Where possible, get customers to point their domain to Cloudflare and let us manage DNS. Frictionless TLS, faster DNS changes, easier subdomain additions later. Make it optional, not required.

**Customer-facing dashboard.** Don't build one for v1. Email-based change requests are fine until ~20 customers. Re-evaluate then. A dashboard built too early is wasted money.

**Status page.** A single shared `status.[ourdomain].com` is plenty. Update it manually when there's an actual incident, which on Cloudflare Pages will be rare.

**Internal pipeline visibility.** Track every customer in one place (Airtable is fine) with: current tier, MRR, domain, deploy date, last change date, support time spent this month. Once a quarter, look at the support-time column and identify customers who are unprofitable.

## Margins (rough estimate)

If we have 50 customers averaging $50/mo, that's $2,500 MRR. Cloudflare hosting cost: ~$20/mo. Email sending cost: ~$20/mo. Domain costs pass through. Stripe fees: ~3%.

Variable cost per customer per month: realistically the support time we spend on their site. If that averages more than 15–20 minutes per customer per month, the unit economics get tight. This is why automated triage and disciplined scope-of-included-changes matter.

## What we don't do

- E-commerce as a primary offering. We can do it as a Pro add-on but it's not the core. Shopify exists; we don't need to compete.
- Custom backend applications. We're a static-site shop. If a customer needs an app, we refer them out.
- Membership sites, course platforms, etc. Same reason. Refer out.

These boundaries keep the business simple and the ops scalable.

# Hosting Strategy

The goal: a hosting model that is cheap for us, transparent and accessible for the customer, and naturally sticky without trapping anyone.

## Recommended stack: Cloudflare Pages

**Why:**
- Free tier handles small-business traffic easily (most clients will be well under any limits)
- Free SSL, free CDN, free custom domains
- We can host thousands of customer sites under one paid team plan ($20/mo Pro is generous; $200/mo Business unlikely to be needed for a long time) — no per-site cost
- Git-driven deploys mean every customer site is version-controlled and rollback is one click
- Cloudflare also handles DNS, which simplifies domain operations dramatically when customers let us manage theirs

**Alternatives considered:**

| Option | Why we passed |
|---|---|
| Vercel | Per-team pricing gets awkward with many client sites; commercial use of free tier is unclear |
| Netlify | Comparable to Cloudflare; slightly worse free tier; no real advantage |
| VPS (Hetzner, DigitalOcean) | Cheapest at scale but introduces ops overhead we don't want |
| Webflow / Framer / Squarespace | Per-site subscription kills our margins and creates the exact platform lock-in we're selling against |
| Self-hosted WordPress | Maintenance burden, security surface, no |

## Pricing: one tier, two ways to pay

Starting with a single tier keeps everything simple — for us, for the customer, and for the marketing site. We can introduce additional tiers later when actual customer demand tells us what they want above the baseline. We won't be guessing.

**The tier:**

- **$25/mo billed monthly** — cancel anytime
- **$19/mo billed annually** ($228 upfront, ~24% off) — annual prepayment is non-refundable; your website and domain remain yours either way (see lock-in stance below)

**No build fee at this tier.** The work of producing the site is absorbed into the recurring revenue at scale. This is what makes the pitch "no effort, no expense" actually true — and it's what gates everything: the only way this math works is if the production cost per customer is genuinely low, which it is with Claude-assisted generation.

These numbers are starting numbers. The right way to find pricing is to ship the first cohort and let conversion data inform us. **Plan: A/B test in the first wave of cold outreach — 100 prospects at $25/mo and 100 at $35/mo.** The conversion gap will tell us where the market actually is faster than any amount of theorizing now. Repeat the test at higher numbers if the $35 cohort converts comparably.

## What's included vs. what's extra (PUBLISH THIS)

The single most important hosting-related thing we can do is publish this list on our marketing site. The agency industry's biggest sin is hidden monthly creep; the antidote is radical transparency.

**Included, no extra charge:**

- Hosting, SSL, global CDN
- Daily backups
- Uptime monitoring
- Domain transfer help if they own a domain elsewhere
- Email-based support
- **Site changes via email.** Send us what you want changed; we'll do it. If it's small and clear, it just gets done. If it's bigger, or if we'd need to ask you something to do it right, we tell you what (if anything) it costs before doing anything. No counting, no monthly allowances, no metering.

The mechanics behind that last point live in `automation-pipeline.md` — the email-driven update system triages requests by type, executes confidently when it can, asks clarifying questions when it can't, and escalates when something is out of scope or carries risk.

**Extra, priced clearly upfront:**

- New page additions: **$50/page flat**
- Major design changes / redesigns: quoted per project in writing before work starts
- Integrations (booking, e-commerce, CRM, custom forms): quoted per project
- Domain registration: pass-through cost (see `domain-registration-playbook.md`)
- E-commerce setup and ongoing support: quoted per project (and we'll honestly assess whether Shopify is a better fit for them than us)
- Anything outside what's listed above: quoted in writing before doing it

The "no surprises" promise is the marketing.

## Lock-in stance: your assets, always

**Our public promise:** your website is yours. Your domain is yours. If you ever leave us, we export the full static site and help you migrate wherever you want. If your domain is registered through us, we transfer ownership to you. This is on our marketing site, by name, prominently.

**Precision matters here.** What we promise is *asset* freedom, not contract freedom:

- Monthly customers can cancel anytime — the next month doesn't bill.
- Annual customers committed up-front; the prepayment is non-refundable, the same way virtually every annual subscription on the internet works.
- In either case, the website and the domain are yours, and we help you leave with them.

The marketing language must reflect this precisely. "Your website, your domain, always" works. Generic "no lock-in" does not, because we'd lose the trust signal the moment an annual customer asked for a refund and got told no. Don't ever let the marketing copy drift toward unqualified "no lock-in" language.

**Why this stance works:**
- Turns the biggest unspoken objection ("am I trapped if this doesn't work out?") into a trust signal
- Cheap to deliver because the sites genuinely are static files
- Doesn't discourage anyone from signing up — people confident they can leave are more willing to start

## Operational notes

**One Cloudflare Pages project per customer.** Don't share infrastructure between customers. Isolation is cheap with Pages.

**Domain management.** Where possible, get customers to point their domain at Cloudflare and let us manage DNS. Frictionless TLS, faster DNS changes, easier subdomain additions later. Make it optional, not required.

**No customer-facing dashboard, v1 or otherwise.** The customer's interface is their email. For the small-business owner we're targeting — someone who doesn't want to learn another tool — that's a feature, not a limitation. Internal dashboards for *us* (customer status, MRR, support load) are a different concern and live in `automation-pipeline.md`.

**Status page.** A single shared `status.[ourdomain].com` is plenty. Update it manually when there's an actual incident, which on Cloudflare Pages will be rare. At the 1,000-customer scale this approach will need to be revisited.

**Internal pipeline visibility.** Track every customer in one place (Airtable initially) with: payment plan (monthly or annual), MRR contribution, domain, deploy date, last change date, support minutes spent this month. Once a quarter, look at the support-minutes column and identify customers who are unprofitable. That's the column that tells you whether the model is actually working.

## Margins at scale

Designing for the ~1,000-customer endgame from `business-overview.md`:

Blended ARPU, assuming ~50/50 monthly/annual mix: ~$22/mo. At 1,000 customers, ~$22K MRR / $264K ARR.

Variable cost per customer per month: ~$2–3 (Stripe fees, API spend for update automation, email send). Gross margin per customer: ~$19–20/mo. At 1,000 customers, ~$19–20K/mo gross margin, ~$228–240K/yr.

Fixed costs (don't scale much with customer count): email sending platform, Airtable, Cloudflare team plan, domain/tooling overhead, business basics. Call it $100–200/mo at scale. Negligible against gross margin.

The real variable cost is labor. At our target of ~5 minutes of human attention per customer per month, 1,000 customers = ~83 hours/month. Roughly one full-time-equivalent at part-time pace, or one part-time hire plus founder slack. If support-minutes-per-customer drifts to 15, labor cost roughly triples and margins get tight. This is why automated triage and disciplined scope of included changes are operationally load-bearing, not nice-to-have.

Smaller-scale checkpoints: at 100 customers (~$2,200 MRR), this is a side project that pays for itself plus some. At 500 customers (~$11K MRR), it's an actual small business. At 1,000, it's a real business that can support two partners comfortably. See `business-overview.md` for what changes operationally between those phases.

## What we don't do

- E-commerce as a primary offering. We can quote it as an extra but it's not the core. Shopify exists; we don't need to compete with it.
- Custom backend applications. We're a static-site shop. If a customer needs an app, we refer them out.
- Membership sites, course platforms, etc. Same reason. Refer out.

These boundaries keep the business simple and the ops scalable.

## Open questions and things to validate

- Whether $25/$19 is the right starting price, validated through the first cold-outreach A/B test ($25 vs $35 cohorts). Re-test at higher anchors if the $35 cohort converts comparably to $25.
- Whether to add a higher tier later — driven by what customers actually ask for above the baseline, not what we guess they might want
- Whether to offer a quarterly billing option as a middle path between monthly and annual (skip for v1 unless customers explicitly ask)
- How "small and clear" changes get classified by the update automation in practice — the precise routing logic lives in `automation-pipeline.md`

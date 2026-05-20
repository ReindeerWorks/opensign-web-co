# Automation Pipeline

The goal is to automate everything that doesn't require human judgment or human warmth, and to do that without ever shipping mediocre work to a prospect. Every stage below ends with a human checkpoint of some kind, even if it's just a 30-second eyeball.

## Stage 1 — Lead generation (mostly automated)

**Input:** a geography + industry combination chosen by you.
**Output:** a list of qualified leads in Airtable.

Approach: pull businesses from the Google Places API (or Apify if Places gets restrictive) for the chosen radius and industry. For each, capture name, address, phone, website URL (if any), Google rating, review count, and listed hours.

Then filter:
- No website at all → keep
- Website exists but fails our quality bar → keep
- Website looks competent and recent → skip

Quality-bar heuristics (any one disqualifies the existing site, marking the lead as worth pursuing):
- Not mobile-responsive (check viewport meta + screenshot at 375px)
- SSL warnings or HTTP-only
- Copyright year more than 3 years old in the footer
- Generic Wix/Squarespace/GoDaddy template with no real customization
- Broken images or layout
- Loads in over 6 seconds

Human checkpoint: you skim the list before mockup generation kicks off, removing anyone obviously off (closed, chain, etc.).

## Stage 2 — Brand intake (automated)

**Input:** a lead from Stage 1.
**Output:** a brief that Claude can use to generate mockups.

Pull whatever public info exists:
- Existing site (if any) — text, palette, imagery
- Google Business Profile — photos, hours, services list, reviews
- Facebook / Instagram — recent posts, tone, photos
- Reviews (top 10 most recent) — summarized to extract themes about what customers value

Generate a brief containing: business name, one-line description, vibe/tone, suggested palette direction, content sections needed, key info to display (address, hours, phone, services), and any standout details from reviews.

Flag for human review if there isn't enough public info to write a credible brief. These leads either get skipped or queued for manual intake.

## Stage 3 — Mockup generation (Claude + human gate)

**Input:** brief from Stage 2.
**Output:** 2–3 deployable mockup sites at preview URLs.

Generate 2–3 mockups using *different* design DNAs (see `design-system-and-variety.md`). Each mockup is a real, navigable static site — not a screenshot — so the prospect can actually click around.

Each mockup deploys to a preview URL like `previews.[ourdomain].com/[business-slug]-1`, `-2`, `-3`. A landing page at `previews.[ourdomain].com/[business-slug]` shows all three side-by-side with a "pick one" CTA.

**Human checkpoint:** review takes 30–60 seconds per batch. Look for:
- Wrong info (hours, address, phone)
- Off-tone content
- Imagery problems
- "This feels like the last few we sent" sameness — if yes, regenerate at least one with a different DNA

This is the single most important human gate. Nothing skips it.

## Stage 4 — Outreach (automated send, human-written templates)

**Input:** approved mockup batch.
**Output:** an email sent.

Short personalized email with a link to the preview gallery. Format and approach detailed in `prospecting-playbook.md`.

Send from a real human inbox (you or Richard, alternating, or a shared "studio" name). Not a "noreply" address. Replies route to a shared inbox.

One follow-up email after 5–7 days if no response. After that, move on. We have effectively infinite leads.

## Stage 5 — Discovery call (human)

When they reply, you or Richard takes it. This is where the human warmth lives, and it can't be automated. Goal of the call: understand what they actually want, identify the right tier, close on price, schedule the follow-up to gather details.

Light automation: a scheduling link in the reply, a brief CRM update after the call.

## Stage 6 — Build (mostly automated, human finishes)

The chosen mockup is already 70–85% of the site. Remaining work:
- Swap placeholder content for real content
- Source/license real imagery (or use what they provide)
- Add functional pieces: contact form, map, booking integration, etc.
- Polish the bits Claude got wrong

Intake of real content can be either a simple form we email, or a 15-minute call where we capture it ourselves. The latter usually wins on speed and customer satisfaction.

## Stage 7 — Deploy (automated)

Push the finished site to Cloudflare Pages under our team. Connect their domain (either they have one, we register one for them, or we move their existing one).

30-minute onboarding call: how to request updates, what's included in their tier, billing setup, what to expect.

## Stage 8 — Ongoing (mostly automated, human ad-hoc)

- Monthly hosting billing via Stripe
- Support requests via email → triaged automatically into "small change", "billable change", "needs a call"
- Quarterly automated check-in email asking if anything needs updating
- Annual review with a "here's what we did this year" summary

## Tooling stack (recommended v1)

| Stage | Tool | Why |
|---|---|---|
| Lead gen | Google Places API + Python, or Apify | Simple, predictable |
| CRM / pipeline | Airtable | You have it connected; lightweight |
| Brief generation | Claude API | What it's good at |
| Mockup generation | Claude + Astro (or Next.js) | Static output, easy to deploy |
| Mockup hosting | Cloudflare Pages (wildcard subdomain) | Free, fast, scales |
| Email send | Postmark or Resend | Reliable transactional delivery |
| Production hosting | Cloudflare Pages | See `hosting-strategy.md` |
| Billing | Stripe | Standard |
| Internal coordination | Whatever you and Richard already use | Don't add tools for the sake of it |

## What NOT to automate (at least initially)

- The first email reply with a prospect. They should feel like they're talking to a person from word one.
- Pricing conversations.
- Anything involving copy that touches the customer's identity or values.
- Any change that could embarrass us if Claude got it wrong.

# Automation Pipeline

The goal: automate everything that doesn't require human judgment or human warmth, and do that without ever shipping low-quality or wrong work to a prospect or customer. Every stage has either a human checkpoint or an automated check with a customer-confirmation step before anything goes live.

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

Human checkpoint here is light: a skim of the list before mockup generation kicks off, removing anyone obviously off (closed, chain, etc.). At scale this becomes sample-based rather than exhaustive.

## Stage 2 — Brand intake (automated)

**Input:** a lead from Stage 1.
**Output:** a brief Claude can use to generate mockups.

Pull whatever public info exists:
- Existing site (if any) — text, palette, imagery
- Google Business Profile — photos, hours, services list, reviews
- Facebook / Instagram — recent posts, tone, photos
- Reviews (top 10 most recent) — summarized to extract themes about what customers value

Generate a brief containing: business name, one-line description, vibe/tone, suggested palette direction, content sections needed, key info to display (address, hours, phone, services), and any standout details from reviews.

Flag for human review if there isn't enough public info to write a credible brief. These leads either get skipped or queued for manual intake.

## Stage 3 — Mockup generation (automated production, sampled human review)

**Input:** brief from Stage 2.
**Output:** 2 deployable mockup sites at preview URLs.

Generate 2 mockups using meaningfully different design DNAs drawn from our component bucket system (see `design-system-and-variety.md` for how the bucket works). Each mockup is a real, navigable static site — not a screenshot — so the prospect can actually click around. Both deploy to preview URLs like `previews.[ourdomain].com/[business-slug]-1` and `-2`, with a gallery landing page at `previews.[ourdomain].com/[business-slug]`.

**Automated checks run on every batch, no exceptions:**
- Information correctness: name, address, phone, hours match the intake brief; no hallucinated services or locations
- Mobile rendering: both mockups render correctly at 375px viewport
- Similarity score against the rolling 100 most recent mockups sent
- Basic content sanity: no broken images, no Lorem Ipsum, no obvious LLM-default copy patterns ("supercharge your...", "the modern way to...")

If any automated check fails, the batch auto-regenerates. If similarity scores exceed the regenerate threshold, the offending mockup regenerates with explicit instruction to draw different components from the bucket.

**Human review, sampled at varying rates:**
- First 50 batches in a new industry + geography combination: 100% human review
- First 20 batches in a new geography within an already-established vertical: 1-in-5 sampled
- Established vertical + geography: 1-in-10 random sampled

Plus a forced-review override: any batch flagged "near-miss" by the similarity detector (above the warning threshold but below auto-regenerate) gets human eyes regardless of sampling rate.

When a human reviews a batch, they're looking for what the algorithms can't catch:
- Subtle info errors (name misspellings, tone mismatches)
- "This feels like the last several we sent" sameness the score didn't catch
- Off-tone content for the business type
- Imagery problems
- Whether the two mockups in the batch feel meaningfully distinct from each other

Sampling rates and similarity thresholds get tuned against real-world data. If reviewers find nothing in 9 of 10 samples, the rate is too high. If they're consistently flagging issues, it's too low or the automated checks need tightening. Expect to re-tune in the first few months.

## Stage 4 — Outreach (automated send, human-written templates)

**Input:** approved mockup batch.
**Output:** an email sent.

Short personalized email with a link to the preview gallery. Format and approach detailed in `prospecting-playbook.md`.

Send from a real human inbox (you or Richard, alternating, or a shared studio name). Not a noreply address. Replies route to a shared inbox.

One follow-up email after 5–7 days if no response. After that, move on. We have effectively infinite leads.

## Stage 5 — Discovery call (human)

When a prospect replies, you or Richard takes it. This is where the human warmth lives, and it can't be automated. Goal of the call: understand what they actually want, confirm the match, close on price (per `hosting-strategy.md`), and schedule the next step to gather details.

Light automation: a scheduling link in the reply, a brief CRM update after the call.

## Stage 6 — Build (mostly automated, human finishes)

The chosen mockup is already 70–85% of the production site. Remaining work:
- Swap placeholder content for real content
- Source/license real imagery (or use what the customer provided)
- Add functional pieces: contact form, map, booking integration, etc.
- Polish the bits the generator approximated or got wrong

Real-content intake is either a simple form we email or a 15-minute call where we capture it ourselves. The latter usually wins on speed and customer satisfaction.

**Human QA is firm here, no sampling.** This is a customer-facing deliverable they're paying for; the entire build gets reviewed before deploy. Stage 3's sampled approach works because mockups are sales material with a low-stakes failure mode (the prospect doesn't reply). Production builds have a high-stakes failure mode (the customer sees a mistake on their own site), so the gate stays tight.

## Stage 7 — Deploy (automated)

Push the finished site to Cloudflare Pages under our team. Connect their domain (either they have one, we register one for them, or we move their existing one). See `domain-registration-playbook.md` for the customer-facing flow.

30-minute onboarding call: how to request updates, what's included at this price, billing setup, what to expect.

## Stage 8 — Ongoing operations (the email-driven update system)

This stage carries the unit economics of the entire business. At our price point we cannot afford to spend more than ~5 minutes of human attention per customer per month on average (see `business-overview.md`). The update automation is what makes that possible.

### The shared support inbox

One customer-facing email address for everything (e.g., `support@[ourdomain].com`). The customer never has to wonder where to send a request — there's one place. Internal routing is invisible to them.

Before any change-related classification, the system also handles **informational requests** (renewal dates, plan details, "remind me what my login is") with auto-replies pulled from the customer's record. These don't deploy anything and don't need the change-classification flow below. If the question can't be confidently answered from the record, it escalates.

### Request classification: four buckets

Once a request is identified as a change request, the classifier assigns it to one of four paths.

**1. Auto-handle (preview + confirm)** — trivial, unambiguous, reversible changes:
- Text edits (typos, copy tweaks, content updates within existing sections)
- Contact info changes (hours, phone, address, email, social links)
- Image swaps when the customer provides the new image
- Single-word or sentence-level fixes

Flow: the system generates the change, deploys it to a preview URL on the customer's domain, and emails them: *"Here's the change you asked for: [preview link]. Reply YES to push it live, or reply with what you'd like adjusted."* On YES, it deploys to production.

**Nothing goes live without explicit customer confirmation, ever — not even at high model confidence.** The cost of asking "look good?" is one email. The cost of a public mistake (wrong phone number, mistyped hours, misinterpreted instruction) is enormous. This is the single most important guardrail in the entire pipeline.

**2. Clarify, then auto-handle** — small in scope, ambiguous in detail:
- *"Update my hours"* → which day? *"Change my main photo"* → to what? *"Fix the services page"* → what specifically?

Flow: system replies asking the clarifying question; when answered, the request re-enters the auto-handle path with the resolved details.

**3. Quote, then handle** — requests that are clearly priced extras per our published list:
- New page additions ($50/page per `hosting-strategy.md`)
- Domain registrations (pass-through cost)
- Other items on the published extras list

Flow: system replies with the quote: *"Adding a new About page costs $50. Reply YES to approve and we'll get started."* On approval, the request moves into execution, ending in the same preview-and-confirm step before anything goes live.

**4. Escalate to human** — anything that doesn't fit cleanly into the first three:
- Design or layout changes (color schemes, type adjustments, section reordering)
- Copy requiring judgment about the customer's voice or brand (rewriting their About page, drafting an FAQ)
- Anything below the classifier's confidence threshold for the auto-handle path
- Anything touching legal/identity-sensitive content (testimonials, claims, regulated language)
- Anything the customer flags as urgent or important
- Anything that smells weird — when in doubt, the classifier defaults to escalate

Flow: request lands in the human queue with the classifier's reasoning and recommended action. A human takes it from there.

### Confidence thresholds

The classifier is biased toward escalation. The cost of an unnecessary escalation is a few minutes of human time. The cost of a misclassified auto-execute is a customer-facing mistake. We tune for the former — **if there's any doubt, escalate.** Specific thresholds get calibrated against real data; the operating principle is conservative.

### Logging and audit

Every request, classification decision, and outcome gets logged. Reviewed weekly during the first months of operation to catch misclassifications and tune thresholds. Sampled thereafter. The log is also the source of pattern discovery — if 30% of incoming requests are "update my hours," there's an even more efficient path worth building.

### Quarterly check-in (automated)

Once a quarter, every customer receives an automated check-in: *"Anything need updating? Here's what's been changed in the last 90 days: [list]."* Replies route through the same classification system.

### Annual review (automated)

Once a year, each customer receives a "here's what we did this year" summary plus, for annual customers, a renewal-or-cancel touchpoint. Automated send; replies route through standard support.

### Monthly billing

Via Stripe. Failed payments trigger a polite automated dunning sequence (3 attempts over 10 days). After that, the customer gets escalated to a human before any service interruption — we don't want a card-expired customer waking up to a dark site.

## Tooling stack

| Stage | Tool | Why |
|---|---|---|
| Lead gen | Google Places API + Python, or Apify | Simple, predictable |
| CRM / pipeline | Airtable | Lightweight, fast to iterate on |
| Brief generation | Claude API | What it's good at |
| Mockup generation | Claude + Astro (or Next.js) | Static output, easy to deploy |
| Component bucket / variety system | Custom (see `design-system-and-variety.md`) | The thing that prevents mockup sameness at scale |
| Similarity detection | Perceptual hashing + LLM-vision check | Catches drift the bucket alone won't |
| Mockup hosting | Cloudflare Pages (wildcard subdomain) | Free, fast, scales |
| Email send + receive | Postmark or Resend (send) + inbox provider with parseable webhooks | Reliable transactional delivery; webhook-driven parsing feeds Stage 8 |
| Update classifier | Claude API with structured outputs | The core of Stage 8 |
| Production hosting | Cloudflare Pages | See `hosting-strategy.md` |
| Billing | Stripe | Standard |
| Internal coordination | Whatever you and Richard already use | Don't add tools for the sake of it |

## What stays human

The framework isn't "what NOT to automate" anymore — most things get automated with the right guardrails. The framework now is "where do humans add irreplaceable value":

- **First reply to a prospect who responds to outreach.** They should feel they're talking to a person from word one.
- **Pricing conversations and discovery calls.** Closing needs warmth and judgment.
- **Anything escalated by Stage 8's classifier.** By design these are the requests that need a human.
- **Sampled review of mockup batches** at the rate prescribed by Stage 3. Catching drift that algorithms miss.
- **Final QA on every production build** before Stage 7 deploy. Customer-facing deliverable, full human review every time, no sampling.
- **Quarterly review of the support-minutes-per-customer metric.** Identifies customers who are unprofitable and patterns worth automating further.

And one thing we explicitly never do, regardless of model confidence:

- **Deploy a change to a customer's live site without explicit customer confirmation.** The preview-and-confirm step is non-negotiable. This is the single guardrail that keeps us from a brand-damaging public mistake at scale, and the entire economics of $25/mo hosting depend on never having to recover from one.

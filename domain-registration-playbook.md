# Domain Registration Playbook

## What this covers

Every customer either has a domain or needs one. This playbook covers both cases: registering new ones, transferring existing ones, and pointing them at our Cloudflare-hosted sites. Most of this is internal reference for us; the customer-facing walkthrough lives at the end, ready to copy.

## Our two service models

**Self-serve (free, default).** Customer registers their own domain at a registrar we recommend, in their own name. We then handle the DNS and deployment side. Domain is theirs from day one — cleanest alignment with our no-lock-in promise.

**Concierge (+$25 setup, +pass-through annual cost).** We register the domain on their behalf, in their legal name, paid by us, billed back annually. Easier for them, but creates a touchpoint we manage. Reserve for customers who explicitly ask, or who get stuck mid-walkthrough.

Default everyone to self-serve. Only offer concierge if they ask or visibly bounce off the walkthrough.

## Recommended registrars

| Registrar | Best for | Cost (.com) | Notes |
|---|---|---|---|
| **Porkbun** | Default for customers | ~$10–11/yr | Simple checkout, free WHOIS privacy, minimal upsells, clean UI |
| **Spaceship** | Price-sensitive customers | $2.90–$4.99 first year, $9.98/yr renewal | Owned by Namecheap; cheapest 5-year cost |
| **Cloudflare Registrar** | Transfer destination only | $10.44/yr at-cost forever | Can't register new domains directly — register elsewhere, transfer in after a year |

Do not recommend GoDaddy (ToS issues, upsells), Wix Domains, Squarespace Domains, Bluehost, or Network Solutions. Either expensive, predatory, or both.

## TLD selection

- **.com is always first choice.** Even if the customer prefers something else, the .com gets typed by mistake forever. If they really want .co or similar, register the .com too and redirect it.
- **.co — the best fallback** if the .com is taken. Recognizable, professional.
- **Regional TLDs (.nyc, .la, .uk, etc.)** — fine for hyper-local businesses, but always pair with the .com.
- **Avoid for serious businesses:** .biz, .info, .us, .website, .online, .site, .xyz. They read as cheap.
- **Industry TLDs (.law, .restaurant)** — usually overpriced, rarely worth it.
- **Premium domains** (already-owned names listed at $1,000+) — almost never worth it for a small business. Pick a different word combination.

If the ideal .com is taken, useful patterns to try: add the city ("denverwellnessstudio.com"), restructure ("wellnessstudio" → "studiowellness"), use a "get" or "try" prefix, or hyphenate as a last resort (one hyphen max).

## DNS setup after registration

Cleanest workflow, regardless of registrar:

1. We add the customer's domain as a zone in our Cloudflare account (free)
2. We send the customer two nameserver addresses
3. Customer changes nameservers at their registrar to point to those
4. After propagation, we add the custom domain to their Pages project; SSL provisions automatically

Steps 1, 2, and 4 are ours. Step 3 is the customer's (or ours if concierge).

Note: the domain registration stays in the customer's name. Only the DNS zone lives in our Cloudflare account, and they can move nameservers anywhere they want at any time. This preserves the no-lock-in stance.

If a customer refuses to change nameservers (rare): we can use a CNAME record on a subdomain (`www.theirdomain.com`) and a redirect from the apex. Slightly worse but functional.

## Concierge workflow (internal)

When a customer chooses concierge:

1. Confirm exact legal entity name and contact info (this matters for ICANN registration)
2. Register at Porkbun in their name, using our payment method
3. Tag in Airtable as "managed domain"; set renewal reminder 60 days before expiry
4. Configure DNS through to Cloudflare ourselves
5. Bill the domain cost annually as a clearly-labeled pass-through line item, no markup beyond the original $25 setup
6. In the welcome email, state plainly: "Your domain is registered in your name. If you ever leave us, we'll transfer it to any registrar you want at no charge."

When they leave: initiate transfer-out at Porkbun, provide the auth code, done.

## Common gotchas

- **WHOIS privacy:** must be enabled, should be free. Porkbun and Spaceship include it by default. If a registrar charges, it's the wrong registrar.
- **Auto-renewal:** strongly recommend enabling. A lapsed domain can be grabbed in minutes and ransomed back.
- **Multi-year registration:** small savings plus protection against forgetting. 2–3 years is fine; don't go beyond 5.
- **Email forwarding:** usually free at recommended registrars. Take it if offered — lets them have `info@theirdomain.com` forward to their existing inbox without paying for hosted email.
- **Things to refuse at registrar checkout:** premium DNS (Cloudflare gives it free), SSL certificates (also free via us), site builders, "domain protection" beyond standard privacy, "professional email" upsells. Most small businesses want forwarding, not a $6/month Workspace seat.

## Existing domains

If a customer already has a domain at another registrar:

- **Default: don't move it.** Just change the DNS to Cloudflare's nameservers. Less risky, faster, no transfer fee.
- **Transfer only if:** their current registrar is GoDaddy, very expensive, or about to expire and they want to consolidate.
- **Transfer process:** unlock domain at old registrar → get auth code → initiate transfer at new registrar → approve via email → wait 5–7 days. Domain extends by 1 year as part of the transfer.

If they've lost access to their old registrar, the public WHOIS record will show where it's registered. Recovery is usually a support ticket with proof of identity. This can take a week or more; manage expectations.

---

## Customer-facing walkthrough (templates)

Copy-paste these. Bracketed fields get filled in per customer.

### Email 1: Register the domain

> **Subject:** Quick walkthrough — registering [domain.com]
>
> Hi [Name],
>
> Here's the simplest path to getting [domain.com] registered. Takes about 10 minutes.
>
> **1. Go to porkbun.com.** They're who we recommend — fair pricing, no upsell games, clean checkout.
>
> **2. Search for [domain.com].** If it's available, add it to your cart. If not, reply to this email and we'll pick something else together.
>
> **3. At checkout:**
> - Take WHOIS privacy (should be free)
> - Skip the upsells: no premium DNS, no SSL, no website builder, no "professional email" — we handle all of that on our end
> - Email forwarding is optional and usually free; take it if you want emails to addresses like info@[domain.com] forwarded to your existing inbox
> - 1 year is fine; 2–3 years gets a small discount if you'd like
>
> **4. Create your Porkbun account in your name** (not ours). Use an email address you'll have access to long-term — this is where renewal reminders will go.
>
> **5. Once you're done, reply to this email** and let me know it's registered. I'll send the next short step.
>
> Any questions, just reply. Happy to hop on a quick call if you'd rather we do it together.
>
> — [Your name]

### Email 2: Point the domain at the site

Send after they confirm registration.

> **Subject:** Step 2 — connecting [domain.com] to your site
>
> Nice work. One more short step.
>
> **1. Log into Porkbun and click on [domain.com].**
>
> **2. Find the "Authoritative Nameservers" section** (sometimes called "NS Records"). Replace the current nameservers with these two:
>
> ```
> [ns1.example.cloudflare.com]
> [ns2.example.cloudflare.com]
> ```
>
> **3. Save the change.**
>
> That's it on your end. It takes anywhere from 5 minutes to 24 hours for the change to fully propagate across the internet. We'll handle the rest and email you when your site is live at [domain.com].
>
> — [Your name]

### Optional: short call script (if they'd rather do it together)

Helpful for less-technical customers. 10–15 minutes on a screen share.

1. Open porkbun.com together, search the domain, confirm it
2. Walk them through creating their account (their name, their email, their card)
3. Checkout — actively tell them what NOT to click ("ignore that one... skip that one")
4. After purchase, navigate to the domain settings together
5. Either change nameservers live OR explain we'll send them in an email and they can do it later

Reassure them several times that this is a one-time setup, not something they'll need to revisit.

## Open questions to resolve

- Whether to formalize the $25 concierge fee or fold it into the standard build
- Whether to maintain an affiliate relationship with Porkbun or any preferred registrar (small revenue; tradeoff is editorial independence in our recommendation)
- How to handle customers who insist on a domain we don't think is great (too long, hard to spell, weird TLD). Current default: tell them honestly once, then build whatever they want

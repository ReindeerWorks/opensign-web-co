# Business Overview

## The problem we solve

Small business owners know they need a website but every path is broken. Agencies are expensive, slow, and require a pile of information before they'll even start. DIY consumes hours and produces something mediocre. Subscription tools (Squarespace, Wix) feel templated and never quite fit. And once a site exists, it's never clear what's included in hosting and what costs extra, so owners often just stop touching it. The result is a class of customer who either skips having a website entirely or spends nights and weekends cobbling one together — and either way feels resentful about it.

We're aiming squarely at that decision point.

## Who this is for

The customer we serve is the small business owner who needs a website but can't justify the cost of an agency and doesn't have the time, taste, or appetite to build it themselves. We've been that customer. We're building for them on purpose, not as a way station to a more upmarket buyer.

In specifics:

- Single-location service businesses and small retailers
- An existing website that's dated, broken, or absent
- Comfortable with a modest monthly fee for hosting and light maintenance (firm pricing TBD; see `hosting-strategy.md`)
- Located in whatever geography we're currently working

Good initial verticals to test: restaurants/cafés/bakeries, salons/barbers/spas, solo or small-firm independent professionals (lawyers, dentists, optometrists, chiropractors), contractors (HVAC, plumbing, electrical), fitness/yoga/martial arts studios, specialty retail (bookstores, boutiques, pet shops). Bad fits and explicit skips: large chains, multi-location businesses with corporate IT, anything regulated enough to need legal review on copy (medical claims, financial advisory), anything we couldn't comfortably show off in our portfolio.

## What we promise

Two commitments shape every decision we make. They go on our marketing site, by name.

**Accessible pricing.** A small business should be able to afford a real website and ongoing maintenance without it being a line item that hurts. We do that by automating production aggressively, not by cutting corners on the work itself. The entry tier exists for the customer who genuinely couldn't pay agency prices, and it never goes away — even when larger customers ask us to focus on them instead.

**No lock-in, ever.** If a customer leaves, we export the full static site and help them migrate wherever they want. If their domain is registered through us, we transfer ownership to them. This is publicly stated, prominently. Most agencies treat the inability to leave as a feature; we treat it as a threat to the customer, and the opposite as marketing. People who are confident they can leave are more willing to start.

## How the model works

Two things make the business viable at the price point we're targeting.

**Claude-assisted production at every stage where humans don't add irreplaceable value.** Cold-outreach mockups, brand intake briefs, the bulk of build work, and routine update execution all run through automation. Humans stay in the loop for: closing conversations with prospects, final QA on customer-facing deliverables, design judgment on the new templates we add to our generation library each quarter, and any support request the automation flags as ambiguous or risky. The traditional agency cost structure is people-hours; ours shifts most of that to compute.

**Recurring hosting and light maintenance as the revenue base.** Build fees alone produce lumpy income and rusty incentives — every customer is a one-off scramble. The real business is monthly hosting with included small changes, priced transparently, with the changes themselves handled mostly through email-driven update automation: the customer emails what they want; the system understands, executes, asks for confirmation when there's any ambiguity, and escalates to us when it's beyond scope or carries risk. Cold outreach with finished mockups is our acquisition engine, not our value prop — it works because it removes the leap of faith and costs us almost nothing per prospect.

Tying both together is a hard rule: every customer should feel like the site was made *for them*, not adapted from a template. The automation buys us scale; the variety discipline (see `design-system-and-variety.md`) keeps the work from devolving into a thousand versions of the same page.

## What we are not

- Not an agency. No 20-page proposals, no 6-month projects, no "we'll get back to you next quarter."
- Not a SaaS tool. We don't make customers learn an editor; they email us changes.
- Not WordPress jockeys. Our sites are static and fast.
- Not a marketing agency. We make the website; we don't run their ads.
- Not a high-margin boutique. The model works on volume, not on each customer being a five-figure check.

## Operating model: designed for scale, scrappy at first

We're designing for an endgame of ~1,000 customers, not 50. That choice constrains decisions we make today. The update automation has to actually work, not be a half-measure we'll patch later. The mockup generation has to defend against sameness at volume, not rely on a human glancing at every batch. Pricing has to make sense at scale, not just at the first 20 customers. The published commitments above have to be ones we can honor when we have 1,000 of them — not just 10.

That said, the first 6–12 months will be visibly scrappier than the endgame. The CRM is Airtable. The status page is a static file. The on-call rotation is "whoever has their laptop open." This is fine. The discipline is making sure that the things we *can't* easily walk back later — the pricing structure, the no-lock-in promise, the customer commitment, the underlying automation architecture — are built right from the start, even when the surface area is small enough that we could fake them.

And one principle that survives the scaling: better to send 50 great mockups in a week than 500 mediocre ones. Volume that erodes quality eats the brand, and the brand is the business.

## Success metrics

For the first 90 days, optimize for learning, not revenue:

- Cost per prospect, all-in (API, tooling, email send): target under ~$2
- Reply rate on cold outreach (baseline guess: 1–3%)
- Reply-to-call rate and call-to-close rate
- How many "this feels like a previous one" rejections during human review of mockup samples

Once a stable funnel exists, the single most important number to track is **average minutes of human attention per customer per month.** At our price point the model works if this stays under ~5 minutes; it gets tight at 15 and breaks at 30. Everything else — net new MRR per week, churn rate, gross margin — follows from this number.

## Open questions

- Business name and domain
- Initial geographic focus and first industry vertical
- Pricing calibration — placeholder direction is roughly $20–25/mo monthly with an aggressive annual-prepay discount, build fee at or near $0 (firm numbers TBD in `hosting-strategy.md`)
- Whose name and inbox cold outreach goes out under (yours, Richard's, or a shared studio identity)

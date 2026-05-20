# Prospecting Playbook

The wedge: showing up with finished mockups is dramatically more compelling than asking for a discovery call. We trade cheap compute for expensive conversion. Every other detail in this playbook serves that core idea.

## Target list construction

Start narrow. Pick **one geography + one industry per week.** Reasons:

- Local context lets mockups reference real landmarks, neighborhoods, weather, vernacular — quality goes up
- Industry-specific patterns let us iterate the brief template and component-bucket biases (see `design-system-and-variety.md`)
- A narrow batch is measurable: we can actually see what reply rate looks like for "independent dentists in Lancaster County, PA" before scaling
- Easier to be embarrassed by 50 prospects in one industry than 50 in fifty industries (and embarrassment is the friction that produces quality)

**Sourcing leads:**
- Google Places API for businesses matching the industry within a radius
- Cross-reference against existing-website-quality heuristics (see `automation-pipeline.md` Stage 1)
- Final list: 50–200 leads per week initially, scaling significantly higher as the funnel proves out (see conversion math below)

## Outreach format

Email beats LinkedIn beats phone for this approach. The mockups are visual and the medium needs to support them.

### Email structure (short!)

Aim for under 100 words, ideally under 75.

```
Subject: A couple of quick mockups for [Business Name]

Hi [First Name],

I'm [Your Name] — my brother Richard and I make websites for small
businesses. Saw [Business Name] [specific reason] and put together two
quick ideas for what yours could look like:

→ previews.[ourdomain].com/[business-slug]

If either feels close, reply and we'll polish your favorite. Hosting
from $19/mo, your site is always yours. If not, no worries either way.

— [Your Name]
[ourdomain].com
```

The "[specific reason]" matters. Without it, the email reads as automated. With it, the email reads as if a real person spent a minute on this business. Good examples:

- "Saw your booth at the Friday farmers market last weekend"
- "Saw your shop is closing in on its 10th year"
- "Your reviews are wild — clearly something special is happening there"
- "Noticed you're one of the few [X] in [neighborhood]"

These don't have to be deeply researched. They have to be specific enough to be unmistakably human.

The price line near the end ("Hosting from $19/mo, your site is always yours") is the only piece of marketing positioning in the email — it hits both the affordability angle and the no-asset-lock-in promise in eight words, before they've even clicked through. Anything more than that turns the email into a pitch.

**Replies are answered by a human, never an auto-reply.** You or Richard takes them. The first interaction sets the tone for the whole relationship; the update automation in `automation-pipeline.md` is for existing customers, not prospects.

### What we don't do

- **No long follow-up sequences.** One follow-up email after 5–7 days, max. If they didn't reply, move on. We have more leads than time.
- **No fake personalization.** Either someone (or a careful prompt) wrote the email after looking at the business, or it doesn't go out. The mass-mailed-but-tries-to-look-personal vibe is recognizable and counterproductive.
- **No high-pressure CTAs.** The mockups do the selling. "Reply to see more" or "limited time" cheapens the offer.
- **No discount pitching.** This isn't a SaaS landing page. We don't have to convince anyone to "act now."

## Expected conversion (educated guess, falsify with data)

- ~1–3% reply rate on cold outreach
- ~40–60% of replies → real discovery conversation
- ~30–50% of conversations → close
- Net: ~0.2–1% of prospects become customers

At 100 prospects/week, that's 0.2–1 new customers per week. Looks slow on paper. Compounds: a year in, that's ~10–50 customers at a blended ~$22/mo (see `hosting-strategy.md`), or $220–1,100 added MRR plus the upfront annual prepayments from customers who chose that path.

Hitting the 1,000-customer endgame in `business-overview.md` requires scaling prospect volume aggressively. Rough targets to anchor against:

- ~100 customers: 100–200 prospects/week, sustained roughly a year
- ~500 customers: 300–500 prospects/week
- ~1,000 customers: 500–1,000 prospects/week

Volume scales cheaply — each prospect costs ~$2 all-in (compute + email send). At 500 prospects/week that's ~$4K/month in prospecting spend, real but sustainable against the MRR it generates.

The first few cohorts will tell us where the real numbers are. Track them.

## Ethical / legal baseline

- Comply with CAN-SPAM and applicable equivalents in any geography we email into. Real reply-to address, real physical address in footer, working unsubscribe.
- No scraping behind logins. Public data only.
- No impersonating known platforms or anyone else's brand.
- If a prospect asks how we got their info: tell them plainly. "Google Maps and public business listings."
- If anyone asks to be removed, remove them and don't re-add them to any future list.

## Mockup privacy considerations

Mockups live at predictable, publicly-accessible URLs (`previews.[ourdomain].com/[slug]`). This is intentional — easy to share, easy for a prospect to forward to a partner or spouse. Risks and mitigations:

- We use the business's name (public information) and contact info (public information). We don't use logos or trademarks they own.
- We use generic stock photography for mockups, NOT photos pulled from their existing site or social accounts unless those photos are clearly marked for reuse.
- Once a prospect engages and pays, we then license/source/photograph real imagery for the production build.
- Mockup URLs expire 30 days after generation. The mockup is taken down unless the prospect signs up.

## Variations worth testing

The "send 2 mockups cold" approach is our v1 hypothesis. Things to test once we have baseline data:

- **Pricing A/B ($25 vs $35).** This is the first scheduled test, per `hosting-strategy.md`. Send 100 prospects at each price point in the same vertical/geography and read the conversion gap.
- **One mockup + "tell us what to change"** — invites collaboration earlier; might convert better because the choice burden is lower.
- **Mockup + short Loom-style video walkthrough** — adds human warmth, costs more compute time.
- **No mockup, just a screenshot teaser linking to a "create one for me" form** — costs us nothing until they engage; might work for verticals where the mockup approach underperforms.
- **Targeting source variation** — Google Maps vs. industry directories vs. local Chamber of Commerce listings. Different sources select for different kinds of business.

Run any test for at least 100 prospects before drawing conclusions. Small samples lie.

## The "no" responses are useful

Track reasons prospects say no, even briefly:

- "Have one already" (we misqualified — improve the filter)
- "Can't afford it" (real signal; might suggest the entry tier needs to be even more accessible, or this vertical is wrong)
- "Don't trust it" (signal that our marketing site or email needs more credibility cues)
- "Not interested" (fine, move on)
- No response at all (the default; don't read meaning into any single one)

Patterns in the "no" pile point at fixes faster than patterns in the "yes" pile.

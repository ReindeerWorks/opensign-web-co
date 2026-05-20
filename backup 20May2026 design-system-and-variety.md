# Design System and Variety

## The risk

LLMs have a house style. Left unchecked, they default to: Inter or Geist sans-serif, generous whitespace, a gradient hero, a three-card feature row, a navy-or-purple-or-emerald accent color, vague tech-startup polish. Without intervention, 100 sites we generate will look like 100 versions of the same site, and the business dies.

This is the single biggest design risk and gets the most discipline.

## Our defense: four layers

1. A curated **Style Library** of distinct design DNAs
2. An **industry-to-DNA mapping** so a yoga studio doesn't get the same DNA as a law firm
3. **Per-batch constraints** forcing variety inside a single prospect's 3 mockups
4. **Rolling visual review** of recent sends to catch creeping sameness

## 1. The Style Library

Maintain ~15–20 named design DNAs. Each one is a complete aesthetic spec, not just a color palette. A DNA defines:

- **Typography pair** — display + body, with weight ranges, tracking, line height
- **Color system** — 3–5 palettes that fit this DNA (e.g., Editorial's palettes are different from Brutalist Indie's)
- **Layout grid** — symmetric, asymmetric, magazine, list-driven, brutalist, etc.
- **Imagery treatment** — full-bleed photo, illustration, no imagery, halftone, etc.
- **Motion** — none, subtle (fade-ins), prominent (parallax, animated transitions)
- **Density** — sparse / balanced / dense

### Seed DNAs to start with

- **Editorial** — serif display, generous margins, photo-led, magazine-style spreads
- **Brutalist Indie** — bold sans, hard edges, monochrome with one accent, asymmetric, deliberately "designed"
- **Warm Hospitality** — handwritten or warm serif, cream/terracotta/sage palettes, photo-rich, generous
- **Clinical Precision** — clean geometric sans, blue/gray/white, strict grid, minimal imagery
- **Boutique Retail** — display serif headlines, fashion-magazine inspired, full-bleed photography, restrained type
- **Local Trade** — strong sans, single primary color, list-driven, mobile-first, no-nonsense
- **Soft Modern** — rounded sans, pastel palettes, illustration over photography, friendly
- **Old-School Storefront** — varsity or carnival-display headlines, off-white backgrounds, hand-built feel
- **Tech-Forward Service** — mono headline pairings, dark mode option, structured but lively
- **Print-Inspired** — newspaper or magazine typography conventions, ink-heavy, considered
- **Maximalist Color** — bold palette, layered shapes, expressive headlines, controlled chaos

Add to this list over time. Quarterly: retire any DNA that produces weak results, add new ones inspired by sites you admire in the wild.

Each DNA gets a written spec and a representative example so Claude can pull it by name and apply it consistently.

## 2. Industry → DNA mapping

Soft rules: each industry has a set of DNAs that work and a set that don't. Within the allowed set, randomize per project so two restaurants don't get the same DNA.

| Industry | Good fits | Avoid |
|---|---|---|
| Law firms | Clinical Precision, Editorial, Print-Inspired | Brutalist Indie, Maximalist Color, Soft Modern |
| Restaurants | Warm Hospitality, Editorial, Old-School Storefront, Boutique Retail | Clinical Precision |
| Yoga / wellness | Soft Modern, Warm Hospitality, Editorial | Brutalist Indie, Local Trade |
| Contractors / trades | Local Trade, Tech-Forward Service | Boutique Retail, Editorial |
| Salons / spas | Boutique Retail, Soft Modern, Editorial | Local Trade, Brutalist Indie |
| Boutique retail | Boutique Retail, Editorial, Maximalist Color | Clinical Precision, Local Trade |
| Fitness studios | Brutalist Indie, Tech-Forward Service, Local Trade | Soft Modern, Warm Hospitality |
| Independent medical | Clinical Precision, Soft Modern | Brutalist Indie, Maximalist Color |

Expand this table as you encounter new verticals.

## 3. Per-batch constraints (the most important lever)

For each prospect, we generate 3 mockups. They MUST be in three meaningfully different DNAs. Same DNA with different colors does not count as different. The prospect should be choosing between distinct creative directions, not three flavors of the same thing.

Additionally, draw one **random constraint card** per batch to force creative pressure. Examples of constraint cards:

- "At least one mockup must use horizontal scrolling on a section"
- "At least one mockup must use a serif display face"
- "At least one mockup must NOT use a large hero photo"
- "At least one mockup must use a non-rectangular hero shape"
- "At least one mockup must place navigation somewhere other than the top"
- "At least one mockup must use a numbered list as the primary content structure"
- "At least one mockup must use an off-white or non-white background as primary"
- "Use only two fonts across all three mockups, distributed differently"

These pressure the generator out of defaults. Build a list of 30+ constraints; randomly draw one per batch.

## 4. Rolling visual review

Maintain a folder (or Airtable view) of the last 25 sites sent. Before approving a new mockup batch, glance at the grid. If anything in the new batch feels like it could be confused with something from the last 10, regenerate it.

This is a 60-second check but it catches drift that the per-batch process can miss.

## Reference-first generation (optional but powerful)

Before generating a mockup, optionally find 1–2 real-world sites in the same industry that you admire (NOT to copy, but as design references). Feed them to Claude as inspiration. This grounds the output in real-world variety rather than LLM defaults.

Sources for references: awwwards.com, godly.website, siteinspire.com, httpster.net, and just looking at independent businesses in cities known for design (Portland, Copenhagen, Tokyo, Melbourne).

## Things Claude should default to NOT doing

Unless a DNA specifically calls for them:

- The "three-card feature row right under the hero" layout
- Generic gradient backgrounds
- Inter / Geist / DM Sans (rotate among other fonts; Google Fonts has hundreds)
- Centered hero with big H1, smaller subhead, two buttons
- Stock photography from Unsplash's most-downloaded set
- Emoji as visual decoration
- "Trusted by" rows with logos
- Generic SaaS-style language ("supercharge your...", "the modern way to...")

These are the LLM defaults. We deliberately avoid them. When they appear, ask: does this DNA actually need this, or did I default to it?

## Quality bar

A mockup is ready to send when:
- It feels like it was designed by a human who cared about this specific business
- It's clearly distinct from the other two in the batch
- It would not be confused with a recent mockup we sent another prospect
- It works at 375px width as well as 1440px
- All the business's real info is correct

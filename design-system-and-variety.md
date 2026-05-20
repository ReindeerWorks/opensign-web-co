# Design System and Variety

## The risk

LLMs have a house style. Left unchecked, they default to: Inter or Geist sans-serif, generous whitespace, a gradient hero, a three-card feature row, a navy-or-purple-or-emerald accent color, vague tech-startup polish. Without intervention, 1,000 sites we generate will look like 1,000 versions of the same site, and the business dies.

This is the single biggest design risk at our scale, and gets the most discipline.

## How we defend against it

The defense has two layers, working together:

1. **Generation-time control via a component bucket.** We don't generate "a website" — we generate a combination of pre-defined components (type pairs, palettes, grids, hero treatments, voice registers, etc.) with compatibility rules and forced rotation. The bucket constrains what the LLM can default to.

2. **Selection-time control via overgeneration and filtering.** Generate more mockups than we need, then run automated similarity detection (see `automation-pipeline.md`) against recent sends. Pick the most distinct ones to send.

The two work together: the bucket prevents most sameness at the source; the filter catches drift the bucket can't see.

Two named tools sit on top:

- **DNA presets** — curated, named combinations of components that we know work for specific aesthetics (Editorial, Warm Hospitality, etc.). Starting points, not the only path.
- **Industry → preset mapping** — soft rules about which DNA presets fit which verticals.

## The component bucket

Each mockup is a combination of choices across these component categories. Components have compatibility rules; not every option works with every other option.

### Visual components

**Type pair** — display + body font combination, with weight ranges, tracking, and line height. Seed values include serif/sans pairings, mono accents, varsity display, geometric sans, etc. Explicitly avoid Inter, Geist, and DM Sans — the LLM defaults. Use Google Fonts' wider catalog deliberately.

**Color palette** — 3–5 colors per palette, semantically labeled (primary, surface, accent, text). Seed palettes span warm/cream, cool/blue-gray, monochrome with one accent, earthy/terracotta, high-saturation maximalist, soft pastels, and ink-heavy print.

**Grid layout** — symmetric, asymmetric, magazine spreads, brutalist offset, list-driven, full-bleed image, framed/contained.

**Hero treatment** — full-bleed photo, illustration, halftone-treated photo, type-led (no imagery), pattern/texture, video, split-screen, no hero (skip straight to content).

**Navigation placement** — top horizontal, left vertical, hamburger-only, bottom fixed, in-page anchors only, minimal/no nav.

**Imagery style** — photography (warm, editorial, documentary), illustration, iconographic, mixed, none.

**Density** — sparse, balanced, dense. Different from grid — describes how packed each section feels.

**Motion** — none, subtle (fade-ins, gentle parallax), prominent (animated transitions, scroll effects).

### Voice components

Without these, visually distinct sites still all sound the same. Voice components are part of the bucket.

**Tone register** — formal, conversational, warm, sparse, lyrical, plainspoken.

**Sentence cadence** — short-and-punchy, flowing-and-long, varied, list-driven.

**Hook style** — question opener, statement opener, scene-setter, fact-led, anecdote-led.

**Vocabulary level** — simple/everyday, elevated, technical, mixed.

**Person** — first-person ("We do X"), second-person ("You'll find..."), third-person/descriptive.

**Energy** — subdued, enthusiastic, matter-of-fact, playful.

## Compatibility rules

Not every combination works. Examples:

- Brutalist type pair with pastel palette → no
- Clinical grid with playful voice → no
- Type-led hero with sparse density → no (it'll feel empty)
- Maximalist color with sparse density → no (defeats the point)
- Old-school storefront type with prominent motion → no (clashing eras)

These rules get encoded in the generator. New rules get added when human review or real data flags a combination that consistently feels wrong.

## Forced rotation: used vs. unused

Each component value carries a status: available, recently-used, or in-cooldown. When generating a batch, the system draws from the available pool. After use, that component moves to recently-used for a cooldown period (length tunable; start with ~25 batches). When the available pool thins out, recently-used components rotate back in.

This applies *per component*, not per whole mockup. The same color palette might come back into rotation while the type pair is still in cooldown — that's fine. It's the *combinations* that need to feel fresh, and rotation at the component level forces fresh combinations naturally without the operator having to think about it.

## DNA presets

Named, curated combinations of components that work well together. Starting points — not the only path to a mockup, but a fast route to known-good combinations when we don't want to roll fresh from the bucket.

**Seed presets:**

- **Editorial** — serif display, generous margins, photo-led, magazine-style spreads, lyrical voice
- **Brutalist Indie** — bold sans, hard edges, monochrome with one accent, asymmetric grid, plainspoken voice
- **Warm Hospitality** — handwritten or warm serif, cream/terracotta/sage palettes, photo-rich, warm voice
- **Clinical Precision** — clean geometric sans, blue/gray/white, strict grid, minimal imagery, matter-of-fact voice
- **Boutique Retail** — display serif headlines, fashion-magazine inspired, full-bleed photography, elevated voice
- **Local Trade** — strong sans, single primary color, list-driven, mobile-first, plainspoken, no-nonsense
- **Soft Modern** — rounded sans, pastel palettes, illustration over photography, conversational voice
- **Old-School Storefront** — varsity or carnival display headlines, off-white backgrounds, anecdote-led voice
- **Tech-Forward Service** — mono headline pairings, dark-mode option, structured but lively, mixed voice
- **Print-Inspired** — newspaper or magazine typography conventions, ink-heavy, factual voice
- **Maximalist Color** — bold palette, layered shapes, expressive headlines, enthusiastic voice

Each preset is a recipe — a specific combination of component values that adds up to a coherent feel. The bucket can still vary *within* a preset (which exact serif, which precise palette) — the high-level recipe just stays coherent.

Add to this list over time. Retire presets that produce weak results. Quarterly review.

## Industry → DNA preset mapping

Soft rules: each industry has presets that tend to work and presets to avoid. Within the allowed set, randomize per prospect so two restaurants in the same week don't get the same preset.

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

Expand the table as new verticals enter the prospecting rotation.

## Overgeneration and filtering

For each prospect, generate 4 mockups rather than the 2 we send. Run them through automated similarity detection (perceptual hashing plus LLM-vision check; mechanics in `automation-pipeline.md`) against the rolling 100 most recent sends. Pick the 2 most distinct from the set of 4.

This costs ~2x the generation compute per prospect. At our API price points that's still pennies, and it's the strongest defense against the slow drift that the bucket alone won't catch. The two mockups we send should also be meaningfully distinct from each other — the filtering step enforces that pairwise as well.

## Reference-first generation (optional but powerful)

When entering a new vertical, or when we want maximum novelty inside an existing one, look at real-world sites in the same industry that we admire — NOT to copy, but as design references. Decompose what they're doing into component values (type pair, palette, hero treatment, etc.), and either pick similar combinations from the bucket or add the new components to the bucket if they're genuinely new.

Sources: awwwards.com, godly.website, siteinspire.com, httpster.net, and independent businesses in cities known for design (Portland, Copenhagen, Tokyo, Melbourne).

This is also the main way the bucket grows over time — by extracting components from work we admire in the wild.

## Things the generator defaults to NOT doing

These are LLM defaults the bucket explicitly excludes. They appear in component options ONLY when a specific preset or compatibility rule justifies them.

- The "three-card feature row right under the hero" layout
- Generic gradient backgrounds
- Inter / Geist / DM Sans typefaces
- Centered hero with big H1, smaller subhead, two buttons
- Stock photography from Unsplash's most-downloaded set
- Emoji as visual decoration
- "Trusted by" logo rows
- Glassmorphism / frosted-glass UI elements as decoration
- Generic SaaS-style language ("supercharge your...", "the modern way to...")

The exclusion list grows as we identify new LLM creep patterns. When something on this list appears in a generated mockup, ask: is it earning its place via a specific preset or rule, or did the generator default to it?

## Quarterly bucket review

Every quarter, review the bucket: retire component values that produced weak results, add new components from work admired in the wild, tighten compatibility rules where combinations have repeatedly felt off, and audit the exclusion list for new LLM-creep patterns. The bucket is a living system; quarterly review is what keeps it from going stale.

## Quality bar

A mockup is ready to send when:

- It feels like it was designed by a human who cared about this specific business
- It's clearly distinct from the other mockup in the batch
- It would not be confused with a recent mockup we sent another prospect (per the automated similarity check)
- It works at 375px width as well as 1440px
- All the business's real info is correct
- The voice matches the business — a brutalist treatment paired with a warm friendly dentist is a generator failure, not a creative win

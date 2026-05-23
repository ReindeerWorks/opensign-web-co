# Open Sign Web Co — CLAUDE.md

Project-specific context for Claude Code sessions in this repo.

## What this project is

A website creation + hosting business for small businesses. Cold outreach with finished mockups, no agency overhead, transparent pricing ($25/mo monthly or $19/mo annually), no asset lock-in. The strategic source of truth lives in `business-overview.md`, `hosting-strategy.md`, `automation-pipeline.md`, `design-system-and-variety.md`, `prospecting-playbook.md`, and `domain-registration-playbook.md` — read whichever applies before making decisions in unfamiliar territory.

## Stack

- Astro 5 + TypeScript + Tailwind — marketing site and customer sites
- Cloudflare Pages — hosting (one project per customer, at scale)
- Python — one-off pipeline scripts in `scripts/`
- Airtable — CRM / pipeline tracker
- Google Places API (New) v1 — lead generation
- Anthropic API — LLM-driven content generation
- Resend — transactional email (when set up)
- Stripe — billing (when set up)

## Credentials

All credentials live in `.env` at the project root (gitignored). Each bash call spawns a fresh shell, so source the file per command:

    set -a; source .env; set +a && <command>

Current env vars: `OPENSIGN_AT_BASE_ID`, `OPENSIGN_AT_BASE_API_KEY`, `GOOGLE_PLACES_API_KEY`, `ANTHROPIC_API_KEY`. Never inline credentials, never commit them.

## File structure

- `src/` — Astro source for the marketing site
- `scripts/` — Python utilities for the lead/brief/mockup pipeline
- `public/` — static assets
- `.env` — credentials (gitignored)
- `*.md` at project root — strategic reference docs

## Existing pipeline scripts

- `scripts/pull_leads.py` — Google Places → Airtable Leads table. Vertical-interleaved, idempotent, dedupes on Google Place ID.
- `scripts/evaluate_sites.py` — Quality-bar heuristics for existing websites. Populates Site Quality singleSelect + Site Issues + Site Issues Raw (JSON).
- `scripts/generate_briefs.py` — Places Details + reviews → structured markdown brief. Uses Google's generativeSummary as a seed when present, falls back to LLM-original when absent.

## Working patterns (load-bearing — read before working)

**Audit before change.** When touching a schema, data model, or unfamiliar API, read first and report findings before editing. Surface assumptions early so they get corrected cheaply instead of expensively.

**Verify external contracts against reality.** Don't trust API docs alone — hit the endpoint with real data, inspect the actual response, then write the integration. Required-but-undocumented fields are the norm. APIs often include undocumented AI-generated enrichments (Google Places returns generativeSummary, editorialSummary, attribute flags, etc.) — find them, use them.

**Use IDs, not display names.** Airtable table IDs, field IDs, view IDs, option IDs — stable. Display names get renamed. Centralize all IDs in a constants block at the top of each script. Same applies to other external systems.

**Coerce types at the boundary.** Numeric fields written to external systems need explicit `float()` / `int()`. Empty values map to `null`, not `0` or `NaN`. Booleans likewise. Strings should be stripped.

**Scripts must be idempotent.** Re-running should overwrite or skip, never duplicate. Check for existing records (e.g., by Google Place ID, by lead UUID) before inserting.

**Smoke test → review → live run.** Always dry-run on a small sample (2–10 records) before live writes. Surface findings to the user, get approval, then run live. The cadence has caught real issues every time it's been used.

**One task per session, narrow scope.** If a task could plausibly be split into smaller steps, stop and ask before splitting. Default is one task at a time so the user can review between steps.

## Airtable gotchas

- `singleSelect` fields take a bare option-ID string as the value, not `{"id": "..."}`. The object form 422s with `INVALID_VALUE_FOR_COLUMN`. Same bare-string shape works regardless of whether you reference fields by ID or by name.
- `createdTime` field type can't be created via the Meta API (`UNSUPPORTED_FIELD_TYPE_FOR_CREATE`). Must be added manually in the Airtable UI.
- Meta API returns field NAMES as keys by default. Pass `returnFieldsByFieldId=true` to get field IDs instead.

## Design discipline (when working on mockups or marketing site)

Design distinctiveness is the product. Generic-looking = failure. Before generating any visual work, read `design-system-and-variety.md` for the DNA presets, component bucket, compatibility rules, and the explicit exclusion list of LLM defaults to avoid (Inter/Geist fonts, three-card feature rows, generic gradients, etc.).

Mobile-first by default. Test layouts at 375px before 1440px.

## What not to do

- Don't introduce new dependencies without a clear reason. If you add one, name what you considered as the alternative and why this won.
- Don't refactor opportunistically. Change the minimum needed to accomplish the task — no drive-by refactors, no unrequested tests or docs.
- Don't commit credentials, ever.
- Don't use display names for cross-system references — use IDs.
- Don't deploy changes to a customer's live site without explicit customer confirmation (the preview-and-confirm step is non-negotiable per `automation-pipeline.md` Stage 8).

## When in doubt

Stop and ask, especially mid-task. A clarifying question costs less than an undo. If you hit something genuinely ambiguous, surface it rather than guessing.
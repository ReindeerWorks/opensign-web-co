#!/usr/bin/env python3
"""
Generate structured brand-intake briefs (Stage 2) for active Lead prospects.

For each lead where:
  - Site Quality is Weak or No Site
  - Brief field is empty (or --lead-id forces overwrite)

we fetch fresh Google Places Details, build a Claude prompt grounded in the
Airtable record + Places Details + the Site Quality verdict, call the
Anthropic Messages API, and write the resulting markdown brief back to the
Brief field.

Usage:
    python3 scripts/generate_briefs.py [--dry-run] [--limit N] [--lead-id RECID] [--model NAME]

Args:
    --dry-run     Print briefs; do not PATCH Airtable.
    --limit N     Cap briefs generated per run.
    --lead-id ID  Regenerate one lead (record ID), forcing overwrite.
                  Bypasses both the empty-Brief filter and the
                  Weak/No-Site filter.
    --model NAME  Override Claude model. Default: claude-sonnet-4-6.

Re-running in batch mode is idempotent (existing briefs are kept; --lead-id
forces an overwrite when iterating on the prompt or model).

Env (loaded from open-sign-web-co/.env by the caller):
    OPENSIGN_AT_BASE_ID
    OPENSIGN_AT_BASE_API_KEY
    GOOGLE_PLACES_API_KEY
    ANTHROPIC_API_KEY

## Brief structure (v1)
Schema is enforced by the system prompt: markdown with fixed section
headers, an explicit Source line marking generativeSummary vs. LLM-written,
hedge-language rules for Vibe/Palette, data-grounded-only rules for Key
info / Services / Standout themes, and an INSUFFICIENT INFO escape hatch
when public data is too thin.

## Airtable gotchas
(See scripts/pull_leads.py and scripts/evaluate_sites.py for the canonical
write-up.) This script only writes to a multilineText field (Brief), so the
singleSelect option-ID rules don't apply — it's just plain text.

## Reading Site Quality and Industry from Airtable
With `returnFieldsByFieldId=true` and no `cellFormat=json`, singleSelect
fields come back as their DISPLAY-NAME STRING ("Weak", "Bar"), not the
option ID and not a dict. ACTIVE_QUALITIES below matches against the
display name — keep it in sync if you rename options in the UI.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---- Airtable constants (from Meta API audit) ----------------------------

AT_BASE_ID    = os.environ.get("OPENSIGN_AT_BASE_ID", "")
AT_API_KEY    = os.environ.get("OPENSIGN_AT_BASE_API_KEY", "")
GOOGLE_KEY    = os.environ.get("GOOGLE_PLACES_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

LEADS_TABLE_ID = "tblESiclDloDb62Ce"

FIELD = {
    "name":            "fldmsO0zX05NXZe7N",
    "business_name":   "fldcV6NJJBAoz5YdL",
    "address":         "fld1fMhUcNaF0LVGX",
    "city":            "fldbXvTOjgipseg27",
    "state":           "fldFwNNmwbVP2q6Rc",
    "phone":           "fldPTFJkRORoY3yI7",
    "website":         "fldYJZYO5AIyQ79WP",
    "place_id":        "fld3x5qgVFf2X4JPR",
    "industry":        "fldtlq78EsDh0K6cJ",
    "site_quality":    "fldODBV2JZCQUZzt5",
    "site_issues":     "fldEOTIBLTknr6nnl",
    "site_issues_raw": "fldvomzQVpzuFuz7O",
    "brief":           "fldoqqD5DLX2zdFdC",
}

# Display-name strings as returned by Airtable for the Site Quality singleSelect.
ACTIVE_QUALITIES = {"Weak", "No Site"}

# Default model. Bump to claude-opus-4-7 if dry-run briefs come out generic.
DEFAULT_MODEL = "claude-sonnet-4-6"

# Sentinel the LLM emits when public data is too thin to write a credible brief.
INSUFFICIENT_MARKER = "## INSUFFICIENT INFO"

# ---- Google Places (New) v1 Details ------------------------------------

# Wider mask than pull_leads.py: we want reviews, summaries, attribute flags,
# accessibility, parking, payment, and price signals to feed the LLM.
PLACES_FIELD_MASK = ",".join([
    "id", "displayName", "primaryType", "primaryTypeDisplayName", "types",
    "formattedAddress",
    "nationalPhoneNumber", "websiteUri",
    "rating", "userRatingCount", "priceLevel", "priceRange",
    "regularOpeningHours.weekdayDescriptions",
    "businessStatus", "editorialSummary", "generativeSummary",
    "reviews",
    "accessibilityOptions", "parkingOptions", "paymentOptions",
    "takeout", "delivery", "dineIn", "curbsidePickup", "reservable",
    "servesBreakfast", "servesLunch", "servesDinner", "servesBrunch",
    "servesBeer", "servesWine", "servesCoffee", "servesDessert",
    "servesVegetarianFood", "servesCocktails",
    "outdoorSeating", "liveMusic", "menuForChildren", "restroom",
    "goodForChildren", "goodForGroups", "goodForWatchingSports", "allowsDogs",
])

# ---- HTTP helper --------------------------------------------------------

def http_request(url, method="GET", headers=None, body=None, timeout=90):
    """Tiny urllib wrapper. Returns (status, parsed_json_or_text)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw

# ---- Places Details fetch ----------------------------------------------

def fetch_place_details(place_id):
    url = f"https://places.googleapis.com/v1/places/{urllib.parse.quote(place_id)}"
    headers = {
        "X-Goog-Api-Key":   GOOGLE_KEY,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    status, payload = http_request(url, "GET", headers)
    if status != 200:
        raise RuntimeError(f"Places Details {status}: {payload}")
    return payload

def trim_places_for_prompt(p):
    """Drop photo blobs and noisy URI fields from reviews so the prompt
    stays focused on signal (and burns fewer input tokens)."""
    out = dict(p)
    out.pop("photos", None)
    reviews = []
    for r in p.get("reviews", []):
        reviews.append({
            "rating":      r.get("rating"),
            "text":        (r.get("text") or {}).get("text") or "",
            "publishTime": r.get("relativePublishTimeDescription"),
            "author":      (r.get("authorAttribution") or {}).get("displayName"),
        })
    if reviews:
        out["reviews"] = reviews
    return out

# ---- Site context extraction -------------------------------------------

def extract_site_context(lead_fields):
    """Pull the Site Quality verdict + key issues from the Lead's fields so
    the LLM can write the Website line in Key info with template/age detail."""
    quality = lead_fields.get(FIELD["site_quality"]) or "Unknown"
    issues  = lead_fields.get(FIELD["site_issues"]) or ""
    raw_str = lead_fields.get(FIELD["site_issues_raw"]) or ""
    final_url = None
    templates = []
    footer_year = None
    if raw_str:
        try:
            raw = json.loads(raw_str)
            final_url = raw.get("final_url")
            heur = raw.get("heuristics") or {}
            templates = heur.get("templates_detected") or []
            footer_year = heur.get("footer_year_latest")
        except json.JSONDecodeError:
            pass
    return {
        "verdict":            quality,
        "issues_summary":     issues,
        "final_url":          final_url,
        "templates_detected": templates,
        "footer_year_latest": footer_year,
    }

# ---- Claude prompt -----------------------------------------------------

# TODO(next-prompt-revision): tighten the WEBSITE LINE section below to keep
# interpretive language out of Key info. Stick to what's literally in
# EXISTING WEBSITE CONTEXT — verdict, template name, footer year, mobile
# flags. Inferences like "custom or aging static site" belong in Vibe &
# tone, not Key info. Observed on Warehouse Gourmet in the v1 dry-run.

SYSTEM_PROMPT = """You write structured brand-intake briefs for a small-business website redesign service. Each brief feeds downstream mockup generation, so it must capture what's DISTINCTIVE about THIS specific business — not generic copy.

# OUTPUT FORMAT

Produce a markdown brief matching this exact structure (when there is enough public data; otherwise see INSUFFICIENT INFO below):

```
# {Business Name}

## One-line description
**Source:** {pick exactly one: "Google generativeSummary" or "LLM" — see SOURCE LINE below}

{one sentence — what this business is}

## Vibe & tone
{2–3 sentences capturing distinctive feel, with hedge language where inferred}

## Palette direction
{2–3 sentences — color story + texture/style guidance, with hedge language where inferred}

## Key info
- **Address:** {formatted address}
- **Phone:** {national phone number, or "—" if missing}
- **Website:** {URL} — {short note about current state}
- **Hours:** {compact one-line summary, e.g. "Closed Mon; Tue–Sun 7am–3pm"}
- **Price range:** {priceLevel description, or e.g. "$10–$20" from priceRange, or "—"}

## Services & offerings
- {bullets — dine-in / takeout / delivery, alcohol service, parking, accessibility, etc.}

## Content sections needed
- {bullets — what the mockup homepage should contain}

## Standout themes from reviews
- **{theme}** — {sentence with concrete review-grounded specifics: specific dishes, products, staff behaviors, atmosphere details}
```

# EPISTEMIC RULES — STRICT

1. **Vibe & tone** and **Palette direction** sections MAY include inferences from business name, naming patterns, neighborhood context, etc. — but only with explicit HEDGE LANGUAGE: "the name suggests…", "leaning into the X angle could…", "if named for…", "could lean…". NEVER make confident factual claims about origin or history without source data.

2. **Key info**, **Services & offerings**, and **Standout themes** are DATA-GROUNDED ONLY. Every claim must be traceable to the provided data. No inferences. No leaps. No invented services, hours, prices, or amenities.

3. When in doubt, prefer hedged language over confident claims.

4. **Standout themes** must cite specific review content: specific dishes/drinks/products, named staff behaviors, concrete atmosphere details. Generic praise ("friendly staff", "good food") is NOT a standout theme — skip it. If the reviews contain only generic praise with no specifics, that section gets few or no bullets.

# SOURCE LINE

- Set "**Source:** Google generativeSummary" if the Places data contains a `generativeSummary.overview.text` field. Use Google's text as a seed; rephrase or extend if needed to make it stronger.
- Set "**Source:** LLM" if no `generativeSummary` was provided. Write the one-liner yourself, grounded in the available data.

# WEBSITE LINE

Combine the Site Quality verdict + a one-line summary of Site Issues from the EXISTING WEBSITE CONTEXT block. Examples:
- "aldusbrewing.com — currently a default Wix template (the reason they're a candidate)"
- "thebrittoncoffee.com — outdated template, mobile-responsive issues"
- "no existing website — clean slate"
- "(broken Square site URL — 404)"

Be specific about template/age when known. If the verdict is "No Site", say so explicitly. The point is to give the downstream mockup generator context on what to contrast against.

# HOURS LINE

Compress the weekday descriptions into ONE compact line — never list seven days verbatim. Examples:
- "Closed Mon; Tue–Sun 7am–3pm"
- "Mon–Fri 6am–6pm; Sat–Sun 7am–4pm"
- "Wed–Sat 11:30am–9pm; closed Sun–Tue"

# INSUFFICIENT INFO

If public data is too thin to write a credible brief — no reviews, OR all reviews are generic with no specific details AND no useful attribute fields AND no editorialSummary/generativeSummary — output ONLY this and stop:

```
# {Business Name}

## INSUFFICIENT INFO

{1–2 sentences explaining what's missing}
```

Guideline (not a hard rule): 5 reviews with concrete specifics is usually enough. 5 reviews of pure generic praise with no specifics is borderline — call INSUFFICIENT INFO if you genuinely can't identify what makes this place distinctive. Be honest, not generous.

# OUTPUT

Output ONLY the markdown brief — no preamble, no commentary, no code fences wrapping the whole thing. Start with `# {Business Name}`."""

def build_user_message(lead_fields, places, site_ctx):
    business = {
        "name":     lead_fields.get(FIELD["business_name"]) or lead_fields.get(FIELD["name"]) or "(no name)",
        "industry": lead_fields.get(FIELD["industry"]) or "(unknown)",
        "city":     lead_fields.get(FIELD["city"]) or "",
        "state":    lead_fields.get(FIELD["state"]) or "",
        "phone":    lead_fields.get(FIELD["phone"]) or "",
        "website":  lead_fields.get(FIELD["website"]) or "",
    }
    parts = [
        "BUSINESS RECORD (from Airtable):",
        json.dumps(business, indent=2),
        "",
        "EXISTING WEBSITE CONTEXT (from our Site Quality evaluation):",
        json.dumps(site_ctx, indent=2),
        "",
        "GOOGLE PLACES DETAILS:",
        json.dumps(trim_places_for_prompt(places), indent=2),
    ]
    return "\n".join(parts)

# ---- Anthropic Messages API call ---------------------------------------

def call_claude(system, user_text, model, max_tokens=3000, timeout=120):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key":         ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    body = {
        "model":      model,
        "max_tokens": max_tokens,
        "system":     system,
        "messages":   [{"role": "user", "content": user_text}],
    }
    status, payload = http_request(url, "POST", headers, body, timeout=timeout)
    if status != 200:
        raise RuntimeError(f"Anthropic API {status}: {payload}")
    blocks = payload.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    if not text:
        raise RuntimeError(f"Anthropic returned empty text. Stop reason: {payload.get('stop_reason')}")
    return text, (payload.get("usage") or {})

# ---- Airtable I/O ------------------------------------------------------

def list_scope(lead_id=None):
    """Return list of (record_id, fields_dict) for leads in scope.

    Batch mode: leads where Site Quality is in ACTIVE_QUALITIES and Brief
    is empty. --lead-id mode: that single lead, regardless of state."""
    headers = {"Authorization": f"Bearer {AT_API_KEY}"}

    if lead_id:
        url = (f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}/{lead_id}"
               "?returnFieldsByFieldId=true")
        status, payload = http_request(url, "GET", headers)
        if status != 200:
            raise RuntimeError(f"Airtable get {lead_id} {status}: {payload}")
        return [(payload["id"], payload.get("fields", {}))]

    out = []
    offset = None
    while True:
        qs = "pageSize=100&returnFieldsByFieldId=true"
        if offset:
            qs += f"&offset={urllib.parse.quote(offset)}"
        url = f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}?{qs}"
        status, payload = http_request(url, "GET", headers)
        if status != 200:
            raise RuntimeError(f"Airtable list {status}: {payload}")
        for rec in payload.get("records", []):
            f = rec.get("fields", {})
            if f.get(FIELD["site_quality"]) not in ACTIVE_QUALITIES:
                continue
            if f.get(FIELD["brief"]):
                continue
            out.append((rec["id"], f))
        offset = payload.get("offset")
        if not offset:
            break
    return out

def patch_brief(record_id, brief_text):
    url = f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AT_API_KEY}",
        "Content-Type":  "application/json",
    }
    body = {"fields": {FIELD["brief"]: brief_text}}
    status, payload = http_request(url, "PATCH", headers, body)
    if status != 200:
        raise RuntimeError(f"Airtable patch {record_id} {status}: {payload}")
    return payload

# ---- Main --------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=(
            "Generate brand-intake briefs (Stage 2) for active Lead prospects "
            "via Google Places Details + Anthropic Messages API."
        )
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Print briefs; do not PATCH Airtable.")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap briefs generated per run.")
    p.add_argument("--lead-id", default=None,
                   help="Regenerate one lead (record ID), forcing overwrite.")
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Claude model (default: {DEFAULT_MODEL}).")
    args = p.parse_args()

    for var, val in [
        ("OPENSIGN_AT_BASE_ID",      AT_BASE_ID),
        ("OPENSIGN_AT_BASE_API_KEY", AT_API_KEY),
        ("GOOGLE_PLACES_API_KEY",    GOOGLE_KEY),
        ("ANTHROPIC_API_KEY",        ANTHROPIC_KEY),
    ]:
        if not val:
            print(f"ERROR: env var {var} is not set", file=sys.stderr)
            sys.exit(2)

    print(f"Mode:    {'DRY RUN — no Airtable writes' if args.dry_run else 'LIVE — will PATCH Airtable'}")
    print(f"Model:   {args.model}")
    if args.lead_id:
        print(f"Scope:   single lead {args.lead_id} (forces overwrite)")
    else:
        print(f"Scope:   leads where Site Quality in {sorted(ACTIVE_QUALITIES)} AND Brief is empty")
    if args.limit:
        print(f"Limit:   {args.limit} briefs max")
    print()

    leads = list_scope(lead_id=args.lead_id)
    print(f"Leads in scope: {len(leads)}")
    if args.limit:
        leads = leads[: args.limit]
        print(f"After --limit:  {len(leads)}")
    print()

    full_briefs    = 0
    insufficient   = 0
    errors         = 0
    written        = 0
    total_in_tok   = 0
    total_out_tok  = 0

    for rec_id, f in leads:
        name = f.get(FIELD["business_name"]) or f.get(FIELD["name"]) or "(no name)"
        quality = f.get(FIELD["site_quality"])
        place_id = f.get(FIELD["place_id"])

        print(f"=== [{rec_id}]  {name}  ({quality}) ===")

        if not place_id:
            print(f"    ! no Google Place ID — skipping", file=sys.stderr)
            errors += 1
            print()
            continue

        try:
            places = fetch_place_details(place_id)
        except Exception as e:
            print(f"    ! Places Details error: {e}", file=sys.stderr)
            errors += 1
            print()
            continue

        site_ctx = extract_site_context(f)
        user_msg = build_user_message(f, places, site_ctx)

        try:
            brief_text, usage = call_claude(SYSTEM_PROMPT, user_msg, args.model)
        except Exception as e:
            print(f"    ! Claude API error: {e}", file=sys.stderr)
            errors += 1
            print()
            continue

        in_t  = usage.get("input_tokens")  or 0
        out_t = usage.get("output_tokens") or 0
        total_in_tok  += in_t
        total_out_tok += out_t

        is_insufficient = INSUFFICIENT_MARKER in brief_text
        if is_insufficient:
            insufficient += 1
            print(f"    INSUFFICIENT INFO  ({in_t} in / {out_t} out tokens)")
        else:
            full_briefs += 1
            print(f"    brief generated  ({in_t} in / {out_t} out tokens)")
        print()
        print(brief_text)
        print()

        if args.dry_run:
            continue

        try:
            patch_brief(rec_id, brief_text)
            written += 1
        except Exception as e:
            errors += 1
            print(f"    ! WRITE ERROR: {e}", file=sys.stderr)

        # Be polite to both APIs.
        time.sleep(0.5)

    print()
    print("=== SUMMARY ===")
    print(f"  full briefs:          {full_briefs}")
    print(f"  insufficient info:    {insufficient}")
    print(f"  errors:               {errors}")
    print(f"  total tokens:         {total_in_tok} in / {total_out_tok} out")
    if args.dry_run:
        print()
        print("  (dry run — nothing written)")
    else:
        print(f"  written to Airtable:  {written}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate self-contained HTML website mockups (Stage 3) for qualifying Leads.

For each lead where:
  - Brief is non-empty AND does not start with "## INSUFFICIENT INFO"
  - Mockup URL 1 is empty

we send the Brief to Claude with a "Warm Hospitality" DNA system prompt, write
the returned HTML to public/previews/<slug>.html, and PATCH Mockup URL 1 in
Airtable with the live Cloudflare Pages URL.

Site Quality is intentionally NOT used as a filter — the presence of a Brief
already implies the lead passed the quality bar in Stage 2.

Usage:
    python3 scripts/generate_mockups.py [--dry-run] [--limit N]

Args:
    --dry-run   Call Claude as normal, but write no files and make no Airtable
                writes. Prints name, slug, target URL, and the first 200 chars
                of the generated HTML for each lead.
    --limit N   Cap mockups generated per run (applies in both modes).

Env (loaded from open-sign-web-co/.env by the caller):
    OPENSIGN_AT_BASE_ID
    OPENSIGN_AT_BASE_API_KEY
    ANTHROPIC_API_KEY

## Hosting / URL contract
Cloudflare Pages serves public/previews/foo.html at /previews/foo (extension
stripped). Astro copies public/ verbatim, so dropping HTML files into
public/previews/ is all that is needed for them to deploy on the next build.

## Airtable gotchas
(See scripts/pull_leads.py for the canonical write-up.) This script only writes
to a url field (Mockup URL 1), so the singleSelect option-ID rules don't apply
— it's just a string value. typecast=false is kept for symmetry; url fields
accept any string.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# ---- Airtable constants (from Meta API audit) ----------------------------

AT_BASE_ID    = os.environ.get("OPENSIGN_AT_BASE_ID", "")
AT_API_KEY    = os.environ.get("OPENSIGN_AT_BASE_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

LEADS_TABLE_ID = "tblESiclDloDb62Ce"

FIELD = {
    "name":          "fldmsO0zX05NXZe7N",
    "business_name": "fldcV6NJJBAoz5YdL",
    "brief":         "fldoqqD5DLX2zdFdC",
    "mockup_url_1":  "fldMYUoN6Kpjda0gJ",
    "site_quality":  "fldODBV2JZCQUZzt5",
}

# Sentinel the brief generator emits when public data was too thin. Leads with
# this marker get skipped — no mockup is worth generating without a real brief.
INSUFFICIENT_MARKER = "## INSUFFICIENT INFO"

# ---- Output paths --------------------------------------------------------

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT   = os.path.dirname(SCRIPT_DIR)
PREVIEWS_DIR   = os.path.join(PROJECT_ROOT, "public", "previews")

PUBLIC_URL_BASE = "https://opensignwebco.com/previews"

# ---- Claude model --------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS    = 12000

# ---- HTTP helper --------------------------------------------------------

def http_request(url, method="GET", headers=None, body=None, timeout=180):
    """Tiny urllib wrapper. Returns (status, parsed_json_or_text).

    Timeout bumped vs. briefs because Claude takes longer to emit ~8k tokens
    of HTML than a 2–3k-token markdown brief."""
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

# ---- Slug ---------------------------------------------------------------

def slugify(name):
    """Lowercase → spaces-to-hyphens → strip non-alphanumeric/non-hyphen →
    collapse consecutive hyphens → trim leading/trailing hyphens."""
    s = (name or "").lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")

# ---- Claude prompt ------------------------------------------------------

SYSTEM_PROMPT = """You are generating a self-contained HTML website mockup for a small business.
Output ONLY valid HTML — no markdown, no explanation, no code fences. Start with <!DOCTYPE html>.

DNA: Warm Hospitality
Typography: Google Fonts only. Pick ONE display font from: Playfair Display, Lora,
Cormorant Garamond, Crimson Text. Pair with one body font from: Source Serif Pro,
Libre Baskerville, PT Serif. You may add one handwritten accent (Dancing Script or
Caveat) used sparingly — one decorative element only. Whenever you use the
handwritten accent font, ensure the text color has strong contrast against its
background — dark text on light backgrounds, light text on dark. Never render
handwritten text in a color close to the background color.

Palette: Build a 4-color scheme using these ranges:
  cream:      #FAF7F2–#F5ECD7
  terracotta: #C4603A–#B85C38
  sage:       #7A8C6E–#6B7F5E
  warm brown: #5C3D2E–#4A3728
Pick one accent (terracotta or sage) and one near-neutral (cream or warm brown).

Voice: Warm, conversational, first or second person. Short sentences. Reads like a
person wrote it, not a marketing team. No filler phrases. No "supercharge your",
"the modern way to", "seamlessly", "passionate about", "dedicated to".

Imagery: CSS gradient blocks only — no <img> tags, no external image URLs. Use warm
terracotta-to-cream gradients for visual breaks and section backgrounds. Make them
feel intentional, not placeholder-ish: vary dimensions, layer them with text.

Layout: Mobile-first. Must render correctly at 375px width. All CSS in a single
<style> block in <head>. No JavaScript. No external CSS. Only external dependency:
Google Fonts via @import in the style block.

Explicitly forbidden:
- Inter, Geist, DM Sans typefaces
- Three-card feature row directly under hero
- No generic gradient backgrounds (purple-to-blue, navy-to-teal, etc.). Warm
  palette gradients (cream-to-terracotta, sage-to-brown) are acceptable only for
  full-bleed decorative sections, never as the primary hero background.
- Centered hero with big H1, subhead, two buttons
- "Trusted by" logo rows
- Glassmorphism or frosted glass
- Emoji as decoration
- Generic stock imagery URLs (placeholder.com, via.placeholder.com, etc.)
- Lorem ipsum"""

USER_PROMPT_PREFIX = """Generate a complete website mockup for the business described in the brief below.

Requirements:
- Include ALL real business info: name, address, phone, hours, services exactly as
  stated in the brief. Do not invent, omit, or paraphrase contact information.
- Build sections matching exactly what's listed under "Content sections needed".
- Work the standout review themes naturally into copy — don't quote them directly,
  let them inform the voice.
- Tone must match the brief's "Vibe & tone" section.
- The result should feel like it was designed for this specific business, not adapted
  from a template.

BRIEF:
"""

def build_user_message(brief_text):
    # Concatenate rather than .format() so curly braces in the brief don't blow up.
    return USER_PROMPT_PREFIX + brief_text

# ---- Anthropic Messages API call ---------------------------------------

def call_claude(system, user_text, model, max_tokens=MAX_TOKENS, timeout=180):
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
    """Return list of (record_id, fields_dict) for leads where Brief is a
    real brief (non-empty, not INSUFFICIENT INFO) and Mockup URL 1 is empty.

    --lead-id mode: fetches that single record, bypassing both the
    INSUFFICIENT INFO filter and the empty-Mockup-URL-1 filter (so we can
    force-regenerate truncated or stale mockups).

    Filters client-side; mirrors generate_briefs.py's approach (Airtable
    filterByFormula doesn't play nicely with multilineText `startswith` and
    field-name vs field-ID quirks)."""
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
            brief = (f.get(FIELD["brief"]) or "").strip()
            if not brief:
                continue
            if brief.startswith(INSUFFICIENT_MARKER):
                continue
            if f.get(FIELD["mockup_url_1"]):
                continue
            out.append((rec["id"], f))
        offset = payload.get("offset")
        if not offset:
            break
    return out

def patch_mockup_url(record_id, url_value):
    url = f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AT_API_KEY}",
        "Content-Type":  "application/json",
    }
    body = {
        "fields":   {FIELD["mockup_url_1"]: url_value},
        "typecast": False,
    }
    status, payload = http_request(url, "PATCH", headers, body)
    if status != 200:
        raise RuntimeError(f"Airtable patch {record_id} {status}: {payload}")
    return payload

# ---- Main --------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=(
            "Generate HTML mockups (Stage 3) for active Lead prospects via the "
            "Anthropic Messages API; write to public/previews/<slug>.html and "
            "patch Mockup URL 1 in Airtable."
        )
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Call Claude as normal but write no files and make no Airtable writes.")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap mockups generated per run. Ignored when --lead-id is set.")
    p.add_argument("--lead-id", default=None,
                   help="Regenerate one lead (record ID), forcing overwrite. Bypasses the "
                        "empty-Mockup-URL-1 filter; --limit is ignored.")
    args = p.parse_args()

    for var, val in [
        ("OPENSIGN_AT_BASE_ID",      AT_BASE_ID),
        ("OPENSIGN_AT_BASE_API_KEY", AT_API_KEY),
        ("ANTHROPIC_API_KEY",        ANTHROPIC_KEY),
    ]:
        if not val:
            print(f"ERROR: env var {var} is not set", file=sys.stderr)
            sys.exit(2)

    print(f"Mode:    {'DRY RUN — no files, no Airtable writes' if args.dry_run else 'LIVE — will write files and PATCH Airtable'}")
    print(f"Model:   {DEFAULT_MODEL}")
    print(f"Output:  {PREVIEWS_DIR}/<slug>.html  →  {PUBLIC_URL_BASE}/<slug>")
    if args.lead_id:
        print(f"Scope:   single lead {args.lead_id} (forces overwrite)")
    else:
        print(f"Scope:   leads with non-empty Brief (excl. INSUFFICIENT INFO) AND empty Mockup URL 1")
        if args.limit:
            print(f"Limit:   {args.limit} mockups max")
    print()

    leads = list_scope(lead_id=args.lead_id)
    print(f"Leads in scope: {len(leads)}")
    if args.limit and not args.lead_id:
        leads = leads[: args.limit]
        print(f"After --limit:  {len(leads)}")
    print()

    if not args.dry_run and leads:
        os.makedirs(PREVIEWS_DIR, exist_ok=True)

    generated     = 0
    errors        = 0
    total_in_tok  = 0
    total_out_tok = 0

    for rec_id, f in leads:
        name = f.get(FIELD["name"]) or f.get(FIELD["business_name"]) or "(no name)"
        slug = slugify(name)

        if not slug:
            print(f"✗ {name}: empty slug after normalization — skipping", file=sys.stderr)
            errors += 1
            continue

        live_url = f"{PUBLIC_URL_BASE}/{slug}"
        out_path = os.path.join(PREVIEWS_DIR, f"{slug}.html")
        brief    = (f.get(FIELD["brief"]) or "").strip()

        print(f"=== [{rec_id}]  {name} ===")
        print(f"    slug: {slug}")
        print(f"    url:  {live_url}")

        try:
            html, usage = call_claude(SYSTEM_PROMPT, build_user_message(brief), DEFAULT_MODEL)
        except Exception as e:
            print(f"✗ {name}: Claude API error: {e}", file=sys.stderr)
            errors += 1
            continue

        in_t  = usage.get("input_tokens")  or 0
        out_t = usage.get("output_tokens") or 0
        total_in_tok  += in_t
        total_out_tok += out_t

        if not html.lstrip().startswith("<!DOCTYPE"):
            print(f"✗ {name}: response did not start with <!DOCTYPE (skipping write). "
                  f"First 200 chars: {html[:200]!r}", file=sys.stderr)
            errors += 1
            continue

        if not html.rstrip().endswith("</html>"):
            print(f"✗ {name}: generation failure: response truncated (missing </html>). "
                  f"Last 200 chars: {html[-200:]!r}", file=sys.stderr)
            errors += 1
            continue

        if args.dry_run:
            print(f"    tokens: {in_t} in / {out_t} out")
            print(f"    first 200 chars of HTML:")
            print(f"    {html[:200]!r}")
            print(f"✓ {slug}  (dry run — not written)")
            print()
            generated += 1
            continue

        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(html)
        except Exception as e:
            print(f"✗ {name}: file write error ({out_path}): {e}", file=sys.stderr)
            errors += 1
            continue

        try:
            patch_mockup_url(rec_id, live_url)
        except Exception as e:
            print(f"✗ {name}: Airtable patch error: {e}", file=sys.stderr)
            errors += 1
            # File was written but Airtable wasn't updated — leave the file in place
            # so a re-run can patch it without re-paying the Claude tokens.
            continue

        print(f"    tokens: {in_t} in / {out_t} out")
        print(f"    wrote:  {out_path}")
        print(f"✓ {slug}")
        print()
        generated += 1

        # Be polite to both APIs.
        time.sleep(0.5)

    print()
    print("=== SUMMARY ===")
    print(f"  generated:           {generated} of {len(leads)} leads")
    print(f"  errors:              {errors}")
    print(f"  total tokens:        {total_in_tok} in / {total_out_tok} out")
    if args.dry_run:
        print()
        print("  (dry run — no files written, no Airtable writes)")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Evaluate the existing website of each Lead against the Stage 1 quality bar
(see automation-pipeline.md). Writes a Site Quality verdict, a human-readable
failure list, a raw JSON record, and a timestamp to Airtable.

Usage:
    python3 scripts/evaluate_sites.py [--dry-run] [--limit N] [--lead-id RECID]

Args:
    --dry-run     Print findings without writing to Airtable.
    --limit N     Cap evaluations per run.
    --lead-id ID  Evaluate just one lead (record ID), regardless of state.
                  Useful for debugging or forcing a re-evaluation.
    (default)     Evaluate all leads where Site Quality is unset.

Re-running is idempotent: it overwrites the four Site * fields on the lead
(no stacking, no duplicate records).

Env (loaded from open-sign-web-co/.env by the caller):
    OPENSIGN_AT_BASE_ID
    OPENSIGN_AT_BASE_API_KEY

## Airtable gotchas
(See scripts/pull_leads.py for the canonical write-up. Same rules apply here:
singleSelect values are bare option-ID strings, never {"id": ...} objects, and
the shape is identical whether the field is referenced by ID or by name.)

## Site Issues Raw JSON schema (v1)
The raw JSON we write to the Site Issues Raw field. STABLE — bump
schema_version on any breaking change so historical entries stay parseable.

{
  "schema_version": 1,                       # int, bumped on breaking changes
  "evaluated_at": "2026-05-21T14:23:11Z",    # ISO 8601 UTC, same as the
                                             # Site Evaluated At field value
  "input_url":  "http://aldusbrewing.com/",  # exactly what was on the Lead
  "final_url":  "https://www.aldusbrewing.com/",  # after redirects; null on
                                                  # network error
  "verdict":    "Strong" | "Weak" | "No Site" | "Error",
  "failures":   ["Footer year: 2018 (8 years old)", ...],
                                             # human-readable failure list,
                                             # one per heuristic that fired
  "fetch": {
    "status":      200 | <int> | null,       # HTTP status; null on network err
    "elapsed_ms":  2511,                     # initial-HTML fetch (no JS)
    "redirected":  true | false,             # final_url != input_url
    "error":       null | "DNS"              # taxonomy: DNS, Timeout,
                 | "Timeout"                 # ConnectionRefused, SSL,
                 | "ConnectionRefused"       # Other
                 | "SSL: <detail>"
                 | "Other: <detail>"
                 | "InvalidURL"              # didn't parse as http(s)
  },
  "heuristics": {
    # Each key is a binary signal we evaluated. null = not evaluated (e.g.
    # because fetch failed). false/empty = evaluated and did not fire.
    "viewport_meta_present":        true | false | null,
    "viewport_width_device_width":  true | false | null,
    "final_scheme":                 "https" | "http" | null,
    "ssl_error":                    null | "<detail>",
    "footer_years":                 [2025] | [],
    "footer_year_latest":           2025 | null,
    "footer_year_old":              true | false | null,
                                    # true iff latest < current_year - 3
    "templates_detected":           ["Wix"] | [],
    "load_ms":                      2511 | null,
    "load_over_6s":                 true | false | null,
    "img_count":                    26 | null
                                    # recorded for future analysis only;
                                    # broken-images heuristic skipped in v1
  }
}

## Heuristic decisions (locked in v1 — adjust here, not silently in code)
- Final URL is what we evaluate (urllib follows redirects). HTTP-only is
  determined by the FINAL scheme, not the input.
- SSL cert invalid / TLS handshake error → verdict = Weak (playbook lists
  "SSL warnings" as a quality-bar failure, not as an Error).
- DNS fail, timeout, connection refused, 4xx, 5xx → verdict = Error.
- 200 OK with content → run all heuristics; verdict = Strong iff none fire,
  else Weak.
- Template detection: any single signature hit in body, headers, or final URL
  flags the platform. Adding a new platform = one entry in TEMPLATE_SIGS.
- Footer year: latest 20XX in <footer>...</footer> (or last 3000 chars of
  body as fallback). Fires iff latest < current_year - 3 (today: < 2023).
- Broken-images: SKIPPED in v1. img_count recorded for later analysis.
- Mobile responsive: viewport meta with width=device-width. No Playwright in
  v1 — the spike showed no false positives across the 3 test URLs.
"""

import argparse
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ---- Airtable constants (from Meta API audit) ----------------------------

AT_BASE_ID = os.environ.get("OPENSIGN_AT_BASE_ID", "")
AT_API_KEY = os.environ.get("OPENSIGN_AT_BASE_API_KEY", "")

LEADS_TABLE_ID = "tblESiclDloDb62Ce"

FIELD = {
    "name":              "fldmsO0zX05NXZe7N",
    "website":           "fldYJZYO5AIyQ79WP",
    "city":              "fldbXvTOjgipseg27",
    "site_quality":      "fldODBV2JZCQUZzt5",
    "site_issues":       "fldEOTIBLTknr6nnl",
    "site_issues_raw":   "fldvomzQVpzuFuz7O",
    "site_evaluated_at": "fld8LPGzbbWwyIXID",
}

# singleSelect option IDs — write bare strings (see "Airtable gotchas").
SITE_QUALITY_OPTION_ID = {
    "Strong":  "selgUFmmFQpnNXhds",
    "Weak":    "sel6MokZiiTODIdQP",
    "No Site": "selnSU7kmS0BOIlyE",
    "Error":   "selKtsTBBbdlvVQbA",
}

# ---- Heuristic config ---------------------------------------------------

SCHEMA_VERSION = 1
FOOTER_YEAR_OFFSET = 3      # flag latest_year < current_year - OFFSET
LOAD_TIME_THRESHOLD_MS = 6000
FETCH_TIMEOUT_SEC = 10

# platform → list of regex patterns. Matched (case-insensitive) against body
# + final URL + header lines. To add a platform (Wordpress.com, Site123,
# Jimdo, Shopify default theme, etc.), append one entry. Single match fires.
TEMPLATE_SIGS = {
    "Wix":         [r'wix\.com', r'static\.parastorage\.com', r'x-wix-'],
    "Squarespace": [r'squarespace\.com', r'static1\.squarespace\.com', r'sqs-'],
    "GoDaddy":     [r'websites\.godaddy', r'\bgodaddy\.com', r'img1\.wsimg\.com'],
    "Weebly":      [r'weebly\.com', r'\.weebly\.net'],
    "Square":      [r'square\.site', r'square\.online'],
}

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

VIEWPORT_RE     = re.compile(r'<meta[^>]+name=["\']viewport["\'][^>]*>', re.I)
WIDTH_DEVICE_RE = re.compile(r'width\s*=\s*device-width', re.I)
FOOTER_RE       = re.compile(r'<footer\b[\s\S]*?</footer>', re.I)
YEAR_RE         = re.compile(r'\b(20\d{2})\b')
IMG_RE          = re.compile(r'<img\b', re.I)

# ---- Fetch --------------------------------------------------------------

def _classify_network_error(exc):
    """Map an exception from urllib.urlopen() to our error taxonomy."""
    msg = str(exc)
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, ssl.SSLError):
            return f"SSL: {reason.__class__.__name__}: {reason}"
        if isinstance(reason, ssl.CertificateError):
            return f"SSL: CertificateError: {reason}"
        if isinstance(reason, socket.timeout):
            return "Timeout"
        if isinstance(reason, ConnectionRefusedError):
            return "ConnectionRefused"
        if isinstance(reason, socket.gaierror):
            return "DNS"
    if isinstance(exc, socket.timeout):
        return "Timeout"
    return f"Other: {type(exc).__name__}: {msg}"

def fetch_site(url, timeout=FETCH_TIMEOUT_SEC):
    """Fetch one URL. Returns dict:
        status:     int or None
        headers:    {str: str}
        body:       str (may be empty)
        elapsed_ms: float
        final_url:  str (post-redirect) or original url on error
        error:      None on success, else taxonomy string
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            elapsed = (time.monotonic() - t0) * 1000
            return {
                "status":     r.status,
                "headers":    dict(r.headers),
                "body":       body,
                "elapsed_ms": round(elapsed, 1),
                "final_url":  r.url,
                "error":      None,
            }
    except urllib.error.HTTPError as e:
        # 4xx/5xx — we have a response, just not OK
        elapsed = (time.monotonic() - t0) * 1000
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return {
            "status":     e.code,
            "headers":    dict(e.headers or {}),
            "body":       body,
            "elapsed_ms": round(elapsed, 1),
            "final_url":  getattr(e, "url", url) or url,
            "error":      None,
        }
    except Exception as e:
        elapsed = (time.monotonic() - t0) * 1000
        return {
            "status":     None,
            "headers":    {},
            "body":       "",
            "elapsed_ms": round(elapsed, 1),
            "final_url":  url,
            "error":      _classify_network_error(e),
        }

# ---- Heuristics ---------------------------------------------------------

def extract_footer_text(html):
    """Best-effort grab of <footer>...</footer>; fallback to last 3000 chars."""
    if not html:
        return ""
    m = FOOTER_RE.search(html)
    if m:
        return m.group(0)
    return html[-3000:]

def detect_templates(body, headers, final_url):
    """Return list of platform names with at least one matching signature."""
    haystack_parts = [body or "", final_url or ""]
    for k, v in (headers or {}).items():
        haystack_parts.append(f"{k}: {v}")
    haystack = "\n".join(haystack_parts)
    hits = []
    for name, sigs in TEMPLATE_SIGS.items():
        for s in sigs:
            if re.search(s, haystack, re.I):
                hits.append(name)
                break
    return hits

def evaluate_site(url):
    """Top-level. Returns (verdict, failures_list, raw_dict)."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    current_year = datetime.now(timezone.utc).year

    raw = {
        "schema_version": SCHEMA_VERSION,
        "evaluated_at":   now_iso,
        "input_url":      url,
        "final_url":      None,
        "verdict":        None,
        "failures":       [],
        "fetch": {
            "status":     None,
            "elapsed_ms": None,
            "redirected": None,
            "error":      None,
        },
        "heuristics": {
            "viewport_meta_present":        None,
            "viewport_width_device_width":  None,
            "final_scheme":                 None,
            "ssl_error":                    None,
            "footer_years":                 [],
            "footer_year_latest":           None,
            "footer_year_old":              None,
            "templates_detected":           [],
            "load_ms":                      None,
            "load_over_6s":                 None,
            "img_count":                    None,
        },
    }

    # --- URL sanity ---
    if not url or not url.strip():
        raw["verdict"] = "No Site"
        return "No Site", [], raw

    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raw["fetch"]["error"] = "InvalidURL"
        raw["verdict"] = "Error"
        raw["failures"] = [f"Invalid URL: {url}"]
        return "Error", raw["failures"], raw

    # --- Fetch ---
    fetched = fetch_site(url)
    raw["fetch"]["status"]     = fetched["status"]
    raw["fetch"]["elapsed_ms"] = fetched["elapsed_ms"]
    raw["fetch"]["error"]      = fetched["error"]
    raw["final_url"]           = fetched["final_url"]
    raw["fetch"]["redirected"] = fetched["final_url"] != url
    raw["heuristics"]["load_ms"] = fetched["elapsed_ms"]

    # SSL handshake failure → Weak (playbook: "SSL warnings")
    if fetched["error"] and fetched["error"].startswith("SSL:"):
        raw["heuristics"]["ssl_error"] = fetched["error"]
        failures = [fetched["error"]]
        raw["verdict"] = "Weak"
        raw["failures"] = failures
        return "Weak", failures, raw

    # Network errors (DNS, timeout, refused, other) → Error
    if fetched["error"]:
        raw["verdict"] = "Error"
        raw["failures"] = [fetched["error"]]
        return "Error", raw["failures"], raw

    # 4xx/5xx → Error (dead/broken/blocked URL, not a quality signal)
    if fetched["status"] != 200:
        raw["verdict"] = "Error"
        raw["failures"] = [f"HTTP {fetched['status']}"]
        return "Error", raw["failures"], raw

    # --- 200 OK: run heuristics ---
    body = fetched["body"]
    headers = fetched["headers"]
    final_url = fetched["final_url"]
    final_scheme = urllib.parse.urlparse(final_url).scheme
    raw["heuristics"]["final_scheme"] = final_scheme

    failures = []

    # HTTP-only (final scheme not https)
    if final_scheme != "https":
        failures.append(f"HTTP-only: final response is {final_scheme}://")

    # Viewport
    vp_match = VIEWPORT_RE.search(body)
    if vp_match:
        raw["heuristics"]["viewport_meta_present"] = True
        has_dw = bool(WIDTH_DEVICE_RE.search(vp_match.group(0)))
        raw["heuristics"]["viewport_width_device_width"] = has_dw
        if not has_dw:
            failures.append("Not mobile-responsive: viewport meta missing width=device-width")
    else:
        raw["heuristics"]["viewport_meta_present"] = False
        raw["heuristics"]["viewport_width_device_width"] = False
        failures.append("Not mobile-responsive: no viewport meta tag")

    # Footer year
    footer = extract_footer_text(body)
    years = sorted({int(y) for y in YEAR_RE.findall(footer)})
    raw["heuristics"]["footer_years"] = years
    if years:
        latest = years[-1]
        raw["heuristics"]["footer_year_latest"] = latest
        is_old = latest < current_year - FOOTER_YEAR_OFFSET
        raw["heuristics"]["footer_year_old"] = is_old
        if is_old:
            age = current_year - latest
            failures.append(f"Footer year: {latest} ({age} years old)")
    else:
        raw["heuristics"]["footer_year_old"] = False

    # Template detection
    templates = detect_templates(body, headers, final_url)
    raw["heuristics"]["templates_detected"] = templates
    if templates:
        failures.append(f"Template detected: {', '.join(templates)}")

    # Load time
    load_ms = fetched["elapsed_ms"]
    is_slow = load_ms > LOAD_TIME_THRESHOLD_MS
    raw["heuristics"]["load_over_6s"] = is_slow
    if is_slow:
        failures.append(f"Load time: {load_ms/1000:.1f}s")

    # Image count (recorded only — heuristic skipped in v1)
    raw["heuristics"]["img_count"] = len(IMG_RE.findall(body))

    verdict = "Weak" if failures else "Strong"
    raw["verdict"] = verdict
    raw["failures"] = failures
    return verdict, failures, raw

# ---- HTTP helpers for Airtable -----------------------------------------

def http_request(url, method="GET", headers=None, body=None, timeout=30):
    """Tiny urllib wrapper. Returns (status, parsed_json_or_text)."""
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
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

# ---- Airtable I/O ------------------------------------------------------

def list_leads(only_unset=True, lead_id=None):
    """Return list of (record_id, fields_dict) for leads in scope.
       fields_dict is keyed by field ID."""
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
            if only_unset and f.get(FIELD["site_quality"]):
                continue
            out.append((rec["id"], f))
        offset = payload.get("offset")
        if not offset:
            break
    return out

def patch_lead(record_id, verdict, failures, raw):
    """Idempotent overwrite of the four Site * fields for one lead."""
    url = f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}/{record_id}"
    headers = {
        "Authorization": f"Bearer {AT_API_KEY}",
        "Content-Type":  "application/json",
    }
    fields = {
        FIELD["site_quality"]:      SITE_QUALITY_OPTION_ID[verdict],
        FIELD["site_issues"]:       "\n".join(failures) if failures else "",
        FIELD["site_issues_raw"]:   json.dumps(raw, separators=(",", ":")),
        FIELD["site_evaluated_at"]: raw["evaluated_at"],
    }
    status, payload = http_request(url, "PATCH", headers, {"fields": fields})
    if status != 200:
        raise RuntimeError(f"Airtable patch {record_id} {status}: {payload}")
    return payload

# ---- Main --------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=(
            "Evaluate Lead websites against the Stage 1 quality bar and write "
            "Site Quality / Site Issues / Site Issues Raw / Site Evaluated At."
        )
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Print findings; do not PATCH Airtable.")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap evaluations per run.")
    p.add_argument("--lead-id", default=None,
                   help="Evaluate just this record ID (forces re-evaluation).")
    args = p.parse_args()

    for var, val in [
        ("OPENSIGN_AT_BASE_ID", AT_BASE_ID),
        ("OPENSIGN_AT_BASE_API_KEY", AT_API_KEY),
    ]:
        if not val:
            print(f"ERROR: env var {var} is not set", file=sys.stderr)
            sys.exit(2)

    print(f"Mode:    {'DRY RUN — no Airtable writes' if args.dry_run else 'LIVE — will PATCH Airtable'}")
    if args.lead_id:
        print(f"Scope:   single lead {args.lead_id} (force re-eval)")
    else:
        print(f"Scope:   all leads where Site Quality is unset")
    if args.limit:
        print(f"Limit:   {args.limit} evaluations max")
    print()

    leads = list_leads(only_unset=(args.lead_id is None), lead_id=args.lead_id)
    print(f"Leads in scope: {len(leads)}")
    if args.limit:
        leads = leads[: args.limit]
        print(f"After --limit:  {len(leads)}")
    print()

    by_verdict = {"Strong": 0, "Weak": 0, "No Site": 0, "Error": 0}
    write_errors = 0
    written = 0

    for rec_id, f in leads:
        name = f.get(FIELD["name"]) or "(no name)"
        city = f.get(FIELD["city"]) or ""
        url  = f.get(FIELD["website"]) or ""

        try:
            verdict, failures, raw = evaluate_site(url)
        except Exception as e:
            print(f"  ! {rec_id}  {name}  EVAL CRASH: {type(e).__name__}: {e}", file=sys.stderr)
            continue

        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1

        head = f"  [{verdict:7s}] {rec_id}  {name}"
        if city:
            head += f"  ({city})"
        print(head)
        print(f"             URL: {url or '(none)'}")
        if raw["final_url"] and raw["final_url"] != url:
            print(f"             →    {raw['final_url']}")
        if failures:
            for fa in failures:
                print(f"             • {fa}")
        elif verdict == "Strong":
            print(f"             • (passes all heuristics)")
        print()

        if args.dry_run:
            continue

        try:
            patch_lead(rec_id, verdict, failures, raw)
            written += 1
        except Exception as e:
            write_errors += 1
            print(f"             ! WRITE ERROR: {e}", file=sys.stderr)

    print()
    print("=== SUMMARY ===")
    print(f"  Strong:   {by_verdict.get('Strong', 0)}")
    print(f"  Weak:     {by_verdict.get('Weak', 0)}")
    print(f"  No Site:  {by_verdict.get('No Site', 0)}")
    print(f"  Error:    {by_verdict.get('Error', 0)}")
    print()
    if args.dry_run:
        print("  (dry run — no writes)")
    else:
        print(f"  written:  {written}")
        print(f"  errors:   {write_errors}")

if __name__ == "__main__":
    main()

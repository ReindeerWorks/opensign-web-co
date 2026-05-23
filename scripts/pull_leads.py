#!/usr/bin/env python3
"""
Pull restaurant / cafe / bakery / bar leads from Google Places (API New v1)
into the Airtable Leads table.

Usage:
    python3 scripts/pull_leads.py [--limit N] [--radius MILES] [--dry-run]

--limit N is the TOTAL number of records written across all four vertical
queries combined, after de-duplication by Google Place ID. It is not N per
query. Default 10.

Env (loaded from open-sign-web-co/.env by the caller):
    OPENSIGN_AT_BASE_ID
    OPENSIGN_AT_BASE_API_KEY
    GOOGLE_PLACES_API_KEY

## Airtable gotchas
(Notes collected while building this script — grep "Airtable gotchas" to find them
from any sibling script in scripts/.)

1. singleSelect write shape: the REST API takes a BARE option-ID STRING as the
   field value, e.g. `{fldXYZ: "selABC"}`. Passing the `{"id": "selABC"}` object
   form (which is correct for linked-record fields) 422s with
   INVALID_VALUE_FOR_COLUMN on singleSelect. Passing the display name (e.g.
   "Restaurant") also 422s when `typecast` is false — and we keep typecast
   false deliberately so unknown options fail loud instead of silently creating
   new ones.

2. Field reference by ID vs. by name: the bare-string singleSelect shape works
   identically whether the field is referenced by its `fld...` ID or by its
   display name. We reference by ID throughout (less brittle to UI renames),
   but the option-value shape is the same either way.
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

AT_BASE_ID = os.environ.get("OPENSIGN_AT_BASE_ID", "")
AT_API_KEY = os.environ.get("OPENSIGN_AT_BASE_API_KEY", "")
GOOGLE_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")

LEADS_TABLE_ID = "tblESiclDloDb62Ce"

FIELD = {
    "name":           "fldmsO0zX05NXZe7N",
    "business_name":  "fldcV6NJJBAoz5YdL",
    "address":        "fld1fMhUcNaF0LVGX",
    "city":           "fldbXvTOjgipseg27",
    "state":          "fldFwNNmwbVP2q6Rc",
    "phone":          "fldPTFJkRORoY3yI7",
    "website":        "fldYJZYO5AIyQ79WP",
    "place_id":       "fld3x5qgVFf2X4JPR",
    "rating":         "fldxh1KodaVqliAfr",
    "review_count":   "fldjtghIaHVimSbKI",
    "hours":          "fldkKbe9AaBkjYZXv",
    "industry":       "fldtlq78EsDh0K6cJ",
    "geography":      "fldIcGBW8WwYtBRJL",
    "source":         "fldZz4xNn7kmFC769",
}

# Single-select option IDs. Writing by field ID requires writing the option's
# ID too — passing the display name 422s with INVALID_VALUE_FOR_COLUMN.
INDUSTRY_OPTION_ID = {
    "Restaurant": "selFO32jMWbnOyZRP",
    "Cafe":       "selUWmyFaL817EywQ",
    "Bakery":     "seldN7HPIyzQTzQei",
    "Bar":        "selHeGpa06EoATgye",
}
SOURCE_GOOGLE_PLACES_ID = "seld4s6igOvLIXHSW"

# ---- Geography ----------------------------------------------------------

DEFAULT_CENTER = {
    "label": "Hanover, PA",
    "latitude": 39.8009,
    "longitude": -76.9830,
}
DEFAULT_RADIUS_MILES = 18  # ~Hanover → Gettysburg (~14mi) + small towns around
METERS_PER_MILE = 1609.34

# ---- Vertical queries ---------------------------------------------------
# Each entry: (text_query, industry_single_select_value)
# We run one Places searchText call per vertical, then dedupe by place_id.

VERTICAL_QUERIES = [
    ("restaurants near {center}", "Restaurant"),
    ("cafes and coffee shops near {center}", "Cafe"),
    ("bakeries and donut shops near {center}", "Bakery"),
    ("bars and pubs near {center}", "Bar"),
]

# Google Places "types" → our Industry single-select. Order matters: when a
# place has multiple types, the first match wins. We check primaryType first
# then walk types[] in order.
TYPE_TO_INDUSTRY = [
    # Bakery before restaurant — donut/bagel shops sometimes also tag restaurant
    ("bakery",              "Bakery"),
    ("donut_shop",          "Bakery"),
    ("bagel_shop",          "Bakery"),
    # Cafe before restaurant — coffee shops often also tag restaurant/cafe
    ("coffee_shop",         "Cafe"),
    ("cafe",                "Cafe"),
    # Bar variants before restaurant — many gastropubs tag both
    ("wine_bar",            "Bar"),
    ("pub",                 "Bar"),
    ("bar_and_grill",       "Bar"),
    ("bar",                 "Bar"),
    ("night_club",          "Bar"),
    # Catch-all restaurant (and *_restaurant via suffix below)
    ("restaurant",          "Restaurant"),
]

def classify_industry(primary_type, types_list, hint):
    """Map a Place's types to our Industry single-select. `hint` is the
    vertical that surfaced this place — used as a tiebreaker only."""
    candidates = []
    if primary_type:
        candidates.append(primary_type)
    candidates.extend(t for t in (types_list or []) if t not in candidates)

    # First pass: exact match against our table
    for cand in candidates:
        for needle, label in TYPE_TO_INDUSTRY:
            if cand == needle:
                return label
    # Second pass: any *_restaurant variant
    for cand in candidates:
        if cand.endswith("_restaurant"):
            return "Restaurant"
    # Fallback: trust the query hint (e.g., we searched "bars" → call it Bar)
    return hint

# ---- HTTP helpers -------------------------------------------------------

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

# ---- Google Places (New) v1 --------------------------------------------

PLACES_FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.addressComponents",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.rating",
    "places.userRatingCount",
    "places.regularOpeningHours.weekdayDescriptions",
    "places.types",
    "places.primaryType",
    "places.businessStatus",
])

def search_places(text_query, center, radius_meters, max_results=20):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_KEY,
        "X-Goog-FieldMask": PLACES_FIELD_MASK,
    }
    body = {
        "textQuery": text_query,
        "maxResultCount": max_results,
        "locationBias": {
            "circle": {
                "center": {"latitude": center["latitude"], "longitude": center["longitude"]},
                "radius": radius_meters,
            }
        },
    }
    status, payload = http_request(url, "POST", headers, body)
    if status != 200:
        raise RuntimeError(f"Places API {status}: {payload}")
    return payload.get("places", [])

# ---- Address parsing ---------------------------------------------------

def parse_city_state(address_components):
    """Pull city (locality) and state (admin_area_level_1 shortText) from the
    structured components. Avoid regex on formatted_address."""
    city = None
    state = None
    for c in address_components or []:
        types = c.get("types", [])
        if "locality" in types and not city:
            city = c.get("longText") or c.get("shortText")
        elif "administrative_area_level_1" in types and not state:
            state = c.get("shortText") or c.get("longText")
    return city, state

# ---- Build Airtable record ---------------------------------------------

def place_to_fields(place, industry, geography_label):
    name = (place.get("displayName") or {}).get("text") or ""
    city, state = parse_city_state(place.get("addressComponents"))

    rating = place.get("rating")
    rating_val = float(rating) if rating is not None else None

    rc = place.get("userRatingCount")
    rc_val = int(rc) if rc is not None else None

    hours_list = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    hours = "\n".join(hours_list) if hours_list else None

    fields = {
        FIELD["name"]:          name,
        FIELD["business_name"]: name,
        FIELD["address"]:       place.get("formattedAddress") or "",
        FIELD["city"]:          city or "",
        FIELD["state"]:         state or "",
        FIELD["phone"]:         place.get("nationalPhoneNumber") or "",
        FIELD["website"]:       place.get("websiteUri") or "",
        FIELD["place_id"]:      place.get("id") or "",
        # Airtable's REST API takes singleSelect as a bare string of the
        # option ID (the {"id": ...} object form is for linked records only
        # and 422s on singleSelect).
        FIELD["industry"]:      INDUSTRY_OPTION_ID[industry],
        FIELD["geography"]:     geography_label,
        FIELD["source"]:        SOURCE_GOOGLE_PLACES_ID,
    }
    if rating_val is not None:
        fields[FIELD["rating"]] = rating_val
    if rc_val is not None:
        fields[FIELD["review_count"]] = rc_val
    if hours:
        fields[FIELD["hours"]] = hours
    return fields

# ---- Airtable I/O ------------------------------------------------------

def airtable_existing_place_ids():
    """Page through Leads and collect every non-empty Google Place ID."""
    seen = set()
    url = (
        f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}"
        f"?fields%5B%5D={FIELD['place_id']}&pageSize=100"
    )
    headers = {"Authorization": f"Bearer {AT_API_KEY}"}
    while True:
        status, payload = http_request(url, "GET", headers)
        if status != 200:
            raise RuntimeError(f"Airtable list {status}: {payload}")
        for rec in payload.get("records", []):
            pid = (rec.get("fields") or {}).get(FIELD["place_id"])
            if pid:
                seen.add(pid)
        offset = payload.get("offset")
        if not offset:
            break
        url = (
            f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}"
            f"?fields%5B%5D={FIELD['place_id']}&pageSize=100&offset={offset}"
        )
    return seen

def airtable_create_records(records):
    """Write up to 10 records per request (Airtable max). Uses typecast=false
    so we get a hard error if a single-select value is unknown."""
    out_created = []
    url = f"https://api.airtable.com/v0/{AT_BASE_ID}/{LEADS_TABLE_ID}"
    headers = {
        "Authorization": f"Bearer {AT_API_KEY}",
        "Content-Type": "application/json",
    }
    for i in range(0, len(records), 10):
        chunk = records[i:i+10]
        body = {"records": [{"fields": f} for f in chunk]}
        status, payload = http_request(url, "POST", headers, body)
        if status != 200:
            raise RuntimeError(f"Airtable create {status}: {payload}")
        out_created.extend(payload.get("records", []))
        time.sleep(0.25)  # be polite — 5 req/sec base limit
    return out_created

# ---- Main --------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description=(
            "Pull restaurant/cafe/bakery/bar leads from Google Places into "
            "the Airtable Leads table."
        )
    )
    p.add_argument("--limit", type=int, default=10,
        help=(
            "TOTAL records to write across all four vertical queries combined, "
            "after de-duplication by Google Place ID (not per-query). Default 10."
        ))
    p.add_argument("--radius", type=float, default=DEFAULT_RADIUS_MILES,
        help=f"Search radius in miles. Default {DEFAULT_RADIUS_MILES}.")
    p.add_argument("--center", default=DEFAULT_CENTER["label"],
        help="Geography label written to the Geography field. Default Hanover, PA.")
    p.add_argument("--dry-run", action="store_true",
        help="Print what would be written; do not call Airtable's create endpoint.")
    args = p.parse_args()

    for var, val in [
        ("OPENSIGN_AT_BASE_ID", AT_BASE_ID),
        ("OPENSIGN_AT_BASE_API_KEY", AT_API_KEY),
        ("GOOGLE_PLACES_API_KEY", GOOGLE_KEY),
    ]:
        if not val:
            print(f"ERROR: env var {var} is not set", file=sys.stderr)
            sys.exit(2)

    center = dict(DEFAULT_CENTER, label=args.center)
    radius_m = args.radius * METERS_PER_MILE

    print(f"Center:  {center['label']}  ({center['latitude']}, {center['longitude']})")
    print(f"Radius:  {args.radius} mi  ({radius_m:.0f} m)")
    print(f"Limit:   {args.limit} total records (deduped across all 4 verticals)")
    print(f"Mode:    {'DRY RUN — no Airtable writes' if args.dry_run else 'LIVE — will write to Airtable'}")
    print()

    # 1. Pull from each vertical (kept in per-vertical queues so we can
    #    round-robin below).
    per_vertical = []      # list[(industry_hint, [places…])]
    pulled_count = 0
    for query_tpl, industry_hint in VERTICAL_QUERIES:
        query = query_tpl.format(center=center["label"])
        print(f"  searching: {query!r}  (industry hint: {industry_hint})")
        results = search_places(query, center, radius_m, max_results=20)
        pulled_count += len(results)
        kept = [
            pl for pl in results
            if pl.get("id")
            and (not pl.get("businessStatus") or pl["businessStatus"] == "OPERATIONAL")
        ]
        per_vertical.append((industry_hint, kept))
        print(f"    → {len(results)} returned, {len(kept)} operational with IDs")

    # 2. Round-robin interleave: restaurant → cafe → bakery → bar → restaurant …
    #    Dedupe by place_id across the rounds (first occurrence wins).
    pulled_by_pid = {}     # place_id -> (industry_hint, place_dict)
    interleaved_order = []  # preserves the round-robin order for the limit slice
    cursors = [0] * len(per_vertical)
    while True:
        progressed = False
        for vi, (industry_hint, queue) in enumerate(per_vertical):
            while cursors[vi] < len(queue):
                pl = queue[cursors[vi]]
                cursors[vi] += 1
                pid = pl["id"]
                if pid in pulled_by_pid:
                    continue  # already taken by an earlier vertical this round
                pulled_by_pid[pid] = (industry_hint, pl)
                interleaved_order.append(pid)
                progressed = True
                break  # move to the next vertical for this round
        if not progressed:
            break
    print()

    # 2. Filter against existing Airtable place IDs
    print("Fetching existing Place IDs from Airtable for dedupe…")
    existing = airtable_existing_place_ids()
    print(f"  {len(existing)} place IDs already in Leads")
    print()

    new_candidates = []
    for pid in interleaved_order:
        if pid in existing:
            continue
        hint, pl = pulled_by_pid[pid]
        new_candidates.append((pid, hint, pl))
    skipped_dupe = len(pulled_by_pid) - len(new_candidates)

    # 3. Apply --limit (after dedupe, as spec'd)
    to_write = new_candidates[: args.limit]

    # 4. Build records
    records, build_errors = [], 0
    for pid, hint, pl in to_write:
        try:
            industry = classify_industry(pl.get("primaryType"), pl.get("types"), hint)
            records.append(place_to_fields(pl, industry, center["label"]))
        except Exception as e:
            build_errors += 1
            print(f"  build error for {pid}: {e}", file=sys.stderr)

    # 5. Preview
    print(f"Pulled from Places: {pulled_count} raw / {len(pulled_by_pid)} unique operational")
    print(f"Already in Airtable (skipped as duplicate): {skipped_dupe}")
    print(f"Would write: {len(records)}  (--limit {args.limit})")
    print()
    industry_name_by_id = {v: k for k, v in INDUSTRY_OPTION_ID.items()}
    print("Records to write:")
    for r in records:
        ind_id = r.get(FIELD["industry"])
        print(f"  - {r.get(FIELD['name'])} | {r.get(FIELD['city'])}, {r.get(FIELD['state'])} | "
              f"industry={industry_name_by_id.get(ind_id, '?')} | "
              f"website={r.get(FIELD['website']) or '(none)'} | "
              f"rating={r.get(FIELD['rating'])} ({r.get(FIELD['review_count'])} reviews)")
    print()

    # 6. Write (or skip)
    write_errors = 0
    written = 0
    if args.dry_run:
        print("DRY RUN — no records written.")
    elif not records:
        print("Nothing to write.")
    else:
        try:
            created = airtable_create_records(records)
            written = len(created)
        except Exception as e:
            write_errors += 1
            print(f"WRITE ERROR: {e}", file=sys.stderr)

    # 7. Summary
    print()
    print("=== SUMMARY ===")
    print(f"  pulled from Places:        {pulled_count}")
    print(f"  unique operational:        {len(pulled_by_pid)}")
    print(f"  skipped as duplicate:      {skipped_dupe}")
    print(f"  would-write (post-limit):  {len(records)}")
    print(f"  written to Airtable:       {written if not args.dry_run else '(dry run)'}")
    print(f"  build errors:              {build_errors}")
    print(f"  write errors:              {write_errors}")

if __name__ == "__main__":
    main()

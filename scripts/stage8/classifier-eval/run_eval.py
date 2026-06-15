#!/usr/bin/env python3
"""
Offline evaluation harness for the Stage 8 inbound classifier.

Reads eval_cases.jsonl, sends each case body through Claude with the system
prompt from classifier_prompt.md, parses the structured tool-use output, and
writes eval_results.csv. Prints per-bucket accuracy and a mismatch list.

Usage (from project root):
    set -a; source .env; set +a
    python3 scripts/stage8/classifier-eval/run_eval.py
    python3 scripts/stage8/classifier-eval/run_eval.py --limit 5
    python3 scripts/stage8/classifier-eval/run_eval.py --case-id AUTO_01
    python3 scripts/stage8/classifier-eval/run_eval.py --model claude-sonnet-4-6

Each run also writes a per-model JSON artifact (results_<model>.json) for
side-by-side comparison across models:
    python3 scripts/stage8/classifier-eval/run_eval.py \\
        --compare results_claude-sonnet-4-6.json results_claude-fable-5.json

Env:
    ANTHROPIC_API_KEY (required)

This script does not touch Airtable, email infrastructure, or the live
classifier in production. It is purely a local iteration loop for tuning
classifier_prompt.md.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

# ---- Config ------------------------------------------------------------

DEFAULT_MODEL = "claude-sonnet-4-6"
# Tier 1 limit is 30k input tokens/min. At ~3500 tokens/request the minimum
# safe gap is ~7s; 8s gives a small buffer.
INTER_REQUEST_SLEEP = 8
# On a 429, sleep this long before retrying. 60s gives the sliding window
# time to drain — 30s tends to retry into another 429.
RATE_LIMIT_RETRY_SLEEP = 60
RATE_LIMIT_MAX_RETRIES = 2
SCRIPT_DIR = Path(__file__).resolve().parent
CASES_PATH = SCRIPT_DIR / "eval_cases.jsonl"
PROMPT_PATH = SCRIPT_DIR / "classifier_prompt.md"
RESULTS_PATH = SCRIPT_DIR / "eval_results.csv"
API_URL = "https://api.anthropic.com/v1/messages"

VALID_BUCKETS = {"INFORMATIONAL", "AUTO_HANDLE", "CLARIFY", "QUOTE", "ESCALATE"}

CLASSIFY_TOOL = {
    "name": "classify_request",
    "description": (
        "Classify the inbound customer email into one of five buckets and "
        "report needs_split if the email contains multiple distinct requests."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "bucket": {
                "type": "string",
                "enum": sorted(VALID_BUCKETS),
                "description": "The routing bucket for this email.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Subjective confidence in the bucket choice (0-1).",
            },
            "reasoning": {
                "type": "string",
                "description": "1-3 sentences explaining the choice, referencing specificity.",
            },
            "needs_split": {
                "type": "boolean",
                "description": "True if the email contains multiple distinct requests.",
            },
            "split_requests": {
                "type": "array",
                "items": {"type": "string"},
                "description": "When needs_split=true, list each distinct request.",
            },
        },
        "required": ["bucket", "confidence", "reasoning", "needs_split"],
    },
}

# ---- HTTP helper (house style, stdlib only) ----------------------------

def http_request(url, method="GET", headers=None, body=None, timeout=120):
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

# ---- Claude call -------------------------------------------------------

def classify(api_key, model, system_prompt, subject, body, timeout=120):
    """Send one case through Claude. Returns the tool_use input dict."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    user_text = f"Subject: {subject}\n\n{body}"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "tools": [CLASSIFY_TOOL],
        "tool_choice": {"type": "tool", "name": "classify_request"},
        "messages": [{"role": "user", "content": user_text}],
    }
    status, resp = http_request(API_URL, "POST", headers, payload, timeout=timeout)
    for _ in range(RATE_LIMIT_MAX_RETRIES):
        if status != 429:
            break
        time.sleep(RATE_LIMIT_RETRY_SLEEP)
        status, resp = http_request(API_URL, "POST", headers, payload, timeout=timeout)
    if status != 200:
        raise RuntimeError(f"Anthropic API {status}: {resp}")
    blocks = resp.get("content") or []
    for b in blocks:
        if b.get("type") == "tool_use" and b.get("name") == "classify_request":
            return b.get("input") or {}
    raise RuntimeError(
        f"No tool_use block in response. stop_reason={resp.get('stop_reason')}, "
        f"content={blocks!r}"
    )

# ---- Eval orchestration ------------------------------------------------

def load_cases(path):
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise RuntimeError(f"{path}:{lineno} bad JSON: {e}")
    return cases

def run(cases, api_key, model, system_prompt):
    rows = []
    for i, case in enumerate(cases, start=1):
        case_id = case["case_id"]
        print(f"  [{i}/{len(cases)}] {case_id} … ", end="", flush=True)
        t0 = time.time()
        try:
            result = classify(
                api_key, model, system_prompt,
                case.get("subject", ""), case.get("body", ""),
            )
        except Exception as e:
            print(f"ERROR ({e})")
            rows.append({
                "case_id": case_id,
                "subject": case.get("subject", ""),
                "expected_bucket": case["expected_bucket"],
                "predicted_bucket": "ERROR",
                "confidence": "",
                "match": False,
                "needs_split_match": "",
                "reasoning": str(e),
                "needs_split": "",
                "notes": case.get("notes", ""),
            })
            if i < len(cases):
                time.sleep(INTER_REQUEST_SLEEP)
            continue

        predicted = result.get("bucket", "")
        bucket_match = predicted == case["expected_bucket"]
        if "expected_needs_split" in case:
            ns_match = bool(result.get("needs_split")) == bool(case["expected_needs_split"])
            match = bucket_match and ns_match
            ns_match_field = ns_match
        else:
            match = bucket_match
            ns_match_field = ""
        dt = time.time() - t0
        print(f"{predicted} (expected {case['expected_bucket']}) "
              f"{'OK' if match else 'MISS'} {dt:.1f}s")

        rows.append({
            "case_id": case_id,
            "subject": case.get("subject", ""),
            "expected_bucket": case["expected_bucket"],
            "predicted_bucket": predicted,
            "confidence": result.get("confidence", ""),
            "match": match,
            "needs_split_match": ns_match_field,
            "reasoning": result.get("reasoning", ""),
            "needs_split": result.get("needs_split", ""),
            "notes": case.get("notes", ""),
        })
        if i < len(cases):
            time.sleep(INTER_REQUEST_SLEEP)
    return rows

def write_results(rows, path):
    fieldnames = [
        "case_id", "subject", "expected_bucket", "predicted_bucket",
        "confidence", "match", "needs_split_match", "reasoning",
        "needs_split", "notes",
    ]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

# ---- Per-model artifact + comparison -----------------------------------

def model_slug(model):
    """Filesystem-safe form of a model id, for the artifact filename."""
    return model.replace("/", "_").replace(" ", "_")

def model_results_path(model):
    return SCRIPT_DIR / f"results_{model_slug(model)}.json"

def write_model_results(rows, model):
    """Persist a per-model artifact keyed by model id.

    One record per case (case_id, expected_bucket, predicted_bucket, match)
    plus a header with the model and its overall score, so two runs on
    different models can be diffed by `--compare`.
    """
    path = model_results_path(model)
    payload = {
        "model": model,
        "total": len(rows),
        "correct": sum(1 for r in rows if r["match"]),
        "cases": [
            {
                "case_id": r["case_id"],
                "expected_bucket": r["expected_bucket"],
                "predicted_bucket": r["predicted_bucket"],
                "match": bool(r["match"]),
            }
            for r in rows
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path

def load_model_results(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "model" not in data or "cases" not in data:
        raise RuntimeError(
            f"{path}: not a per-model results file (missing 'model'/'cases'). "
            f"Generate one with a normal eval run."
        )
    return data

def compare(path_a, path_b):
    """Print a side-by-side report of two per-model results files."""
    a = load_model_results(path_a)
    b = load_model_results(path_b)
    model_a, model_b = a["model"], b["model"]
    cases_a = {c["case_id"]: c for c in a["cases"]}
    cases_b = {c["case_id"]: c for c in b["cases"]}

    total_a = a.get("total", len(a["cases"]))
    total_b = b.get("total", len(b["cases"]))
    correct_a = a.get("correct", sum(1 for c in a["cases"] if c["match"]))
    correct_b = b.get("correct", sum(1 for c in b["cases"] if c["match"]))

    print("=" * 72)
    print(f"Compare: {model_a}  vs  {model_b}")
    print("=" * 72)
    print()
    print("Accuracy:")
    print(f"  {model_a:24s} {correct_a}/{total_a}")
    print(f"  {model_b:24s} {correct_b}/{total_b}")
    print()

    # Bucket distribution over predicted labels. Show every valid bucket
    # (all five the harness uses), plus any extra label that actually
    # appeared (e.g. ERROR) so nothing is silently dropped.
    seen = ({c["predicted_bucket"] for c in a["cases"]}
            | {c["predicted_bucket"] for c in b["cases"]})
    bucket_order = sorted(VALID_BUCKETS) + sorted(seen - VALID_BUCKETS)
    da = Counter(c["predicted_bucket"] for c in a["cases"])
    db = Counter(c["predicted_bucket"] for c in b["cases"])
    print("Predicted bucket distribution:")
    print(f"  {'bucket':15s} {model_a:>22s} {model_b:>22s}")
    for bk in bucket_order:
        print(f"  {bk:15s} {da.get(bk, 0):>22d} {db.get(bk, 0):>22d}")
    print()

    # Disagreements, aligned by case_id (a-order first, then any b-only ids).
    ids = [c["case_id"] for c in a["cases"]]
    ids += [cid for cid in cases_b if cid not in cases_a]
    disagreements = []
    for cid in ids:
        ca, cb = cases_a.get(cid), cases_b.get(cid)
        pa = ca["predicted_bucket"] if ca else "(absent)"
        pb = cb["predicted_bucket"] if cb else "(absent)"
        if pa != pb:
            exp = (ca or cb)["expected_bucket"]
            disagreements.append((cid, exp, pa, pb))
    if disagreements:
        print(f"Disagreements ({len(disagreements)}):")
        print(f"  {'case_id':12s} {'expected':15s} {model_a:>22s} {model_b:>22s}")
        for cid, exp, pa, pb in disagreements:
            print(f"  {cid:12s} {exp:15s} {pa:>22s} {pb:>22s}")
    else:
        print("Disagreements: none — both models predicted the same bucket "
              "on every case.")

def print_summary(rows):
    total = len(rows)
    correct = sum(1 for r in rows if r["match"])
    errors = sum(1 for r in rows if r["predicted_bucket"] == "ERROR")
    print()
    print("=" * 60)
    print(f"Overall: {correct}/{total} correct ({100*correct/total:.1f}%)"
          f"  errors={errors}")

    per_bucket = defaultdict(lambda: [0, 0])  # [correct, total]
    for r in rows:
        per_bucket[r["expected_bucket"]][1] += 1
        if r["match"]:
            per_bucket[r["expected_bucket"]][0] += 1
    print()
    print("Per expected bucket:")
    for bucket in sorted(per_bucket.keys()):
        c, t = per_bucket[bucket]
        print(f"  {bucket:15s} {c}/{t}  ({100*c/t:.0f}%)")

    mismatches = [r for r in rows if not r["match"]]
    if mismatches:
        print()
        print(f"Mismatches ({len(mismatches)}):")
        for r in mismatches:
            print(f"  - {r['case_id']}: expected {r['expected_bucket']}, "
                  f"got {r['predicted_bucket']}")
            if r["reasoning"]:
                print(f"      reasoning: {r['reasoning']}")

# ---- Main --------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=DEFAULT_MODEL,
                   help=f"Model ID (default: {DEFAULT_MODEL})")
    p.add_argument("--limit", type=int, default=None,
                   help="Run only the first N cases (smoke test).")
    p.add_argument("--case-id", default=None,
                   help="Run only the case with this ID.")
    p.add_argument("--compare", nargs=2, metavar=("RESULTS_A", "RESULTS_B"),
                   default=None,
                   help="Compare two per-model results JSON files and exit. "
                        "Does not call the API.")
    args = p.parse_args()

    if args.compare:
        compare(args.compare[0], args.compare[1])
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set. Source .env first: "
                 "`set -a; source .env; set +a`")

    if not PROMPT_PATH.exists():
        sys.exit(f"Missing prompt file: {PROMPT_PATH}")
    if not CASES_PATH.exists():
        sys.exit(f"Missing cases file: {CASES_PATH}")

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    cases = load_cases(CASES_PATH)

    if args.case_id:
        cases = [c for c in cases if c["case_id"] == args.case_id]
        if not cases:
            sys.exit(f"No case found with id={args.case_id}")
    if args.limit:
        cases = cases[:args.limit]

    print(f"Running {len(cases)} case(s) against {args.model}")
    print(f"Prompt: {PROMPT_PATH}")
    print(f"Cases:  {CASES_PATH}")
    print()

    rows = run(cases, api_key, args.model, system_prompt)
    write_results(rows, RESULTS_PATH)
    print(f"\nWrote {RESULTS_PATH}")
    model_results = write_model_results(rows, args.model)
    print(f"Wrote {model_results}")
    print_summary(rows)

if __name__ == "__main__":
    main()

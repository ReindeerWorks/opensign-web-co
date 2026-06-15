# Inbound email intake — `POST /api/inbound/postmark`

Stage 8 Step 2. Postmark receives mail to our support address and POSTs an
INBOUND webhook here. The Function authenticates (Basic Auth), fast-acknowledges
with `200`, then in the background dedupes on Postmark MessageID, matches the
sender to a Customer, and writes a Request (+ Request Event) to Airtable.

**Scope:** intake only. It does not classify, generate, deploy, or send email.
Unmatched senders are always written as `Escalate` / `Escalated` and never
classified.

## Environment variables

| Var | Purpose | Set where |
| --- | --- | --- |
| `OPENSIGN_AT_BASE_ID` | Airtable base id (existing) | Cloudflare Pages secret |
| `OPENSIGN_AT_BASE_API_KEY` | Airtable PAT (existing) | Cloudflare Pages secret |
| `POSTMARK_WEBHOOK_USER` | Basic Auth username (new) | Cloudflare Pages secret |
| `POSTMARK_WEBHOOK_PASS` | Basic Auth password (new) | Cloudflare Pages secret |

All four must be configured as **encrypted Secrets** in the Cloudflare Pages
project (Settings → Environment variables) before a live test. In Postmark, set
the inbound webhook URL with the same credentials embedded:
`https://USER:PASS@<your-domain>/api/inbound/postmark`.

## Local smoke test (`wrangler pages dev`)

1. Create a `.dev.vars` file at the repo root (gitignored) with the four vars:

   ```
   OPENSIGN_AT_BASE_ID=appBheOH4o6oIsS8H
   OPENSIGN_AT_BASE_API_KEY=pat...           # from .env
   POSTMARK_WEBHOOK_USER=pmuser              # any test value
   POSTMARK_WEBHOOK_PASS=pmpass              # any test value
   ```

   > ⚠️ A live local run with a real `OPENSIGN_AT_BASE_API_KEY` **writes to the
   > production Airtable base**. Use a throwaway base/PAT if you don't want real
   > rows, or just confirm the 401/200 responses without valid Airtable creds.

2. Build and serve (Functions are picked up from `functions/` automatically):

   ```bash
   npm run build && npx wrangler pages dev dist
   ```

3. POST the sample payload with Basic Auth (default dev port is 8788):

   ```bash
   curl -i -u "pmuser:pmpass" \
     -H "Content-Type: application/json" \
     --data @functions/api/inbound/sample-postmark-inbound.json \
     http://localhost:8788/api/inbound/postmark
   ```

   Expected: `HTTP/1.1 200 OK` with `{"success":true}` almost immediately.
   Wrong/missing `-u` credentials → `401 {"error":"Unauthorized"}`.

4. Verify in Airtable: a new **Requests** row (matched → linked Customer +
   `Status: New`; unmatched → `Classification: Escalate`, `Status: Escalated`)
   and one linked **Request Events** row (`matched` / `unmatched_escalated`).
   POST the same payload twice — the second is deduped (no new Request; an
   optional `duplicate_ignored` event).

// Stage 8 Step 2 — inbound customer-email intake endpoint.
//
// Postmark receives mail to our support address and POSTs an INBOUND webhook
// here. This Function authenticates the webhook, fast-acknowledges (200), and
// in the background dedupes, matches the sender to a Customer, and writes a
// Request (+ Request Event) to Airtable.
//
// SCOPE: intake only. This file does NOT classify, generate, deploy, or email.
// Classification of matched requests is the next task. Unmatched senders are
// always written as Escalate and never classified — a hard rule (see below).
//
// Field names "Postmark INBOUND payload": From / FromFull.Email, Subject,
// TextBody, StrippedTextReply, MessageID, Date — verified against Postmark's
// official inbound-webhook documentation.

import {
  AIRTABLE_API_BASE,
  CLASSIFICATION,
  CUSTOMERS_FIELDS,
  FILTER_FIELD_NAMES,
  REQUEST_EVENTS_FIELDS,
  REQUESTS_FIELDS,
  STATUS,
  TABLES,
} from '../../_lib/airtable';

interface Env {
  OPENSIGN_AT_BASE_ID: string;
  OPENSIGN_AT_BASE_API_KEY: string;
  POSTMARK_WEBHOOK_USER: string;
  POSTMARK_WEBHOOK_PASS: string;
}

interface PostmarkInbound {
  From?: unknown;
  FromFull?: unknown;
  Subject?: unknown;
  TextBody?: unknown;
  StrippedTextReply?: unknown;
  MessageID?: unknown;
  Date?: unknown;
}

interface Extracted {
  fromEmail: string | null;
  subject: string | null;
  body: string | null;
  messageId: string | null;
  receivedAt: string | null; // ISO 8601, or null
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

// Coerce at the boundary: a non-empty trimmed string, otherwise null.
const asStringOrNull = (v: unknown): string | null => {
  if (typeof v !== 'string') return null;
  const t = v.trim();
  return t === '' ? null : t;
};

// Postmark Date is RFC 2822 ("Fri, 1 Aug 2014 16:45:32 -04:00"); Airtable
// dateTime wants ISO 8601. Parse and normalise; unparseable/missing -> null.
const toIso = (v: string | null): string | null => {
  if (!v) return null;
  const t = Date.parse(v);
  return Number.isNaN(t) ? null : new Date(t).toISOString();
};

// Escape a value for an Airtable formula double-quoted string literal.
const escapeFormulaValue = (v: string): string =>
  v.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

const errToString = (err: unknown): string =>
  err instanceof Error ? err.message : String(err);

// ---- Basic Auth (synchronous) -----------------------------------------

function checkBasicAuth(request: Request, env: Env): boolean {
  // No configured credentials => cannot authenticate anyone => deny.
  if (!env.POSTMARK_WEBHOOK_USER || !env.POSTMARK_WEBHOOK_PASS) {
    console.error('[postmark inbound] webhook credentials are not configured');
    return false;
  }
  const header = request.headers.get('Authorization') || '';
  if (!header.startsWith('Basic ')) return false;
  let decoded: string;
  try {
    decoded = atob(header.slice('Basic '.length).trim());
  } catch {
    return false;
  }
  const sep = decoded.indexOf(':');
  if (sep === -1) return false;
  const user = decoded.slice(0, sep);
  const pass = decoded.slice(sep + 1);
  return user === env.POSTMARK_WEBHOOK_USER && pass === env.POSTMARK_WEBHOOK_PASS;
}

// ---- Airtable REST (raw fetch, no SDK) ---------------------------------

async function airtableRequest(
  env: Env,
  path: string,
  init: RequestInit = {},
): Promise<Record<string, unknown>> {
  const res = await fetch(`${AIRTABLE_API_BASE}/${env.OPENSIGN_AT_BASE_ID}/${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.OPENSIGN_AT_BASE_API_KEY}`,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`Airtable ${res.status} on ${path}: ${detail}`);
  }
  return (await res.json()) as Record<string, unknown>;
}

// Returns the matching record id, or null. reads use returnFieldsByFieldId.
async function findFirstRecordId(
  env: Env,
  tableId: string,
  formula: string,
): Promise<string | null> {
  const qs = new URLSearchParams({
    filterByFormula: formula,
    maxRecords: '1',
    returnFieldsByFieldId: 'true',
  });
  const data = await airtableRequest(env, `${tableId}?${qs.toString()}`);
  const records = (data.records as Array<{ id?: string }> | undefined) || [];
  return records.length > 0 && records[0].id ? records[0].id : null;
}

async function createRecord(
  env: Env,
  tableId: string,
  fields: Record<string, unknown>,
): Promise<string> {
  const data = await airtableRequest(env, tableId, {
    method: 'POST',
    body: JSON.stringify({ fields, typecast: false }),
  });
  const id = data.id as string | undefined;
  if (!id) throw new Error(`Airtable create on ${tableId} returned no record id`);
  return id;
}

function findRequestByMessageId(env: Env, messageId: string): Promise<string | null> {
  const formula = `{${FILTER_FIELD_NAMES.requestsPostmarkMessageId}}="${escapeFormulaValue(messageId)}"`;
  return findFirstRecordId(env, TABLES.requests, formula);
}

function findCustomerByEmail(env: Env, email: string): Promise<string | null> {
  // Case-insensitive: lowercase both sides (LOWER() on the field, lowered input).
  const formula = `LOWER({${FILTER_FIELD_NAMES.customersEmail}})="${escapeFormulaValue(email.toLowerCase())}"`;
  return findFirstRecordId(env, TABLES.customers, formula);
}

async function createRequestEvent(
  env: Env,
  requestId: string | null,
  eventType: string,
  detail: string,
  messageId: string | null,
): Promise<void> {
  const fields: Record<string, unknown> = {
    [REQUEST_EVENTS_FIELDS.eventType]: eventType,
    [REQUEST_EVENTS_FIELDS.timestamp]: new Date().toISOString(),
    [REQUEST_EVENTS_FIELDS.detail]: detail,
    [REQUEST_EVENTS_FIELDS.postmarkMessageId]: messageId,
  };
  if (requestId) {
    fields[REQUEST_EVENTS_FIELDS.request] = [requestId];
  }
  await createRecord(env, TABLES.requestEvents, fields);
}

// ---- Background processing ---------------------------------------------

async function process(env: Env, m: Extracted): Promise<void> {
  try {
    // a. Idempotency — skip if we've already stored this MessageID.
    if (m.messageId) {
      const existing = await findRequestByMessageId(env, m.messageId);
      if (existing) {
        console.log(`[postmark inbound] duplicate MessageID ${m.messageId}, ignoring`);
        await createRequestEvent(
          env,
          existing,
          'duplicate_ignored',
          `Duplicate inbound ignored for MessageID ${m.messageId}`,
          m.messageId,
        );
        return;
      }
    }

    // b. Match sender (case-insensitive). No sender => no match.
    const customerId = m.fromEmail ? await findCustomerByEmail(env, m.fromEmail) : null;
    const matched = customerId !== null;

    // c. Create one Requests row.
    const fields: Record<string, unknown> = {
      [REQUESTS_FIELDS.subject]: m.subject,
      [REQUESTS_FIELDS.fromEmail]: m.fromEmail,
      [REQUESTS_FIELDS.body]: m.body,
      [REQUESTS_FIELDS.postmarkMessageId]: m.messageId,
      [REQUESTS_FIELDS.receivedAt]: m.receivedAt,
    };
    if (matched) {
      // Matched: link the customer, status New. Leave Classification /
      // Confidence empty — classification is the next task.
      fields[REQUESTS_FIELDS.customer] = [customerId];
      fields[REQUESTS_FIELDS.status] = STATUS.new;
    } else {
      // Unmatched senders are ALWAYS escalated and NEVER classified.
      fields[REQUESTS_FIELDS.classification] = CLASSIFICATION.escalate;
      fields[REQUESTS_FIELDS.status] = STATUS.escalated;
    }
    const requestId = await createRecord(env, TABLES.requests, fields);

    // d. Create the linked Request Event.
    const eventType = matched ? 'matched' : 'unmatched_escalated';
    const detail = matched
      ? `Matched customer ${customerId}`
      : `no customer match for ${m.fromEmail ?? '(unknown sender)'}`;
    await createRequestEvent(env, requestId, eventType, detail, m.messageId);
  } catch (err) {
    // e. Best-effort error event so failures are visible in Airtable too.
    console.error('[postmark inbound] background processing failed', err);
    try {
      await createRequestEvent(
        env,
        null,
        'error',
        `Background processing error: ${errToString(err)}`,
        m.messageId,
      );
    } catch (eventErr) {
      console.error('[postmark inbound] failed to write error event', eventErr);
    }
  }
}

// ---- Handler -----------------------------------------------------------

export const onRequestPost: PagesFunction<Env> = async (context) => {
  const { request, env, waitUntil } = context;

  // 1. Basic Auth — wrong/missing credentials get 401 and nothing else.
  if (!checkBasicAuth(request, env)) {
    return json({ error: 'Unauthorized' }, 401);
  }

  // 2. Parse the Postmark inbound payload and extract fields.
  let payload: PostmarkInbound;
  try {
    payload = (await request.json()) as PostmarkInbound;
  } catch {
    return json({ error: 'Invalid JSON.' }, 400);
  }

  const fromFull =
    payload.FromFull && typeof payload.FromFull === 'object'
      ? (payload.FromFull as { Email?: unknown })
      : null;

  const extracted: Extracted = {
    // Prefer the structured FromFull.Email, fall back to the From string.
    fromEmail: asStringOrNull(fromFull?.Email) ?? asStringOrNull(payload.From),
    subject: asStringOrNull(payload.Subject),
    // Prefer the plain-text body; fall back to the stripped reply text.
    body: asStringOrNull(payload.TextBody) ?? asStringOrNull(payload.StrippedTextReply),
    messageId: asStringOrNull(payload.MessageID),
    receivedAt: toIso(asStringOrNull(payload.Date)),
  };

  // 3. Fast-acknowledge: 200 to Postmark now, all Airtable work in the
  //    background so Postmark never times out or retries.
  waitUntil(process(env, extracted));

  return json({ success: true });
};

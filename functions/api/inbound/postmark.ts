// Stage 8 Step 2 — inbound customer-email intake endpoint.
//
// Postmark receives mail to our support address and POSTs an INBOUND webhook
// here. This Function authenticates the webhook, fast-acknowledges (200), and
// in the background dedupes, matches the sender to a Customer, classifies the
// email (matched senders only), and writes a Request (+ Request Events) to
// Airtable.
//
// SCOPE: intake + classification only. This file does NOT execute anything —
// no change generation, no preview deploys, no outbound email. Even an
// Auto-handle classification is only recorded; execution is a later stage.
// Unmatched senders are always written as Escalate and never classified — a
// hard rule (see below).
//
// The classifier request contract (model, system prompt, tool schema, parsing)
// is ported 1:1 from the validated eval harness
// scripts/stage8/classifier-eval/run_eval.py. The system prompt is the LOCKED
// scripts/stage8/classifier-eval/classifier_prompt.md, copied at build time to
// _lib/classifier-prompt.generated.txt (see scripts/build/
// copy-classifier-prompt.mjs) so harness and Function read the one file.
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
import CLASSIFIER_SYSTEM_PROMPT from '../../_lib/classifier-prompt.generated.txt';

interface Env {
  OPENSIGN_AT_BASE_ID: string;
  OPENSIGN_AT_BASE_API_KEY: string;
  POSTMARK_WEBHOOK_USER: string;
  POSTMARK_WEBHOOK_PASS: string;
  ANTHROPIC_API_KEY: string;
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

// ---- Classifier (raw fetch, no SDK) -------------------------------------
//
// Everything in this section mirrors run_eval.py's classify() exactly: same
// model, same tool schema, same tool_choice, same user-message shape, same
// response parsing. Production must match what the eval validated.

const ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages';
// The validated eval baseline (run_eval.py DEFAULT_MODEL). Do not bump without
// re-running the eval on the new model first.
const CLASSIFIER_MODEL = 'claude-sonnet-4-6';

// Ported from run_eval.py CLASSIFY_TOOL (enum order = Python sorted()).
const CLASSIFY_TOOL = {
  name: 'classify_request',
  description:
    'Classify the inbound customer email into one of five buckets and ' +
    'report needs_split if the email contains multiple distinct requests.',
  input_schema: {
    type: 'object',
    properties: {
      bucket: {
        type: 'string',
        enum: ['AUTO_HANDLE', 'CLARIFY', 'ESCALATE', 'INFORMATIONAL', 'QUOTE'],
        description: 'The routing bucket for this email.',
      },
      confidence: {
        type: 'number',
        minimum: 0,
        maximum: 1,
        description: 'Subjective confidence in the bucket choice (0-1).',
      },
      reasoning: {
        type: 'string',
        description: '1-3 sentences explaining the choice, referencing specificity.',
      },
      needs_split: {
        type: 'boolean',
        description: 'True if the email contains multiple distinct requests.',
      },
      split_requests: {
        type: 'array',
        items: { type: 'string' },
        description: 'When needs_split=true, list each distinct request.',
      },
    },
    required: ['bucket', 'confidence', 'reasoning', 'needs_split'],
  },
} as const;

// The classifier's enum strings and the Airtable singleSelect option names
// are NOT identical — explicit mapping, no string munging.
const BUCKET_TO_CLASSIFICATION: Record<string, string> = {
  AUTO_HANDLE: CLASSIFICATION.autoHandle,
  CLARIFY: CLASSIFICATION.clarify,
  QUOTE: CLASSIFICATION.quote,
  ESCALATE: CLASSIFICATION.escalate,
  INFORMATIONAL: CLASSIFICATION.informational,
};

interface Classified {
  classification: string; // Airtable option name
  confidence: number | null;
  reasoning: string | null;
}

// One attempt, no retry loop: unlike the offline harness (which sleeps 60s on
// a 429), we run inside waitUntil() and fail toward escalation instead.
async function classifyEmail(
  env: Env,
  subject: string,
  body: string,
): Promise<Classified> {
  const payload = {
    model: CLASSIFIER_MODEL,
    max_tokens: 1024,
    system: CLASSIFIER_SYSTEM_PROMPT,
    tools: [CLASSIFY_TOOL],
    tool_choice: { type: 'tool', name: 'classify_request' },
    messages: [{ role: 'user', content: `Subject: ${subject}\n\n${body}` }],
  };
  const res = await fetch(ANTHROPIC_API_URL, {
    method: 'POST',
    headers: {
      'x-api-key': env.ANTHROPIC_API_KEY,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: JSON.stringify(payload),
    // Bounded so a hung call still leaves time to write the escalation row
    // before the runtime ends the waitUntil() lifetime.
    signal: AbortSignal.timeout(20_000),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(`Anthropic API ${res.status}: ${detail}`);
  }
  const data = (await res.json()) as {
    stop_reason?: string;
    content?: Array<{ type?: string; name?: string; input?: Record<string, unknown> }>;
  };
  const blocks = data.content ?? [];
  const toolUse = blocks.find(
    (b) => b.type === 'tool_use' && b.name === 'classify_request',
  );
  if (!toolUse || !toolUse.input) {
    throw new Error(
      `No tool_use block in response. stop_reason=${data.stop_reason}`,
    );
  }
  const input = toolUse.input;
  const bucket = typeof input.bucket === 'string' ? input.bucket : '';
  const classification = BUCKET_TO_CLASSIFICATION[bucket];
  if (!classification) {
    throw new Error(`Classifier returned unknown bucket: ${JSON.stringify(input.bucket)}`);
  }
  // Coerce at the boundary: bad values -> null, never 0/NaN.
  const confidence =
    typeof input.confidence === 'number' && Number.isFinite(input.confidence)
      ? input.confidence
      : null;
  return {
    classification,
    confidence,
    reasoning: asStringOrNull(input.reasoning),
  };
}

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

    // c. Matched senders only: classify BEFORE creating the row, so the
    //    Request lands fully populated in one write (a crash mid-flight means
    //    no row, and Postmark's retry re-processes from scratch). Any
    //    classifier failure fails toward escalation — never drop the request.
    let classified: Classified | null = null;
    let classifierError: string | null = null;
    if (matched) {
      try {
        classified = await classifyEmail(env, m.subject ?? '', m.body ?? '');
      } catch (err) {
        classifierError = errToString(err);
        console.error('[postmark inbound] classifier failed, escalating', err);
      }
    }

    // d. Create one Requests row.
    const fields: Record<string, unknown> = {
      [REQUESTS_FIELDS.subject]: m.subject,
      [REQUESTS_FIELDS.fromEmail]: m.fromEmail,
      [REQUESTS_FIELDS.body]: m.body,
      [REQUESTS_FIELDS.postmarkMessageId]: m.messageId,
      [REQUESTS_FIELDS.receivedAt]: m.receivedAt,
    };
    if (matched && classified) {
      fields[REQUESTS_FIELDS.customer] = [customerId];
      fields[REQUESTS_FIELDS.classification] = classified.classification;
      fields[REQUESTS_FIELDS.confidence] = classified.confidence;
      fields[REQUESTS_FIELDS.classifierReasoning] = classified.reasoning;
      // Escalate classifications go straight to the Escalation Queue.
      fields[REQUESTS_FIELDS.status] =
        classified.classification === CLASSIFICATION.escalate
          ? STATUS.escalated
          : STATUS.classified;
    } else if (matched) {
      // Classifier errored/unparseable: keep the customer link, escalate.
      fields[REQUESTS_FIELDS.customer] = [customerId];
      fields[REQUESTS_FIELDS.classification] = CLASSIFICATION.escalate;
      fields[REQUESTS_FIELDS.status] = STATUS.escalated;
    } else {
      // Unmatched senders are ALWAYS escalated and NEVER classified.
      fields[REQUESTS_FIELDS.classification] = CLASSIFICATION.escalate;
      fields[REQUESTS_FIELDS.status] = STATUS.escalated;
    }
    const requestId = await createRecord(env, TABLES.requests, fields);

    // e. Create the linked Request Events.
    const eventType = matched ? 'matched' : 'unmatched_escalated';
    const detail = matched
      ? `Matched customer ${customerId}`
      : `no customer match for ${m.fromEmail ?? '(unknown sender)'}`;
    await createRequestEvent(env, requestId, eventType, detail, m.messageId);
    if (matched) {
      if (classified) {
        await createRequestEvent(
          env,
          requestId,
          'classified',
          `${classified.classification} (confidence ${classified.confidence ?? 'n/a'})`,
          m.messageId,
        );
      } else {
        await createRequestEvent(
          env,
          requestId,
          'classifier_error_escalated',
          `Classifier error: ${classifierError ?? '(unknown)'}`,
          m.messageId,
        );
      }
    }
  } catch (err) {
    // f. Best-effort error event so failures are visible in Airtable too.
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

// Airtable schema constants for the Open Sign Web Co base
// (OPENSIGN_AT_BASE_ID = appBheOH4o6oIsS8H).
//
// Tables and fields are referenced by STABLE ID, never by display name —
// matching the convention in scripts/pull_leads.py and the other Python
// pipeline scripts (display names get renamed; IDs don't). The base ID and
// API key are NOT here: they live in the environment as OPENSIGN_AT_BASE_ID
// and OPENSIGN_AT_BASE_API_KEY (see .env / .env.example), the same names the
// Python scripts use.
//
// This module exports only constants — no `onRequest*` handler — so Cloudflare
// Pages never turns it into a route. It also lives under functions/_lib/ (the
// leading underscore is the conventional non-routed location for shared code).

export const AIRTABLE_API_BASE = 'https://api.airtable.com/v0';

export const TABLES = {
  customers: 'tbl9CpBvJ8YNA5YSf',
  requests: 'tblmuo63ByDUgRwUp',
  requestEvents: 'tblbZzQXSRaaE8p28',
} as const;

export const CUSTOMERS_FIELDS = {
  email: 'fldPmIOVbovFwC8A5',
} as const;

export const REQUESTS_FIELDS = {
  subject: 'fldYeX23SZ6GpHu5k', // primary, singleLineText
  customer: 'fldAVIOsXmuAtP4a4', // link to Customers
  fromEmail: 'fld6EPQ53x7xzPMgn',
  postmarkMessageId: 'fldYQesx9Mk4vymIZ',
  receivedAt: 'fldCuFDRTUX5q347f', // dateTime
  body: 'fldiYtdFQtn0vNGmp',
  classification: 'fldxCTrV1efLMciRK', // singleSelect
  confidence: 'fldEtavEytXO6IFZq', // number
  classifierReasoning: 'fldWwK5BrLNPFCBir',
  status: 'fldtN03WSpj4JadDK', // singleSelect
} as const;

export const REQUEST_EVENTS_FIELDS = {
  eventType: 'fldP29LABHq5EOIHB', // primary, singleLineText
  request: 'fldciGuxMglWmYV03', // link to Requests
  timestamp: 'fldxrc1PgFeFdtiSh', // dateTime
  detail: 'fld4JA2PMgEKXbZVi',
  postmarkMessageId: 'fldj1CXFT58e1D20I',
} as const;

// Requests.Classification — singleSelect option-name strings. Airtable writes
// take the bare option name (not an object), per the CLAUDE.md Airtable gotcha.
export const CLASSIFICATION = {
  autoHandle: 'Auto-handle',
  clarify: 'Clarify',
  quote: 'Quote',
  escalate: 'Escalate',
  informational: 'Informational',
} as const;

// Requests.Status — singleSelect option-name strings.
export const STATUS = {
  new: 'New',
  classified: 'Classified',
  escalated: 'Escalated',
  error: 'Error',
} as const;

// filterByFormula references fields by NAME, not ID — this is the ONE place
// names are unavoidable. Two are needed: Customers.Email (sender match) and
// Requests."Postmark Message ID" (idempotency lookup). Everything else in this
// integration uses the field IDs above.
export const FILTER_FIELD_NAMES = {
  customersEmail: 'Email',
  requestsPostmarkMessageId: 'Postmark Message ID',
} as const;

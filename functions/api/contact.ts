interface Env {
  RESEND_API_KEY: string;
}

interface ContactPayload {
  name?: unknown;
  businessName?: unknown;
  description?: unknown;
  email?: unknown;
}

const RECIPIENT = 'hello@opensignwebco.com';
const SENDER = 'hello@opensignwebco.com';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const asString = (v: unknown) => (typeof v === 'string' ? v.trim() : '');

const isEmail = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

const escapeHtml = (s: string) =>
  s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.RESEND_API_KEY) {
    return json({ error: 'Email service is not configured.' }, 500);
  }

  let payload: ContactPayload;
  try {
    payload = (await request.json()) as ContactPayload;
  } catch {
    return json({ error: 'Invalid JSON.' }, 400);
  }

  const name = asString(payload.name);
  const businessName = asString(payload.businessName);
  const description = asString(payload.description);
  const email = asString(payload.email);

  if (!name || !businessName || !description || !email) {
    return json({ error: 'All fields are required.' }, 400);
  }
  if (!isEmail(email)) {
    return json({ error: 'Please enter a valid email address.' }, 400);
  }

  const subject = `New inquiry — ${businessName}`;
  const text = [
    `Name: ${name}`,
    `Business name: ${businessName}`,
    '',
    'What they do:',
    description,
    '',
    `Reply-to: ${email}`,
  ].join('\n');
  const html = `
    <p><strong>Name:</strong> ${escapeHtml(name)}</p>
    <p><strong>Business name:</strong> ${escapeHtml(businessName)}</p>
    <p><strong>What they do:</strong><br>${escapeHtml(description).replace(/\n/g, '<br>')}</p>
    <p><strong>Reply-to:</strong> ${escapeHtml(email)}</p>
  `.trim();

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
    },
    body: JSON.stringify({
      from: `Open Sign Web Co <${SENDER}>`,
      to: [RECIPIENT],
      reply_to: email,
      subject,
      text,
      html,
    }),
  });

  if (!res.ok) {
    let detail = '';
    try {
      const body = (await res.json()) as { message?: string };
      detail = body?.message || '';
    } catch {
      detail = await res.text();
    }
    return json({ error: `Failed to send: ${detail || res.statusText}` }, 502);
  }

  return json({ success: true });
};

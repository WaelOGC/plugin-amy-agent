# Email Marketing — FluentSMTP / hello@ setup

Amy Email Marketing sends with WordPress `wp_mail()`. On ogcnewfinity.com that
routes through **FluentSMTP** (active). There is **no** AgentMail or personal
Gmail path. Hostinger Agentic Mail REST is **not** required for this v1 send.

## From address

| Setting | Default |
| --- | --- |
| Amy → Settings → **Marketing From email** | `hello@ogcnewfinity.com` |
| Amy → Settings → **Marketing From name** | `OGC NewFinity` |

The Email Marketing page shows the From address clearly. Personal Gmail,
AgentMail (`@agentmail.to`), and common free webmail hosts are rejected.

## Admin flow (never silent)

1. Select audience (Analytics emails with multi-select).
2. Write subject + body.
3. Click **Approve draft** (localStorage only — no mail yet).
4. Click **Send now** and confirm. AJAX `amy_email_marketing_send` requires
   `approved=1` + `confirmed=1` + `manage_options`.

Each recipient gets an individual `wp_mail()` call with
`From: OGC NewFinity <hello@ogcnewfinity.com>` (or the configured From).

## What Abdulla must configure

### 1. Hostinger mailbox

1. hPanel → Emails → create/confirm mailbox **`hello@ogcnewfinity.com`**.
2. Note SMTP host/port/user/password for FluentSMTP (or use Hostinger’s
   recommended SMTP for the domain).

### 2. FluentSMTP (WordPress)

1. wp-admin → **FluentSMTP** → Connections.
2. Add/edit a connection that can send **as** `hello@ogcnewfinity.com`
   (same mailbox, or a connection whose From allow-list includes hello@).
3. Set the connection’s From email to `hello@ogcnewfinity.com` (or ensure
   Amy’s From matches a verified sender on that connection).
4. Send FluentSMTP’s test email **From hello@** to yourself and confirm
   delivery + that the message is not spoofed/spam.

Transactional mail (contact forms, Submit Idea) can keep using
`contact@ogcnewfinity.com` if that is already the FluentSMTP default —
Amy only overrides From for Email Marketing sends.

### 3. DNS (SPF / DKIM / DMARC)

On the DNS zone for **ogcnewfinity.com** (Hostinger DNS or wherever the
domain is managed):

1. **SPF** — include Hostinger / the SMTP provider FluentSMTP uses
   (typical Hostinger include is already present for Business Email).
2. **DKIM** — enable signing for the domain in hPanel Email / FluentSMTP
   provider docs; publish the DKIM TXT records.
3. **DMARC** — optional but recommended (`_dmarc` TXT) once SPF+DKIM pass.

Until hello@ is a real mailbox **and** FluentSMTP can authenticate sends as
that address with SPF/DKIM aligned, Amy Send will fail or land in spam.

### 4. Deploy plugin

Deploy Amy Agent **0.2.37+** from this repo. Analytics outage (service URL /
Dokploy) is separate — audience list still needs a healthy amy-agent-service.

## Hard rules

- No personal Gmail for marketing.
- No AgentMail for marketing.
- No automatic send on Approve.
- From must stay a domain mailbox (default hello@).

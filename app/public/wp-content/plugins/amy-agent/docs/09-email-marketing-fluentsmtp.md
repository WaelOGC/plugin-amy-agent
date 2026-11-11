# Email Marketing — FluentSMTP / hello@ + history

Amy Email Marketing sends with WordPress `wp_mail()`. On ogcnewfinity.com that
routes through **FluentSMTP** (active). There is **no** AgentMail or personal
Gmail path. Hostinger Agentic Mail is **not** used for marketing send or
reply capture.

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
5. Each successful/failed/opted-out recipient is written to **Send & reply
   history** in the Amy Python service.

Each recipient gets an individual `wp_mail()` call with
`From: OGC NewFinity <hello@ogcnewfinity.com>` (or the configured From) and an
**Unsubscribe** footer linking to the public opt-out endpoint.

## History & inbound limitation

| Capability | Status |
| --- | --- |
| Durable outbound log | Yes — service `email_*` tables in `conversations.db` |
| Manual reply / internal notes | Yes — Email Marketing history panel |
| Opt-out / suppression | Yes — footer link + admin Opt out; checked before send |
| Amy propose draft (no send) | Yes — `POST /wp-json/amy-agent/v1/email-marketing/propose` |
| Automatic hello@ IMAP/Agentic Mail inbound | **No** — FluentSMTP is outbound-only; no AgentMail |

Optional: authenticated `POST /wp-json/amy-agent/v1/email-inbound` (header
`X-Amy-Secret`) forwards JSON into history if you wire a mail forwarder
yourself.

## Amy hooks (WordPress)

- `amy_email_marketing_before_send`
- `amy_email_marketing_send_result`
- `amy_email_marketing_after_send`
- `amy_email_marketing_propose`

## What Abdulla must configure

### 1. Hostinger mailbox

1. hPanel → Emails → create/confirm mailbox **`hello@ogcnewfinity.com`**.
2. Note SMTP host/port/user/password for FluentSMTP.

### 2. FluentSMTP (WordPress)

1. wp-admin → **FluentSMTP** → Connections.
2. Authorize sending **as** `hello@ogcnewfinity.com`.
3. Send FluentSMTP’s test email **From hello@** and confirm delivery.

Transactional mail can keep using `contact@ogcnewfinity.com` if that is the
FluentSMTP default — Amy only overrides From for Email Marketing sends.

### 3. DNS (SPF / DKIM / DMARC)

SPF includes Hostinger / SMTP provider; DKIM published; DMARC recommended.

### 4. Deploy

Deploy Amy Agent **0.2.47+** and amy-agent-service **0.2.10+**.

## Hard rules

- No personal Gmail for marketing.
- No AgentMail for marketing.
- No automatic send on Approve (or on Amy propose).
- From must stay a domain mailbox (default hello@).
- Respect opt-outs before send.

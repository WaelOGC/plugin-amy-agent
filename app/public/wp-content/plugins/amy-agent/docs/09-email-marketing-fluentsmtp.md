# Email Marketing — FluentSMTP / per-site From + history

Amy Email Marketing sends with WordPress `wp_mail()` → **FluentSMTP**.
There is **no** AgentMail or personal Gmail path. Hostinger Agentic Mail is
**not** used for marketing send or reply capture.

## Per-site Marketing From (Settings)

Each WordPress install configures its own sender under
**Amy → Settings → Email Marketing From**:

| Setting | Behavior |
| --- | --- |
| **Marketing From email** | Site-owned domain mailbox. Empty → plugin default `hello@ogcnewfinity.com` (OGC NewFinity preference). |
| **Marketing From name** | Display name. Empty → `OGC NewFinity`. |

**Buyers / other sites:** set *your* domain mailbox here and authorize that
exact address in FluentSMTP (plus SPF/DKIM on your domain). Do not use
personal Gmail, AgentMail (`@agentmail.to`), or free webmail — those hosts
are rejected in Settings sanitize + live validation.

The Email Marketing page always shows the resolved From from Settings.

## Admin flow (never silent)

1. Select audience (Analytics emails with multi-select).
2. Write subject + body.
3. Click **Approve draft** (localStorage only — no mail yet).
4. Click **Send now** and confirm. AJAX `amy_email_marketing_send` requires
   `approved=1` + `confirmed=1` + `manage_options`.
5. Each successful/failed/opted-out recipient is written to **Send & reply
   history** in the Amy Python service.

Each recipient gets an individual `wp_mail()` call with the configured From
and an **Unsubscribe** footer linking to the public opt-out endpoint.

## History & inbound limitation

| Capability | Status |
| --- | --- |
| Durable outbound log | Yes — service `email_*` tables in `conversations.db` |
| Manual reply / internal notes | Yes — Email Marketing history panel |
| Opt-out / suppression | Yes — footer link + admin Opt out; checked before send |
| Amy propose draft (no send) | Yes — `POST /wp-json/amy-agent/v1/email-marketing/propose` |
| Automatic mailbox IMAP / AgentMail inbound | **No** — FluentSMTP is outbound-only |

Optional: authenticated `POST /wp-json/amy-agent/v1/email-inbound` (header
`X-Amy-Secret`) forwards JSON into history if you wire a mail forwarder
yourself.

## Amy hooks (WordPress)

- `amy_email_marketing_before_send`
- `amy_email_marketing_send_result`
- `amy_email_marketing_after_send`
- `amy_email_marketing_propose`

## What each site must configure

### 1. Domain mailbox

1. Create/confirm the Marketing From mailbox on **your** domain (for OGC
   NewFinity: **`hello@ogcnewfinity.com`**).
2. Note SMTP credentials for FluentSMTP.

### 2. FluentSMTP (WordPress)

1. wp-admin → **FluentSMTP** → Connections.
2. Authorize sending **as** the same address saved in Amy → Settings.
3. Send FluentSMTP’s test email From that address and confirm delivery.

Transactional mail can keep a different FluentSMTP default — Amy only
overrides From for Email Marketing (and Task notify) sends.

### 3. DNS (SPF / DKIM / DMARC)

SPF includes your SMTP provider; DKIM published; DMARC recommended.

### 4. Deploy

Deploy Amy Agent **0.2.47+** and amy-agent-service **0.2.10+**.

## Hard rules

- No personal Gmail for marketing.
- No AgentMail for marketing.
- No automatic send on Approve (or on Amy propose).
- From = per-site Settings domain mailbox (fallback hello@ when empty).
- Respect opt-outs before send.

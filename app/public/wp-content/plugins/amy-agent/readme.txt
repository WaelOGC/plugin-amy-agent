=== Amy Agent ===
Contributors: ogcnewfinity
Tags: ai, chat, assistant, ogc-newfinity
Requires at least: 6.0
Tested up to: 6.8
Requires PHP: 8.0
Stable tag: 0.2.11
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Digital employee for OGC NewFinity. Floating chat widget powered by a Python service and admin-selected AI providers.

== Description ==

Amy Agent is the customer-facing AI layer for OGC NewFinity. The WordPress plugin handles hooks, admin settings, and the floating chat widget; a separate Python service owns intelligence and calls the admin-selected AI provider.

== Installation ==

1. Activate the plugin in WordPress.
2. Go to Settings → Amy Agent and configure the Python service URL, shared secret, AI provider, and API key. Turn on Enable Amy.
3. Run the sibling `amy-agent-service` Python process (see that service's README).
4. Reload any front-end page — the floating Amy widget should appear.

== Changelog ==

= 0.2.11 =
* Temporary build watermark for live deployment verification.

= 0.2.10 =
* Stronger Amy/You bubble distinction (accent edge + sender dots, chat padding); restore terminal centered success card on submit.

= 0.2.9 =
* WhatsApp country-code dropdown on the in-chat contact step; finer LED-style dot-pattern tray background.

= 0.2.8 =
* Auto-growing composer with Shift+Enter newlines, in-chat contact step, and chat-clearing confirmation message.

= 0.2.7 =
* Phase 2: unified conversational chat tray for Submit Your Idea (service pills, one-at-a-time questions, deep-dive in one scroll view).

= 0.2.0 =
* Phase 2: public chat REST route, floating widget, rate limiting. Python providers call real APIs.

= 0.1.0 =
* Phase 1 scaffold: admin settings, theme bridge stubs, REST health, API contract docs.

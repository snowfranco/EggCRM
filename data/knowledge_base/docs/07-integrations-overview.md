---
doc_title: Integrations Overview
doc_type: feature_guide
---

# Integrations Overview

Manage all integrations under **Settings > Integrations**. Which integrations you can connect
depends on your plan.

## Integrations by tier
- **Every plan:** email integration (connect a mailbox so messages log to contact timelines).
- **Professional or higher:** Slack integration, Gmail integration, and API access (see the
  **API Overview & Authentication** guide).
- **Enterprise only:** Zapier integration and custom webhooks.

## Email integration (all plans)
Connect a mailbox via IMAP/SMTP or, on Professional+, with one-click Gmail OAuth. Once connected,
inbound and outbound email is logged to the matching contact's timeline automatically.

## Slack (Professional+)
The Slack integration lets automations post messages to a channel and lets users receive deal and
task notifications in Slack. Connect it from **Settings > Integrations > Slack** and authorize the
EggCRM Slack app for your workspace.

## Gmail (Professional+)
Gmail integration adds two-way email sync, send-from-EggCRM using your Gmail address, and email
open tracking. Connect from **Settings > Integrations > Gmail** with Google OAuth.

## Zapier (Enterprise only)
The Zapier integration connects EggCRM to thousands of third-party apps via Zaps. It is available
**only on the Enterprise plan**. Connect by generating an API key (see below) and authorizing the
EggCRM app inside Zapier.

## Custom webhooks (Enterprise only)
Custom webhooks let EggCRM POST event payloads to a URL you control when records change. Webhooks
are **Enterprise-only**; see the **Webhooks API** reference for event types and payloads.

## API access (Professional+)
Programmatic access uses API keys generated under **Settings > Integrations > API Keys > Generate
New Key**. API access requires Professional or higher. See **API Overview & Authentication**.

## When an integration fails to connect
If an integration fails to connect or sync, verify that the API key has the required permissions
and check the EggCRM **integration status page** for any ongoing incidents. See **Email Sync &
Integration Troubleshooting** for step-by-step recovery.

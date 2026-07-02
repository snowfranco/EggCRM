---
doc_title: Security & Access Control
doc_type: feature_guide
---

# Security & Access Control

## Passwords and sign-in
EggCRM accounts sign in with email and password by default. Passwords must be at least 12
characters. A user can reset their own password with the **"Forgot password?"** link on the login
page, which emails a reset link to their registered address. A support agent can also trigger a
password-reset email to the account's registered email address — agents never set or view
passwords directly. See **Login & Account Access Troubleshooting** for lockouts.

## Roles and permissions
Team members have roles set under **Settings > Team**. Standard roles:
- **Admin** — full access, including billing, integrations, and team management.
- **Manager** — manage pipelines, reports, and other users' records.
- **Member** — work their own contacts and deals.
- **Read-only** — view access without edit.
Record-level ownership still applies — a Member sees shared records and their own.

## Two-factor authentication (2FA)
2FA via authenticator app (TOTP) is available on every plan and can be required org-wide by an
admin under **Settings > Security**.

## SSO / SAML (Enterprise only)
Single sign-on via SAML 2.0 is **Enterprise-only**. Admins configure it under **Settings >
Security > SSO** with their identity provider's metadata (Okta, Azure AD, Google Workspace, and
other SAML IdPs are supported). When SSO is enforced, users sign in through the IdP instead of a
EggCRM password. SSO/SAML configuration issues are handled by the **integrations team**.

## Audit log
Enterprise accounts have an audit log under **Settings > Security > Audit Log** recording sign-ins,
permission changes, exports, and API-key creation.

## Data security
All data is encrypted in transit (TLS) and at rest. Storage limits are 5GB on Starter, 50GB on
Professional, and unlimited on Enterprise.

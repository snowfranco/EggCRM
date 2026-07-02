---
doc_title: Login & Account Access Troubleshooting
doc_type: troubleshooting
---

# Login & Account Access Troubleshooting

## Forgot password
Use the **"Forgot password?"** link on the login page. EggCRM emails a reset link to the
account's registered address; the link is valid for 60 minutes. A support agent can also trigger a
password-reset email to the registered address — agents never view or set passwords directly.

## Reset email not arriving
1. Check spam/junk and any filtering on the registered mailbox.
2. Confirm the email entered matches the **registered** address on the account.
3. Wait a few minutes — delivery is usually under 5.
If it still doesn't arrive, have an agent re-trigger the reset to the registered address and
confirm that address is correct.

## Account locked out
After several failed sign-in attempts, an account is temporarily locked to protect it. The lock
clears automatically after 30 minutes. To restore access sooner, an agent verifies the user's
identity and triggers a password-reset email, which also clears the lock.

## SSO sign-in problems (Enterprise)
On Enterprise accounts with SSO/SAML enforced, users sign in through the identity provider, not a
EggCRM password. If SSO sign-in fails — IdP misconfiguration, certificate/metadata mismatch, or
user not assigned the EggCRM app in the IdP — this is handled by the **integrations team**;
escalate SSO configuration issues there.

## Can't access a feature after signing in
If a user is signed in but can't see a feature, it is usually either a **role/permission** limit
(see **Security & Access Control**) or a **plan-tier** limit (the feature requires a higher plan —
see **Plans & Pricing** for the tier matrix). Confirm both before treating it as a bug.

## 2FA device lost
If a user loses their TOTP device, an admin can reset 2FA for that user under **Settings >
Team**. If the lost device belongs to the only admin, escalate to support to verify ownership.

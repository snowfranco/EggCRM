"""Topic-boundary check (Phase 4) — decision tree, not a flat list (P1 lesson).

Declines ONLY on positive out-of-scope signals; lean-allow everything else (the agent's own
boundary handles general off-topic) so keyword-less follow-ups aren't false-positived:
  1. competitor comparison                       -> decline (boundary #3)
  2. medical/legal/financial advice or misuse    -> decline (safety boundary)
  3. greeting / meta-about-the-bot               -> allow
  4. mentions EggCRM surface (in-scope keyword) -> allow
  5. otherwise (ambiguous)                       -> allow (let the agent clarify)

Deterministic (no LLM call); the `llm` param is kept only for interface compatibility.
"""

from __future__ import annotations

IN_SCOPE = [
    "novacrm", "account", "billing", "invoice", "charge", "plan", "tier", "upgrade", "downgrade",
    "refund", "cancel", "password", "login", "sso", "saml", "api", "integration", "slack",
    "gmail", "zapier", "webhook", "export", "ticket", "bug", "dashboard", "workflow",
    "automation", "seat", "storage", "report", "feature",
]
_COMPETITORS = ["salesforce", "hubspot", "zoho", "pipedrive", "monday.com", "freshsales", "dynamics"]
# Medical/financial/legal ADVICE requests and misuse → decline. NOTE: legal *threats*
# ("I'll sue you") are deliberately NOT here — those must reach the agent so it can escalate
# to the supervisor team (Q8). Only requests for legal/financial *advice* are out-of-scope.
_ADVICE_MISUSE = [
    "medication", "symptom", "diagnos", "chest pain", "headache", "prescri",
    "legal advice", "tax advice", "investment advice", "financial advice",
    "scrape", "phishing", "malware", "exploit",
]
_GREETING = ["hello", "hi ", "hey", "good morning", "good afternoon",
             "are you a bot", "are you a real", "are you human", "who are you", "what are you"]

DECLINE_MESSAGE = (
    "I can only help with EggCRM support — happy to assist with your account, billing, "
    "features, integrations, or any issues you're running into. Is there something there I can help with?"
)


def _has(text: str, terms) -> bool:
    t = text.lower()
    return any(term in t for term in terms)


def check(text: str, llm=None) -> tuple[bool, str, str]:
    """Return (in_scope, category, reason).

    The guard declines ONLY on positive out-of-scope signals (competitor / advice / misuse —
    the safety-sensitive ones). Everything else — including ambiguous follow-ups like "yes, go
    ahead" or "it's broken" — is ALLOWED, and the agent's own boundary handles general off-topic
    (e.g. "weather"). Leaning allow avoids false-positive declines on legitimate support turns
    that carry no domain keyword. (Both-defenses: guard = net for the egregious, prompt = primary.)
    """
    t = text.lower()

    if _has(t, _COMPETITORS):
        return False, "competitor", "competitor comparison — declined per boundary"
    if _has(t, _ADVICE_MISUSE):
        return False, "advice-or-misuse", "medical/legal/financial advice or misuse — declined"
    if any(g in (t + " ") for g in _GREETING):
        return True, "greeting", "greeting / meta — allow briefly"
    if _has(t, IN_SCOPE):
        return True, "in-scope", "matches EggCRM support surface"
    return True, "ambiguous-allow", "no clear out-of-scope signal; allow and let the agent handle/clarify"

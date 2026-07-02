"""FastAPI wrapper exposing the agent over HTTP for the demo UI (run: python -m novacrm_agent.server)."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from .memory import retriever
from .orchestrator import SupportAgent
from .session import Session, new_session

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBUI = _REPO_ROOT / "webui"

app = FastAPI(title="EggCRM Support Agent")
# Allow the demo UI (served here, or opened from another localhost port) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"], allow_headers=["*"],
)

_agent = SupportAgent(guardrails=True)
_GUARD_OUT = {"ok": "✓ approved", "redacted": "⚠ redacted",
              "blocked": "✗ blocked", "rewritten": "⚠ rewritten"}


class ChatIn(BaseModel):
    message: str
    session_id: Optional[str] = None
    customer_id: Optional[str] = None


def _safe(session_id: Optional[str]) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "")[:64] or "web"


def _load_session(session_id: Optional[str], customer_id: Optional[str]) -> Session:
    """Restore the conversation by session_id so history + memory persist across requests."""
    sid = _safe(session_id)
    try:
        s = Session.load(sid)
    except FileNotFoundError:
        s = new_session(sid, user_id=customer_id)
    if customer_id and not s.user_id:
        s.user_id = customer_id
    return s


def _span(result, phase):
    if not result.tracer:
        return None
    return next((sp for sp in result.tracer.spans if sp.phase == phase), None)


def _trace(result, session, latency_ms: int) -> dict:
    """Shape the orchestrator's trace for the UI's 'Under the Hood' panel."""
    if result.blocked_by:
        guard_in = f"✗ blocked ({result.blocked_by})"
    else:
        ig = _span(result, "input_guard")
        guard_in = "⚠ redacted" if (ig and ig.extra.get("redactions")) else "✓ clean"
    og = _span(result, "output_guard")
    action = (og.extra.get("action") if og else None) or ("n/a" if result.blocked_by else "ok")
    tools = [{"name": tc["name"], "input": tc["arguments"], "output": str(tc["output"])[:300]}
             for tc in result.tool_calls]
    memories = ([{"topic": m.topic.value, "fact": m.fact, "action": "recalled"}
                 for m in retriever.get_memories(session.user_id)] if session.user_id else [])
    return {
        "guardrails": {"input": guard_in, "output": _GUARD_OUT.get(action, action)},
        "tools": tools,
        "memories": memories,
        "iterations": result.iterations,
        "latency_ms": latency_ms,
        "tokens": result.tracer.total_tokens() if result.tracer else 0,
    }


@app.get("/")
def index():
    """Serve the prebuilt demo UI (webui/) so localhost:<port> shows the demo."""
    if (_WEBUI / "index.html").exists() and (_WEBUI / "app.js").exists():
        return FileResponse(_WEBUI / "index.html")
    return HTMLResponse(
        "<h2>UI not built.</h2><p>Run <code>npm install &amp;&amp; npm run build</code> "
        "from the repo root.</p><p>API still works: <code>/health</code>, <code>/chat</code>.</p>")


@app.get("/app.js")
def app_js():
    return FileResponse(_WEBUI / "app.js", media_type="application/javascript")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(body: ChatIn):
    session = _load_session(body.session_id, body.customer_id)
    t0 = time.monotonic()
    result = _agent.run(body.message, customer_id=body.customer_id, session=session)
    latency_ms = int((time.monotonic() - t0) * 1000)
    return {"response": result.final_text, "trace": _trace(result, session, latency_ms)}


def main() -> None:
    import argparse
    import os

    import uvicorn

    ap = argparse.ArgumentParser(description="EggCRM agent demo server")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8001")))
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    args = ap.parse_args()
    print(f"EggCRM agent server → http://{args.host}:{args.port}  (/, /health, /chat)")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

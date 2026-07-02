"""CLI entry point — talk to Nova from the terminal.

    python -m novacrm_agent.runner --customer CUST-1001
    python -m novacrm_agent.runner --once "How much is the Pro plan?"

Single-turn for Phase 1. Multi-turn session memory arrives in Phase 2.
"""

from __future__ import annotations

import argparse

from .orchestrator import SupportAgent


def _print_turn(result) -> None:
    if result.tool_calls:
        print(f"  [tools: {', '.join(result.tool_names())}]")
    print(f"Nova: {result.final_text}\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="EggCRM support agent (Nova)")
    ap.add_argument("--customer", help="customer id, e.g. CUST-1001")
    ap.add_argument("--once", help="run a single message and exit")
    args = ap.parse_args()

    agent = SupportAgent()

    if args.once:
        result = agent.run(args.once, customer_id=args.customer)
        _print_turn(result)
        return

    print("EggCRM support — Nova. Ctrl-C to quit.\n")
    try:
        while True:
            msg = input("You: ").strip()
            if not msg:
                continue
            result = agent.run(msg, customer_id=args.customer)
            _print_turn(result)
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye.")


if __name__ == "__main__":
    main()

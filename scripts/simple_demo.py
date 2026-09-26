#!/usr/bin/env python3
"""Run the real AgentGate loop and print each stage."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.adapters import create_adapters
from src.agents import BuilderAgent, FixerAgent
from src.orchestrator import Orchestrator


def main():
    repo = os.getenv("REPO_PATH", str(Path(__file__).resolve().parents[2]))
    os.environ.pop("GITHUB_TOKEN", None)
    os.environ.pop("JEV_API_KEY", None)
    os.environ.pop("TYPESAFE_API_KEY", None)

    adapters = create_adapters(repo)
    print(f"\nAgentGate  mode={adapters['mode']}")

    def show(event):
        data = event.data or {}
        if event.type == "review_complete":
            n = data.get("critical_count", 0)
            print(f"CodeRabbit   {'🔴 ' + str(n) + ' Critical' if n else '🟢 Clean'}")
        elif event.type == "decision_complete":
            print(
                f"Jev          {data.get('action', '').upper()}  "
                f"risk {data.get('risk')} / 10  "
                f"({data.get('source', 'jev')})"
            )
        elif event.type == "fix_complete":
            print(f"Fixer        {data.get('message')}")
        elif event.type == "merge_complete":
            print("Merge        ✅")

    orch = Orchestrator(
        builder=BuilderAgent(adapters["llm"], adapters["github"], repo),
        fixer=FixerAgent(adapters["llm"], repo),
        github=adapters["github"],
        coderabbit=adapters["coderabbit"],
        jev=adapters["jev"],
        repo_path=repo,
        event_callback=show,
    )
    result = orch.run_loop("Create a refund endpoint", "agentgate/add-refund-endpoint")
    print(f"\nResult: {'MERGE' if result.get('success') else result.get('reason')}  attempts={result.get('attempts')}")
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())

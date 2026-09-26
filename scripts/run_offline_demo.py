#!/usr/bin/env python3
"""
Run offline demo end-to-end without dashboard
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters import create_adapters
from src.agents import BuilderAgent, FixerAgent
from src.orchestrator import Orchestrator


def main():
    print("="*60)
    print("AgentGate Offline Demo")
    print("="*60)
    print()
    
    # Setup
    repo_path = os.getenv("REPO_PATH", str(Path(__file__).resolve().parents[2]))
    os.environ.pop("GITHUB_TOKEN", None)  # Force offline mode
    os.environ.pop("JEV_API_KEY", None)
    os.environ.pop("TYPESAFE_API_KEY", None)
    
    # Create adapters
    adapters = create_adapters(repo_path)
    print(f"Mode: {adapters['mode'].upper()}")
    print()
    
    # Create agents
    builder = BuilderAgent(
        adapters["llm"],
        adapters["github"],
        repo_path
    )
    fixer = FixerAgent(adapters["llm"], repo_path)
    
    # Event callback
    def log_event(event):
        print(f"[{event.type}] PR #{event.pr_number}")
    
    # Create orchestrator
    orchestrator = Orchestrator(
        builder=builder,
        fixer=fixer,
        github=adapters["github"],
        coderabbit=adapters["coderabbit"],
        jev=adapters["jev"],
        repo_path=repo_path,
        event_callback=log_event
    )
    
    # Run loop
    issue = "Create a refund endpoint"
    branch = "agentgate/demo-refund-endpoint"
    
    result = orchestrator.run_loop(issue, branch)
    
    # Print result
    print()
    print("="*60)
    print("Demo Result")
    print("="*60)
    print(f"Success: {result['success']}")
    print(f"PR Number: {result['pr_number']}")
    print(f"Attempts: {result['attempts']}")
    if result.get('decision'):
        print(f"Final Decision: {result['decision']['action'].upper()}")
        print(f"Risk: {result['decision']['risk']}/10")
        print(f"Confidence: {result['decision']['confidence']:.1f}%")
    print()
    
    return 0 if result['success'] else 1


if __name__ == "__main__":
    sys.exit(main())

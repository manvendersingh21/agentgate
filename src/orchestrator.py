"""
Main orchestrator for the AgentGate safety loop
"""
import sys
import time
import subprocess
from typing import Dict, Any
from datetime import datetime, timezone

from .models import PRState, Finding, Action, Event
from .adapters import GitHubAdapter, CodeRabbitAdapter, JevAdapter
from .agents import BuilderAgent, FixerAgent


class Orchestrator:
    """Coordinates the full PR safety loop"""
    
    def __init__(
        self,
        builder: BuilderAgent,
        fixer: FixerAgent,
        github: GitHubAdapter,
        coderabbit: CodeRabbitAdapter,
        jev: JevAdapter,
        repo_path: str,
        event_callback=None
    ):
        self.builder = builder
        self.fixer = fixer
        self.github = github
        self.coderabbit = coderabbit
        self.jev = jev
        self.repo_path = repo_path
        self.event_callback = event_callback or (lambda e: None)
    
    def run_loop(self, issue: str, branch: str) -> Dict[str, Any]:
        """
        Run the full safety loop for an issue
        Returns: {success: bool, pr_number: int, decision: dict, attempts: int}
        """
        print(f"\n{'='*60}")
        print(f"AgentGate Safety Loop: {issue}")
        print(f"{'='*60}\n")
        
        # Step 1: Build
        self._emit_event("builder_start", 0, {"issue": issue})
        build_result = self.builder.build(issue, branch)
        
        if not build_result["success"]:
            self._emit_event("builder_failed", 0, {"error": build_result.get("message")})
            return {"success": False, "error": "Build failed"}
        
        pr_number = build_result["pr_number"]
        self._emit_event("builder_complete", pr_number, {"branch": branch})
        
        # Create PR state
        pr_state = PRState(
            pr_number=pr_number,
            branch=branch,
            title=f"feat: {issue}"
        )
        
        # Step 2: Loop until approved or max attempts
        while pr_state.attempt <= pr_state.max_attempts:
            print(f"\n--- Attempt {pr_state.attempt}/{pr_state.max_attempts} ---")
            
            # Run tests
            self._emit_event("tests_start", pr_number, {"attempt": pr_state.attempt})
            test_results = self._run_tests()
            pr_state.test_results = test_results
            self._emit_event("tests_complete", pr_number, test_results)
            
            # Get CodeRabbit review
            self._emit_event("review_start", pr_number, {"attempt": pr_state.attempt})
            
            # Ask CodeRabbit on every attempt, including the first.
            self.coderabbit.request_review(pr_number)
            time.sleep(3)
            
            findings = self.coderabbit.get_review(pr_number)
            pr_state.findings = findings
            
            blocking = self._blocking_findings(findings)
            self._emit_event("review_complete", pr_number, {
                "findings_count": len(findings),
                "critical_count": len(blocking),
                "findings": [self._finding_to_dict(f) for f in findings]
            })
            
            # Get Jev decision
            self._emit_event("decision_start", pr_number, {"attempt": pr_state.attempt})
            
            jev_input = self._prepare_jev_input(pr_state)
            decision = self._apply_guardrails(self.jev.decide(jev_input), pr_state)
            pr_state.decision = decision
            
            answers = (decision.raw_response or {}).get("answers", {})
            action_answer = answers.get("action", {}) if isinstance(answers, dict) else {}
            self._emit_event("decision_complete", pr_number, {
                "merge_safe": decision.merge_safe,
                "confidence": decision.confidence,
                "risk": decision.risk,
                "action": decision.action.value,
                "noul": (answers.get("merge_safe") or {}).get("noul"),
                "probabilities": action_answer.get("probabilities") or {},
                "source": (decision.raw_response or {}).get("source")
                    or (decision.raw_response or {}).get("model")
                    or "jev",
            })
            
            # Handle decision
            if decision.action == Action.MERGE:
                # Merge and done
                self._emit_event("merge_start", pr_number, {})
                self.github.merge_pr(pr_number)
                self._emit_event("merge_complete", pr_number, {})
                
                print(f"\n✅ PR #{pr_number} merged successfully!")
                
                return {
                    "success": True,
                    "pr_number": pr_number,
                    "decision": self._decision_to_dict(decision),
                    "attempts": pr_state.attempt
                }
            
            elif decision.action == Action.FIX and pr_state.attempt < pr_state.max_attempts:
                # Apply fixes
                self._emit_event("fix_start", pr_number, {
                    "findings_count": len(findings),
                    "attempt": pr_state.attempt
                })
                
                diff = self.github.get_pr_diff(pr_number)
                fix_result = self.fixer.fix(
                    [self._finding_to_dict(f) for f in findings],
                    diff,
                    branch,
                    pr_number=pr_number,
                    github=self.github if hasattr(self.github, "list_commit_shas") else None
                )
                
                self._emit_event("fix_complete", pr_number, fix_result)
                
                pr_state.attempt += 1
                # Loop continues
            
            else:
                # Human review or reject
                self._emit_event("human_review_required", pr_number, {
                    "reason": decision.action.value,
                    "attempts": pr_state.attempt
                })
                
                print(f"\n⚠️  PR #{pr_number} requires human review")
                
                return {
                    "success": False,
                    "pr_number": pr_number,
                    "decision": self._decision_to_dict(decision),
                    "attempts": pr_state.attempt,
                    "reason": "human_review_required"
                }
        
        # Max attempts reached
        print(f"\n❌ Max attempts ({pr_state.max_attempts}) reached")
        
        return {
            "success": False,
            "pr_number": pr_number,
            "decision": self._decision_to_dict(pr_state.decision) if pr_state.decision else None,
            "attempts": pr_state.attempt,
            "reason": "max_attempts"
        }
    
    def _apply_guardrails(self, decision, pr_state: PRState):
        """Never merge while tests fail or a critical/security finding is open."""
        tests_pass = (pr_state.test_results or {}).get("passed", False)
        blocked = (not tests_pass) or bool(self._blocking_findings(pr_state.findings))
        if decision.action != Action.MERGE or not blocked:
            return decision
        action = Action.FIX if pr_state.attempt < pr_state.max_attempts else Action.HUMAN_REVIEW
        raw = dict(decision.raw_response or {})
        raw["guardrail"] = "merge_blocked"
        return type(decision)(
            merge_safe=False,
            confidence=decision.confidence,
            risk=decision.risk,
            action=action,
            raw_response=raw,
        )

    def _blocking_findings(self, findings) -> list:
        return [f for f in findings if f.severity.value in ("critical", "security")]

    def _run_tests(self) -> Dict[str, Any]:
        """Run tests on demo target"""
        test_path = f"{self.repo_path}/agentgate/demo-target"
        
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "test_app.py", "-v", "--tb=short"],
            cwd=test_path,
            capture_output=True,
            text=True
        )
        
        passed = result.returncode == 0
        
        return {
            "passed": passed,
            "exit_code": result.returncode,
            "output": result.stdout + result.stderr
        }
    
    def _prepare_jev_input(self, pr_state: PRState) -> Dict[str, Any]:
        """Prepare input for Jev decision"""
        diff = self.github.get_pr_diff(pr_state.pr_number)
        
        return {
            "pr_number": pr_state.pr_number,
            "findings": [self._finding_to_dict(f) for f in pr_state.findings],
            "tests_pass": pr_state.test_results.get("passed", False),
            "diff": diff,
            "attempt": pr_state.attempt,
            "files_changed": len(set(f.file for f in pr_state.findings))
        }
    
    def _finding_to_dict(self, finding: Finding) -> dict:
        """Convert Finding to dict"""
        return {
            "severity": finding.severity.value,
            "category": finding.category,
            "file": finding.file,
            "line": finding.line,
            "message": finding.message,
            "suggested_fix": finding.suggested_fix
        }
    
    def _decision_to_dict(self, decision) -> dict:
        """Convert JevDecision to dict"""
        return {
            "merge_safe": decision.merge_safe,
            "confidence": decision.confidence,
            "risk": decision.risk,
            "action": decision.action.value
        }
    
    def _emit_event(self, event_type: str, pr_number: int, data: dict):
        """Emit event for dashboard"""
        event = Event(
            type=event_type,
            pr_number=pr_number,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        self.event_callback(event)

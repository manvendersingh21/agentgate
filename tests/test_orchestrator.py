"""
Tests for orchestrator state machine
"""
import pytest
from unittest.mock import Mock, MagicMock
from src.orchestrator import Orchestrator
from src.models import Finding, JevDecision, Action, Severity


def create_mock_orchestrator():
    """Create orchestrator with mocked dependencies"""
    builder = Mock()
    fixer = Mock()
    github = Mock()
    coderabbit = Mock()
    jev = Mock()
    
    orchestrator = Orchestrator(
        builder=builder,
        fixer=fixer,
        github=github,
        coderabbit=coderabbit,
        jev=jev,
        repo_path="/tmp",
        event_callback=Mock()
    )
    
    return orchestrator, builder, fixer, github, coderabbit, jev


def test_orchestrator_success_flow():
    """Test successful flow: build -> review -> approve -> merge"""
    orchestrator, builder, fixer, github, coderabbit, jev = create_mock_orchestrator()
    
    # Mock successful build
    builder.build.return_value = {
        "success": True,
        "pr_number": 123,
        "branch": "test-branch"
    }
    
    # Mock clean review
    coderabbit.get_review.return_value = []
    
    # Mock tests passing
    orchestrator._run_tests = Mock(return_value={
        "passed": True,
        "exit_code": 0,
        "output": "All tests passed"
    })
    
    # Mock Jev approval
    jev.decide.return_value = JevDecision(
        merge_safe=True,
        confidence=95.0,
        risk=1.0,
        action=Action.MERGE
    )
    
    # Mock diff
    github.get_pr_diff.return_value = "diff content"
    
    # Run
    result = orchestrator.run_loop("test issue", "test-branch")
    
    # Verify
    assert result["success"] is True
    assert result["pr_number"] == 123
    assert result["attempts"] == 1
    github.merge_pr.assert_called_once_with(123)


def test_orchestrator_fix_then_merge():
    """Test flow with fix: build -> review (fail) -> fix -> review (pass) -> merge"""
    orchestrator, builder, fixer, github, coderabbit, jev = create_mock_orchestrator()
    
    # Mock successful build
    builder.build.return_value = {
        "success": True,
        "pr_number": 123,
        "branch": "test-branch"
    }
    
    # Mock tests passing
    orchestrator._run_tests = Mock(return_value={
        "passed": True,
        "exit_code": 0,
        "output": "All tests passed"
    })
    
    # Mock review: first with findings, then clean
    finding = Finding(
        severity=Severity.CRITICAL,
        category="security",
        file="app.py",
        line=10,
        message="Auth missing"
    )
    coderabbit.get_review.side_effect = [[finding], []]
    
    # Mock Jev: first FIX, then MERGE
    jev.decide.side_effect = [
        JevDecision(
            merge_safe=False,
            confidence=95.0,
            risk=9.0,
            action=Action.FIX
        ),
        JevDecision(
            merge_safe=True,
            confidence=98.0,
            risk=1.0,
            action=Action.MERGE
        )
    ]
    
    # Mock fixer success
    fixer.fix.return_value = {"success": True}
    
    # Mock diff
    github.get_pr_diff.return_value = "diff content"
    
    # Run
    result = orchestrator.run_loop("test issue", "test-branch")
    
    # Verify
    assert result["success"] is True
    assert result["attempts"] == 2
    fixer.fix.assert_called_once()
    github.merge_pr.assert_called_once_with(123)


def test_orchestrator_max_attempts():
    """Test max attempts reached"""
    orchestrator, builder, fixer, github, coderabbit, jev = create_mock_orchestrator()
    
    # Mock successful build
    builder.build.return_value = {
        "success": True,
        "pr_number": 123,
        "branch": "test-branch"
    }
    
    # Mock tests passing
    orchestrator._run_tests = Mock(return_value={"passed": True, "exit_code": 0})
    
    # Mock persistent findings
    finding = Finding(
        severity=Severity.CRITICAL,
        category="security",
        file="app.py",
        line=10,
        message="Auth missing"
    )
    coderabbit.get_review.return_value = [finding]
    
    # Mock Jev always says FIX
    jev.decide.return_value = JevDecision(
        merge_safe=False,
        confidence=95.0,
        risk=9.0,
        action=Action.FIX
    )
    
    # Mock fixer success but doesn't fix the issue
    fixer.fix.return_value = {"success": True}
    
    # Mock diff
    github.get_pr_diff.return_value = "diff content"
    
    # Run
    result = orchestrator.run_loop("test issue", "test-branch")
    
    # Verify we stopped at max attempts
    # On the 3rd attempt, Jev says FIX but we've hit max attempts,
    # so it goes to human_review instead
    assert result["success"] is False
    assert result["reason"] == "human_review_required"
    assert fixer.fix.call_count == 2  # Called twice (attempts 1 and 2)


def test_orchestrator_blocks_merge_when_tests_fail():
    """A MERGE decision cannot ship while the demo tests are failing."""
    orchestrator, builder, fixer, github, coderabbit, jev = create_mock_orchestrator()
    builder.build.return_value = {"success": True, "pr_number": 123, "branch": "test-branch"}
    orchestrator._run_tests = Mock(return_value={"passed": False, "exit_code": 1, "output": "fail"})
    coderabbit.get_review.return_value = []
    jev.decide.return_value = JevDecision(
        merge_safe=True, confidence=90.0, risk=1.0, action=Action.MERGE
    )
    fixer.fix.return_value = {"success": True}
    github.get_pr_diff.return_value = "diff"

    result = orchestrator.run_loop("test issue", "test-branch")

    github.merge_pr.assert_not_called()
    assert fixer.fix.call_count == 2
    assert result["success"] is False
    assert result["reason"] == "human_review_required"


def test_orchestrator_blocks_merge_when_security_finding_open():
    """A MERGE decision cannot ship while a security finding is open."""
    orchestrator, builder, fixer, github, coderabbit, jev = create_mock_orchestrator()
    builder.build.return_value = {"success": True, "pr_number": 123, "branch": "test-branch"}
    orchestrator._run_tests = Mock(return_value={"passed": True, "exit_code": 0, "output": "ok"})
    coderabbit.get_review.return_value = [Finding(
        severity=Severity.SECURITY,
        category="security",
        file="app.py",
        line=10,
        message="Refund amount is not checked",
    )]
    jev.decide.return_value = JevDecision(
        merge_safe=True, confidence=90.0, risk=2.0, action=Action.MERGE
    )
    fixer.fix.return_value = {"success": True}
    github.get_pr_diff.return_value = "diff"

    result = orchestrator.run_loop("test issue", "test-branch")

    github.merge_pr.assert_not_called()
    assert result["reason"] == "human_review_required"


def test_orchestrator_build_failure():
    """Test build failure"""
    orchestrator, builder, fixer, github, coderabbit, jev = create_mock_orchestrator()
    
    # Mock failed build
    builder.build.return_value = {
        "success": False,
        "message": "Build failed"
    }
    
    # Run
    result = orchestrator.run_loop("test issue", "test-branch")
    
    # Verify
    assert result["success"] is False
    assert "error" in result
    coderabbit.get_review.assert_not_called()
    jev.decide.assert_not_called()

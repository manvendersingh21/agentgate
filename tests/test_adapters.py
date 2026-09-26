"""
Tests for adapters
"""
import pytest
from src.models import Severity, Action
from src.adapters import (
    CannedCodeRabbitAdapter,
    StubJevAdapter,
    CannedLLMAdapter,
    LiveCodeRabbitAdapter,
)


# Real inline comments captured from
# https://github.com/manvendersingh21/PR-slayer/pull/2
PR2_IDOR = """
_🔒 Security & Privacy_ | _🛡️ Detected with Advanced Tier_ | _🟡 Minor_ | _⚡ Quick win_

**IDOR**

**Enforce authentication and payment ownership before refunding.**

`POST /refunds` has no authentication dependency. It checks only whether `payment_id` exists.
CWE-639 Authorization Bypass Through User-Controlled Key (IDOR)
"""

PR2_AMOUNT = """
_🗄️ Data Integrity & Integration_ | _🟠 Major_ | _🏗️ Heavy lift_

**Reject amounts outside the refundable balance.**

The handler copies `refund.amount` into a completed response without comparing it with the payment amount.
"""

PR2_PERSIST = """
_🗄️ Data Integrity & Integration_ | _🟠 Major_ | _🏗️ Heavy lift_

**Persist refunds before reporting completion.**

The endpoint generates a refund ID but stores no refund record.
"""


def test_parse_real_pr2_coderabbit_comments():
    """Parser reads the three findings CodeRabbit posted on PR 2."""
    adapter = LiveCodeRabbitAdapter(github=None, repo="manvendersingh21/PR-slayer", token="unused")
    comments = [
        {"body": PR2_IDOR, "path": "agentgate/demo-target/app.py", "line": 97},
        {"body": PR2_AMOUNT, "path": "agentgate/demo-target/app.py", "line": 102},
        {"body": PR2_PERSIST, "path": "agentgate/demo-target/app.py", "line": 105},
        {"body": "@coderabbitai autofix", "path": "agentgate/demo-target/app.py", "line": 97, "in_reply_to_id": 1},
    ]
    findings = [adapter._parse_comment(c) for c in comments if not c.get("in_reply_to_id")]
    findings = [f for f in findings if f]

    assert len(findings) == 3
    assert findings[0].severity == Severity.CRITICAL
    assert "IDOR" in findings[0].message
    assert findings[1].severity == Severity.SECURITY
    assert "refundable balance" in findings[1].message
    assert findings[2].severity == Severity.SECURITY


def test_canned_coderabbit_first_review():
    """First review should have critical findings"""
    adapter = CannedCodeRabbitAdapter(inject_bug=True)
    findings = adapter.get_review(pr_number=1)
    
    assert len(findings) > 0
    critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
    assert len(critical_findings) > 0
    assert "authorization" in findings[0].message.lower()


def test_canned_coderabbit_second_review():
    """Second review should be clean after fix"""
    adapter = CannedCodeRabbitAdapter(inject_bug=True)
    
    # First review
    findings1 = adapter.get_review(pr_number=1)
    assert len(findings1) > 0
    
    # Second review (after fix)
    findings2 = adapter.get_review(pr_number=1)
    assert len(findings2) == 0


def test_stub_jev_blocks_on_critical():
    """Jev should block merge when critical findings exist"""
    adapter = StubJevAdapter()
    
    pr_state = {
        "findings": [
            {
                "severity": "critical",
                "message": "Security issue",
                "file": "app.py",
                "line": 10
            }
        ],
        "tests_pass": True,
        "attempt": 1
    }
    
    decision = adapter.decide(pr_state)
    
    assert decision.merge_safe is False
    assert decision.action == Action.FIX
    assert decision.risk > 5.0


def test_stub_jev_blocks_on_test_failure():
    """Jev should block merge when tests fail"""
    adapter = StubJevAdapter()
    
    pr_state = {
        "findings": [],
        "tests_pass": False,
        "attempt": 1
    }
    
    decision = adapter.decide(pr_state)
    
    assert decision.merge_safe is False
    assert decision.action == Action.FIX


def test_stub_jev_approves_clean_pr():
    """Jev should approve clean PR with passing tests"""
    adapter = StubJevAdapter()
    
    pr_state = {
        "findings": [],
        "tests_pass": True,
        "attempt": 1
    }
    
    decision = adapter.decide(pr_state)
    
    assert decision.merge_safe is True
    assert decision.action == Action.MERGE
    assert decision.risk == 2.7  # From real Jev capture for clean PR
    assert decision.confidence == 94.0  # From real Jev capture


def test_stub_jev_human_review_on_max_attempts():
    """Jev should require human review after max attempts"""
    adapter = StubJevAdapter()
    
    pr_state = {
        "findings": [{"severity": "critical"}],
        "tests_pass": True,
        "attempt": 3  # Max attempts
    }
    
    decision = adapter.decide(pr_state)
    
    assert decision.action == Action.HUMAN_REVIEW


def test_canned_llm_generates_refund_code():
    """LLM should generate refund endpoint code"""
    adapter = CannedLLMAdapter()
    code = adapter.generate_code("Create a refund endpoint")
    
    assert "refund" in code.lower()
    assert "@app.post" in code or "def create_refund" in code


class _Resp:
    def __init__(self, code, payload=None):
        self.status_code = code
        self.ok = code < 400
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP {self.status_code}")


def test_create_pr_reuses_open_pr_when_create_is_forbidden(monkeypatch):
    """A 403 from the pulls API should use the open PR for that branch."""
    from src.adapters import LiveGitHubAdapter

    adapter = LiveGitHubAdapter("token", "manvendersingh21/PR-slayer")

    def post(url, headers=None, json=None):
        return _Resp(403, {"message": "forbidden"})

    def get(url, headers=None, params=None):
        assert params["head"] == "manvendersingh21:agentgate/add-refund-endpoint"
        assert params["state"] == "open"
        return _Resp(200, [{"number": 6}])

    monkeypatch.setattr("src.adapters.requests.post", post)
    monkeypatch.setattr("src.adapters.requests.get", get)
    assert adapter.create_pr("agentgate/add-refund-endpoint", "feat", "body") == 6


def test_add_comment_returns_false_on_403(monkeypatch):
    """Commenting is forbidden for this token, and that must not raise."""
    from src.adapters import LiveGitHubAdapter

    adapter = LiveGitHubAdapter("token", "manvendersingh21/PR-slayer")
    monkeypatch.setattr("src.adapters.requests.post", lambda *a, **k: _Resp(403))
    assert adapter.add_comment(5, "@coderabbitai review") is False


def test_request_review_survives_forbidden_comment():
    class GitHub:
        def add_comment(self, pr_number, comment):
            return False

    adapter = LiveCodeRabbitAdapter(github=GitHub(), repo="o/r", token="t")
    adapter.request_review(5)


def test_live_review_timeout_is_not_a_clean_review(monkeypatch):
    """No CodeRabbit activity is an unreviewed pull request, not a clean one."""
    adapter = LiveCodeRabbitAdapter(github=None, repo="o/r", token="t")
    monkeypatch.setattr(adapter, "_parse_comments", lambda pr: [])
    monkeypatch.setattr(adapter, "_review_posted", lambda pr: False)
    monkeypatch.setattr("src.adapters.time.sleep", lambda _s: None)
    clock = {"t": 0}

    def fake_time():
        clock["t"] += 301
        return clock["t"]

    monkeypatch.setattr("src.adapters.time.time", fake_time)
    findings = adapter.get_review(5, timeout=300)
    assert len(findings) == 1
    assert findings[0].severity == Severity.SECURITY
    assert "unreviewed" in findings[0].message


def test_live_review_with_no_inline_comments_is_clean(monkeypatch):
    """A finished CodeRabbit review with no inline comments is clean."""
    adapter = LiveCodeRabbitAdapter(github=None, repo="o/r", token="t")
    monkeypatch.setattr(adapter, "_parse_comments", lambda pr: [])
    monkeypatch.setattr(adapter, "_review_posted", lambda pr: True)
    assert adapter.get_review(5, timeout=300) == []


def test_coding_agent_does_not_wait_when_comment_forbidden():
    from src.agents import FixerAgent

    class GitHub:
        def list_commit_shas(self, pr_number):
            return ["abc"]

        def add_comment(self, pr_number, comment):
            return False

    result = FixerAgent(llm=None, repo_path=".")._fix_with_coding_agent(GitHub(), 5, 1)
    assert result["success"] is False
    assert "forbidden" in result["message"]

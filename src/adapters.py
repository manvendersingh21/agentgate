"""
Adapters for external services (GitHub, CodeRabbit, Jev, LLM)
Each adapter has offline/hybrid/live modes based on env vars.
"""
import os
import json
import re
import time
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
import requests

from .models import Finding, JevDecision, Action, Severity


class GitHubAdapter(ABC):
    """Abstract GitHub interface"""
    
    @abstractmethod
    def create_pr(self, branch: str, title: str, body: str) -> int:
        """Create a PR and return PR number"""
        pass
    
    @abstractmethod
    def get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff"""
        pass
    
    @abstractmethod
    def merge_pr(self, pr_number: int):
        """Merge the PR"""
        pass
    
    @abstractmethod
    def add_comment(self, pr_number: int, comment: str):
        """Add a comment to PR"""
        pass


class LocalGitHubAdapter(GitHubAdapter):
    """Offline mode: uses local git"""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
    
    def create_pr(self, branch: str, title: str, body: str) -> int:
        """Simulate PR creation"""
        # Just return a fake PR number
        return hash(branch) % 1000
    
    def get_pr_diff(self, pr_number: int) -> str:
        """Get diff from local git"""
        result = subprocess.run(
            ["git", "diff", "main...HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        return result.stdout
    
    def merge_pr(self, pr_number: int):
        """Simulate merge"""
        print(f"[LocalGitHub] Simulated merge of PR #{pr_number}")
    
    def add_comment(self, pr_number: int, comment: str):
        """Simulate comment"""
        print(f"[LocalGitHub] Simulated comment on PR #{pr_number}: {comment[:50]}...")


class LiveGitHubAdapter(GitHubAdapter):
    """Live mode: real GitHub API"""
    
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo  # owner/name
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"
    
    def create_pr(self, branch: str, title: str, body: str) -> int:
        """Create real PR via GitHub API"""
        url = f"{self.base_url}/repos/{self.repo}/pulls"
        data = {
            "title": title,
            "body": body,
            "head": branch,
            "base": "main"
        }
        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code in (403, 422):
            owner = self.repo.split("/")[0]
            existing = requests.get(
                url,
                headers=self.headers,
                params={"state": "open", "head": f"{owner}:{branch}"},
            )
            if existing.ok:
                pulls = existing.json()
                if isinstance(pulls, list) and pulls:
                    return pulls[0]["number"]
        response.raise_for_status()
        return response.json()["number"]
    
    def get_pr_diff(self, pr_number: int) -> str:
        """Get PR diff"""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}"
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    
    def merge_pr(self, pr_number: int):
        """Merge PR"""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/merge"
        response = requests.put(url, headers=self.headers)
        response.raise_for_status()
    
    def add_comment(self, pr_number: int, comment: str) -> bool:
        """Add comment to PR. Returns False when this token cannot comment."""
        url = f"{self.base_url}/repos/{self.repo}/issues/{pr_number}/comments"
        response = requests.post(url, headers=self.headers, json={"body": comment})
        if response.status_code == 403:
            print("[GitHub] Cannot comment with this token (403)")
            return False
        response.raise_for_status()
        return True

    def list_commit_shas(self, pr_number: int) -> list:
        """Commit SHAs currently on the pull request."""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/commits"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return [commit.get("sha") for commit in response.json() if commit.get("sha")]


class CodeRabbitAdapter(ABC):
    """Abstract CodeRabbit interface"""
    
    @abstractmethod
    def get_review(self, pr_number: int) -> List[Finding]:
        """Get normalized review findings"""
        pass
    
    @abstractmethod
    def request_review(self, pr_number: int):
        """Request a new review"""
        pass


class CannedCodeRabbitAdapter(CodeRabbitAdapter):
    """Offline mode: returns canned findings"""
    
    def __init__(self, inject_bug: bool = True):
        self.inject_bug = inject_bug
        self.review_count = 0
    
    def get_review(self, pr_number: int) -> List[Finding]:
        """Return canned findings"""
        self.review_count += 1
        
        # First review: always has a critical bug
        if self.review_count == 1 and self.inject_bug:
            return [
                Finding(
                    severity=Severity.CRITICAL,
                    category="security",
                    file="agentgate/demo-target/app.py",
                    line=75,
                    message="Missing authorization check: Any user can refund any payment. Verify that user_id from request matches the order's owner.",
                    suggested_fix="Add auth check: if orders_db[payment['order_id']]['user_id'] != refund.user_id: raise HTTPException(403)"
                ),
                Finding(
                    severity=Severity.MAINTAINABILITY,
                    category="code_quality",
                    file="agentgate/demo-target/app.py",
                    line=80,
                    message="Consider adding logging for refund operations for audit trail",
                    suggested_fix=None
                )
            ]
        
        # After fix: clean review
        return []
    
    def request_review(self, pr_number: int):
        """Simulate review request"""
        print(f"[CannedCodeRabbit] Simulated review request for PR #{pr_number}")


def _coderabbit_message(body: str) -> str:
    """Pull the finding title and explanation out of a CodeRabbit comment."""
    text = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    text = re.sub(r"<details>.*?</details>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("**", "")
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" |_")
        if not line or line.startswith("http") or "Script executed" in line:
            continue
        if line.startswith("_") or "Prompt for AI" in line or "Analysis chain" in line:
            continue
        lines.append(line)
    if not lines:
        return ""
    return " ".join(lines[:4])[:500]


class LiveCodeRabbitAdapter(CodeRabbitAdapter):
    """Live mode: polls GitHub for CodeRabbit bot comments"""
    
    def __init__(self, github: GitHubAdapter, repo: str, token: str):
        self.github = github
        self.repo = repo
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.base_url = "https://api.github.com"
    
    def get_review(self, pr_number: int, timeout: int = 300) -> List[Finding]:
        """Poll for CodeRabbit review comments.

        An empty poll is not a clean review. A clean result is returned only
        after CodeRabbit has actually posted a review with no findings.
        """
        print(f"[LiveCodeRabbit] Polling for review on PR #{pr_number}...")
        
        start = time.time()
        while time.time() - start < timeout:
            findings = self._parse_comments(pr_number)
            if findings:
                return findings
            if self._review_posted(pr_number):
                return []
            time.sleep(5)
        
        print("[LiveCodeRabbit] Timeout waiting for review")
        return [
            Finding(
                severity=Severity.SECURITY,
                category="review",
                file="unknown",
                line=0,
                message="CodeRabbit did not post a review before the timeout. The pull request is unreviewed.",
                suggested_fix=None,
            )
        ]

    def _review_posted(self, pr_number: int) -> bool:
        """True when CodeRabbit has finished a review, even with no inline comments."""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/reviews"
        response = requests.get(url, headers=self.headers)
        if not response.ok:
            return False
        for review in response.json():
            if review.get("user", {}).get("login") == "coderabbitai[bot]":
                return True
        return False
    
    def _parse_comments(self, pr_number: int) -> List[Finding]:
        """Parse CodeRabbit comments into findings"""
        url = f"{self.base_url}/repos/{self.repo}/pulls/{pr_number}/comments"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        
        findings = []
        for comment in response.json():
            # Top-level review notes only. Replies are commands such as autofix.
            if comment.get("in_reply_to_id"):
                continue
            if comment.get("user", {}).get("login") == "coderabbitai[bot]":
                finding = self._parse_comment(comment)
                if finding:
                    findings.append(finding)
        
        return findings
    
    def _parse_comment(self, comment: dict) -> Optional[Finding]:
        """Parse a CodeRabbit inline comment from a real review."""
        body = comment.get("body", "")
        if not body or body.strip().startswith("@coderabbit"):
            return None

        message = _coderabbit_message(body)
        if not message:
            return None

        low = body.lower()
        if any(word in low for word in ("critical", "idor", "cwe-639", "vulnerability")):
            severity = Severity.CRITICAL
        elif "major" in low or "security" in low:
            severity = Severity.SECURITY
        elif "minor" in low:
            severity = Severity.MAINTAINABILITY
        else:
            severity = Severity.SUGGESTION

        category = "security" if severity == Severity.CRITICAL else "review"
        return Finding(
            severity=severity,
            category=category,
            file=comment.get("path", "unknown"),
            line=comment.get("line") or 0,
            message=message,
            suggested_fix=None
        )
    
    def request_review(self, pr_number: int):
        """Request CodeRabbit review by adding comment.

        A forbidden comment must not abort the loop. Polling still uses a
        review that is already on the pull request.
        """
        posted = self.github.add_comment(pr_number, "@coderabbitai review")
        if posted is False:
            print(
                "[LiveCodeRabbit] Could not request a review "
                "(GitHub comment was forbidden). Using the review already on the pull request."
            )


class JevAdapter(ABC):
    """Abstract Jev decision interface"""
    
    @abstractmethod
    def decide(self, pr_state: Dict[str, Any]) -> JevDecision:
        """Make a decision on PR safety"""
        pass


class StubJevAdapter(JevAdapter):
    """Offline mode: stub using values from recorded Jev response"""
    
    def decide(self, pr_state: Dict[str, Any]) -> JevDecision:
        """Stub decision based on real Jev API captures"""
        findings = pr_state.get("findings", [])
        tests_pass = pr_state.get("tests_pass", True)
        attempt = pr_state.get("attempt", 1)
        
        # Block on critical and security findings. CodeRabbit labels an auth bypass
        # "Minor" and an over-refund "Major"; both must stop a merge.
        critical_count = sum(1 for f in findings if f["severity"] in ("critical", "security"))
        
        if critical_count > 0 or not tests_pass:
            # Stub (from recorded Jev response) for the buggy PR:
            # noul=0.02, score=3.96 → 9.9/10, choice=fix, confidence=0.93
            action = Action.FIX if attempt < 3 else Action.HUMAN_REVIEW
            return JevDecision(
                merge_safe=False,
                confidence=93.0,
                risk=9.9,
                action=action,
                raw_response={
                    "source": "stub (from recorded Jev response)",
                    "answers": {
                        "merge_safe": {"type": "noul", "noul": 0.02},
                        "action": {
                            "type": "choice",
                            "choice": action.value,
                            "confidence": 0.93,
                            "probabilities": {
                                "fix": 0.95,
                                "merge": 0.0,
                                "reject": 0.0,
                                "human_review": 0.05,
                            },
                        },
                    },
                },
            )
        
        # Stub (from recorded Jev response) for the fixed PR:
        # noul=0.84, score=1.08 → 2.7/10, choice=merge, confidence=0.94
        return JevDecision(
            merge_safe=True,
            confidence=94.0,
            risk=2.7,
            action=Action.MERGE,
            raw_response={
                "source": "stub (from recorded Jev response)",
                "answers": {
                    "merge_safe": {"type": "noul", "noul": 0.84},
                    "action": {
                        "type": "choice",
                        "choice": "merge",
                        "confidence": 0.94,
                        "probabilities": {
                            "merge": 0.96,
                            "human_review": 0.04,
                            "fix": 0.0,
                            "reject": 0.0,
                        },
                    },
                },
            },
        )


class LiveJevAdapter(JevAdapter):
    """Live/Hybrid mode: real Jev API with verified schema"""
    
    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url or os.getenv("JEV_BASE_URL", "https://api.typesafe.ai")
        self.url = f"{self.base_url}/v1/systemone"
        self.available = True
        self.last_error = None
    
    def decide(self, pr_state: Dict[str, Any]) -> JevDecision:
        """Call real Jev API with verified schema"""
        # Build structured state (JSON object, not string)
        findings = pr_state.get("findings", [])
        tests_pass = pr_state.get("tests_pass", True)
        attempt = pr_state.get("attempt", 1)
        
        state = {
            "pr": {
                "number": pr_state.get("pr_number", 0),
                "files_changed": pr_state.get("files_changed", len(set(f.get("file") for f in findings if f.get("file"))))
            },
            "coderabbit_findings": [
                {
                    "severity": f.get("severity"),
                    "category": f.get("category"),
                    "file": f.get("file"),
                    "line": f.get("line"),
                    "message": f.get("message")
                }
                for f in findings
            ],
            "tests": {
                "passing": tests_pass,
                "failed_count": 0 if tests_pass else 1
            },
            "attempt": attempt,
            "previous_attempts": []
        }
        
        # Exact questions from verified real API call
        payload = {
            "model": "jev-latest",
            "state": state,
            "questions": {
                "merge_safe": {
                    "type": "noul",
                    "instructions": "Is this pull request safe to merge as-is?",
                    "criteria": {
                        "true": "No open critical/security issues and tests pass",
                        "false": "Open critical or security issues, or failing tests"
                    }
                },
                "risk": {
                    "type": "score",
                    "instructions": "How risky is merging this pull request?",
                    "criteria": ["None", "Low", "Moderate", "High", "Severe"]
                },
                "action": {
                    "type": "choice",
                    "instructions": "What should the pipeline do next?",
                    "criteria": {
                        "merge": "Safe to merge now",
                        "fix": "Fixable issues; send findings to the fixer agent",
                        "human_review": "Ambiguous or high-stakes; needs a human",
                        "reject": "Fundamentally wrong approach; close the PR"
                    }
                }
            }
        }
        
        try:
            print("[Jev] Calling API...")
            response = requests.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse REAL Jev response schema (verified)
            if not isinstance(data, dict):
                raise ValueError(f"Expected dict response, got {type(data)}")
            
            answers = data.get("answers")
            if not answers or not isinstance(answers, dict):
                print(f"[Jev] Schema mismatch - raw response:")
                print(json.dumps(data, indent=2))
                raise ValueError("Missing or invalid 'answers' field")
            
            # Parse merge_safe (noul)
            merge_safe_data = answers.get("merge_safe", {})
            noul = merge_safe_data.get("noul", 0.5)
            merge_safe = noul >= 0.5
            
            # Parse risk (score with legend)
            risk_data = answers.get("risk", {})
            risk_score = risk_data.get("score", 2.5)
            risk_legend = risk_data.get("legend", {})
            num_levels = len(risk_legend)
            
            # Map to 0-10: score / (levels-1) * 10
            # Example: 3.96 with 5 levels → 3.96/4*10 = 9.9
            if num_levels > 1:
                risk_0_10 = (risk_score / (num_levels - 1)) * 10
            else:
                risk_0_10 = risk_score
            
            # Parse action (choice with probabilities)
            action_data = answers.get("action", {})
            action_choice = action_data.get("choice", "human_review")
            action_confidence = action_data.get("confidence", 0.0)
            
            # Validate action
            if action_choice not in ["merge", "fix", "human_review", "reject"]:
                print(f"[Jev] Invalid action '{action_choice}', defaulting to human_review")
                action_choice = "human_review"
            
            print(f"[Jev] ✅ API responded: action={action_choice}, risk={risk_0_10:.1f}/10, confidence={action_confidence:.0%}")
            
            return JevDecision(
                merge_safe=merge_safe,
                confidence=action_confidence * 100,  # Use action's confidence
                risk=round(risk_0_10, 1),
                action=Action(action_choice),
                raw_response=data
            )
        
        except requests.exceptions.RequestException as e:
            self.available = False
            self.last_error = f"Network error: {e}"
            print(f"[Jev] Jev unavailable: {self.last_error}")
            print("[Jev] Falling back to stub decision")
            stub = StubJevAdapter()
            return stub.decide(pr_state)
        
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            self.available = False
            self.last_error = f"Parse error: {e}"
            print(f"[Jev] Jev unavailable: {self.last_error}")
            print("[Jev] Falling back to stub decision")
            stub = StubJevAdapter()
            return stub.decide(pr_state)
        
        except Exception as e:
            self.available = False
            self.last_error = str(e)
            print(f"[Jev] Jev unavailable: {self.last_error}")
            print("[Jev] Falling back to stub decision")
            stub = StubJevAdapter()
            return stub.decide(pr_state)


class LLMAdapter(ABC):
    """Abstract LLM interface for code generation"""
    
    @abstractmethod
    def generate_code(self, prompt: str) -> str:
        """Generate code from prompt"""
        pass


BUGGY_REFUND = '''
class Refund(BaseModel):
    payment_id: str
    amount: float
    user_id: str


@app.post("/refunds")
def create_refund(refund: Refund):
    """Create a refund for a payment. Missing an ownership check on purpose."""
    if refund.payment_id not in payments_db:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment = payments_db[refund.payment_id]
    refund_id = str(uuid.uuid4())
    return {
        "id": refund_id,
        "payment_id": refund.payment_id,
        "amount": refund.amount,
        "user_id": refund.user_id,
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
'''


class CannedLLMAdapter(LLMAdapter):
    """Offline stand-in. First call ships the bug. Later calls apply the recorded fix."""

    def __init__(self):
        self.call_count = 0

    def generate_code(self, prompt: str) -> str:
        self.call_count += 1
        if self.call_count == 1:
            return BUGGY_REFUND
        fixed = Path(__file__).resolve().parents[1] / "demo-target" / "fixed_app.py"
        return fixed.read_text()


class LiveLLMAdapter(LLMAdapter):
    """Live mode: real OpenAI/Anthropic"""
    
    def __init__(self, api_key: str, provider: str = "openai"):
        self.api_key = api_key
        self.provider = provider
    
    def generate_code(self, prompt: str) -> str:
        """Call real LLM API"""
        if self.provider == "openai":
            return self._call_openai(prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt)
        return "# LLM provider not supported"
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[LLM] OpenAI error: {e}")
            return f"# Error: {e}"
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API"""
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-sonnet-20240229",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]
        except Exception as e:
            print(f"[LLM] Anthropic error: {e}")
            return f"# Error: {e}"


def create_adapters(repo_path: str | None = None) -> Dict[str, Any]:
    """Factory to create adapters based on env vars"""
    if repo_path is None:
        repo_path = str(Path(__file__).resolve().parents[2])
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO", "manvendersingh21/PR-slayer")
    jev_key = os.getenv("JEV_API_KEY") or os.getenv("TYPESAFE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    # Determine mode
    live_mode = bool(github_token)
    hybrid_mode = bool(jev_key and not github_token)
    
    # Create adapters
    if live_mode:
        github = LiveGitHubAdapter(github_token, github_repo)
        coderabbit = LiveCodeRabbitAdapter(github, github_repo, github_token)
    else:
        github = LocalGitHubAdapter(repo_path)
        coderabbit = CannedCodeRabbitAdapter()
    
    if jev_key:
        jev = LiveJevAdapter(jev_key)
    else:
        jev = StubJevAdapter()
    
    if openai_key:
        llm = LiveLLMAdapter(openai_key, "openai")
    elif anthropic_key:
        llm = LiveLLMAdapter(anthropic_key, "anthropic")
    else:
        llm = CannedLLMAdapter()
    
    mode = "live" if live_mode else ("hybrid" if hybrid_mode else "offline")
    
    return {
        "github": github,
        "coderabbit": coderabbit,
        "jev": jev,
        "llm": llm,
        "mode": mode
    }

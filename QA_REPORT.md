# AgentGate QA

Checked on September 26, 2026 against `main` (`6b0e154`) plus the fixes in this branch.

## What was run

- `python3 -m pytest -q` in `agentgate/`: **14 passed**.
- `python3 scripts/simple_demo.py` with no API keys: critical review, Jev FIX risk 9.9, clean review, Jev MERGE risk 2.7, `Result: MERGE  attempts=2`, exit 0. Repeated after the seed-app cleanup.
- Dashboard on port 8000: first `POST /api/start` returns success, the immediate second start returns `Demo already running`. `/api/state` then reaches `complete` with both rounds kept (critical count 1, then 0; actions fix 9.9 then merge 2.7; source `stub (from recorded Jev response)`).
- Browser: opened the dashboard, clicked Start, and saw 9.9, 2.7, FIX, MERGE, a blocking finding, Clean, the offline stand-in label, and the stub source on one page. Screenshot: `demo-artifacts/qa-dashboard.png`.

## Defects fixed

1. **Merge guardrail was only in the offline stub.** The orchestrator merged whenever Jev said merge. It now refuses a merge while tests fail or a critical/security finding is open, and sends the PR to fix or human review. Covered by two new orchestrator tests.
2. **Dashboard called a security-only review clean.** Blocking findings now include `security`, and a review with any finding is not labeled Clean.
3. **A failed Coding Agent run still rendered as a successful push.** The fixer row uses the event message and marks `success: false` as an error.
4. **The demo crashed if the `pytest` executable was not on `PATH`.** The loop runs `python3 -m pytest`.
5. **An exception in the dashboard thread left status `running` forever.** Failures set status `failed` and emit `loop_failed`, which re-enables Start.
6. **`REPO_PATH` defaulted to `/workspace`.** It now defaults to the repository root that contains `agentgate/`.
7. **`main` committed the buggy refund in `demo-target/app.py`.** A fresh checkout failed the refund tests before any demo. `app.py` again matches the clean seed. The builder still appends the bug during the demo.
8. **Default `pytest` from `agentgate/` collected the demo-target oracle tests and failed.** `pytest.ini` limits `make test` to `tests/`.
9. **README showed risk 9.2 and 1.1, and a placeholder author.** The script now says 9.9 and 2.7. Credits say JEVATHON.
10. **Pydantic `.dict()` deprecation on the seed API.** Seed and the clean app use `model_dump()`.
11. **Live Jev fallback text did not say `Jev unavailable`.** Network, parse, and unexpected errors now do, then fall back to the stub.

## Still not code defects

These block prizes and need accounts this session does not have. They are listed in `HACKATHON_GAPS.md`.

- No separate public `manvendersingh21/agentgate` repository. This GitHub credential cannot create repos.
- No CodeRabbit Coding Agent commit.
- No live Jev call. No `JEV_API_KEY` in the environment.
- No public post, Discord note, or HackerSquad submission.

Do not treat the offline stand-in commit as the Coding Agent.

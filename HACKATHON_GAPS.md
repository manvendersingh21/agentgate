# AgentGate handoff — what is still missing to win

Start here. This file is the task list for the next agent. Do not treat the offline demo as a finished hackathon entry.

Checked at 1:33 PM PT on Saturday, September 26, 2026. HackerSquad submission closes at **2:30 PM PT the same day** (9:30 PM UTC). If that time has passed, say so in the first reply and do the public-repo and Coding Agent work anyway; those are what judges and the cash prizes look at.

## How to win

Cash is only from CodeRabbit:

| Prize | Requirement | Status |
| --- | --- | --- |
| $1,000 | Best project **built with the CodeRabbit Coding Agent** | Not met. No Coding Agent commit exists. |
| $500 | Best public tool use. Must be posted publicly with the repo link. | Not met. No public post, and no standalone public repo. |
| $300 | Most Coding Agent feedback in the CodeRabbit Discord | Not met. Requires the human's Discord account. |

Main track 1st–3rd pays Cognition Devin credits and requires Jev. AgentGate's decision path is Jev. A live Jev call has not been made from this environment.

Pitch that must stay true: CodeRabbit is the evidence. Jev is the only thing allowed to merge. The agent only repairs what those two agree is broken. Offline, say out loud that the patch is a stand-in. Live, the repair must be a real `@coderabbitai autofix` commit.

## Work in this order

1. Confirm the clock against 2:30 PM PT.
2. Get a **separate public repo** `manvendersingh21/agentgate` (or the name the user chooses). This checkout is that project. It is not PR-slayer.
3. Put a real CodeRabbit review and a real Coding Agent commit on a non-draft PR in that repo.
4. Run one live Jev decision with `JEV_API_KEY` or `TYPESAFE_API_KEY` and keep the raw response.
5. Draft the HackerSquad submission and the public post. Publish only if the user explicitly asks this agent to post or submit.
6. Replace placeholder credits and any claim that the offline patch was the Coding Agent.

## P0 — separate repository (blocked here)

`gh repo create manvendersingh21/agentgate` failed with `GraphQL: Resource not accessible by integration (createRepository)`.

This cloud session is logged into GitHub as the Cursor GitHub App (`cursor`, a `ghs_` installation token). `gh api user` returns 403. That token can push branches to `manvendersingh21/PR-slayer`. It cannot create a new repository and it cannot edit CodeRabbit's review body.

The standalone tree is already on:

https://github.com/manvendersingh21/PR-slayer/tree/cursor/agentgate-standalone-5bf2

**Do not open a pull request from that branch into `main`.** The diff deletes the PR-slayer game and replaces the repository.

The user must create the repo from their own GitHub login:

```bash
git clone --branch cursor/agentgate-standalone-5bf2 --single-branch https://github.com/manvendersingh21/PR-slayer.git agentgate
cd agentgate
git branch -m cursor/agentgate-standalone-5bf2 main
gh repo create manvendersingh21/agentgate --public --source=. --remote=agentgate --push
```

If a user token is available in the new session, try the create again. Do not print the token. After the repo exists, set `GITHUB_REPO` to it. The code default is already `manvendersingh21/agentgate`.

## P0 — Coding Agent commit ($1,000)

This is the cash qualifier. A previous session posted `@coderabbitai autofix` on PR-slayer PR 2. CodeRabbit never replied and never pushed a second commit. The user then said to merge and that they did not care about that checkbox. Both PRs were merged. That waiver is not a substitute for the prize. Do the autofix on the **new** repo. Do not rewrite PR-slayer history.

What happened on https://github.com/manvendersingh21/PR-slayer/pull/2:

- CodeRabbit skips reviews while a PR is draft. Mark it ready, then comment `@coderabbitai review`.
- Review id `5327261359`, run id `b626f473-bdba-4db0-b23a-a6b2ed32f6be`, profile CHILL, plan Advanced.
- Findings: line 97 IDOR / CWE-639 (Minor Security label, treat as critical auth bypass), line 102 refund amount not compared to the payment, line 105 refund not persisted so a double refund is possible.
- Inline comments: `4112624419`, `4112624426`, `4112624429`.
- Checkbox id `4b0d0e0a-96d7-4f10-b296-3a18ea78f0b9` ("Fix CodeRabbit comments on this PR"). A PUT to check that box returned **403 Resource not accessible by integration**.
- Issue comment `5849498602` is `@coderabbitai autofix` from `cursor[bot]`. The bot ignored it. An inline reply was also ignored.

Live fixer code is `FixerAgent._fix_with_coding_agent` in `src/agents.py`. It posts `@coderabbitai autofix` and polls `list_commit_shas` for 180 seconds. That timeout is probably too short; a real run has taken several minutes. Only `LiveGitHubAdapter` has `list_commit_shas`. Offline correctly uses the local stand-in and labels it `offline-stand-in`.

To qualify:

1. Human redeems coupon `JEVHACK1000` at coderabbit.ai → Billing → Usage → Agent usage → Redeem Coupon. They must be the workspace billing admin. No card. Do not ask them to paste the key into chat.
2. Install the CodeRabbit GitHub App on the new repo.
3. Open a non-draft PR that only touches `demo-target/` and introduces the seeded refund bug (no ownership check, amount can exceed the payment, refund is not stored).
4. Wait for the real review. Then `@coderabbitai autofix`. If the bot still ignores the comment, the human has to click the "Fix CodeRabbit comments" checkbox in the review. The app token cannot click it.
5. The winning artifact is a commit authored by the Coding Agent on that PR. **Do not push a human or LLM patch and call it the Coding Agent.**

## P0 — public post ($500) and Discord ($300)

Draft only, unless the user explicitly tells this agent to publish.

Public post (X or LinkedIn) needs the new repo URL, one sentence of the pitch, and a true statement that CodeRabbit reviewed the refund bug and the Coding Agent pushed the fix. Do not claim the offline stand-in was the Coding Agent. Do not claim a live Jev score that was not returned by the API.

Discord feedback has to come from the user's CodeRabbit Discord account. Leave a short, specific note: draft PRs are skipped, `@coderabbitai autofix` from a GitHub App bot was ignored on PR 2, and the fix checkbox is not settable with an installation token (403).

## P0 — HackerSquad

Submit on hackersquad.io with `./project.sh` before 2:30 PM PT. This session has no HackerSquad credentials. Prepare the blurb from `PITCH.md` and stop if the CLI is not authenticated. Do not invent a submission id.

## P1 — live Jev (main track)

No `JEV_API_KEY` or `TYPESAFE_API_KEY` was present here. `scripts/jev_smoke.py` prints the parser test, then exits 1 when no key is set. Do not invent a live call.

Invite code `ci_o7VF3sQ5EDIHiNYU` at console.typesafe.ai.

Request: `POST {JEV_BASE_URL}/v1/systemone` with bearer `JEV_API_KEY` or `TYPESAFE_API_KEY`. Default base `https://api.typesafe.ai`. `https://thejevai.com` is also accepted. State is a JSON object `{pr, coderabbit_findings[], tests, attempt, previous_attempts[]}`, not a string. `criteria` is required for choice and score. Omitting it is HTTP 422. Response is top-level `{model, answers, usage}` with no `result` wrapper.

Recorded captures already in `scripts/jev_smoke.py` (these are the user's real responses, not a fresh call from this VM):

- Buggy PR, model `jev-1.13.0`: merge_safe noul 0.02, risk score 3.96 confidence 0.96, action `fix` confidence 0.93. Mapped risk **9.9**, confidence **93**, action fix.
- Fixed PR: noul 0.84, score 1.08 confidence 0.88, action `merge` confidence 0.94. Mapped risk **2.7**, confidence **94**, action merge.

Mapping: `score / (levels - 1) * 10`, one decimal. Confidence is the **action** confidence times 100, not the noul. Stub raw payload must keep `"source": "stub (from recorded Jev response)"`. On network or parse failure, live Jev falls back to the stub and must print `Jev unavailable`.

Guardrails are in the orchestrator: never merge while tests fail or a critical/security finding is open, even if Jev returns merge. Cap the loop at 3 attempts, then `human_review`.

## P1 — judge-facing product gaps

- `README.md` credits still say `Built for the [Hackathon Name] by [Your Name]`. Replace with JEVATHON and the user's name only if the repo or the user already states it. Do not invent a person from a git handle.
- Judges who will read the code: Hendrik Krack (CodeRabbit DevEx) and Sourabh Mane (CodeRabbit Design). The story in the README, pitch, and dashboard must match the code.
- `simple_demo.py` must keep driving the real orchestrator. If the file starts with "Simple hardcoded demo", it has regressed.
- `make demo` → http://localhost:8000 → Start must run that same loop and keep **both** rounds on screen (critical, then clean). The server resets state only when Start is pressed, and it refuses a second start while status is `running`.
- Offline builder: start from `demo-target/seed_app.py`, append the buggy refund, commit only `demo-target/app.py`. Offline fixer call 2+ writes `demo-target/fixed_app.py` (403 ownership, 400 amount, double-refund via `refunds_db`). Shared `CannedLLMAdapter.call_count` is required. First call is the bug.
- `.coderabbit.yaml` path filter is `demo-target/**` in this standalone tree. Do not put the `agentgate/` prefix back.
- Runtime repo path is this directory (`Path(__file__).parents[1]` from `scripts/` and `dashboard/`). Do not point it at `/workspace`.
- Do not add ElevenLabs, Photon, Browserbase, LlamaIndex, Whop, or GMI. Only Jev and CodeRabbit matter for the cash.

## Already verified (do not rebuild)

On this standalone tree, commit `b552d87` and its parent:

- `python3 -m pytest -q` → **12 passed**.
- `python3 scripts/simple_demo.py` from the repo root, no API keys:

```
CodeRabbit   🔴 1 Critical
Jev          FIX  risk 9.9 / 10  (stub (from recorded Jev response))
Fixer        Fixed 2 findings
CodeRabbit   🟢 Clean
Jev          MERGE  risk 2.7 / 10  (stub (from recorded Jev response))
Merge        ✅
Result: MERGE  attempts=2
```

- `main` of this standalone history does **not** contain the refund endpoint. The demo branch `agentgate/add-refund-endpoint` does, and it should not be pushed as the product default.
- Screenshots: `demo-artifacts/dashboard-fix.png` and `demo-artifacts/dashboard-merge.png`. An image caption once misread the scores as 1.1/98. Trust `/api/state`, which showed 9.9/93 then 2.7/94.
- Live CodeRabbit review on PR 2 is real and matches the seeded bug. Parser coverage is `tests/test_adapters.py::test_parse_real_pr2_coderabbit_comments`.
- PR-slayer PRs 2 and 3 are merged. `main` there is `09c8e46`. PR-slayer `agentgate/demo-target/app.py` on that main **includes the buggy refund** from PR 2. The standalone `app.py` was reset from `seed_app.py` so a fresh demo starts clean. Do not copy the buggy file back over the seed.

## Do not

- Print tokens, wifi passwords, or API keys.
- Claim a sample Jev body is live unless it is one of the two captures above.
- Fake a Coding Agent commit.
- Modify or delete PR-slayer game files (`index.html`, `scripts/`, root `README.md`, `vercel.json`, `.github/workflows/production_deploy.yml`).
- Commit the stale untracked `/workspace/agentgate-new/` tree.
- Reset `main` or the old feature branch to recover from a demo checkout. Demo runs `git checkout -B`. Return to the product branch afterward.

## Subagents in this repo

`.cursor/agents/` has specialists for publish, Coding Agent, Jev, demo verification, submission copy, and a judge read. The closer agent should read this file and run the list above.

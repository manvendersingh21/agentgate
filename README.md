# AgentGate

**AI agents can write code faster than humans can review it.**

AgentGate gives autonomous coding agents a safety control plane: agents build, CodeRabbit reviews, Jev decides, and agents repair themselves.

## The Pitch

Modern AI coding agents are fast but risky. They can generate entire features in seconds, but shipping bugs to production is expensive. AgentGate creates an autonomous safety loop:

1. **Builder Agent** writes code from an issue
2. **CodeRabbit** reviews for security, correctness, and quality
3. **Jev** (TypeSafe AI's decision API) decides if it's safe to merge
4. **Fixer Agent** repairs code if needed
5. Loop continues until Jev approves or max attempts reached

The result: **autonomous code generation with production-grade safety**.

## Quick Start

**Terminal Demo (Fastest for hackathon):**

```bash
cd agentgate
python3 scripts/simple_demo.py
```

Shows the complete safety loop with visual output in 10 seconds.

**Dashboard Demo (Interactive):**

```bash
cd agentgate
make demo
```

Open http://localhost:8000 and click "Start Demo"

Both demos run offline with no API keys needed.

## 2-Minute Demo Script

**Setup (30 seconds):**
1. Open dashboard: `cd agentgate && make demo`
2. Navigate to http://localhost:8000
3. Explain the pitch: "AI agents are fast but risky. AgentGate adds a safety control plane."

**Demo (90 seconds):**
1. Click "Start Demo"
2. **Builder phase**: "Our agent gets a feature request: add a refund endpoint"
   - Shows: Builder ✅ Complete
3. **First review**: "CodeRabbit catches a critical security bug"
   - Shows: 🔴 1 Critical Issue - Missing authorization check
4. **Jev decision**: "Jev analyzes and blocks the merge"
   - Shows: Risk 9.9/10, Decision: FIX
5. **Fixer repairs**: "The fixer agent patches the security hole"
   - Shows: ↓ Fixer Agent ✅ Fix applied
6. **Second review**: "CodeRabbit re-reviews and finds it clean"
   - Shows: 🟢 Clean
7. **Jev approves**: "Jev recalculates and approves"
   - Shows: Risk 2.7/10, Decision: MERGE
8. **Merge**: "PR merges safely"
   - Shows: ✅ PR MERGED

**Closing**: "This loop runs autonomously. Agents code at AI speed, but nothing ships until Jev approves."

## Modes

AgentGate adapts based on environment variables:

### Offline Mode (default)
No API keys needed. Runs the full loop with:
- Local git repo
- Canned CodeRabbit findings
- Deterministic Jev stub
- Canned buggy code that gets fixed

```bash
make demo
```

### Hybrid Mode
Real Jev decisions, everything else offline. Test Jev integration before going live.

```bash
export JEV_API_KEY=jv_live_your_key
make demo
```

### Live Mode
Real GitHub PRs, CodeRabbit reviews, Jev decisions, and LLM code generation.

```bash
# 1. Install CodeRabbit GitHub App on your repo
#    https://github.com/apps/coderabbitai

# 2. Set environment variables
export GITHUB_TOKEN=ghp_your_token
export GITHUB_REPO=owner/repo-name
export JEV_API_KEY=jv_live_your_key
export OPENAI_API_KEY=sk_your_key  # or ANTHROPIC_API_KEY

# 3. Run
make demo
```

## Setup for Live Mode

### 1. GitHub Token
Create a token with `repo` and `workflow` scopes:
https://github.com/settings/tokens/new

### 2. CodeRabbit Integration
Install the CodeRabbit app on your repository:
https://github.com/apps/coderabbitai

### 3. Jev API Key
Sign up at https://thejevai.com and get an API key.

Test your key:
```bash
export JEV_API_KEY=jv_live_your_key
make test-jev
```

Optional: Configure base URL (defaults to `https://api.typesafe.ai`):
```bash
export JEV_BASE_URL=https://thejevai.com  # Alternative endpoint
```

### 4. LLM API Key
Get a key from:
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/

### 5. Configure
```bash
cp .env.example .env
# Edit .env with your keys
source .env
make demo
```

## How It Works

### The Safety Loop

```
Issue → Builder Agent → PR Created
         ↓
      Tests Run
         ↓
   CodeRabbit Review
         ↓
    Jev Decision
         ↓
   ┌─────┴─────┐
   ↓           ↓
  FIX       MERGE
   ↓
Fixer Agent
   ↓
 Re-review → Jev → ...
```

### Components

**Demo Target** (`demo-target/`): A FastAPI backend with orders and payments. The builder implements a refund endpoint that intentionally has bugs (missing auth, wrong validation, etc). Tests catch these bugs after the fixer patches them.

**Adapters** (`src/adapters.py`): Each external service (GitHub, CodeRabbit, Jev, LLM) has an adapter interface with offline and live implementations. The factory chooses adapters based on env vars.

**Agents** (`src/agents.py`):
- **BuilderAgent**: Generates code from an issue prompt via LLM
- **FixerAgent**: Repairs code based on review findings

**Orchestrator** (`src/orchestrator.py`): Runs the loop. Build → Test → Review → Jev → Fix (if needed) → Repeat. Emits events for the dashboard.

**Dashboard** (`dashboard/`): Single-page app with live updates via Server-Sent Events. Shows the pipeline status, findings, Jev risk scores, and decisions in real-time.

### Jev Integration

Jev is TypeSafe AI's hosted decision API. AgentGate sends:
- PR diff
- CodeRabbit findings (severity, message, file, line)
- Test results
- Attempt count

Jev returns:
- `merge_safe`: yes/no (noul probability)
- `confidence`: 0-100%
- `risk`: 0-10 score
- `action`: merge / fix / human_review / reject

AgentGate adds deterministic guardrails:
- Critical findings → always FIX
- Tests failing → always FIX
- Max attempts reached → HUMAN_REVIEW

### CodeRabbit Integration

In live mode:
1. PR is created
2. CodeRabbit automatically reviews (GitHub App webhook)
3. AgentGate polls PR comments for `coderabbitai[bot]` reviews
4. Parses severity from comment text (critical, security, etc)
5. Normalizes into `Finding` objects

After fixes:
1. Fixer pushes new commit
2. AgentGate adds comment: `@coderabbitai review`
3. Polls for new review
4. Loop continues

## Project Structure

```
agentgate/
├── demo-target/           # Target API to modify
│   ├── app.py            # FastAPI orders backend
│   ├── test_app.py       # Tests (catch bugs after fixes)
│   └── requirements.txt
├── src/
│   ├── models.py         # Data models
│   ├── adapters.py       # Service adapters (offline/live)
│   ├── agents.py         # Builder and fixer agents
│   └── orchestrator.py   # Main loop coordinator
├── dashboard/
│   ├── server.py         # FastAPI server with SSE
│   └── index.html        # Dashboard UI
├── scripts/
│   └── jev_smoke.py      # Jev API key tester
├── tests/
│   └── test_*.py         # Test suite
├── Makefile              # Commands (demo, test, etc)
├── requirements.txt      # Python dependencies
├── .env.example          # Environment template
├── .coderabbit.yaml      # CodeRabbit config
└── README.md             # This file
```

## Testing

```bash
# Run test suite
make test

# Test Jev API key
make test-jev

# Run demo target tests
cd demo-target && pytest -v
```

## Development

```bash
# Install dependencies
make install

# Clean build artifacts
make clean

# See all commands
make help
```

## Customization

### Add your own demo target
Replace `demo-target/` with your own codebase. Update the builder and fixer prompts in `src/agents.py` to match your domain.

### Adjust Jev questions
Edit `LiveJevAdapter.decide()` in `src/adapters.py` to customize:
- State description
- Question types (noul, score, choice)
- Decision mapping

### Change max attempts
Edit `PRState.max_attempts` in `src/models.py` (default: 3).

## Troubleshooting

**Dashboard shows "Mode: OFFLINE" when keys are set**
- Dashboard shows mode from initial server state
- Restart the server after setting env vars

**CodeRabbit doesn't review in live mode**
- Verify CodeRabbit app is installed on the repo
- Check `.coderabbit.yaml` path filters include your target
- PRs may take 30-60 seconds for first review

**Jev returns human_review instead of fix/merge**
- Jev may require human review for edge cases
- Check `decision.raw_response` for Jev's reasoning
- Adjust prompts to give Jev more context

**Tests fail in offline mode**
- Expected! The buggy code fails tests until fixed
- After fixer runs, tests should pass
- Check orchestrator logs for test output

## License

MIT

## Credits

Built for JEVATHON.

- **Jev**: TypeSafe AI's decision API - https://thejevai.com
- **CodeRabbit**: AI code reviewer - https://coderabbit.ai
- **FastAPI**: Modern Python web framework - https://fastapi.tiangolo.com

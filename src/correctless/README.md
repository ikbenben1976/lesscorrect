# Correctless v4

Correctness-oriented development workflow. Spec before code. Test before impl. Nobody grades their own work.

## What changed from v3

v3 was 39,000 lines of bash enforcing workflow constraints through shell hooks, JSON state files, and pattern matching. It worked, but the guarantees were aspirational — "agent separation" was prompt framing, tool restrictions were a bash script racing to parse JSON from stdin.

v4 is **~800 lines of Python** doing the same workflow with real guarantees:

| | v3 (bash) | v4 (Python + Agent SDK) |
|---|---|---|
| State machine | 1,145 lines of bash | ~180 lines of typed Python |
| Tool restrictions | Bash hook parsing stdin JSON | API-level `allowed_tools` per agent |
| Agent isolation | Prompt framing ("you are a fresh agent") | Separate SDK sessions, fresh context |
| File gating | Regex pattern matching on filenames | Agents literally cannot call Write |
| Config | jq + eval on JSON files | Pydantic models |
| Portability | Bash 4+, jq, md5sum/md5, GNU stat | Python 3.11+ |
| Test gates | `eval "$test_cmd"` | `subprocess.run()` with timeout |

## Install

```bash
pip install -e .
```

Requires an Anthropic API key (`ANTHROPIC_API_KEY`) and optionally the Claude Agent SDK for full tool execution.

## Usage

```bash
# Initialize for your project (auto-detects language, test runner)
cl setup

# Start a feature
git checkout -b feature/user-registration
cl spec "user registration with email and password"

# Each command runs a separate agent with restricted tools:
cl review    # Read-only agent reviews spec cold
cl tdd       # RED→GREEN→QA with 3 separate agents
cl verify    # Read-only agent checks spec-to-code correspondence
cl docs      # Updates project documentation

# Utilities
cl status       # Show current phase and next step
cl status-all   # All active workflows across branches
cl reset        # Clear workflow state
cl spec-update "R-002 was ambiguous"  # Return to spec during TDD
```

## The Workflow

```
cl spec → cl review → cl tdd (RED → GREEN → QA) → cl verify → cl docs → done
             ↑                    ↑         |           |
             └── REVISE ──────────┘         |           |
                                  ← FIX ───┘           |
                                  ← ISSUES ─────────────┘
```

### Phase details

| Phase | Agent | Tools | What it does |
|-------|-------|-------|-------------|
| spec | Spec Agent (Sonnet) | read + web + write | Writes testable rules from feature description |
| review | Review Agent (Opus) | **read-only** | Finds gaps, contradictions, untestable rules |
| tdd-red | Test Agent (Sonnet) | read + write + bash | Writes failing tests from spec (no impl) |
| tdd-green | Impl Agent (Sonnet) | full toolset | Makes tests pass (simplest correct code) |
| tdd-qa | QA Agent (Opus) | **read-only** | Reviews spec+tests+impl with fresh eyes |
| verify | Verify Agent (Opus) | read + bash (tests) | Rule-by-rule coverage matrix |
| docs | Docs Agent (Sonnet) | read + write (docs) | Updates AGENT_CONTEXT, ARCHITECTURE |

**Key guarantee:** The QA agent cannot see the impl agent's reasoning. The review agent cannot see the spec author's conversation. Each agent gets a fresh context window with only the artifacts (spec file, test files, source files) — not the chat history that produced them.

## Project structure

```
correctless-v2/
├── pyproject.toml
└── src/correctless/
    ├── __init__.py
    ├── cli.py            # Click commands (cl spec, cl review, etc.)
    ├── workflow.py        # State machine + persistence (~180 lines)
    ├── agents.py          # Agent definitions with tool restrictions
    ├── orchestrator.py    # Runs agents, enforces gates, advances state
    └── config.py          # Project detection (language, test runner)
```

5 files. No sync script. No hook registration. No eval.

## Compared to v3

Things that are **gone**:
- `workflow-gate.sh` (555 lines) — tool restrictions are now API-level
- `workflow-advance.sh` (1,145 lines) — state machine is 180 lines of Python
- `lib.sh` (258 lines) — locking, write detection, file classification all unnecessary
- `sync.sh` — no file duplication
- `setup` (800+ lines) — replaced by `cl setup` (30 lines)
- All 6 hook scripts — no hooks needed when agents have real tool restrictions
- The entire `correctless/` distribution directory — no duplication
- `eval "$(jq ...)"` — no eval anywhere

Things that **carry over**:
- The workflow design (spec → review → TDD → verify → docs)
- Agent separation principle (nobody grades their own work)
- Spec format (rules, prohibitions, edge cases)
- Project context system (ARCHITECTURE.md, AGENT_CONTEXT.md, antipatterns.md)
- QA round counting and spec-update flow

Things that are **new**:
- Real tool isolation (API-level, not pattern matching)
- Fresh context per agent (separate sessions, not prompt framing)
- Typed state machine (Pydantic, not JSON + jq + eval)
- Test gates with timeout (subprocess, not eval)
- Portable (Python, not bash 4+ with GNU tools)

## Extending

### Adding a phase

1. Add the phase to `Phase` enum in `workflow.py`
2. Add transitions in `TRANSITIONS`
3. Define the agent in `agents.py`
4. Add the orchestration in `orchestrator.py`
5. Add the CLI command in `cli.py`

### Managed Agents (cloud isolation)

When Managed Agents multiagent goes GA, each phase agent can run in its
own cloud container. Replace `run_agent()` in `orchestrator.py` with
Managed Agents session creation — the agent definitions and workflow
stay identical.

```python
# Future: cloud-isolated agents
session = await client.sessions.create(
    agent=qa_agent_id,
    environment_id=sandbox_env_id,
)
```

## License

MIT

# Skill Creator -- Architecture Reference

This file provides deeper context for generating Correctless skills.
The skill-creator reads this when it needs detailed information about
the system architecture, agent definitions, or integration patterns.

## SKILL.md Frontmatter Field Reference

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| name | No | string | Lowercase kebab-case, max 64 chars. Defaults to directory name. |
| description | Recommended | string | What the skill does and when to invoke it. Max ~250 chars. |
| argument-hint | No | string | Autocomplete hint, e.g. `[issue-number]` |
| disable-model-invocation | No | bool | Prevent Claude auto-loading. Default: false. |
| user-invocable | No | bool | Show in `/` menu. Default: true. |
| allowed-tools | No | string/list | Tools pre-approved without user permission prompts. |
| model | No | string | Override model for this skill. |
| effort | No | enum | low, medium, high, max. |
| context | No | string | `fork` for isolated subagent execution. |
| agent | No | string | Subagent type: Explore, Plan, general-purpose, or custom. |
| paths | No | string/list | Glob patterns for auto-activation scope. |
| shell | No | string | bash (default) or powershell. |

## Agent Definitions by Category

### Core Agents (core.py -- 8 agents)
- **spec** -- Writes feature specifications with testable rules (R-xxx)
- **review** -- 2-agent adversarial review (assumptions + testability)
- **tdd_test** -- RED phase: writes failing tests from spec rules
- **test_auditor** -- Audits tests assuming impl will take path of least resistance
- **tdd_impl** -- GREEN phase: implements to pass tests (or delegates to Superpowers)
- **qa** -- Isolated QA: reviews spec+tests+impl with hostile lens
- **verify** -- Traces spec rules to tests and implementation (coverage matrix)
- **docs** -- Generates/updates documentation from implementation

### Analysis Agents (analysis.py -- 6 agents)
- **postmortem** -- Root cause analysis, antipattern extraction, CLAUDE.md learning
- **debug** -- Hypothesis-driven debugging with Sequential Thinking
- **devadv** -- Devil's advocate: challenges assumptions
- **wtf** -- Quick "what happened" investigation from audit trail
- **metrics** -- Generates effectiveness dashboards and reports
- **summary** -- Feature summary for PR descriptions

### Security Agents (security.py -- 5 agents)
- **review_spec** -- 5-agent isolated adversarial review (4 reviewers + synthesizer)
- **audit** -- 3 presets: QA (2 agents), Security (3 agents), Hacker (4 agents)
- **redteam** -- Active exploitation attempts against implementation
- **model** -- Alloy formal modeling (deferred, critical-only)

### Maintenance Agents (maintenance.py -- 5 agents)
- **refactor** -- Behavioral-equivalence refactoring with test gates
- **release** -- Version bumps, changelogs, tags, GitHub releases
- **update_arch** -- Architecture documentation refresh
- **quick** -- Lightweight single-pass review for small changes
- **maintain** -- Dependency updates, tech debt tracking

### Collaboration Agents (collaboration.py -- 4 agents)
- **pr_review** -- External PR review with context awareness
- **contribute** -- Learn target project conventions, create compliant PR
- **explain** -- Codebase exploration and explanation with diagrams
- **auto** -- Full pipeline orchestration with escalation/resumption

## TDD Phase Detail

```
RED (test agent)
  - Writes failing tests from spec rules
  - Can create STUB:TDD source stubs for compilation
  - Knowledge: reads spec, antipatterns
  - Produces: test files, optional stubs

TEST AUDIT (auditor agent) -- CORRECTLESS UNIQUE
  - Separate agent, did NOT write tests
  - Checks: mock gaps, weak assertions, untested edge cases
  - Motto: "Assume impl will take path of least resistance"
  - BLOCKING findings must be fixed before GREEN
  - Knowledge: reads spec, test files

GREEN (impl agent OR Superpowers)
  - If Superpowers: delegate to execute-plan with micro-tasks
  - If no Superpowers: standard correctless impl agent
  - Calm reset after N consecutive failures
  - /simplify runs here (treated as untrusted, post-validated)
  - Knowledge: reads spec, tests; writes implementation

QA (QA agent) -- ALWAYS correctless-owned
  - Separate agent, didn't write tests OR implement
  - Reviews spec + tests + implementation with hostile lens
  - Knowledge: reads all; writes qa-findings-{slug}.json
  - BLOCKING -> back to GREEN (fix round)
  - PASS -> advance to verify (high+) or done (standard)
```

## Intensity System Detail

### What intensity controls (NOT model selection):

| Parameter | Standard | High | Critical |
|-----------|----------|------|----------|
| Spec sections | 5 + typed rules | 12 + invariants | 12 + all templates |
| Research agent | If needed | Always (security) | Always |
| STRIDE analysis | No | Yes | Yes |
| QA round max | 2 | 3 | 5 (convergence) |
| Mutation testing | No | Required | Required |
| PBT recommendations | No | No | Yes |
| Calm reset threshold | 3 failures | 2 failures | 2 failures + notify |
| /cupdate-arch | Skipped | Runs | Runs |
| Adversarial review agents | 2 | 4 (full team) | 4 + self-assessment |

### Effective intensity computation:
```
effective = max(project_intensity, feature_intensity)
Ordering: standard < high < critical
```

## Plugin Integration Contract

Every plugin integration follows:

1. **Detect** -- Is the plugin installed?
2. **Gate** -- Does this phase benefit from delegation?
3. **Delegate** -- Invoke plugin with correctless-controlled inputs
4. **Verify** -- Validate plugin output before advancing state
5. **Degrade** -- Handle phase directly if plugin unavailable

No plugin is required. Every phase works without any plugin.

## Error Handling Patterns

### Atomic State Writes
All state writes: write temp file -> os.rename() to target.

### Checkpoint Resume
Long-running skills write checkpoint files:
```json
{
  "phase": "GREEN",
  "sub_step": "micro-task 3 of 7",
  "files_modified": ["src/auth.py", "src/middleware.py"],
  "test_results": {"passed": 12, "failed": 2},
  "timestamp": "2026-04-10T14:30:00Z"
}
```

### API Fallback Chain
```
Agent SDK (30s timeout, 120s for audit)
  -> retry once -> Managed Agents
  -> container failure -> v3 forked subagents
  -> v3 is terminal fallback (always available)
```

## Feedback Loop Pattern

```
Bug escapes -> /cpostmortem
  -> PMB-xxx in workflow-effectiveness.json
  -> AP-xxx in antipatterns.md (CLASS fix)
  -> Learning in CLAUDE.md (2-3 lines)
  -> AP frequency >= 3 -> promote to ARCHITECTURE.md PAT/ABS
Future /cspec reads antipatterns -> spec rules include guards_against: AP-xxx
Future /creview checks against antipatterns -> catches class before recurrence
```

## String Substitutions Available in Skills

| Variable | Description |
|----------|-------------|
| $ARGUMENTS | All arguments passed to the skill |
| $0, $1, $2... | Positional arguments (0-indexed) |
| ${CLAUDE_SESSION_ID} | Current session ID |
| ${CLAUDE_SKILL_DIR} | Directory containing this SKILL.md |

## Dynamic Context (Shell Preprocessing)

Inline: `!`command`` -- output replaces the command before Claude sees it
Multi-line:
````
```!
command1
command2
```
````

Commands execute immediately during preprocessing. Claude sees only results.

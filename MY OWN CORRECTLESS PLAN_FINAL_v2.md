# Correctless v4 — Rebuild Plan (Consolidated)

## Design Principles

1. **The workflow is the foundation.** Knowledge persistence is a lightweight side effect — structured files written after each phase, read by the phases that need them. Not a heavy store injected into every prompt.

2. **Correctless is the general contractor.** It owns the project plan, quality gates, knowledge accumulation, adversarial review, and inspection. Plugins like Superpowers and Frontend Design are subcontractors that handle specific execution work within phases correctless orchestrates.

3. **The state machine, knowledge layer, intensity gates, and adversarial isolation never get delegated.** These are correctless's unique value. Everything else is negotiable.

4. **The user controls the model, not the system.** Intensity controls skill activation, spec depth, QA round caps, and behavioral parameters — never model selection. The user configures their model in Claude Code.

5. **New APIs eliminate infrastructure, not product.** Managed Agents, Agent SDK, and Compaction replace bash hooks and shell scripts. The 27 skill prompts, knowledge persistence, feedback loops, and intensity system carry over.

6. **Every new API path has a v3-proven fallback.** Beta APIs (Managed Agents, Compaction, Advisor Tool, Skills API) are enhancements, not load-bearing walls. The v3 shell-based approach (forked subagents, prompt-based context management, SKILL.md files) remains a permanently maintained, permanently tested code path. The fallback chain is: Agent SDK → Managed Agents → v3-style forked subagents via Claude Code. Each layer is a first-class code path with its own tests.

7. **Correctless tests itself.** The orchestrator, state machine, knowledge layer, and plugin integrations have unit and integration tests. Correctless applies the same rigor to its own infrastructure that it enforces on user projects.

---

## Part 1: What New APIs Eliminate

| v3 Infrastructure | Lines | Replaced By | Notes |
|---|---|---|---|
| `workflow-gate.sh` | 554 | Agent SDK `allowed_tools` | Tool restrictions are API-level, not bash |
| `workflow-advance.sh` | 1,144 | `workflow.py` (~250 lines) | Typed state machine with Pydantic |
| `lib.sh` | 257 | Unnecessary | Locking, write detection, file classification gone |
| `sensitive-file-guard.sh` | 424 | Agent sandboxes | Managed Agents containers can't reach .env |
| `statusline.sh` | 280 | CLI status command | ~30 lines |
| `setup` | 1,072 | `config.py` (~200 lines) | Python detection replaces bash heredocs |
| `sync.sh` | 157 | Nothing to sync | No file duplication |
| `audit-trail.sh` | 216 | Python audit logger | Structured, not bash+eval |
| `auto-format.sh` | 154 | Not needed | Formatters run outside workflow |
| `token-tracking.sh` | 137 | Python token logger | Part of orchestrator |
| Hook registration in setup | ~200 | Not needed | No hooks to register |
| All `eval "$(jq ...)"` | Pervasive | Pydantic models | No eval anywhere |

**Total eliminated: ~4,595 lines of bash infrastructure**

---

## Part 2: Specific Tool & Plugin Integrations

### MCP Servers

#### Serena MCP (symbol-level code analysis)
v3 status: Referenced with graceful degradation. Underused.

| Correctless Skill | How Serena Enhances It |
|---|---|
| `/cverify` | `find_symbol` + `get_references` traces spec rules to implementation at symbol level. Real coverage matrix, not grep. |
| `/crefactor` | Reference tracking gives all call sites before refactoring. Behavioral equivalence checking on the symbol graph. |
| `/caudit` specialists | Concurrency Specialist uses `find_symbol("mutex")` → `get_references` → traces lock/unlock paths semantically. |
| `/cexplain` | `get_symbols_overview` per file for codebase exploration. |
| `/cdebug` | `find_symbol` + `get_references` for root cause tracing through call chains. |
| Cross-session memory | `write_memory` / `read_memory` for investigation results, architectural notes that survive across sessions. Complements file-based persistence. |

Degradation: If Serena unavailable, fall back to grep/glob. Notify user once at end.

#### Context7 MCP (live documentation lookup)
v3 status: Referenced with graceful degradation.

| Correctless Skill | How Context7 Enhances It |
|---|---|
| `/cspec` research phase | Current best practices for the project's exact library versions. "How should Supabase auth handle JWT refresh?" from live docs, not training data. |
| `/ctdd` RED phase | Current testing library APIs when writing tests for unfamiliar libraries. |
| `/cpr-review` | Verifies PR uses current library APIs, not deprecated patterns. |
| `/ccontribute` | Learns target project's library versions and current API patterns. |

Degradation: If Context7 unavailable, fall back to web search. Notify user once at end.

#### Sequential Thinking MCP (structured reasoning)
v3 status: Not used.

| Correctless Skill | How Sequential Thinking Enhances It |
|---|---|
| `/cdebug` | Hypothesis testing as auditable, revisable, branchable thought steps. Each hypothesis is a branch. Failed → revise, don't restart. |
| `/cdevadv` | Structured reasoning against assumptions. Each challenged assumption is a thought step with explicit revision when evidence changes. |
| `/cpostmortem` | "Which phase missed it" trace as sequential steps: spec coverage → review gap → QA blind spot → class fix identification. |

Degradation: If unavailable, skills work as before with prompt-based reasoning. Quality degrades gracefully.

#### GitHub MCP (native GitHub integration)
v3 status: Uses `gh` CLI via shell.

| Correctless Skill | How GitHub MCP Enhances It |
|---|---|
| `/cpr-review` | Reads PRs, diffs, comments, CI status natively through protocol. No shell parsing. |
| `/cauto` PR creation | Creates PR with structured metadata, labels, reviewers through protocol. |
| `/ccontribute` | Reads target project's existing PRs, issues, CI configs to learn conventions. |
| `/crelease` | Creates tags and releases through protocol. |

Degradation: If unavailable, fall back to `gh` CLI. If `gh` not installed, skip PR operations.

### Claude Code Plugins

#### Superpowers (structured workflow execution)
Official Anthropic marketplace. Does: brainstorming → planning → TDD → subagent dev → code review → finalize.

**Integration principle:** Correctless delegates execution, not judgment. Superpowers handles micro-task decomposition and implementation subagents. Correctless keeps knowledge awareness, adversarial review, test authoring, QA, and all quality gates.

**Integration risk:** Correctless depends on Superpowers' `execute-plan` accepting externally-authored test suites and spec constraints as inputs. If Superpowers changes its plan format or review behavior, the GREEN phase delegation breaks. Mitigation: pin to a known-working version where possible; the standard correctless impl agent is always the fallback, and integration tests verify the delegation contract on each correctless update.

| Correctless Phase | Superpowers Role | Correctless Retains |
|---|---|---|
| `/cspec` brainstorm | **Not delegated.** Correctless's brainstorm is knowledge-aware (antipatterns, drift debt, decisions). | Full ownership. |
| `/cspec` plan decomposition | After spec is written and reviewed, Superpowers' `write-plan` decomposes spec rules into 2-5 minute micro-tasks with exact file paths and commands. | Spec content. Plan is derived from correctless's spec. |
| `/creview` / `/creview-spec` | **Not delegated.** Superpowers does single-pass two-stage review. Correctless does 4 isolated hostile-lens adversarial agents. | Full ownership. |
| `/ctdd` RED (test writing) | **Not delegated.** Test agent needs spec rules, antipattern awareness, isolation from impl. | Full ownership. |
| `/ctdd` test audit | **Not delegated.** Correctless-specific phase. | Full ownership. |
| `/ctdd` GREEN (implementation) | **Delegated to Superpowers' `execute-plan`.** Micro-task subagents implement against the plan. Superpowers' two-stage review runs after each task as fast self-review. | Correctless wrote the tests. Correctless wrote the spec. Correctless will QA the result. Superpowers is the hands. |
| `/ctdd` QA | **Not delegated.** Isolated agent that didn't write tests or implement. | Full ownership. |
| `/cverify` | **Not delegated.** Requires Serena symbol tracing, knowledge persistence. | Full ownership. |
| `/caudit` Olympics | **Not delegated.** Multi-round convergence with parallel hostile specialists. | Full ownership. |
| `/cpostmortem` | **Not delegated.** Feeds knowledge layer. | Full ownership. |
| `/crefactor` | Superpowers' execute-plan can handle the mechanical refactoring steps. Correctless owns pre/post test verification and behavioral equivalence gate. | Test gate: tests must pass before AND after. Any test change requires human approval. |

**Detection logic:** Check if Superpowers is installed: `ls .claude/plugins/superpowers* 2>/dev/null` or check `claude plugin list` output. If not installed, correctless's standard implementation agent handles GREEN phase directly.

#### Frontend Design (production-grade UI)
Official Anthropic marketplace. Produces distinctive, non-generic-AI UI.

**Integration principle:** Frontend Design is a context enrichment, not a phase delegation. Correctless loads its design tokens and patterns when the feature involves UI work.

| Correctless Phase | Frontend Design Role |
|---|---|
| `/cspec` | When feature involves UI: load design tokens, component patterns, styling constraints BEFORE writing spec rules. Spec rules include UI-specific testable assertions (e.g., "R-004: Login form follows PAT-UI-001 spacing conventions"). |
| `/ctdd` GREEN | Implementation agents (or Superpowers' subagents) have frontend-design skill active. Produces intentional design instead of generic AI output. |
| `/cpr-review` | When PR touches frontend: load design patterns to check compliance. |
| `/caudit` QA preset | UI-focused specialists check design system compliance. |

**Detection logic:** Check if feature description mentions UI keywords (page, form, component, dashboard, view, layout, modal, etc.) AND frontend-design skill is available. If UI feature but no frontend-design skill: warn "UI feature detected but frontend-design skill not installed. Install for better design quality."

#### Other Plugins (future integration points)
The pattern is the same for any plugin: correctless delegates execution within a phase, never judgment or quality gates.

| Plugin | Potential Integration Point |
|---|---|
| Playwright | `/caudit` Hacker preset: automated browser-based security testing. `/ctdd` GREEN: e2e test execution. |
| commit-commands | `/cauto` commit step: structured commit messages with conventional format. |
| feature-dev | Not integrated — overlaps with correctless's core workflow. |

---

## Part 3: New API Enhancements

### Advisor Tool (beta: `advisor-tool-2026-03-01`)
Pairs fast executor (Sonnet) with high-intelligence advisor (Opus) mid-generation.

| Correctless Phase | How Advisor Enhances It |
|---|---|
| `/ctdd` GREEN | Sonnet writes code, Opus advises on architectural alignment and antipattern avoidance. Opus-quality judgment at Sonnet token rates. |
| `/ctdd` RED | Sonnet writes tests, Opus advises on test strategy and weakness detection. |
| `/cdebug` | Sonnet traces code, Opus advises which hypothesis to pursue. |

**Does NOT replace** multi-agent adversarial review. Advisor shares context with executor — opposite of isolation guarantee.

**Fallback:** If Advisor Tool unavailable, agent runs single-model as in v3. No behavioral change, just loses the fast-executor/strong-advisor split.

### Compaction API (beta: `compact-2026-01-12`)
Server-side context summarization for long-running conversations.

| Correctless Phase | How Compaction Enhances It |
|---|---|
| `/caudit` Olympics | 30-60+ minute multi-round audits. Compact between rounds. Eliminates 70%/85% context cliff. |
| `/cauto` pipeline | Compact between skills. Each skill starts with clean context. |
| `/ctdd` with parallel tracks | Compact after RED before GREEN. Impl agent doesn't drown in test-writing history. |

**Fallback:** If Compaction unavailable, use v3 approach: manual context truncation via prompt engineering (include only spec + test names + current phase context). Less precise but functional. Long audits may hit context limits and require manual checkpoint/resume.

### Managed Agents (beta: `managed-agents-2026-04-01`)
Cloud containers with tool restrictions, SSE streaming, session persistence.

| Correctless Phase | How Managed Agents Enhances It |
|---|---|
| `/creview-spec` 4-agent review | Each reviewer in separate cloud container. Red team agent literally can't access spec author's session. Real isolation, not forked context. |
| `/caudit` Olympics | 4-6 specialists in parallel cloud sessions. Real-time streaming: "Concurrency Specialist complete — 3 findings. 5 still running." |
| `/ctdd` agent separation | Test agent, impl agent, QA agent in separate sessions. Isolation is infrastructure, not prompt framing. |

**Fallback:** When Managed Agents unavailable (no API key, cost concerns, API instability), fall back to Claude Code forked subagents. Same prompts, weaker isolation guarantee. This is the v3 approach and is permanently maintained.

### Managed Agents Research Previews (request access)

| Feature | Correctless Application |
|---|---|
| **Outcomes** | `/cverify` success criteria: "every spec rule maps to test AND implementation." Agent iterates until coverage matrix is complete. `/caudit` convergence: "zero critical/high findings remain" as formal contract. |
| **Multiagent coordination** | Olympics orchestrator as first-class API pattern. Orchestrator agent creates and manages specialist sessions. |
| **Memory** | Could augment CLAUDE.md learnings for cross-session persistence. Watch for GA. |

### Skills API (beta: `skills-2025-10-02`)
Upload custom skills with versioning, shared organization-wide.

| Application | Benefit |
|---|---|
| Distribution | Each correctless skill uploaded via API. Update a spec prompt → push new version → all sessions pick it up. |
| Composition | `/cmetrics` can use Anthropic's xlsx skill to produce actual Excel dashboards. `/csummary` can use docx skill for formatted reports. |

**Fallback:** If Skills API unavailable, skills remain as local SKILL.md files loaded from the plugin directory, as in v3.

### ant CLI
YAML-based agent definition versioning with Claude Code integration.

| Application | Benefit |
|---|---|
| Agent definitions | 27 agent definitions as version-controlled YAML. `ant` pushes updates. |
| Configuration | Workflow config as YAML alongside agent definitions. |

**Fallback:** If `ant` CLI unavailable, agent definitions remain as Python dataclasses in the `agents/` module.

---

## Part 4: Architecture

```
correctless/
├── pyproject.toml
├── src/correctless/
│   ├── __init__.py
│   ├── cli.py                     # All Click commands (27 skills + knowledge + utilities)
│   │
│   ├── workflow.py                # State machine (Phase enum, transitions, WorkflowState)
│   ├── config.py                  # Project detection + ProjectConfig model
│   ├── intensity.py               # Intensity enum, gates, effective computation, calibration
│   │
│   ├── knowledge/                 # === LIGHTWEIGHT PERSISTENCE ===
│   │   ├── __init__.py            # KnowledgeStore (read/write files, selective context injection)
│   │   ├── findings.py            # Finding, FindingsLog (per-feature QA/review/verify)
│   │   ├── antipatterns.py        # Antipattern, Registry, promotion logic (AP→PAT/ABS at 3+)
│   │   ├── drift.py               # DriftItem, DriftDebtTracker
│   │   ├── decisions.py           # Decision (ADR), DecisionLog, staleness checks
│   │   ├── effectiveness.py       # PhaseMetrics, EffectivenessTracker, PMB entries
│   │   ├── audit_trail.py         # AuditEntry, AuditTrail (what agents actually did)
│   │   ├── tokens.py              # TokenUsage per agent/phase/feature
│   │   ├── summaries.py           # FeatureSummary
│   │   ├── escalation.py          # EscalationFile (cauto failure context + resumption)
│   │   └── learnings.py           # Learning entries + CLAUDE.md append (sparse, deduplicated)
│   │
│   ├── agents/                    # === AGENT DEFINITIONS (ported v3 prompts) ===
│   │   ├── __init__.py            # AgentDef, tool sets, plugin detection
│   │   ├── core.py                # spec, review, tdd_test, test_auditor, tdd_impl, qa, verify, docs
│   │   ├── analysis.py            # postmortem, debug, devadv, wtf, metrics, summary
│   │   ├── security.py            # review_spec (5 agents), audit (3 presets), redteam, model
│   │   ├── maintenance.py         # refactor, release, update_arch, quick
│   │   ├── collaboration.py       # pr_review, maintain, contribute, explain
│   │   └── help.py                # help
│   │
│   ├── orchestrator/              # === RUNS AGENTS, INTEGRATES PLUGINS ===
│   │   ├── __init__.py
│   │   ├── runner.py              # run_agent() — Agent SDK + Managed Agents + v3 forked subagents fallback chain
│   │   ├── core.py                # Core pipeline (spec→review→tdd→verify→docs)
│   │   ├── auto.py                # Full auto pipeline (escalation, resumption, PR)
│   │   ├── gates.py               # Test gates (must fail/pass), coverage gates, calm resets
│   │   ├── multi_agent.py         # review-spec (5-agent), audit (convergence, presets)
│   │   ├── feedback.py            # Post-phase knowledge updates, antipattern promotion
│   │   ├── plugins.py             # Plugin detection + delegation (Superpowers, Frontend Design)
│   │   └── recovery.py            # Error handling, state file repair, atomic writes, crash recovery
│   │
│   ├── logging/                   # === CORRECTLESS INTERNAL OBSERVABILITY ===
│   │   ├── __init__.py
│   │   ├── orchestrator_log.py    # Structured logging for orchestrator decisions, plugin delegations, fallback triggers
│   │   └── diagnostics.py         # State file integrity checks, dead state detection, debug dump
│   │
│   └── templates/                 # === STRUCTURED TEMPLATES ===
│       ├── invariants/            # 6 checklists (concurrency, config, data, network, resource, security)
│       ├── spec.py                # Spec templates (lite + full)
│       ├── preferences.py         # Default preferences
│       └── redaction.py           # Redaction rules for external output
│
├── tests/                         # === CORRECTLESS SELF-TESTS ===
│   ├── unit/
│   │   ├── test_workflow.py       # State machine transitions, illegal transition rejection
│   │   ├── test_intensity.py      # Gate computation, effective intensity, calibration
│   │   ├── test_knowledge/        # Pydantic model validation, file read/write, promotion logic
│   │   ├── test_gates.py          # Test gates (must-fail, must-pass, calm reset thresholds)
│   │   ├── test_recovery.py       # Corrupt state handling, atomic write verification, crash recovery
│   │   └── test_plugins.py        # Detection logic, delegation contracts, fallback triggers
│   ├── integration/
│   │   ├── test_fallback_chain.py # Agent SDK → Managed Agents → v3 forked subagents
│   │   ├── test_superpowers.py    # Superpowers delegation contract (execute-plan input/output)
│   │   ├── test_feedback_loop.py  # postmortem → antipattern → spec guards_against
│   │   └── test_pipeline.py       # Full spec→review→tdd→verify on sample project
│   └── conftest.py                # Shared fixtures, mock agent responses
```

---

## Part 5: Plugin Integration Detail

### Detection Module (`orchestrator/plugins.py`)

```python
@dataclass
class PluginAvailability:
    superpowers: bool          # Can we delegate GREEN execution?
    frontend_design: bool      # Can we enrich UI specs and implementation?
    playwright: bool           # Can we run browser-based e2e/security tests?
    context7: bool             # MCP: live docs?
    serena: bool               # MCP: symbol-level code analysis?
    sequential_thinking: bool  # MCP: structured reasoning?
    github_mcp: bool           # MCP: native GitHub operations?

def detect_plugins(repo_root: Path) -> PluginAvailability:
    """Check which plugins and MCPs are available in this session."""
    ...

def is_ui_feature(task: str, spec_content: str) -> bool:
    """Detect if this feature involves UI work."""
    ui_keywords = {"page", "form", "component", "dashboard", "view",
                   "layout", "modal", "dialog", "button", "sidebar", ...}
    ...
```

### Integration Contract

Every plugin integration follows the same pattern:

1. **Detect** — is the plugin installed?
2. **Gate** — does this phase benefit from delegation?
3. **Delegate** — invoke the plugin with correctless-controlled inputs
4. **Verify** — correctless validates the plugin's output before advancing state
5. **Degrade** — if plugin unavailable, correctless handles the phase directly

No plugin is required. Every phase works without any plugin. Plugins make specific phases better, never replace correctless's quality gates.

---

## Part 6: Corrected Intensity System

Intensity does NOT control model selection. The user picks the model.

### What intensity controls:

| Parameter | Standard | High | Critical |
|---|---|---|---|
| Spec sections | 5 + typed rules | 12 + invariants | 12 + all templates |
| Research agent | If needed | Always (security) | Always |
| STRIDE analysis | No | Yes | Yes |
| QA round max | 2 | 3 | 5 (convergence) |
| Mutation testing | No | Required | Required |
| PBT recommendations | No | No | Yes |
| Calm reset threshold | 3 failures | 2 failures | 2 failures + notify |
| `/cupdate-arch` | Skipped | Runs | Runs |
| Adversarial review agents | 2 (assumptions + testability) | 4 (full team) | 4 + self-assessment |

### Per-skill intensity gates (from actual v3 source):

| Minimum Intensity | Skills |
|---|---|
| None (always available) | cspec, creview, ctdd, cverify, cdocs, cstatus, chelp, csummary, cquick, cexplain |
| Standard | cpostmortem, cdevadv, cmetrics, cdebug, crelease, crefactor, cpr-review, cmaintain, ccontribute, cauto, cwtf |
| High | creview-spec, caudit, cupdate-arch |
| Critical | cmodel, credteam |

### Effective intensity computation:
`effective = max(project_intensity, feature_intensity)`

Ordering: `standard < high < critical`

Feature intensity set via `workflow-advance.sh set-intensity` during spec phase. Project intensity from `workflow.intensity` in config. If both absent, defaults to `standard`.

### Calibration modes:
- **Passive** (default): Show advisory during `/cspec` — "calibration data suggests high intensity for this type of feature"
- **Active**: Auto-raise recommendation based on historical data (≥3 avg QA rounds, ≥8 avg BLOCKING findings, ≥200K avg tokens → raise one level)
- **Hybrid**: Passive until 5+ calibration entries exist, then active

---

## Part 7: Corrected TDD Flow

The full TDD cycle has 4 agent phases, not 3:

```
RED (test agent)
  → writes failing tests from spec rules
  → can create STUB:TDD source stubs for compilation
  ↓
TEST AUDIT (auditor agent) ← CORRECTLESS UNIQUE, not in Superpowers
  → separate agent, did NOT write tests
  → "Assume the impl agent will take the path of least resistance"
  → checks: mock gaps, weak assertions, untested edge cases
  → BLOCKING findings must be fixed before GREEN
  ↓
GREEN (impl agent OR Superpowers execute-plan)
  → if Superpowers installed: delegate to execute-plan with micro-task subagents
    → Superpowers' two-stage review runs after each micro-task (fast self-review)
    → frontend-design skill active if UI feature
  → if no Superpowers: standard correctless impl agent
  → calm reset after N consecutive failures (3 standard, 2 high/critical)
  → /simplify runs here (treated as untrusted, post-validated)
  ↓
QA (QA agent) ← ALWAYS correctless-owned, never delegated
  → separate agent, didn't write tests OR implement
  → reviews spec + tests + implementation with hostile lens
  → findings recorded to qa-findings-{slug}.json
  → BLOCKING → back to GREEN (fix round)
  → PASS → advance to verify (high+) or done (standard)
```

### Parallel Tracks

For features with 5+ rules, analyze the dependency graph. Independent rule groups get parallel RED+GREEN agent pairs. Test audit and QA always run on the full integrated codebase.

**Concurrency constraints (must be enforced by the orchestrator):**
- Each parallel track gets its own working branch (e.g., `feature/foo-track-1`, `feature/foo-track-2`).
- Tracks cannot edit the same files. The orchestrator assigns file ownership based on the dependency graph before spawning tracks. If two rule groups touch the same file, they are not independent and must be serialized.
- Merge happens after all tracks complete RED+GREEN, before test audit. The orchestrator runs `git merge --no-ff` of each track branch into the feature branch, aborting the parallel strategy if merge conflicts arise (falls back to serial execution).
- Test audit and QA run on the merged result, not on individual tracks.
- If Managed Agents is available, each track runs in a separate container. If not, tracks run sequentially (parallel benefit is lost but correctness is preserved).

---

## Part 8: Knowledge Persistence (Lightweight)

Correctless writes structured files after each phase. Skills read what they need.

| Artifact | Format | Written By | Read By |
|---|---|---|---|
| `qa-findings-{slug}.json` | JSON | `/ctdd` QA phase | `/cmetrics`, `/csummary`, `/cpostmortem`, `/cwtf` |
| `verification/{slug}-verification.md` | Markdown | `/cverify` | `/cmetrics`, `/csummary`, `/cpostmortem` |
| `meta/workflow-effectiveness.json` | JSON | `/cpostmortem` | `/cspec`, `/cmetrics` |
| `antipatterns.md` | Markdown (AP-xxx) | `/cpostmortem`, `/cdebug` | `/cspec`, `/creview`, `/caudit` |
| `meta/drift-debt.json` | JSON | `/cverify` | `/cspec`, `/cdevadv` |
| `decisions/*.md` | Markdown (ADR) | Various | `/cspec`, `/cmetrics` (staleness) |
| `artifacts/token-log-{slug}.jsonl` | JSONL | All skills | `/cmetrics` |
| `artifacts/audit-trail-{slug}.jsonl` | JSONL | Orchestrator | `/cwtf`, `/cmetrics` |
| `artifacts/summary-{slug}.md` | Markdown | `/csummary` | PR descriptions |
| `artifacts/escalation-{slug}.md` | YAML frontmatter + MD | `/cauto` | `/cauto` (resume) |
| `artifacts/debug-investigation-{slug}.md` | Markdown | `/cdebug` | `/cpostmortem` |
| `artifacts/checkpoint-{skill}-{slug}.json` | JSON | Long-running skills | Same skill (resume) |

### CLAUDE.md vs. Structured Persistence

There are two distinct persistence layers, and the boundary between them is strict:

**CLAUDE.md** is for cross-session behavioral priming — short natural-language learnings that change how Claude Code agents think in future sessions. It is loaded automatically into every Claude Code session. Rules:
- ONLY `/cpostmortem` writes to it.
- One learning entry per postmortem (2-3 lines max).
- Content is behavioral: "auth features in this project need middleware ordering checks" — not data.
- Deduplicated by PMB-N ID.
- Never contains structured data, JSON references, file paths, or metrics.

**Structured JSON/JSONL/Markdown files** are for data that skills query programmatically. Antipattern registries, findings logs, effectiveness metrics, drift debt, token usage — all live here. Skills read these files directly; they are never injected into CLAUDE.md.

The test: if a human reading CLAUDE.md would find the entry useful as a reminder, it belongs in CLAUDE.md. If a Python function needs to parse it, it belongs in a structured file.

### Feedback loops (implemented as Python functions in `orchestrator/feedback.py`):

```
Bug escapes production
  → /cpostmortem
    → creates PMB-xxx entry in workflow-effectiveness.json
    → creates or updates AP-xxx in antipatterns.md (CLASS fix, not instance fix)
    → appends learning to CLAUDE.md (sparse: 2-3 lines per postmortem)
    → checks AP-xxx frequency ≥ 3 features → proposes promotion to ARCHITECTURE.md PAT/ABS entry
  → Future /cspec reads antipatterns.md
    → spec rules include guards_against: AP-xxx
  → Future /creview checks spec against antipatterns
    → catches the class before it recurs
```

---

## Part 9: Error Handling and Recovery

### State File Integrity

All state file writes use atomic operations: write to a temp file, then `os.rename()` to the target path. This prevents corruption from interrupted writes (killed process, disk full, etc.).

On startup, `recovery.py` runs integrity checks:
- State file exists and parses as valid JSON/Pydantic model.
- Current phase is a valid Phase enum value.
- Feature slug matches the current branch.
- Checkpoint files (if any) reference the current feature.

If integrity checks fail, correctless logs the corruption details and offers: (a) reset to last known good state (from git history of the state file), or (b) full reset to spec phase.

### Mid-Phase Crash Recovery

Each long-running phase writes checkpoint files (`artifacts/checkpoint-{skill}-{slug}.json`) at meaningful intervals (e.g., after each test in RED, after each micro-task in GREEN). On resume, the skill checks for a checkpoint and offers to continue from where it left off.

Checkpoint files include:
- Phase and sub-step (e.g., "GREEN, micro-task 3 of 7")
- Files modified so far
- Test results at last checkpoint
- Timestamp

### API Failure Handling

The fallback chain in `runner.py` handles API failures at each layer:

```
Agent SDK call
  → timeout (30s default, 120s for audit) → retry once → fall through to Managed Agents
  → auth error → log, skip to v3 forked subagents
  → rate limit → exponential backoff (3 attempts) → fall through

Managed Agents call
  → container startup failure → log, fall through to v3 forked subagents
  → SSE stream interrupted → if checkpoint exists, resume; else restart phase
  → API unavailable → log, fall through to v3 forked subagents

v3 forked subagents (terminal fallback)
  → this is Claude Code's native subagent mechanism, always available
  → if this fails, the problem is Claude Code itself, not correctless
```

Every fallback trigger is logged to `orchestrator_log.py` with the layer that failed, the error, and what it fell back to.

### Partial Agent Responses

If an agent returns a partial response (truncated, malformed JSON in findings, etc.):
- Knowledge layer writes are skipped for that phase (don't write corrupt data).
- The phase is marked as "incomplete" in the state file.
- User is notified with the partial output and asked whether to retry or advance manually.

---

## Part 10: Correctless Internal Observability

### Orchestrator Logging (`logging/orchestrator_log.py`)

Structured log written to `.correctless/logs/orchestrator-{date}.jsonl`. Separate from the user-facing audit trail.

Each entry includes:
- Timestamp
- Phase and skill
- Action (e.g., "plugin_detection", "fallback_triggered", "gate_check", "state_transition")
- Details (plugin name, API layer, error message, etc.)
- Duration (for agent calls)

### Diagnostics (`logging/diagnostics.py`)

Available via `correctless diagnostics` CLI command:
- State file integrity check (as in recovery)
- Dead state detection (state file references a branch that no longer exists)
- Plugin availability snapshot
- Last 10 orchestrator log entries
- Fallback frequency (how often each API layer is actually used vs. falling back)

---

## Part 11: Build Order

### Phase 1: Foundation
- `workflow.py` — state machine with all v3 transitions
- `config.py` — project detection (language, test runner, monorepo)
- `intensity.py` — intensity enum, effective computation, per-skill gates, calibration
- **Unit tests:** `test_workflow.py` (all legal transitions, all illegal transition rejections), `test_intensity.py` (gate computation, effective intensity)

### Phase 2: Knowledge Layer
Simple file read/write. Pydantic models for structure. No heavy injection.
1. `findings.py` → 2. `antipatterns.py` (with promotion logic) → 3. `drift.py` → 4. `decisions.py` → 5. `effectiveness.py` (with PMB model) → 6. `audit_trail.py` → 7. `tokens.py` → 8. `summaries.py` → 9. `escalation.py` → 10. `learnings.py` (CLAUDE.md append) → 11. `__init__.py` (KnowledgeStore with selective context)
- **Unit tests:** `test_knowledge/` — model validation, file round-trip, promotion threshold, CLAUDE.md append idempotency

### Phase 3: Agent Definitions
Port all 27 v3 SKILL.md prompts. No hardcoded models. Each agent def includes:
- System prompt (from v3, nearly verbatim)
- `allowed_tools` list (replaces YAML frontmatter)
- Intensity-aware behavior flags
- MCP requirements (which MCPs enhance this agent)
- Plugin delegation points (which plugins can handle execution)

Build order: `core.py` (8 agents) → `analysis.py` (6) → `security.py` (5) → `maintenance.py` (5) → `collaboration.py` (4) → `help.py` (1)

### Phase 4: Orchestrator + Error Handling + Logging
1. `recovery.py` — atomic writes, state integrity checks, checkpoint resume
2. `logging/orchestrator_log.py` — structured orchestrator logging
3. `logging/diagnostics.py` — CLI diagnostics command
4. `runner.py` — Agent SDK → Managed Agents → v3 forked subagents fallback chain
5. `plugins.py` — Plugin detection, delegation logic, verification
6. `gates.py` — Test gates, coverage, calm resets, failure tracking
7. `feedback.py` — Post-phase knowledge updates, antipattern promotion
8. `core.py` — Core pipeline with plugin integration points
9. `multi_agent.py` — review-spec (5 agents), audit (3 presets, convergence), parallel track orchestration
10. `auto.py` — Full auto with escalation, resumption, PR
- **Unit tests:** `test_gates.py`, `test_recovery.py`, `test_plugins.py`
- **Integration tests:** `test_fallback_chain.py`, `test_superpowers.py`

### Phase 5: CLI + Templates
1. CLI commands for all 27 skills + `knowledge` subcommands + `status` + `reset` + `diagnostics`
2. 6 invariant templates (concurrency, config, data, network, resource, security)
3. Spec templates (lite + full)
4. Preferences model
5. Redaction rules

### Phase 6: Integration Testing
- Full pipeline end-to-end on sample project
- Knowledge accumulation across multiple features
- Feedback loop (postmortem → antipattern → spec)
- Intensity gates
- Plugin delegation + fallback when plugins unavailable
- Fallback chain exercise (force each API layer to fail, verify graceful degradation)
- Escalation and resumption
- Crash recovery (kill mid-phase, verify checkpoint resume)
- State corruption scenarios (truncated JSON, invalid phase, wrong branch)

---

## Part 12: What to Defer

| Feature | Reason |
|---|---|
| Alloy formal modeling (`/cmodel`) | Niche, requires external tooling, critical-only |
| External model cross-checking | Requires Codex/Gemini CLIs |
| Git trailers/notes | Minor workflow integration |
| Compliance checks | Enterprise-specific |
| Managed Agents Outcomes | Research preview, not GA |
| Managed Agents Multiagent | Research preview, not GA |
| Managed Agents Memory | Research preview, not GA |
| True parallel track execution | Requires Managed Agents for real parallelism; serialize until then (see Part 7) |

---

## Part 13: Estimated Scope

| Component | Files | Est. Lines | v3 Equivalent |
|---|---|---|---|
| Foundation (workflow, config, intensity) | 3 | ~500 | ~2,500 lines bash |
| Knowledge layer | 12 | ~1,200 | Scattered across skills + hooks |
| Agent definitions | 7 | ~2,500 | ~5,000 lines SKILL.md |
| Orchestrator (with plugins, recovery, logging) | 10 | ~2,800 | cauto + core skills + hooks |
| CLI | 1 | ~600 | setup + status + help |
| Templates | 4 | ~400 | templates/ directory |
| Tests | ~12 | ~1,500 | (no v3 equivalent) |
| **Total** | **~49** | **~9,500** | **~39,000 lines** |

The infrastructure reduction is real: ~4,600 lines of bash infrastructure becomes ~3,300 lines of typed Python (foundation + orchestrator). Agent prompt definitions compress from ~5,000 lines of SKILL.md to ~2,500 lines of Python (format change, not content loss). The remaining difference is v3 duplication across the lite/full split and setup/hook scaffolding that disappears entirely.

The addition of ~1,500 lines of tests and ~800 lines of error handling and logging (not present in v3) accounts for the gap between the raw reduction and the final line count. This is net-new quality infrastructure that v3 lacked.

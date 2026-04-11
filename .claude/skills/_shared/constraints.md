# Shared Constraints — All Correctless Skills

These constraints apply to every Correctless skill. Read before executing.

## Workflow State

- Check `.correctless/artifacts/workflow-state-*.json` for the current phase
- Never skip phases — follow the state machine: SPEC → REVIEW → TDD (RED → TEST_AUDIT → GREEN → QA) → VERIFY → DOCS → DONE
- If no workflow is active, tell the user to run `/cspec` first

## Knowledge Injection

Before executing, read these if they exist:
1. `.correctless/AGENT_CONTEXT.md` — project summary for agents
2. `.correctless/ARCHITECTURE.md` — patterns and conventions
3. `.correctless/antipatterns.md` — known bug patterns to watch for
4. `.correctless/knowledge/findings.json` — historical findings
5. `.correctless/knowledge/antipatterns.json` — structured antipattern data

## Agent Separation (The Lens Principle)

- **Never let an agent grade its own work**
- Spec author != reviewer != test author != implementer != QA
- When a skill uses `context: fork`, each forked agent gets a fresh context
- Read-only agents (review, QA, verify) CANNOT write files

## Intensity Awareness

- Read project intensity from `.correctless/config/workflow-config.json`
- Detect feature intensity from spec content and affected file paths
- Effective intensity = max(project, feature)
- Scale behavior according to the intensity table in each skill

## MCP Integration

| MCP | When Available | Fallback |
|-----|---------------|----------|
| Serena | Use for symbol-level tracing, reference finding | grep/glob |
| Context7 | Use for live documentation lookup | Web search or skip |
| Sequential Thinking | Use for structured hypothesis testing | Prompt-based reasoning |

Always degrade gracefully — no skill should fail because an MCP is unavailable.

## Progress Visibility

- Show a task list at the start of execution
- Update between phases with status
- Report findings with severity and count

## Token Tracking

After execution, log to `.correctless/artifacts/token-log-{slug}.jsonl`:
```json
{"skill": "<name>", "phase": "<phase>", "tokens_in": N, "tokens_out": N, "model": "<model>", "timestamp": "<ISO8601>"}
```

## Hard Constraints

- NEVER commit directly to main/master
- NEVER modify test files during GREEN phase (log if detected)
- NEVER suppress or hide findings — all findings are recorded
- NEVER skip QA — even for "simple" changes
- ALWAYS preserve the spec file as the source of truth

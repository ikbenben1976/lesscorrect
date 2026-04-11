---
name: cquick
description: >
  Lightweight single-pass review for small changes that don't need full workflow.
  Runs a combined spec-review-test check without creating workflow state. Use for
  bug fixes, typo fixes, config changes, or changes under ~50 lines.
argument-hint: "<description of what changed>"
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash Read Glob Grep
effort: low
---

# Quick Review

Lightweight single-pass review for small changes. Skips the full workflow
state machine — no SPEC/REVIEW/TDD phases. Use for changes that are too
small to justify the full ceremony.

> **Shared constraints apply.** Before executing, read `_shared/constraints.md` from the parent of this skill's base directory.

## Context Injection

Read these files:
1. `.correctless/AGENT_CONTEXT.md` — project context
2. `.correctless/ARCHITECTURE.md` — patterns and conventions
3. `.correctless/antipatterns.md` — known bug patterns

## Execution Steps

1. **Assess scope**: Check `git diff --stat` to confirm the change is small (< ~50 lines changed, < ~5 files). If larger, recommend the full workflow (`/cspec`).
2. **Read the diff**: `git diff` (or `git diff --cached` for staged changes).
3. **Quick review checklist**:
   - Does the change introduce any antipattern matches?
   - Are there obvious edge cases not handled?
   - Does it follow project conventions from ARCHITECTURE.md?
   - Are there test files that should be updated?
   - Any security concerns (input validation, auth checks)?
4. **Run tests**: Execute the project test command to verify nothing is broken.
5. **Report**: Provide a brief verdict:
   - **OK**: Change looks good. Safe to commit.
   - **CONCERN**: Found issues. List them with suggested fixes.
   - **TOO LARGE**: Change exceeds quick-review scope. Recommend `/cspec`.

## Integration Points

### MCP Enhancements
- None needed for quick reviews.

### Plugin Delegation
- None — quick review is always done by Correctless.

### Knowledge Persistence
- **Reads**: AGENT_CONTEXT.md, ARCHITECTURE.md, antipatterns.md
- **Writes**: token-log-{slug}.jsonl only (no workflow state, no findings)

## Quality Gates

- Tests must pass
- Change must be under scope threshold

## Intensity Behavior

Quick review always runs at standard intensity. If the change touches
security-sensitive paths, recommend upgrading to the full workflow.

## Error Handling

- If no test command configured, warn and skip test step
- If no git diff available, ask user what changed

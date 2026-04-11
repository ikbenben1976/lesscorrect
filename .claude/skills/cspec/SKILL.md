---
name: cspec
description: >
  Write structured feature specifications with testable rules before any code.
  Use when starting a new feature, defining requirements, or revising a spec
  during TDD. Reads antipatterns and historical findings to avoid past mistakes.
argument-hint: "<feature description>"
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash(git *) Read Write Edit Glob Grep WebSearch WebFetch Agent
effort: high
---

# Specification Author

Write a structured, testable specification for a feature BEFORE any code is written.
Every rule in the spec must be verifiable by a test.

> **Shared constraints apply.** Before executing, read `_shared/constraints.md` from the parent of this skill's base directory.

## Context Injection

Read these files before starting:
1. `.correctless/AGENT_CONTEXT.md` — understand the project
2. `.correctless/ARCHITECTURE.md` — know the patterns and conventions
3. `.correctless/antipatterns.md` — avoid repeating past bugs
4. `.correctless/knowledge/antipatterns.json` — structured antipattern data
5. `.correctless/knowledge/drift-debt.json` — spec-to-code drift history
6. `.correctless/config/workflow-config.json` — project settings and intensity

Also read recent findings if they exist:
- `.correctless/knowledge/findings.json` — what past reviews/QA caught

## Execution Steps

1. **Initialize workflow**: Create workflow state for current branch if not active. Refuse if on main/master.
2. **Detect intensity**: Analyze the feature description against the 4-signal detection system (file paths, keywords, trust boundaries, historical density). Report detected vs. project intensity.
3. **Research phase** (if intensity >= HIGH): Search the codebase for related patterns, existing implementations, and test coverage in the affected area.
4. **Gather requirements**: Ask the user what they're building and what "correct" means. Batch questions (max 2 rounds of clarification).
5. **Challenge assumptions**: Ask what would make this feature harmful if wrong. Identify trust boundaries and failure modes.
6. **Write the spec** to `.correctless/specs/{slug}.md` with these sections:

### Spec Format

```markdown
# Spec: {feature name}

## Context
What and why (2-3 sentences). Reference any antipatterns this guards against.

## Rules
Numbered, testable assertions:
- R-001: Given X, when Y, then Z
- R-002: Given A, when B, then C
(each rule must be verifiable by a test)

## Prohibitions
What must never happen:
- P-001: The system must never expose {sensitive data} in {context}
- P-002: ...

## Edge Cases
Explicitly called out edge cases with expected behavior.

## Failure Modes
What happens when dependencies fail (DB down, network timeout, etc.)

## Security Considerations (if intensity >= HIGH)
STRIDE analysis of the feature's attack surface.

## Dependencies
New dependencies required with justification.

## Open Questions
Anything unresolved — these MUST be resolved before review.
```

7. **Validate completeness**: Check that the spec has all sections required by the current intensity level.
8. **Advance workflow**: Move state to REVIEW phase.
9. **Report**: Tell the user to run `/creview` for skeptical review.

## Integration Points

### MCP Enhancements
- **Context7**: Look up library documentation when the feature involves external dependencies. Fallback: skip or use web search.
- **Serena**: Trace existing code patterns relevant to the feature. Fallback: use grep/glob.

### Plugin Delegation
- None — spec writing is never delegated. Correctless retains full ownership.

### Knowledge Persistence
- **Reads**: antipatterns.json, drift-debt.json, findings.json, effectiveness.json, workflow-config.json
- **Writes**: `specs/{slug}.md` (the spec), workflow state (phase advance), `token-log-{slug}.jsonl`

## Quality Gates

- Every rule (R-xxx) must be testable — if you can't describe a test for it, rewrite it
- All sections required by the intensity level must be present
- Open questions section must exist (even if empty)
- guards_against field references antipattern IDs where applicable

## Intensity Behavior

| Parameter | Standard | High | Critical |
|-----------|----------|------|----------|
| Required sections | Context, Rules, Edge cases | + Prohibitions, Failure modes, Dependencies | + Security model, Rollback plan |
| Research agents | No | Yes (codebase search) | Yes (codebase + external) |
| Clarification rounds | 1 | 2 | 2 |
| STRIDE analysis | No | Yes | Yes (detailed) |
| Antipattern cross-ref | Passive (read) | Active (must reference) | Active + new detection |

## Error Handling

- If workflow state is corrupt, offer to reset with `/creset`
- If spec file already exists, offer to revise (preserving history) or start fresh
- If on main/master branch, refuse and instruct user to create a feature branch
- Checkpoint: save partial spec if interrupted (user can resume with `/cspec`)

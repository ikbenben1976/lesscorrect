---
name: creview
description: >
  Skeptical review of a spec by a fresh agent that didn't write it. Finds
  untestable rules, missing edge cases, contradictions, and antipattern matches.
  Read-only — cannot modify the spec, only report findings.
argument-hint: "[optional: specific concerns to focus on]"
disable-model-invocation: false
user-invocable: true
allowed-tools: Read Glob Grep
context: fork
effort: high
---

# Skeptical Spec Review

Review a specification with fresh eyes. You did NOT write this spec — you are reading
it cold, looking for what's WRONG.

> **Shared constraints apply.** Before executing, read `_shared/constraints.md` from the parent of this skill's base directory.

## Context Injection

Read these files:
1. The spec file from workflow state (`spec_file` field)
2. `.correctless/AGENT_CONTEXT.md` — project context
3. `.correctless/ARCHITECTURE.md` — patterns and conventions
4. `.correctless/antipatterns.md` — known bug patterns
5. `.correctless/knowledge/antipatterns.json` — structured antipatterns
6. `.correctless/knowledge/findings.json` — what past reviews found

## Execution Steps

1. **Load workflow state**: Confirm we're in REVIEW phase. If not, explain what phase we're in and what command to run.
2. **Read the spec**: Load the spec file completely.
3. **Read project context**: Load AGENT_CONTEXT.md and ARCHITECTURE.md.
4. **Read antipatterns**: Load both antipatterns.md and the JSON registry.
5. **Detect intensity**: Determine effective intensity from project config and spec content.
6. **Review the spec** — look for these specific problems:

### Review Checklist

- **Untestable rules**: Rules that can't be verified by a test. "The system should be fast" is untestable. "Response time < 200ms for p95" is testable.
- **Missing edge cases**: Empty input, concurrent access, Unicode, max length, zero, negative, null
- **Unstated assumptions**: What does the spec take for granted about the environment, data, or dependencies?
- **Contradictions**: Do any rules conflict with each other?
- **Missing failure modes**: What happens when the database is down? Network fails? Disk full?
- **Antipattern matches**: Does this spec repeat a known bug pattern from antipatterns.md?
- **Prohibition gaps**: Are there obvious "must never" cases not covered?
- **Dependency risks**: Are new dependencies justified? Are versions pinned?

7. **At intensity >= HIGH**, also perform:
   - Second-pass review from a different perspective (security, performance, or operations)
   - STRIDE analysis of the spec's security surface
8. **At CRITICAL intensity**, spawn additional adversarial review agents (up to 3 total)

9. **Format findings**:

For each finding:
- **Severity**: BLOCKING (must fix before TDD) or SUGGESTION (should fix)
- **Rule**: Which rule is affected (R-xxx) or "MISSING" for gaps
- **Category**: testability | edge-case | assumption | contradiction | failure-mode | antipattern | security
- **Finding**: What's wrong (be specific)
- **Proposed fix**: How to fix the SPEC (not code)

10. **Render verdict**:
    - **APPROVE**: No blocking findings. Suggestions noted. Advance to TDD_RED.
    - **REVISE**: Has blocking findings. Return to SPEC phase for fixes.

11. **Record findings**: Write all findings to `.correctless/knowledge/findings.json`
12. **Advance workflow**: Move state based on verdict.

## Integration Points

### MCP Enhancements
- **Serena**: Trace code references mentioned in the spec to verify they exist. Fallback: grep/glob.
- **Sequential Thinking**: Structure the review as hypothesis testing when analyzing complex specs. Fallback: prompt-based reasoning.

### Plugin Delegation
- None — review is NEVER delegated. The Lens Principle requires independent judgment.

### Knowledge Persistence
- **Reads**: spec file, antipatterns.json, findings.json, AGENT_CONTEXT.md, ARCHITECTURE.md
- **Writes**: findings.json (new review findings), workflow state, token-log-{slug}.jsonl

## Quality Gates

- At least 2 findings even for good specs (if you can't find issues, look harder)
- Every BLOCKING finding must have a specific proposed fix
- Every finding must reference a specific rule (R-xxx) or "MISSING"
- Verdict must be clear: APPROVE or REVISE

## Intensity Behavior

| Parameter | Standard | High | Critical |
|-----------|----------|------|----------|
| Review passes | 1 | 2 (different perspectives) | 3 (adversarial agents) |
| STRIDE analysis | No | Yes | Yes (detailed, per-component) |
| Antipattern matching | Passive | Active (must check each AP-xxx) | Active + propose new APs |
| Min findings | 2 | 3 | 5 |

## Error Handling

- If spec file is missing or stub, refuse and tell user to run `/cspec`
- If workflow state is not in REVIEW phase, explain current state
- If antipatterns.json is corrupt, fall back to antipatterns.md
- Checkpoint: save partial review if context limit is approaching

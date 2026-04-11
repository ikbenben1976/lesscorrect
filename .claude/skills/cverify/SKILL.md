---
name: cverify
description: >
  Verify implementation matches spec rule-by-rule. Builds a coverage matrix
  mapping spec rules to tests to code. Read-only with test runner access.
  Catches drift between what was specified and what was built.
argument-hint: ""
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash(pytest *) Bash(go test *) Bash(npm test *) Bash(cargo test *) Read Glob Grep
context: fork
effort: high
---

# Spec-to-Code Verification

Confirm that the implementation matches the specification — rule by rule.
Build a coverage matrix and catch any drift.

> **Shared constraints apply.** Before executing, read `_shared/constraints.md` from the parent of this skill's base directory.

## Context Injection

Read these files:
1. Workflow state — confirm we're in VERIFY phase
2. The spec file (from workflow state)
3. `.correctless/config/workflow-config.json` — test commands, file patterns
4. Test files matching the configured test patterns
5. Source files matching the configured source patterns
6. `.correctless/knowledge/drift-debt.json` — existing drift items

## Execution Steps

1. **Load workflow state**: Confirm VERIFY phase. If not, explain current state.
2. **Read the spec**: Load all rules (R-xxx), prohibitions (P-xxx), and edge cases.
3. **Find test files**: Locate all test files matching configured patterns.
4. **Find source files**: Locate all source files (excluding tests).
5. **Build coverage matrix**:

| Rule | Test(s) | Implementation | Status |
|------|---------|----------------|--------|
| R-001 | test_R001_... in test_foo.py:42 | handler() in foo.py:18 | COVERED |
| R-002 | (none found) | — | MISSING TEST |
| P-001 | test_P001_... in test_foo.py:67 | validate() in foo.py:33 | COVERED |

6. **Run tests**: Execute the test command and verify all pass.
7. **Check for drift**: Compare spec rules against implementation behavior:
   - Rules with no test → drift risk
   - Tests with no matching rule → possible undocumented behavior
   - Implementation that handles cases not in the spec → drift
8. **Dependency audit**: List any new dependencies added, with justification check.
9. **Architecture compliance**: Check if implementation follows patterns from ARCHITECTURE.md.
10. **Record drift items**: Write new drift findings to `drift-debt.json`.
11. **Write verification report** to `.correctless/verification/{slug}-verification.md`.

### Verdict

- **PASS**: Every rule mapped to test + implementation. All tests pass. No drift.
- **FAIL**: Missing coverage, test failures, or significant drift → return to TDD_GREEN.

12. **Advance workflow**: PASS → DOCS, FAIL → TDD_GREEN.

## Integration Points

### MCP Enhancements
- **Serena**: Use symbol-level tracing to find exact implementations of spec rules. Find all callers/references for functions under test. Fallback: grep for function names.

### Plugin Delegation
- None — verification is NEVER delegated.

### Knowledge Persistence
- **Reads**: spec file, test files, source files, drift-debt.json, config
- **Writes**: `verification/{slug}-verification.md`, drift-debt.json (new drift items), findings.json, workflow state, token-log

## Quality Gates

- Every spec rule must map to at least one test — gaps are automatic FAIL
- All tests must pass
- Verification report must be written to `.correctless/verification/`
- Any new drift items must be recorded

## Intensity Behavior

| Parameter | Standard | High | Critical |
|-----------|----------|------|----------|
| Coverage check | Rule → test mapping | + test → impl tracing | + mutation testing results |
| Drift threshold | Report drift | Report + require resolution plan | Block until resolved |
| Dependency audit | List new deps | + justify each | + security scan |
| Architecture check | Pattern match | + convention enforcement | + formal compliance |

## Error Handling

- If test command is not configured, refuse and tell user to run setup
- If spec file is empty, refuse and explain state
- If Serena is unavailable, fall back to grep-based symbol search
- Checkpoint: save partial verification report if context limit is approaching

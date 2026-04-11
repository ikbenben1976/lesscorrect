---
name: ctdd
description: >
  TDD orchestrator running the full RED → TEST_AUDIT → GREEN → QA pipeline.
  Each phase uses a separate agent with restricted tools. Test agent writes
  failing tests, impl agent makes them pass, QA agent reviews everything.
argument-hint: "[optional: phase to resume from — red|green|qa]"
disable-model-invocation: false
user-invocable: true
allowed-tools: Bash Read Write Edit Glob Grep Agent
effort: max
---

# TDD Orchestrator

Run the full test-driven development pipeline with agent separation.
Each phase uses a SEPARATE agent that cannot see the other agents' reasoning.

> **Shared constraints apply.** Before executing, read `_shared/constraints.md` from the parent of this skill's base directory.

## Context Injection

Read these files:
1. Workflow state — determine which TDD sub-phase we're in
2. The spec file (from workflow state)
3. `.correctless/config/workflow-config.json` — test commands, language, patterns
4. `.correctless/AGENT_CONTEXT.md` and `.correctless/ARCHITECTURE.md`
5. `.correctless/knowledge/findings.json` — any open findings from prior QA rounds

## Execution Steps

### Phase 1: RED (Write Failing Tests)

**Agent**: Test Agent — can read code, write test files, run tests. CANNOT write implementation.

1. Load the spec file
2. For each rule (R-xxx) and prohibition (P-xxx), write a test that exercises it
3. Edge cases from the spec get their own tests
4. Test names must reference spec rules: `test_R001_given_x_when_y_then_z`
5. If type stubs are needed for compilation, create minimal stubs marked `# STUB:TDD`
6. **Gate**: Run the test command. Tests MUST FAIL with test failures (not build errors)
7. Report which rules are covered and advance to TEST_AUDIT (if intensity >= HIGH) or GREEN

### Phase 2: TEST_AUDIT (if intensity >= HIGH)

**Agent**: Test Auditor — read-only. Reviews test quality BEFORE implementation.

1. Read the spec and the test files (but NOT any implementation)
2. Check each test for:
   - Does it actually test what the spec rule says?
   - Could this test pass with a subtly wrong implementation?
   - Are assertion messages specific enough to diagnose failures?
   - Are edge case tests truly exercising boundary conditions?
3. **Gate**: If blocking findings, return to RED for test fixes
4. Advance to GREEN

### Phase 3: GREEN (Make Tests Pass)

**Agent**: Impl Agent — full tool access. Writes the simplest correct implementation.

1. Read the spec (for reference) and the test files
2. Write the implementation that makes ALL tests pass
3. Follow existing project patterns and conventions
4. **DO NOT modify test files** — test edits during GREEN are logged as violations
5. **Gate**: Run the test command. ALL tests MUST PASS
6. Advance to QA

### Phase 4: QA (Independent Review)

**Agent**: QA Agent — read-only. Reviews spec + tests + implementation with fresh eyes.

1. Read all three artifacts without knowing how/why they were written
2. Check:
   - **Spec coverage**: Every rule has a corresponding test
   - **Test quality**: Could tests pass with a wrong implementation?
   - **Implementation correctness**: Does code satisfy the spec?
   - **Missing tests**: Behaviors in impl that aren't tested
   - **Security/safety**: Obvious vulnerabilities
3. Format findings with severity and evidence
4. **Verdict**:
   - **PASS**: No blocking findings → advance to VERIFY
   - **FAIL**: Has blocking findings → return to GREEN for fixes (QA round++)
5. Record findings and metrics

## Integration Points

### MCP Enhancements
- **Serena**: During VERIFY check, trace implementation symbols back to spec rules. Fallback: grep.
- **Context7**: During RED, look up testing patterns for the project's framework. Fallback: skip.

### Plugin Delegation
- **Superpowers**: May delegate GREEN phase micro-tasks (file creation, boilerplate) to Superpowers if available. Correctless retains: test authoring (RED), test audit, QA judgment, all gates.
- Pattern: Detect Superpowers → Gate (only GREEN micro-tasks) → Delegate → Verify (tests still pass) → Degrade (run without plugin)

### Knowledge Persistence
- **Reads**: spec file, workflow state, config, findings.json, antipatterns.json
- **Writes**: findings.json (QA findings), effectiveness.json (phase metrics), workflow state, token-log-{slug}.jsonl
- **Writes on QA FAIL**: qa-findings-{slug}.json with structured finding data

## Quality Gates

| Gate | Phase | Condition |
|------|-------|-----------|
| Tests fail | RED | Exit code != 0, failures are test failures not build errors |
| Test audit pass | TEST_AUDIT | No blocking findings about test quality |
| Tests pass | GREEN | Exit code == 0, all tests green |
| QA pass | QA | No BLOCKING findings |
| QA round cap | QA | qa_rounds < max_qa_rounds (from intensity) |

## Intensity Behavior

| Parameter | Standard | High | Critical |
|-----------|----------|------|----------|
| Test audit phase | Skip | Required | Required |
| Min tests per rule | 1 | 2 | 3 (incl. negative) |
| QA round cap | 3 | 5 | 8 |
| Mutation testing | No | No | Yes (after GREEN) |
| Test-to-impl isolation | Agent separation | Agent separation | Container isolation (Managed Agents) |
| Superpowers delegation | GREEN allowed | GREEN allowed | GREEN NOT allowed |

## Error Handling

- If tests don't compile during RED, this is a build error — not a test failure. Help fix compilation issues before gating.
- If GREEN phase can't make tests pass after max_turns, checkpoint and report remaining failures.
- If QA round cap is reached, escalate: report all open findings and recommend `/creview-spec` for deeper analysis.
- Checkpoint between each sub-phase so `/ctdd` can resume from the last completed phase.
- If implementation modified test files during GREEN, log as a violation and flag in QA.

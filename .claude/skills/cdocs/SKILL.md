---
name: cdocs
description: >
  Update project documentation after implementation. Updates AGENT_CONTEXT.md,
  ARCHITECTURE.md, and antipatterns.md based on what was built and what QA found.
argument-hint: ""
disable-model-invocation: false
user-invocable: true
allowed-tools: Read Write Edit Glob Grep
effort: medium
---

# Documentation Updater

Update project documentation to reflect what was just built. Keep docs concise
and scannable — agent context should be a quick reference, not a novel.

> **Shared constraints apply.** Before executing, read `_shared/constraints.md` from the parent of this skill's base directory.

## Context Injection

Read these files:
1. Workflow state — confirm we're in DOCS phase
2. The spec file (from workflow state)
3. `.correctless/verification/{slug}-verification.md` — what was verified
4. `.correctless/AGENT_CONTEXT.md` — current project context
5. `.correctless/ARCHITECTURE.md` — current patterns
6. `.correctless/antipatterns.md` — current bug patterns
7. `.correctless/knowledge/findings.json` — findings from review/QA

## Execution Steps

1. **Load workflow state**: Confirm DOCS phase.
2. **Read the spec and verification report**: Understand what was built.
3. **Update AGENT_CONTEXT.md**:
   - Add the new feature to the project summary
   - Update "Key endpoints / modules" if new ones were added
   - Update "Recent changes" with a dated entry
4. **Update ARCHITECTURE.md** (only if new patterns were introduced):
   - Add new patterns to the patterns section
   - Update conventions if new ones emerged
   - Reference PAT-xxx pattern IDs for traceability
5. **Update antipatterns.md** (if QA found patterns worth remembering):
   - Add entries that reference the specific bug class, not the fix
   - Cross-reference with AP-xxx IDs from the knowledge store
6. **Advance workflow**: Move to DONE phase.
7. **Report completion**: Show summary of what was updated and final workflow stats.

## Integration Points

### MCP Enhancements
- None typically needed for documentation updates.

### Plugin Delegation
- None — documentation updates are owned by Correctless.

### Knowledge Persistence
- **Reads**: spec, verification report, findings.json, existing docs
- **Writes**: AGENT_CONTEXT.md, ARCHITECTURE.md, antipatterns.md, workflow state, token-log

## Quality Gates

- AGENT_CONTEXT.md must be updated with the new feature
- Documentation entries must be concise (scannable, not verbose)
- Antipattern entries must reference bug classes, not specific fixes

## Intensity Behavior

| Parameter | Standard | High | Critical |
|-----------|----------|------|----------|
| Docs scope | AGENT_CONTEXT only | + ARCHITECTURE if patterns | + all docs + ADR summary |
| Antipattern update | If QA found patterns | Required if any findings | Required + trend analysis |
| Change summary | Brief | Detailed | Detailed + risk notes |

## Error Handling

- If verification report is missing, warn but proceed with spec-based documentation
- If AGENT_CONTEXT.md doesn't exist, create it from the template

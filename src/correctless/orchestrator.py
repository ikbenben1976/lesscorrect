"""Orchestrator — runs the right agent for each phase.

This is the heart of Correctless v4. Each phase:
1. Loads the current workflow state
2. Gathers context for the agent (spec, tests, impl, etc.)
3. Spawns a SEPARATE agent with restricted tools
4. Streams the agent's output to the terminal
5. Advances the state machine on success

The key guarantee: each agent gets a FRESH context window with ONLY the
information it needs. The QA agent cannot see the impl agent's reasoning.
The review agent cannot see the spec author's conversation. This is real
isolation, not prompt-based theatre.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import AsyncIterator, Optional

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from . import agents as agent_defs
from .config import ProjectConfig
from .knowledge import (
    KnowledgeStore,
    Finding,
    Antipattern,
    DriftItem,
    Decision,
    PhaseMetrics,
)
from .workflow import (
    Phase,
    WorkflowError,
    WorkflowState,
    WorkflowStore,
    init_workflow,
)

console = Console()


# ---------------------------------------------------------------------------
# Context gathering helpers
# ---------------------------------------------------------------------------

def _read_file(repo_root: Path, rel_path: str) -> str:
    """Read a file relative to repo root, return empty string if missing."""
    p = repo_root / rel_path
    if p.exists():
        return p.read_text()
    return ""


def _read_project_context(repo_root: Path) -> str:
    parts = []
    for name in [".correctless/AGENT_CONTEXT.md", ".correctless/ARCHITECTURE.md"]:
        content = _read_file(repo_root, name)
        if content:
            parts.append(f"### {name}\n{content}")
    return "\n\n".join(parts) if parts else "(no project context found)"


def _read_antipatterns(repo_root: Path) -> str:
    return _read_file(repo_root, ".correctless/antipatterns.md") or "(none yet)"


def _find_files_by_pattern(repo_root: Path, patterns: str) -> list[Path]:
    """Find files matching pipe-delimited glob patterns."""
    results = []
    for pattern in patterns.split("|"):
        pattern = pattern.strip()
        if not pattern:
            continue
        if "/" in pattern:
            results.extend(repo_root.glob(pattern))
        else:
            results.extend(repo_root.rglob(pattern))
    # Exclude .git, node_modules, .correctless
    return [
        f for f in results
        if not any(part.startswith(".") or part == "node_modules"
                   for part in f.relative_to(repo_root).parts[:-1])
    ]


def _read_files_content(files: list[Path], repo_root: Path, max_chars: int = 50_000) -> str:
    """Read multiple files, truncating if total content exceeds max_chars."""
    parts = []
    total = 0
    for f in sorted(files):
        rel = f.relative_to(repo_root)
        try:
            content = f.read_text()
        except (UnicodeDecodeError, PermissionError):
            continue
        if total + len(content) > max_chars:
            parts.append(f"\n### {rel}\n(truncated — {len(content)} chars)")
            break
        parts.append(f"\n### {rel}\n```\n{content}\n```")
        total += len(content)
    return "\n".join(parts) if parts else "(no files found)"


def _run_tests(config: ProjectConfig) -> tuple[int, str]:
    """Run the test command, return (exit_code, output)."""
    cmd = config.commands.test
    if not cmd:
        raise WorkflowError("No test command configured. Run 'cl setup' first.")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300,
        )
        output = result.stdout + result.stderr
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "Test command timed out after 300 seconds"


# ---------------------------------------------------------------------------
# Agent runner — 3-tier fallback chain
# ---------------------------------------------------------------------------
#
# Agent SDK → Messages API → Claude CLI (always available)
#
# Each tier provides the same interface: run an agent with a system prompt,
# tool restrictions, and a user message. Higher tiers have better isolation
# (SDK enforces tools at API level; CLI spawns a separate process).

import shutil

def _has_anthropic_key() -> bool:
    """Check if an Anthropic API key is available."""
    import os
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _has_claude_cli() -> bool:
    """Check if the claude CLI is on PATH."""
    return shutil.which("claude") is not None


async def run_agent(
    agent_def: agent_defs.AgentDef,
    user_message: str,
    repo_root: Path | None = None,
) -> str:
    """Run an agent and return its final text output.

    Fallback chain:
    1. Agent SDK (claude_agent_sdk) — best isolation, tool enforcement at API level
    2. Messages API (anthropic) — needs ANTHROPIC_API_KEY, no tool execution
    3. Claude CLI (claude -p) — always available in Claude Code, full tool support

    Each call creates a completely new agent session with a fresh context window.
    """
    # Tier 1: Agent SDK
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions

        console.print(f"\n[dim]({agent_def.name} via Agent SDK)[/dim]\n")
        full_output = []
        async for message in query(
            prompt=user_message,
            options=ClaudeAgentOptions(
                system_prompt=agent_def.system_prompt,
                model=agent_def.model,
                allowed_tools=agent_def.allowed_tools,
                max_turns=agent_def.max_turns,
                cwd=str(repo_root) if repo_root else None,
            ),
        ):
            if hasattr(message, "content"):
                for block in message.content:
                    if hasattr(block, "text"):
                        console.print(block.text, end="")
                        full_output.append(block.text)
            elif hasattr(message, "result"):
                full_output.append(str(message.result))

        return "\n".join(full_output)

    except ImportError:
        pass

    # Tier 2: Messages API (only if API key is available)
    if _has_anthropic_key():
        return await _run_agent_messages_api(agent_def, user_message)

    # Tier 3: Claude CLI (always available in Claude Code environments)
    if _has_claude_cli():
        return await _run_agent_claude_cli(agent_def, user_message, repo_root)

    raise WorkflowError(
        "No agent execution backend available. Install one of:\n"
        "  1. claude-agent-sdk (pip install claude-agent-sdk)\n"
        "  2. Set ANTHROPIC_API_KEY environment variable\n"
        "  3. Install Claude CLI (available in Claude Code)"
    )


async def _run_agent_messages_api(
    agent_def: agent_defs.AgentDef,
    user_message: str,
) -> str:
    """Tier 2: Use the Anthropic Messages API directly."""
    import anthropic

    client = anthropic.AsyncAnthropic()

    console.print(f"\n[dim]({agent_def.name} via Messages API)[/dim]\n")

    response = await client.messages.create(
        model=agent_def.model,
        max_tokens=16384,
        system=agent_def.system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = "\n".join(
        block.text for block in response.content if block.type == "text"
    )
    console.print(Markdown(text))
    return text


async def _run_agent_claude_cli(
    agent_def: agent_defs.AgentDef,
    user_message: str,
    repo_root: Path | None = None,
) -> str:
    """Tier 3: Use the Claude CLI to spawn a subagent process.

    This is the v3-compatible fallback that's always available inside
    Claude Code. Each agent runs as a separate `claude -p` invocation
    with its own system prompt and tool restrictions.
    """
    console.print(f"\n[dim]({agent_def.name} via Claude CLI)[/dim]\n")

    # Write system prompt to a temp file to avoid shell length limits.
    # Use --append-system-prompt-file to keep Claude Code's default tool
    # instructions (Read, Write, Edit, Bash, etc.) while adding our
    # agent-specific role and context.
    import tempfile
    prompt_file = Path(tempfile.mktemp(suffix=".txt", prefix="correctless-prompt-"))
    prompt_file.write_text(
        "IMPORTANT: You are a Correctless agent. Focus ONLY on the task "
        "given below. Do NOT address uncommitted changes, repo state, or "
        "anything outside your assigned task. Execute your instructions "
        "and produce the requested output.\n\n"
        + agent_def.system_prompt
    )

    cmd = [
        "claude", "-p",
        "--model", agent_def.model,
        "--append-system-prompt-file", str(prompt_file),
        "--output-format", "text",
    ]

    # Apply tool restrictions
    if agent_def.allowed_tools:
        cmd.extend(["--allowed-tools", " ".join(agent_def.allowed_tools)])

    # The user message is passed via stdin to avoid shell escaping issues
    cwd = str(repo_root) if repo_root else None

    try:
        proc = await asyncio.subprocess.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=user_message.encode()),
            timeout=600,  # 10 minute timeout for agent execution
        )

        output = stdout.decode()

        if proc.returncode != 0:
            err = stderr.decode()
            console.print(f"[yellow]Agent warning (exit {proc.returncode}):[/yellow] {err[:500]}")

        if output:
            console.print(Markdown(output))

        return output

    except asyncio.TimeoutError:
        console.print("[red]Agent timed out after 10 minutes[/red]")
        if proc:
            proc.kill()
        return "(agent timed out)"
    except FileNotFoundError:
        raise WorkflowError("Claude CLI not found. Is Claude Code installed?")
    finally:
        # Clean up temp prompt file
        prompt_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Knowledge extraction helpers
# ---------------------------------------------------------------------------

def _extract_and_record_findings(
    log: "FindingsLog",
    agent_output: str,
    phase: str,
    feature: str,
    branch: str,
) -> list[Finding]:
    """Parse agent output for findings and record them.

    Agents are prompted to use a structured format:
    - **Severity**: BLOCKING / HIGH / MEDIUM / LOW
    - **Finding**: description

    This does best-effort extraction. Even if the format isn't perfect,
    we capture what we can. The structured data compounds over time.
    """
    findings = []
    lines = agent_output.split("\n")
    current_severity = ""
    current_finding = ""
    current_category = ""
    current_rule = ""

    for line in lines:
        line_lower = line.lower().strip()

        # Look for severity markers
        for sev in ["BLOCKING", "HIGH", "MEDIUM", "LOW"]:
            if sev.lower() in line_lower and ("severity" in line_lower or f"**{sev.lower()}" in line_lower):
                # Save previous finding if exists
                if current_finding and current_severity:
                    findings.append(Finding(
                        id="",
                        phase=phase,
                        severity=current_severity,
                        category=current_category or "general",
                        finding=current_finding.strip(),
                        spec_rule=current_rule,
                        feature=feature,
                        branch=branch,
                    ))
                current_severity = sev
                current_finding = ""
                current_category = ""
                current_rule = ""
                break

        # Look for finding text
        if "finding" in line_lower and ":" in line:
            current_finding = line.split(":", 1)[1].strip().strip("*")

        # Look for category
        if "category" in line_lower and ":" in line:
            current_category = line.split(":", 1)[1].strip().strip("*").lower()

        # Look for rule reference
        if "rule" in line_lower and ":" in line:
            val = line.split(":", 1)[1].strip().strip("*")
            if val.startswith("R-") or val.startswith("P-"):
                current_rule = val

    # Save last finding
    if current_finding and current_severity:
        findings.append(Finding(
            id="",
            phase=phase,
            severity=current_severity,
            category=current_category or "general",
            finding=current_finding.strip(),
            spec_rule=current_rule,
            feature=feature,
            branch=branch,
        ))

    # Record all extracted findings
    for f in findings:
        log.add(f)

    return findings


# ---------------------------------------------------------------------------
# Phase runners — one function per workflow phase
# ---------------------------------------------------------------------------

async def run_spec(store: WorkflowStore, task: str) -> WorkflowState:
    """Start or continue the spec phase."""
    state = store.load()

    if state.phase == Phase.NONE:
        state = init_workflow(store, task)
        console.print(Panel(
            f"[bold green]Workflow started[/bold green]\n{state.summary}",
            title="correctless",
        ))

    if state.phase != Phase.SPEC:
        raise WorkflowError(f"Expected phase 'spec', got '{state.phase.value}'")

    repo = store.repo_root
    knowledge = KnowledgeStore(repo)
    agent = agent_defs.spec_agent(
        project_context=_read_project_context(repo),
        antipatterns=_read_antipatterns(repo),
        knowledge_context=knowledge.agent_context(),
    )

    console.print(f"\n[bold]Spec Agent[/bold] — writing specification for: {task}\n")
    await run_agent(
        agent,
        f"Write a spec for: {task}\n\n"
        f"IMPORTANT: You are running in non-interactive mode. Do NOT ask "
        f"clarifying questions. Instead, make reasonable assumptions and "
        f"document them in the spec's 'Open Questions' section. Write the "
        f"spec directly to the file: {state.spec_file}\n\n"
        f"Use the Edit or Write tool to update the spec file with the full "
        f"specification including Rules (R-xxx), Prohibitions (P-xxx), Edge "
        f"Cases, and Open Questions sections.",
        repo_root=repo,
    )

    # Advance to review
    state = store.load()  # reload in case agent wrote to state
    state.advance(Phase.REVIEW)
    store.save(state)
    console.print(f"\n[green]→ Spec complete. Run [bold]cl review[/bold] for skeptical review.[/green]")
    return state


async def run_review(store: WorkflowStore) -> WorkflowState:
    """Run the skeptical review phase."""
    state = store.load()
    if state.phase != Phase.REVIEW:
        raise WorkflowError(f"Expected phase 'review', got '{state.phase.value}'")

    repo = store.repo_root
    spec_content = _read_file(repo, state.spec_file)
    if not spec_content or "_(to be written)_" in spec_content:
        raise WorkflowError("Spec file is empty or still a stub. Run 'cl spec' first.")

    agent = agent_defs.review_agent(
        spec_content=spec_content,
        project_context=_read_project_context(repo),
    )

    console.print("\n[bold]Review Agent[/bold] — reading spec cold, looking for problems\n")
    result = await run_agent(
        agent,
        "Review this spec. Find what's wrong.\n\n"
        "You are running in non-interactive mode. Produce your complete "
        "review with all findings in a single response. End with a clear "
        "verdict: APPROVE or REVISE.",
        repo_root=repo,
    )

    # Record findings from this review into the knowledge store
    knowledge = KnowledgeStore(repo)
    findings_log = knowledge.findings()
    _extract_and_record_findings(findings_log, result, "review", state.task, state.branch)
    knowledge.save_findings(findings_log)

    # Check verdict
    if "REVISE" in result.upper():
        state.advance(Phase.SPEC)  # Back to spec for fixes
        store.save(state)
        console.print(f"\n[yellow]← Review found blocking issues. "
                      f"Fix the spec, then run [bold]cl review[/bold] again.[/yellow]")
    else:
        state.advance(Phase.TDD_RED)
        store.save(state)
        console.print(f"\n[green]→ Review passed. Run [bold]cl tdd[/bold] to start TDD.[/green]")

    return state


async def run_tdd(store: WorkflowStore) -> WorkflowState:
    """Run the full TDD cycle: RED → GREEN → QA."""
    state = store.load()
    repo = store.repo_root
    config = ProjectConfig.load(repo)

    # ---------- RED phase ----------
    if state.phase == Phase.TDD_RED:
        spec_content = _read_file(repo, state.spec_file)
        agent = agent_defs.test_agent(spec_content, config.model_dump())

        console.print("\n[bold red]RED Phase[/bold red] — Test Agent writing failing tests\n")
        await run_agent(
            agent,
            "Write failing tests for every rule in the spec. "
            "You are running in non-interactive mode. Write the test files "
            "directly using the Write or Edit tool. Then run the tests to "
            "verify they fail with test failures (not build errors).",
            repo_root=repo,
        )

        # Gate: tests must fail (not build errors)
        console.print("\n[dim]Verifying tests fail...[/dim]")
        exit_code, output = _run_tests(config)
        if exit_code == 0:
            raise WorkflowError(
                "Tests pass — they need to fail first. "
                "The test agent should have written tests that exercise unimplemented behavior."
            )
        console.print("[red]Tests fail as expected ✓[/red]")

        state.advance(Phase.TDD_GREEN)
        store.save(state)

    # ---------- GREEN phase ----------
    if state.phase == Phase.TDD_GREEN:
        spec_content = _read_file(repo, state.spec_file)
        test_files = _find_files_by_pattern(repo, config.patterns.test_file)
        test_content = _read_files_content(test_files, repo)

        agent = agent_defs.impl_agent(spec_content, test_content, config.model_dump())

        console.print("\n[bold green]GREEN Phase[/bold green] — Impl Agent making tests pass\n")
        await run_agent(
            agent,
            "Make all failing tests pass. You are running in non-interactive "
            "mode. Write the implementation directly using Write or Edit tools. "
            "Do NOT modify test files. Run the tests to verify they pass.",
            repo_root=repo,
        )

        # Gate: tests must pass
        console.print("\n[dim]Verifying tests pass...[/dim]")
        exit_code, output = _run_tests(config)
        if exit_code != 0:
            console.print(f"[red]Tests still failing:[/red]\n{output[-500:]}")
            raise WorkflowError("Tests don't pass yet. Fix the implementation and run 'cl tdd' again.")
        console.print("[green]All tests pass ✓[/green]")

        state.advance(Phase.TDD_QA)
        store.save(state)

    # ---------- QA phase ----------
    if state.phase == Phase.TDD_QA:
        spec_content = _read_file(repo, state.spec_file)
        test_files = _find_files_by_pattern(repo, config.patterns.test_file)
        source_files = _find_files_by_pattern(repo, config.patterns.source_file)
        # Exclude test files from source files
        test_set = set(test_files)
        source_only = [f for f in source_files if f not in test_set]

        agent = agent_defs.qa_agent(
            spec_content=spec_content,
            test_files=_read_files_content(test_files, repo),
            impl_files=_read_files_content(source_only, repo),
            project_context=_read_project_context(repo),
        )

        console.print(f"\n[bold cyan]QA Phase[/bold cyan] — QA Agent reviewing (round {state.qa_rounds + 1})\n")
        result = await run_agent(
            agent,
            "Review the spec, tests, and implementation. Find bugs. "
            "You are running in non-interactive mode. Produce your complete "
            "review with all findings. End with: PASS or FAIL.",
            repo_root=repo,
        )

        # Record QA findings
        knowledge = KnowledgeStore(repo)
        findings_log = knowledge.findings()
        _extract_and_record_findings(findings_log, result, "qa", state.task, state.branch)
        knowledge.save_findings(findings_log)

        # Record phase metrics
        effectiveness = knowledge.effectiveness()
        qa_findings = [f for f in findings_log.findings if f.phase == "qa" and f.feature == state.task]
        effectiveness.record(PhaseMetrics(
            phase="tdd-qa",
            feature=state.task,
            branch=state.branch,
            findings_count=len(qa_findings),
            blocking_count=sum(1 for f in qa_findings if f.severity == "BLOCKING"),
            outcome="fail" if ("FAIL" in result.upper() and "BLOCKING" in result.upper()) else "pass",
        ))
        knowledge.save_effectiveness(effectiveness)

        if "FAIL" in result.upper() and "BLOCKING" in result.upper():
            # QA found issues — go back to GREEN for fixes
            state.advance(Phase.TDD_GREEN)
            store.save(state)
            console.print(f"\n[yellow]← QA found blocking issues. "
                          f"Fix them and run [bold]cl tdd[/bold] again.[/yellow]")
        else:
            state.advance(Phase.VERIFY)
            store.save(state)
            console.print(f"\n[green]→ QA passed. Run [bold]cl verify[/bold] for final verification.[/green]")

    return state


async def run_verify(store: WorkflowStore) -> WorkflowState:
    """Run the verification phase."""
    state = store.load()
    if state.phase != Phase.VERIFY:
        raise WorkflowError(f"Expected phase 'verify', got '{state.phase.value}'")

    repo = store.repo_root
    config = ProjectConfig.load(repo)
    spec_content = _read_file(repo, state.spec_file)
    source_files = _find_files_by_pattern(repo, config.patterns.source_file)
    impl_content = _read_files_content(source_files, repo)

    agent = agent_defs.verify_agent(spec_content, impl_content, config.model_dump())

    console.print("\n[bold]Verify Agent[/bold] — checking spec-to-code correspondence\n")
    result = await run_agent(
        agent,
        "Verify the implementation matches the spec. "
        "You are running in non-interactive mode. Build the coverage "
        "matrix and produce the verification report. Write it to "
        ".correctless/verification/. End with: PASS or FAIL.",
        repo_root=repo,
    )

    if "FAIL" in result.upper():
        state.advance(Phase.TDD_GREEN)
        store.save(state)
        console.print(f"\n[yellow]← Verification found issues. "
                      f"Fix and run [bold]cl tdd[/bold] to re-enter TDD.[/yellow]")
    else:
        state.advance(Phase.DOCS)
        store.save(state)
        console.print(f"\n[green]→ Verified. Run [bold]cl docs[/bold] to update documentation.[/green]")

    return state


async def run_docs(store: WorkflowStore) -> WorkflowState:
    """Run the documentation phase."""
    state = store.load()
    if state.phase != Phase.DOCS:
        raise WorkflowError(f"Expected phase 'docs', got '{state.phase.value}'")

    repo = store.repo_root
    spec_content = _read_file(repo, state.spec_file)
    project_context = _read_project_context(repo)

    agent = agent_defs.docs_agent(
        spec_content=spec_content,
        impl_summary=f"Feature: {state.task}\nSpec: {state.spec_file}",
        project_context=project_context,
    )

    console.print("\n[bold]Docs Agent[/bold] — updating project documentation\n")
    await run_agent(
        agent,
        "Update documentation for this feature. "
        "You are running in non-interactive mode. Update the doc files "
        "directly using Write or Edit tools.",
        repo_root=repo,
    )

    state.advance(Phase.DONE)
    store.save(state)
    console.print(Panel(
        f"[bold green]Workflow complete![/bold green]\n\n"
        f"Task: {state.task}\n"
        f"QA rounds: {state.qa_rounds}\n"
        f"Spec revisions: {state.spec_updates}\n\n"
        f"Branch is ready to merge.",
        title="correctless",
    ))
    return state

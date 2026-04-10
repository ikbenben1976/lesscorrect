"""CLI — the user-facing commands.

Maps directly to the workflow phases:
  cl setup     → detect project, create config
  cl spec      → write a specification
  cl review    → skeptical review of the spec
  cl tdd       → RED → GREEN → QA cycle
  cl verify    → check impl matches spec
  cl docs      → update documentation
  cl done      → (automatic after docs)
  cl status    → show current phase
  cl reset     → clear workflow state
"""

from __future__ import annotations

import asyncio
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import ProjectConfig
from .workflow import Phase, WorkflowError, WorkflowStore

console = Console()


def _run_async(coro):
    """Run an async function from sync context."""
    return asyncio.run(coro)


@click.group()
@click.version_option(package_name="correctless")
def main():
    """Correctless — spec before code, test before impl, nobody grades their own work."""
    pass


@main.command()
def setup():
    """Initialize Correctless for this project."""
    from .workflow import _find_repo_root

    repo = _find_repo_root()
    config = ProjectConfig.detect(repo)
    config.save(repo)

    # Create directory structure
    for d in ["specs", "verification", "artifacts", "config"]:
        (repo / ".correctless" / d).mkdir(parents=True, exist_ok=True)

    # Create template files
    for name, content in _TEMPLATES.items():
        path = repo / ".correctless" / name
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    console.print(Panel(
        f"[bold green]Correctless initialized[/bold green]\n\n"
        f"Language: {config.project.language}\n"
        f"Test cmd: {config.commands.test or '(not detected — edit config)'}\n"
        f"Config:   .correctless/config/workflow-config.json\n\n"
        f"Next: [bold]git checkout -b feature/my-feature[/bold]\n"
        f"Then: [bold]cl spec \"what you're building\"[/bold]",
        title="correctless setup",
    ))


@main.command()
@click.argument("task", nargs=-1, required=True)
def spec(task: tuple[str, ...]):
    """Write a specification for a new feature."""
    from .orchestrator import run_spec

    task_str = " ".join(task)
    store = WorkflowStore()
    try:
        _run_async(run_spec(store, task_str))
    except WorkflowError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
def review():
    """Run a skeptical review of the spec (fresh agent, read-only)."""
    from .orchestrator import run_review

    store = WorkflowStore()
    try:
        _run_async(run_review(store))
    except WorkflowError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
def tdd():
    """Run the TDD cycle: RED (write tests) → GREEN (implement) → QA (review)."""
    from .orchestrator import run_tdd

    store = WorkflowStore()
    try:
        _run_async(run_tdd(store))
    except WorkflowError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
def verify():
    """Verify implementation matches spec (fresh agent, read-only + test runner)."""
    from .orchestrator import run_verify

    store = WorkflowStore()
    try:
        _run_async(run_verify(store))
    except WorkflowError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
def docs():
    """Update project documentation."""
    from .orchestrator import run_docs

    store = WorkflowStore()
    try:
        _run_async(run_docs(store))
    except WorkflowError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command()
def status():
    """Show current workflow state."""
    store = WorkflowStore()
    state = store.load()

    if state.phase == Phase.NONE:
        console.print("[dim]No active workflow. Run [bold]cl spec \"task\"[/bold] to start.[/dim]")
        return

    # Phase progression visualization
    phases = [Phase.SPEC, Phase.REVIEW, Phase.TDD_RED, Phase.TDD_GREEN, Phase.TDD_QA, Phase.VERIFY, Phase.DOCS, Phase.DONE]
    progress = []
    for p in phases:
        if p == state.phase:
            progress.append(f"[bold cyan]●{p.value}[/bold cyan]")
        elif phases.index(p) < phases.index(state.phase) if state.phase in phases else False:
            progress.append(f"[green]✓{p.value}[/green]")
        else:
            progress.append(f"[dim]○{p.value}[/dim]")

    console.print(Panel(
        f"{' → '.join(progress)}\n\n{state.summary}\n\n"
        f"Next: [bold]{_next_command(state.phase)}[/bold]",
        title="correctless status",
    ))


@main.command()
def reset():
    """Clear workflow state for the current branch."""
    store = WorkflowStore()
    state = store.load()
    if state.phase == Phase.NONE:
        console.print("[dim]No active workflow to reset.[/dim]")
        return

    store.reset()
    console.print(f"[yellow]Workflow state cleared for branch '{state.branch}'.[/yellow]")


@main.command(name="spec-update")
@click.argument("reason", nargs=-1, required=True)
def spec_update(reason: tuple[str, ...]):
    """Return to spec phase during TDD (spec was wrong)."""
    store = WorkflowStore()
    state = store.load()
    try:
        state.spec_update(" ".join(reason))
        store.save(state)
        console.print(f"[yellow]Returned to spec phase. "
                      f"Edit the spec, then run [bold]cl review[/bold].[/yellow]")
    except WorkflowError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command(name="status-all")
def status_all():
    """Show all active workflows across branches."""
    store = WorkflowStore()
    states = store.all_active()

    if not states:
        console.print("[dim]No active workflows.[/dim]")
        return

    table = Table(title="Active Workflows")
    table.add_column("Branch", style="cyan")
    table.add_column("Phase")
    table.add_column("Task")
    table.add_column("QA Rounds")
    table.add_column("Started")

    for s in states:
        phase_style = "green" if s.phase == Phase.DONE else "yellow"
        table.add_row(
            s.branch,
            f"[{phase_style}]{s.phase.value}[/{phase_style}]",
            s.task[:40],
            str(s.qa_rounds),
            s.started_at[:10],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# Knowledge commands — inspect and manage accumulated knowledge
# ---------------------------------------------------------------------------

@main.group()
def knowledge():
    """Inspect and manage accumulated project knowledge."""
    pass


@knowledge.command(name="findings")
@click.option("--unresolved", is_flag=True, help="Show only unresolved findings")
@click.option("--feature", default=None, help="Filter by feature name")
def knowledge_findings(unresolved: bool, feature: str | None):
    """Show all findings from reviews, QA, and verification."""
    from .knowledge import KnowledgeStore
    from .workflow import _find_repo_root

    ks = KnowledgeStore(_find_repo_root())
    log = ks.findings()

    items = log.unresolved() if unresolved else log.findings
    if feature:
        items = [f for f in items if feature.lower() in f.feature.lower()]

    if not items:
        console.print("[dim]No findings recorded yet.[/dim]")
        return

    table = Table(title=f"Findings ({len(items)} total)")
    table.add_column("ID", style="cyan")
    table.add_column("Phase")
    table.add_column("Severity")
    table.add_column("Finding")
    table.add_column("Feature")
    table.add_column("Resolved", justify="center")

    for f in items:
        sev_style = {"BLOCKING": "red bold", "HIGH": "red", "MEDIUM": "yellow", "LOW": "dim"}.get(f.severity, "")
        table.add_row(
            f.id,
            f.phase,
            f"[{sev_style}]{f.severity}[/{sev_style}]",
            f.finding[:60],
            f.feature[:20],
            "✓" if f.resolved else "",
        )

    console.print(table)

    # Summary
    summary = log.severity_summary()
    console.print(f"\n[dim]Summary: {summary}[/dim]")


@knowledge.command(name="antipatterns")
def knowledge_antipatterns():
    """Show known antipatterns (bug patterns from past QA rounds)."""
    from .knowledge import KnowledgeStore
    from .workflow import _find_repo_root

    ks = KnowledgeStore(_find_repo_root())
    registry = ks.antipatterns()

    if not registry.antipatterns:
        console.print("[dim]No antipatterns recorded yet. "
                      "They accumulate as QA finds recurring patterns.[/dim]")
        return

    table = Table(title="Known Antipatterns")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Occurrences", justify="right")
    table.add_column("Description")
    table.add_column("Detection")

    for ap in sorted(registry.antipatterns, key=lambda x: -x.occurrences):
        table.add_row(
            ap.id, ap.name, str(ap.occurrences),
            ap.description[:50], ap.detection[:40],
        )

    console.print(table)


@knowledge.command(name="drift")
def knowledge_drift():
    """Show open spec-to-code drift debt."""
    from .knowledge import KnowledgeStore
    from .workflow import _find_repo_root

    ks = KnowledgeStore(_find_repo_root())
    tracker = ks.drift_debt()
    open_items = tracker.open_items()

    if not open_items:
        console.print("[green]No open drift debt.[/green]")
        return

    table = Table(title=f"Open Drift Debt ({len(open_items)} items)")
    table.add_column("ID", style="cyan")
    table.add_column("Spec")
    table.add_column("Rule")
    table.add_column("Description")
    table.add_column("Since")

    for item in open_items:
        table.add_row(
            item.id, item.spec_file, item.spec_rule,
            item.description[:50], item.detected_at[:10],
        )

    console.print(table)


@knowledge.command(name="decisions")
def knowledge_decisions():
    """Show active architectural decisions and their rationale."""
    from .knowledge import KnowledgeStore
    from .workflow import _find_repo_root

    ks = KnowledgeStore(_find_repo_root())
    log = ks.decisions()
    active = log.active()

    if not active:
        console.print("[dim]No decisions recorded yet.[/dim]")
        return

    for d in active:
        console.print(Panel(
            f"[bold]{d.title}[/bold]\n\n"
            f"[dim]Context:[/dim] {d.context}\n"
            f"[dim]Decision:[/dim] {d.decision}\n"
            f"[dim]Rationale:[/dim] {d.rationale}\n"
            f"[dim]Alternatives:[/dim] {', '.join(d.alternatives) or 'none recorded'}\n"
            f"[dim]Feature:[/dim] {d.feature}  [dim]Phase:[/dim] {d.phase}",
            title=d.id,
        ))


@knowledge.command(name="effectiveness")
def knowledge_effectiveness():
    """Show phase effectiveness metrics (what catches the most bugs?)."""
    from .knowledge import KnowledgeStore
    from .workflow import _find_repo_root

    ks = KnowledgeStore(_find_repo_root())
    tracker = ks.effectiveness()
    summary = tracker.phase_summary()

    if not summary:
        console.print("[dim]No effectiveness data yet. "
                      "Accumulates as you complete workflow cycles.[/dim]")
        return

    table = Table(title="Phase Effectiveness")
    table.add_column("Phase")
    table.add_column("Runs", justify="right")
    table.add_column("Total Findings", justify="right")
    table.add_column("Avg Findings/Run", justify="right")
    table.add_column("Blocking", justify="right")
    table.add_column("Total Cost", justify="right")

    for phase, s in sorted(summary.items()):
        avg = s["total_findings"] / max(s["total_runs"], 1)
        table.add_row(
            phase,
            str(s["total_runs"]),
            str(s["total_findings"]),
            f"{avg:.1f}",
            str(s["total_blocking"]),
            f"${s['total_cost']:.2f}",
        )

    console.print(table)


@knowledge.command(name="summary")
def knowledge_summary():
    """Show a high-level summary of all accumulated knowledge."""
    from .knowledge import KnowledgeStore
    from .workflow import _find_repo_root

    ks = KnowledgeStore(_find_repo_root())

    findings = ks.findings()
    antipatterns = ks.antipatterns()
    drift = ks.drift_debt()
    decisions = ks.decisions()
    effectiveness = ks.effectiveness()

    console.print(Panel(
        f"[bold]Findings:[/bold] {len(findings.findings)} total, "
        f"{len(findings.unresolved())} unresolved\n"
        f"[bold]Antipatterns:[/bold] {len(antipatterns.antipatterns)} known patterns\n"
        f"[bold]Drift Debt:[/bold] {len(drift.open_items())} open items\n"
        f"[bold]Decisions:[/bold] {len(decisions.active())} active ADRs\n"
        f"[bold]Phase Runs:[/bold] {len(effectiveness.metrics)} recorded",
        title="Knowledge Summary",
    ))



def _next_command(phase: Phase) -> str:
    return {
        Phase.SPEC: "cl review",
        Phase.REVIEW: "cl tdd",
        Phase.TDD_RED: "cl tdd",
        Phase.TDD_GREEN: "cl tdd",
        Phase.TDD_QA: "cl tdd  (or cl verify if QA passed)",
        Phase.VERIFY: "cl docs",
        Phase.DOCS: "cl done  (automatic)",
        Phase.DONE: "git merge",
    }.get(phase, "cl status")


# ---------------------------------------------------------------------------
# Template files
# ---------------------------------------------------------------------------

_TEMPLATES = {
    "ARCHITECTURE.md": """# Architecture

## Components
_(Describe your project's main components here)_

## Patterns
_(Document recurring patterns — e.g., "all API handlers validate input at the boundary")_

## Conventions
_(Project conventions — naming, error handling, etc.)_
""",
    "AGENT_CONTEXT.md": """# Agent Context

## What is this project?
_(Brief description for AI agents working on this codebase)_

## Key endpoints / modules
_(List the main entry points so agents know where to look)_

## Recent changes
_(Updated by /cl docs after each feature)_
""",
    "antipatterns.md": """# Known Antipatterns

Bugs and patterns that have bitten us before. Each entry feeds into spec
reviews so we don't repeat mistakes.

_(Will be populated as QA finds patterns)_
""",
}


if __name__ == "__main__":
    main()

"""Workflow state machine.

Replaces workflow-advance.sh (1145 lines of bash) with a typed, testable
state machine. All transitions are validated. The state is a simple JSON
file in .correctless/artifacts/.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------

class Phase(str, Enum):
    """Every phase the workflow can be in, and what it means."""

    NONE = "none"               # No active workflow
    SPEC = "spec"               # Writing the specification
    REVIEW = "review"           # Skeptical review of the spec
    TDD_RED = "tdd-red"         # Writing failing tests (no source edits)
    TDD_GREEN = "tdd-green"     # Making tests pass (all edits allowed)
    TDD_QA = "tdd-qa"           # QA review (no edits)
    VERIFY = "verify"           # Checking impl matches spec
    DOCS = "docs"               # Updating documentation
    DONE = "done"               # Ready to merge


# Allowed transitions — the arrows in the state machine.
# Each key maps to the set of phases it can move to.
TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.NONE:      {Phase.SPEC},
    Phase.SPEC:      {Phase.REVIEW},
    Phase.REVIEW:    {Phase.TDD_RED, Phase.SPEC},          # can reject back to spec
    Phase.TDD_RED:   {Phase.TDD_GREEN},                    # gate: tests must fail
    Phase.TDD_GREEN: {Phase.TDD_QA},                       # gate: tests must pass
    Phase.TDD_QA:    {Phase.TDD_GREEN, Phase.VERIFY},      # fix round or advance
    Phase.VERIFY:    {Phase.DOCS, Phase.TDD_GREEN},         # issues found → fix
    Phase.DOCS:      {Phase.DONE},
    Phase.DONE:      set(),                                 # terminal
}

# Phases where the spec can be revised mid-flight (returns to SPEC).
# This preserves history so you know the spec was revised during TDD.
SPEC_UPDATE_PHASES = {Phase.TDD_RED, Phase.TDD_GREEN, Phase.TDD_QA}


# ---------------------------------------------------------------------------
# State model
# ---------------------------------------------------------------------------

class SpecUpdate(BaseModel):
    from_phase: str
    reason: str
    timestamp: str


class WorkflowState(BaseModel):
    phase: Phase = Phase.NONE
    task: str = ""
    spec_file: str = ""
    branch: str = ""
    started_at: str = ""
    phase_entered_at: str = ""
    qa_rounds: int = 0
    spec_updates: int = 0
    spec_update_history: list[SpecUpdate] = Field(default_factory=list)
    findings: dict[str, list[str]] = Field(default_factory=dict)  # phase → findings

    def advance(self, to: Phase) -> None:
        """Move to a new phase, validating the transition."""
        if to not in TRANSITIONS.get(self.phase, set()):
            raise WorkflowError(
                f"Cannot move from '{self.phase.value}' to '{to.value}'. "
                f"Valid targets: {', '.join(p.value for p in TRANSITIONS.get(self.phase, set()))}"
            )
        if to == Phase.TDD_QA:
            self.qa_rounds += 1
        self.phase = to
        self.phase_entered_at = _now()

    def spec_update(self, reason: str) -> None:
        """Return to spec phase during TDD (spec was wrong)."""
        if self.phase not in SPEC_UPDATE_PHASES:
            raise WorkflowError(
                f"Cannot revise spec from phase '{self.phase.value}'. "
                f"Only allowed during TDD phases."
            )
        self.spec_update_history.append(SpecUpdate(
            from_phase=self.phase.value,
            reason=reason,
            timestamp=_now(),
        ))
        self.spec_updates += 1
        self.phase = Phase.SPEC
        self.phase_entered_at = _now()

    def record_findings(self, phase: str, findings: list[str]) -> None:
        """Record findings from a phase (review, QA, verify)."""
        self.findings[phase] = findings

    @property
    def summary(self) -> str:
        lines = [
            f"Phase:   {self.phase.value}",
            f"Task:    {self.task}",
            f"Branch:  {self.branch}",
            f"Spec:    {self.spec_file}",
            f"Started: {self.started_at}",
            f"QA rounds: {self.qa_rounds}",
        ]
        if self.spec_updates:
            lines.append(f"Spec revisions: {self.spec_updates}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class WorkflowStore:
    """Read/write workflow state to .correctless/artifacts/."""

    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or _find_repo_root()
        self.artifacts_dir = self.repo_root / ".correctless" / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _state_path(self) -> Path:
        branch = _current_branch()
        slug = _branch_slug(branch)
        return self.artifacts_dir / f"workflow-state-{slug}.json"

    def load(self) -> WorkflowState:
        path = self._state_path()
        if not path.exists():
            return WorkflowState()
        return WorkflowState.model_validate_json(path.read_text())

    def save(self, state: WorkflowState) -> None:
        path = self._state_path()
        path.write_text(state.model_dump_json(indent=2) + "\n")

    def reset(self) -> None:
        path = self._state_path()
        if path.exists():
            path.unlink()

    def all_active(self) -> list[WorkflowState]:
        states = []
        for f in self.artifacts_dir.glob("workflow-state-*.json"):
            try:
                states.append(WorkflowState.model_validate_json(f.read_text()))
            except Exception:
                continue
        return states


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class WorkflowError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_repo_root() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _current_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise WorkflowError("Not in a git repository or detached HEAD")


def _branch_slug(branch: str) -> str:
    import hashlib
    safe = "".join(c if c.isalnum() else "-" for c in branch)[:80]
    h = hashlib.sha256(branch.encode()).hexdigest()[:8]
    return f"{safe}-{h}"


def init_workflow(store: WorkflowStore, task: str) -> WorkflowState:
    """Start a new workflow on the current branch."""
    branch = _current_branch()
    if branch in ("main", "master"):
        raise WorkflowError(
            f"Cannot start workflow on '{branch}'. "
            "Create a feature branch first."
        )

    existing = store.load()
    if existing.phase != Phase.NONE:
        raise WorkflowError(
            f"Workflow already active (phase: {existing.phase.value}). "
            "Run 'correctless reset' to clear it."
        )

    # Generate spec filename from task
    slug = "".join(c if c.isalnum() else "-" for c in task.lower())[:50].strip("-")
    spec_file = f".correctless/specs/{slug}.md"
    (store.repo_root / ".correctless" / "specs").mkdir(parents=True, exist_ok=True)

    state = WorkflowState(
        phase=Phase.SPEC,
        task=task,
        spec_file=spec_file,
        branch=branch,
        started_at=_now(),
        phase_entered_at=_now(),
    )
    store.save(state)

    # Create spec stub
    spec_path = store.repo_root / spec_file
    if not spec_path.exists():
        spec_path.write_text(f"# Spec: {task}\n\n## Rules\n\n_(to be written)_\n")

    return state

"""Structured knowledge persistence.

This is the memory layer. Every review finding, QA bug, spec revision,
and architectural decision gets captured in structured JSON so that:

1. Future spec agents see what went wrong before (antipatterns)
2. Future review agents know what to look for (historical findings)
3. Drift between specs and code is tracked over time (drift debt)
4. Decision rationale is preserved (decision log)
5. Phase effectiveness is measured (what catches bugs?)
6. Token costs are tracked per phase per feature (cost awareness)

The key insight: conversations with Claude are ephemeral, but the
STRUCTURED ARTIFACTS from those conversations compound. Every QA round
that finds a bug should make the next spec review smarter.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Finding — the universal unit of "something we learned"
# ---------------------------------------------------------------------------

class Finding(BaseModel):
    """A finding from any phase (review, QA, verify, audit)."""

    id: str                          # e.g., "QA-001", "REV-003"
    phase: str                       # Which phase found it
    severity: str                    # BLOCKING, HIGH, MEDIUM, LOW
    category: str                    # coverage, test-quality, correctness, security, spec-gap, drift
    finding: str                     # What's wrong
    evidence: str = ""               # Specific code/test/rule reference
    resolution: str = ""             # How it was fixed (filled in after fix)
    spec_rule: str = ""              # Which spec rule is affected (R-001, etc.)
    resolved: bool = False
    timestamp: str = ""
    feature: str = ""                # Which feature/task this belongs to
    branch: str = ""


class FindingsLog(BaseModel):
    """Append-only log of all findings across all features."""

    findings: list[Finding] = Field(default_factory=list)
    _next_id: int = 0

    def add(self, finding: Finding) -> Finding:
        if not finding.id:
            self._next_id = len(self.findings) + 1
            prefix = finding.phase[:3].upper()
            finding.id = f"{prefix}-{self._next_id:03d}"
        if not finding.timestamp:
            finding.timestamp = _now()
        self.findings.append(finding)
        return finding

    def resolve(self, finding_id: str, resolution: str) -> None:
        for f in self.findings:
            if f.id == finding_id:
                f.resolved = True
                f.resolution = resolution
                return
        raise KeyError(f"Finding {finding_id} not found")

    def unresolved(self) -> list[Finding]:
        return [f for f in self.findings if not f.resolved]

    def by_category(self) -> dict[str, list[Finding]]:
        cats: dict[str, list[Finding]] = {}
        for f in self.findings:
            cats.setdefault(f.category, []).append(f)
        return cats

    def by_feature(self, feature: str) -> list[Finding]:
        return [f for f in self.findings if f.feature == feature]

    def severity_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Antipattern — a recurring bug class extracted from findings
# ---------------------------------------------------------------------------

class Antipattern(BaseModel):
    """A known bug pattern that feeds into future spec reviews."""

    id: str                          # AP-001, AP-002, etc.
    name: str                        # Short name: "bcrypt cost factor"
    description: str                 # What goes wrong
    detection: str                   # How to spot it during spec/review
    example: str = ""                # Example from a real finding
    source_finding: str = ""         # Finding ID that triggered this
    occurrences: int = 1             # How many times we've seen it
    added_at: str = ""
    last_seen: str = ""
    tags: list[str] = Field(default_factory=list)  # e.g., ["security", "auth"]


class AntipatternRegistry(BaseModel):
    """Growing registry of bug patterns. Fed into every spec and review agent."""

    antipatterns: list[Antipattern] = Field(default_factory=list)

    def add(self, ap: Antipattern) -> Antipattern:
        if not ap.id:
            ap.id = f"AP-{len(self.antipatterns) + 1:03d}"
        if not ap.added_at:
            ap.added_at = _now()
        ap.last_seen = ap.added_at
        self.antipatterns.append(ap)
        return ap

    def bump(self, ap_id: str) -> None:
        """Record another occurrence of this antipattern."""
        for ap in self.antipatterns:
            if ap.id == ap_id:
                ap.occurrences += 1
                ap.last_seen = _now()
                return

    def as_prompt_context(self) -> str:
        """Format for injection into agent system prompts."""
        if not self.antipatterns:
            return "(no known antipatterns yet)"
        lines = []
        for ap in sorted(self.antipatterns, key=lambda x: -x.occurrences):
            lines.append(
                f"- **{ap.id}: {ap.name}** (seen {ap.occurrences}x) — "
                f"{ap.description}. Detection: {ap.detection}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Drift Debt — spec-to-code divergence tracking
# ---------------------------------------------------------------------------

class DriftItem(BaseModel):
    """A place where code has diverged from its spec."""

    id: str                          # DRIFT-001, etc.
    spec_file: str                   # Which spec
    spec_rule: str                   # Which rule diverged
    description: str                 # What drifted
    detected_at: str = ""
    detected_by: str = ""            # Phase that caught it (verify, audit)
    status: str = "open"             # open, resolved, accepted
    resolution: str = ""
    resolved_at: str = ""


class DriftDebtTracker(BaseModel):
    """Tracks spec-to-code drift across the project."""

    items: list[DriftItem] = Field(default_factory=list)

    def add(self, item: DriftItem) -> DriftItem:
        if not item.id:
            item.id = f"DRIFT-{len(self.items) + 1:03d}"
        if not item.detected_at:
            item.detected_at = _now()
        self.items.append(item)
        return item

    def resolve(self, drift_id: str, resolution: str) -> None:
        for item in self.items:
            if item.id == drift_id:
                item.status = "resolved"
                item.resolution = resolution
                item.resolved_at = _now()
                return
        raise KeyError(f"Drift item {drift_id} not found")

    def open_items(self) -> list[DriftItem]:
        return [i for i in self.items if i.status == "open"]

    def as_prompt_context(self) -> str:
        open_items = self.open_items()
        if not open_items:
            return "(no open drift debt)"
        lines = []
        for item in open_items:
            lines.append(
                f"- **{item.id}**: {item.spec_file} rule {item.spec_rule} — "
                f"{item.description} (since {item.detected_at[:10]})"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Decision Log — preserving WHY choices were made
# ---------------------------------------------------------------------------

class Decision(BaseModel):
    """A design or implementation decision with rationale."""

    id: str
    title: str                       # Short: "Use bcrypt over argon2"
    context: str                     # What prompted this decision
    decision: str                    # What was decided
    rationale: str                   # WHY — this is the valuable part
    alternatives: list[str] = Field(default_factory=list)  # What was considered
    consequences: list[str] = Field(default_factory=list)  # What follows from this
    feature: str = ""                # Which feature
    phase: str = ""                  # Which phase made this decision
    timestamp: str = ""
    status: str = "active"           # active, superseded, deprecated
    superseded_by: str = ""          # ID of replacement decision


class DecisionLog(BaseModel):
    """Architectural Decision Records (ADRs) — lightweight version."""

    decisions: list[Decision] = Field(default_factory=list)

    def add(self, decision: Decision) -> Decision:
        if not decision.id:
            decision.id = f"DEC-{len(self.decisions) + 1:03d}"
        if not decision.timestamp:
            decision.timestamp = _now()
        self.decisions.append(decision)
        return decision

    def active(self) -> list[Decision]:
        return [d for d in self.decisions if d.status == "active"]

    def for_feature(self, feature: str) -> list[Decision]:
        return [d for d in self.decisions if d.feature == feature]

    def as_prompt_context(self) -> str:
        active = self.active()
        if not active:
            return "(no active decisions recorded)"
        lines = []
        for d in active[-20:]:  # Last 20 active decisions
            lines.append(f"- **{d.id}: {d.title}** — {d.decision} (reason: {d.rationale})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase Effectiveness — measuring what catches bugs
# ---------------------------------------------------------------------------

class PhaseMetrics(BaseModel):
    """Metrics for a single phase execution."""

    phase: str
    feature: str
    branch: str
    started_at: str = ""
    completed_at: str = ""
    findings_count: int = 0
    blocking_count: int = 0
    duration_seconds: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0
    model: str = ""
    outcome: str = ""                # "pass", "fail", "revise"


class EffectivenessTracker(BaseModel):
    """Tracks which phases catch the most bugs, informing future intensity."""

    metrics: list[PhaseMetrics] = Field(default_factory=list)

    def record(self, m: PhaseMetrics) -> None:
        if not m.completed_at:
            m.completed_at = _now()
        self.metrics.append(m)

    def phase_summary(self) -> dict[str, dict]:
        """Aggregate metrics by phase."""
        summary: dict[str, dict] = {}
        for m in self.metrics:
            if m.phase not in summary:
                summary[m.phase] = {
                    "total_runs": 0, "total_findings": 0,
                    "total_blocking": 0, "total_cost": 0.0,
                }
            s = summary[m.phase]
            s["total_runs"] += 1
            s["total_findings"] += m.findings_count
            s["total_blocking"] += m.blocking_count
            s["total_cost"] += m.cost_usd
        return summary

    def feature_cost(self, feature: str) -> float:
        return sum(m.cost_usd for m in self.metrics if m.feature == feature)

    def as_prompt_context(self) -> str:
        summary = self.phase_summary()
        if not summary:
            return "(no effectiveness data yet)"
        lines = ["Phase effectiveness (historical):"]
        for phase, s in sorted(summary.items()):
            avg_findings = s["total_findings"] / max(s["total_runs"], 1)
            lines.append(
                f"- {phase}: {s['total_runs']} runs, "
                f"avg {avg_findings:.1f} findings/run, "
                f"${s['total_cost']:.2f} total"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Knowledge Store — unified access to all structured knowledge
# ---------------------------------------------------------------------------

class KnowledgeStore:
    """Reads and writes all structured knowledge files.

    Everything lives under .correctless/ as JSON files. Each store is a
    Pydantic model that serializes/deserializes cleanly.

    Directory layout:
        .correctless/
        ├── knowledge/
        │   ├── findings.json          # All findings across all features
        │   ├── antipatterns.json       # Growing bug pattern registry
        │   ├── drift-debt.json         # Spec-to-code divergence
        │   ├── decisions.json          # ADRs
        │   └── effectiveness.json      # Phase metrics
        ├── specs/                      # Spec files per feature
        ├── verification/               # Verification reports
        ├── artifacts/                  # Workflow state (ephemeral)
        └── config/                     # Project config
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.knowledge_dir = repo_root / ".correctless" / "knowledge"
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

    def _load(self, model_cls, filename: str):
        path = self.knowledge_dir / filename
        if path.exists():
            try:
                return model_cls.model_validate_json(path.read_text())
            except Exception:
                # Corrupted file — start fresh but keep backup
                backup = path.with_suffix(".json.bak")
                path.rename(backup)
        return model_cls()

    def _save(self, model: BaseModel, filename: str) -> None:
        path = self.knowledge_dir / filename
        path.write_text(model.model_dump_json(indent=2) + "\n")

    # --- Findings ---
    def findings(self) -> FindingsLog:
        return self._load(FindingsLog, "findings.json")

    def save_findings(self, log: FindingsLog) -> None:
        self._save(log, "findings.json")

    # --- Antipatterns ---
    def antipatterns(self) -> AntipatternRegistry:
        return self._load(AntipatternRegistry, "antipatterns.json")

    def save_antipatterns(self, registry: AntipatternRegistry) -> None:
        self._save(registry, "antipatterns.json")

    # --- Drift Debt ---
    def drift_debt(self) -> DriftDebtTracker:
        return self._load(DriftDebtTracker, "drift-debt.json")

    def save_drift_debt(self, tracker: DriftDebtTracker) -> None:
        self._save(tracker, "drift-debt.json")

    # --- Decisions ---
    def decisions(self) -> DecisionLog:
        return self._load(DecisionLog, "decisions.json")

    def save_decisions(self, log: DecisionLog) -> None:
        self._save(log, "decisions.json")

    # --- Effectiveness ---
    def effectiveness(self) -> EffectivenessTracker:
        return self._load(EffectivenessTracker, "effectiveness.json")

    def save_effectiveness(self, tracker: EffectivenessTracker) -> None:
        self._save(tracker, "effectiveness.json")

    # --- Composite context for agents ---
    def agent_context(self) -> str:
        """Build the full knowledge context string for agent system prompts.

        This is what makes every cycle smarter: the spec agent sees
        antipatterns, drift debt, decisions, and effectiveness data
        from ALL previous features.
        """
        sections = []

        ap = self.antipatterns()
        if ap.antipatterns:
            sections.append(f"## Known Antipatterns\n{ap.as_prompt_context()}")

        drift = self.drift_debt()
        if drift.open_items():
            sections.append(f"## Open Drift Debt\n{drift.as_prompt_context()}")

        dec = self.decisions()
        if dec.active():
            sections.append(f"## Active Decisions\n{dec.as_prompt_context()}")

        eff = self.effectiveness()
        if eff.metrics:
            sections.append(f"## Phase Effectiveness\n{eff.as_prompt_context()}")

        # Recent unresolved findings (last 10)
        findings = self.findings()
        unresolved = findings.unresolved()[-10:]
        if unresolved:
            lines = [f"- {f.id} ({f.severity}): {f.finding}" for f in unresolved]
            sections.append(f"## Recent Unresolved Findings\n" + "\n".join(lines))

        return "\n\n".join(sections) if sections else ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

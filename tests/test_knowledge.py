"""Tests for the knowledge persistence layer."""

import json
import pytest
from pathlib import Path

from correctless.knowledge import (
    Finding,
    FindingsLog,
    Antipattern,
    AntipatternRegistry,
    DriftItem,
    DriftDebtTracker,
    Decision,
    DecisionLog,
    PhaseMetrics,
    EffectivenessTracker,
    KnowledgeStore,
)


class TestFindingsLog:
    """Finding CRUD and querying."""

    def test_add_finding_auto_id(self):
        log = FindingsLog()
        f = log.add(Finding(id="", phase="review", severity="HIGH", category="testability", finding="R-001 untestable"))
        assert f.id.startswith("REV-")
        assert f.timestamp != ""

    def test_add_finding_explicit_id(self):
        log = FindingsLog()
        f = log.add(Finding(id="QA-042", phase="qa", severity="BLOCKING", category="correctness", finding="wrong"))
        assert f.id == "QA-042"

    def test_resolve_finding(self):
        log = FindingsLog()
        f = log.add(Finding(id="", phase="qa", severity="HIGH", category="coverage", finding="missing test"))
        log.resolve(f.id, "Added test_R003")
        assert log.findings[0].resolved
        assert log.findings[0].resolution == "Added test_R003"

    def test_resolve_nonexistent_raises(self):
        log = FindingsLog()
        with pytest.raises(KeyError):
            log.resolve("NOPE-999", "fix")

    def test_unresolved(self):
        log = FindingsLog()
        log.add(Finding(id="", phase="qa", severity="HIGH", category="x", finding="a"))
        f2 = log.add(Finding(id="", phase="qa", severity="LOW", category="x", finding="b"))
        log.resolve(f2.id, "fixed")
        assert len(log.unresolved()) == 1

    def test_by_category(self):
        log = FindingsLog()
        log.add(Finding(id="", phase="qa", severity="HIGH", category="coverage", finding="a"))
        log.add(Finding(id="", phase="qa", severity="LOW", category="security", finding="b"))
        log.add(Finding(id="", phase="qa", severity="MEDIUM", category="coverage", finding="c"))
        cats = log.by_category()
        assert len(cats["coverage"]) == 2
        assert len(cats["security"]) == 1

    def test_severity_summary(self):
        log = FindingsLog()
        log.add(Finding(id="", phase="qa", severity="HIGH", category="x", finding="a"))
        log.add(Finding(id="", phase="qa", severity="HIGH", category="x", finding="b"))
        log.add(Finding(id="", phase="qa", severity="LOW", category="x", finding="c"))
        summary = log.severity_summary()
        assert summary["HIGH"] == 2
        assert summary["LOW"] == 1

    def test_by_feature(self):
        log = FindingsLog()
        log.add(Finding(id="", phase="qa", severity="HIGH", category="x", finding="a", feature="auth"))
        log.add(Finding(id="", phase="qa", severity="LOW", category="x", finding="b", feature="dashboard"))
        assert len(log.by_feature("auth")) == 1


class TestAntipatternRegistry:
    """Antipattern tracking and prompt context generation."""

    def test_add_antipattern(self):
        reg = AntipatternRegistry()
        ap = reg.add(Antipattern(
            id="", name="bcrypt cost", description="Wrong cost factor",
            detection="Check cost factor in bcrypt calls",
        ))
        assert ap.id == "AP-001"
        assert ap.occurrences == 1

    def test_bump_occurrence(self):
        reg = AntipatternRegistry()
        ap = reg.add(Antipattern(id="", name="test", description="d", detection="det"))
        reg.bump(ap.id)
        assert reg.antipatterns[0].occurrences == 2

    def test_as_prompt_context_empty(self):
        reg = AntipatternRegistry()
        assert "no known antipatterns" in reg.as_prompt_context()

    def test_as_prompt_context_populated(self):
        reg = AntipatternRegistry()
        reg.add(Antipattern(id="", name="SQL injection", description="Unparameterized queries", detection="Check for string concat in SQL"))
        ctx = reg.as_prompt_context()
        assert "AP-001" in ctx
        assert "SQL injection" in ctx


class TestDriftDebtTracker:
    """Spec-to-code drift tracking."""

    def test_add_drift_item(self):
        tracker = DriftDebtTracker()
        item = tracker.add(DriftItem(
            id="", spec_file="specs/auth.md", spec_rule="R-003",
            description="Impl doesn't check empty password",
        ))
        assert item.id == "DRIFT-001"
        assert item.status == "open"

    def test_resolve_drift(self):
        tracker = DriftDebtTracker()
        item = tracker.add(DriftItem(id="", spec_file="s", spec_rule="R-1", description="d"))
        tracker.resolve(item.id, "Added validation")
        assert tracker.items[0].status == "resolved"

    def test_open_items(self):
        tracker = DriftDebtTracker()
        tracker.add(DriftItem(id="", spec_file="s", spec_rule="R-1", description="a"))
        item2 = tracker.add(DriftItem(id="", spec_file="s", spec_rule="R-2", description="b"))
        tracker.resolve(item2.id, "fixed")
        assert len(tracker.open_items()) == 1


class TestDecisionLog:
    """Architectural decision records."""

    def test_add_decision(self):
        log = DecisionLog()
        d = log.add(Decision(
            id="", title="Use bcrypt", context="Need password hashing",
            decision="Use bcrypt with cost 12", rationale="Industry standard",
        ))
        assert d.id == "DEC-001"

    def test_active_decisions(self):
        log = DecisionLog()
        log.add(Decision(id="", title="A", context="c", decision="d", rationale="r"))
        d2 = log.add(Decision(id="", title="B", context="c", decision="d", rationale="r", status="superseded"))
        assert len(log.active()) == 1


class TestEffectivenessTracker:
    """Phase metrics tracking."""

    def test_record_metrics(self):
        tracker = EffectivenessTracker()
        tracker.record(PhaseMetrics(
            phase="tdd-qa", feature="auth", branch="feat/auth",
            findings_count=3, blocking_count=1, cost_usd=0.05,
        ))
        assert len(tracker.metrics) == 1
        assert tracker.metrics[0].completed_at != ""

    def test_phase_summary(self):
        tracker = EffectivenessTracker()
        tracker.record(PhaseMetrics(phase="tdd-qa", feature="a", branch="b", findings_count=3, cost_usd=0.05))
        tracker.record(PhaseMetrics(phase="tdd-qa", feature="c", branch="d", findings_count=1, cost_usd=0.03))
        tracker.record(PhaseMetrics(phase="review", feature="a", branch="b", findings_count=5, cost_usd=0.10))
        summary = tracker.phase_summary()
        assert summary["tdd-qa"]["total_runs"] == 2
        assert summary["tdd-qa"]["total_findings"] == 4
        assert summary["review"]["total_runs"] == 1

    def test_feature_cost(self):
        tracker = EffectivenessTracker()
        tracker.record(PhaseMetrics(phase="qa", feature="auth", branch="b", cost_usd=0.10))
        tracker.record(PhaseMetrics(phase="review", feature="auth", branch="b", cost_usd=0.05))
        tracker.record(PhaseMetrics(phase="qa", feature="other", branch="c", cost_usd=0.20))
        assert tracker.feature_cost("auth") == pytest.approx(0.15)


class TestKnowledgeStore:
    """Unified knowledge store persistence."""

    def test_round_trip_findings(self, tmp_path):
        ks = KnowledgeStore(tmp_path)
        log = ks.findings()
        log.add(Finding(id="", phase="qa", severity="HIGH", category="x", finding="test"))
        ks.save_findings(log)

        log2 = ks.findings()
        assert len(log2.findings) == 1
        assert log2.findings[0].finding == "test"

    def test_round_trip_antipatterns(self, tmp_path):
        ks = KnowledgeStore(tmp_path)
        reg = ks.antipatterns()
        reg.add(Antipattern(id="", name="test", description="d", detection="det"))
        ks.save_antipatterns(reg)

        reg2 = ks.antipatterns()
        assert len(reg2.antipatterns) == 1

    def test_corrupt_file_recovery(self, tmp_path):
        ks = KnowledgeStore(tmp_path)
        # Write corrupt JSON
        corrupt_path = tmp_path / ".correctless" / "knowledge" / "findings.json"
        corrupt_path.write_text("NOT VALID JSON {{{")

        log = ks.findings()
        assert len(log.findings) == 0
        # Backup should exist
        assert corrupt_path.with_suffix(".json.bak").exists()

    def test_agent_context_empty(self, tmp_path):
        ks = KnowledgeStore(tmp_path)
        assert ks.agent_context() == ""

    def test_agent_context_populated(self, tmp_path):
        ks = KnowledgeStore(tmp_path)
        reg = ks.antipatterns()
        reg.add(Antipattern(id="", name="sql-inj", description="SQL injection", detection="check"))
        ks.save_antipatterns(reg)

        ctx = ks.agent_context()
        assert "Antipatterns" in ctx
        assert "sql-inj" in ctx

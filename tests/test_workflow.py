"""Tests for the workflow state machine."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from correctless.workflow import (
    Phase,
    WorkflowState,
    WorkflowStore,
    WorkflowError,
    TRANSITIONS,
    SPEC_UPDATE_PHASES,
    init_workflow,
    _branch_slug,
)


class TestPhaseTransitions:
    """Verify the state machine allows only valid transitions."""

    def test_none_to_spec(self):
        state = WorkflowState()
        state.advance(Phase.SPEC)
        assert state.phase == Phase.SPEC

    def test_spec_to_review(self):
        state = WorkflowState(phase=Phase.SPEC)
        state.advance(Phase.REVIEW)
        assert state.phase == Phase.REVIEW

    def test_review_to_tdd_red(self):
        state = WorkflowState(phase=Phase.REVIEW)
        state.advance(Phase.TDD_RED)
        assert state.phase == Phase.TDD_RED

    def test_review_can_reject_back_to_spec(self):
        state = WorkflowState(phase=Phase.REVIEW)
        state.advance(Phase.SPEC)
        assert state.phase == Phase.SPEC

    def test_tdd_red_to_green(self):
        state = WorkflowState(phase=Phase.TDD_RED)
        state.advance(Phase.TDD_GREEN)
        assert state.phase == Phase.TDD_GREEN

    def test_tdd_green_to_qa(self):
        state = WorkflowState(phase=Phase.TDD_GREEN)
        state.advance(Phase.TDD_QA)
        assert state.phase == Phase.TDD_QA

    def test_qa_can_return_to_green(self):
        state = WorkflowState(phase=Phase.TDD_QA)
        state.advance(Phase.TDD_GREEN)
        assert state.phase == Phase.TDD_GREEN

    def test_qa_can_advance_to_verify(self):
        state = WorkflowState(phase=Phase.TDD_QA)
        state.advance(Phase.VERIFY)
        assert state.phase == Phase.VERIFY

    def test_verify_to_docs(self):
        state = WorkflowState(phase=Phase.VERIFY)
        state.advance(Phase.DOCS)
        assert state.phase == Phase.DOCS

    def test_verify_can_return_to_green(self):
        state = WorkflowState(phase=Phase.VERIFY)
        state.advance(Phase.TDD_GREEN)
        assert state.phase == Phase.TDD_GREEN

    def test_docs_to_done(self):
        state = WorkflowState(phase=Phase.DOCS)
        state.advance(Phase.DONE)
        assert state.phase == Phase.DONE

    def test_done_is_terminal(self):
        state = WorkflowState(phase=Phase.DONE)
        with pytest.raises(WorkflowError, match="Cannot move"):
            state.advance(Phase.SPEC)

    def test_invalid_transition_raises(self):
        state = WorkflowState(phase=Phase.SPEC)
        with pytest.raises(WorkflowError, match="Cannot move"):
            state.advance(Phase.TDD_RED)  # Must go through REVIEW

    def test_skip_review_not_allowed(self):
        state = WorkflowState(phase=Phase.SPEC)
        with pytest.raises(WorkflowError):
            state.advance(Phase.TDD_GREEN)

    def test_all_phases_have_transition_entries(self):
        for phase in Phase:
            assert phase in TRANSITIONS


class TestQARounds:
    """QA round counting."""

    def test_qa_round_increments_on_enter(self):
        state = WorkflowState(phase=Phase.TDD_GREEN)
        state.advance(Phase.TDD_QA)
        assert state.qa_rounds == 1

    def test_multiple_qa_rounds(self):
        state = WorkflowState(phase=Phase.TDD_GREEN)
        state.advance(Phase.TDD_QA)  # round 1
        state.advance(Phase.TDD_GREEN)  # fix
        state.advance(Phase.TDD_QA)  # round 2
        assert state.qa_rounds == 2


class TestSpecUpdate:
    """Mid-TDD spec revision."""

    def test_spec_update_from_tdd_red(self):
        state = WorkflowState(phase=Phase.TDD_RED)
        state.spec_update("Rule R-003 was wrong")
        assert state.phase == Phase.SPEC
        assert state.spec_updates == 1
        assert len(state.spec_update_history) == 1
        assert state.spec_update_history[0].reason == "Rule R-003 was wrong"

    def test_spec_update_from_tdd_green(self):
        state = WorkflowState(phase=Phase.TDD_GREEN)
        state.spec_update("Missing edge case")
        assert state.phase == Phase.SPEC

    def test_spec_update_not_allowed_from_review(self):
        state = WorkflowState(phase=Phase.REVIEW)
        with pytest.raises(WorkflowError, match="Cannot revise spec"):
            state.spec_update("nope")

    def test_spec_update_not_allowed_from_verify(self):
        state = WorkflowState(phase=Phase.VERIFY)
        with pytest.raises(WorkflowError, match="Cannot revise spec"):
            state.spec_update("nope")

    def test_spec_update_allowed_phases(self):
        for phase in SPEC_UPDATE_PHASES:
            state = WorkflowState(phase=phase)
            state.spec_update("test reason")
            assert state.phase == Phase.SPEC


class TestWorkflowStore:
    """State persistence."""

    def test_save_and_load(self, tmp_path):
        with patch("correctless.workflow._find_repo_root", return_value=tmp_path), \
             patch("correctless.workflow._current_branch", return_value="feature/test"):
            store = WorkflowStore(tmp_path)
            state = WorkflowState(
                phase=Phase.SPEC,
                task="test task",
                branch="feature/test",
            )
            store.save(state)
            loaded = store.load()
            assert loaded.phase == Phase.SPEC
            assert loaded.task == "test task"

    def test_load_nonexistent_returns_default(self, tmp_path):
        with patch("correctless.workflow._current_branch", return_value="feature/x"):
            store = WorkflowStore(tmp_path)
            state = store.load()
            assert state.phase == Phase.NONE

    def test_reset_clears_state(self, tmp_path):
        with patch("correctless.workflow._current_branch", return_value="feature/test"):
            store = WorkflowStore(tmp_path)
            state = WorkflowState(phase=Phase.SPEC, task="t", branch="feature/test")
            store.save(state)
            store.reset()
            loaded = store.load()
            assert loaded.phase == Phase.NONE

    def test_all_active(self, tmp_path):
        artifacts = tmp_path / ".correctless" / "artifacts"
        artifacts.mkdir(parents=True)
        for i, branch in enumerate(["feat-a", "feat-b"]):
            state = WorkflowState(phase=Phase.SPEC, task=f"task-{i}", branch=branch)
            path = artifacts / f"workflow-state-{branch}.json"
            path.write_text(state.model_dump_json(indent=2))

        store = WorkflowStore(tmp_path)
        active = store.all_active()
        assert len(active) == 2


class TestBranchSlug:
    """Branch name slugification."""

    def test_simple_branch(self):
        slug = _branch_slug("feature/add-auth")
        assert "feature-add-auth" in slug

    def test_long_branch_truncated(self):
        slug = _branch_slug("a" * 200)
        assert len(slug) <= 89  # 80 chars + dash + 8 char hash

    def test_different_branches_different_slugs(self):
        assert _branch_slug("feat/a") != _branch_slug("feat/b")


class TestInitWorkflow:
    """Workflow initialization."""

    def test_refuses_main_branch(self, tmp_path):
        with patch("correctless.workflow._current_branch", return_value="main"):
            store = WorkflowStore(tmp_path)
            with pytest.raises(WorkflowError, match="Cannot start workflow on 'main'"):
                init_workflow(store, "test task")

    def test_refuses_master_branch(self, tmp_path):
        with patch("correctless.workflow._current_branch", return_value="master"):
            store = WorkflowStore(tmp_path)
            with pytest.raises(WorkflowError, match="Cannot start workflow on 'master'"):
                init_workflow(store, "test task")

    def test_refuses_if_workflow_active(self, tmp_path):
        with patch("correctless.workflow._current_branch", return_value="feature/x"):
            store = WorkflowStore(tmp_path)
            state = WorkflowState(phase=Phase.SPEC, task="existing", branch="feature/x")
            store.save(state)
            with pytest.raises(WorkflowError, match="already active"):
                init_workflow(store, "new task")

    def test_creates_spec_file(self, tmp_path):
        with patch("correctless.workflow._current_branch", return_value="feature/test"):
            store = WorkflowStore(tmp_path)
            state = init_workflow(store, "add user authentication")
            assert state.phase == Phase.SPEC
            spec_path = tmp_path / state.spec_file
            assert spec_path.exists()
            assert "add user authentication" in spec_path.read_text()

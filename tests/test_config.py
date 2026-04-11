"""Tests for project configuration detection."""

import json
import pytest
from pathlib import Path

from correctless.config import ProjectConfig, _detect_language


class TestLanguageDetection:
    """Auto-detect project language from marker files."""

    def test_detect_python(self, tmp_path):
        (tmp_path / "pyproject.toml").touch()
        assert _detect_language(tmp_path) == "python"

    def test_detect_go(self, tmp_path):
        (tmp_path / "go.mod").touch()
        assert _detect_language(tmp_path) == "go"

    def test_detect_typescript(self, tmp_path):
        (tmp_path / "package.json").touch()
        assert _detect_language(tmp_path) == "typescript"

    def test_detect_rust(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        assert _detect_language(tmp_path) == "rust"

    def test_detect_java(self, tmp_path):
        (tmp_path / "pom.xml").touch()
        assert _detect_language(tmp_path) == "java"

    def test_detect_unknown(self, tmp_path):
        assert _detect_language(tmp_path) == "other"

    def test_priority_go_over_python(self, tmp_path):
        """go.mod checked before pyproject.toml."""
        (tmp_path / "go.mod").touch()
        (tmp_path / "pyproject.toml").touch()
        assert _detect_language(tmp_path) == "go"


class TestProjectConfig:
    """Config detection, loading, and saving."""

    def test_detect_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").touch()
        config = ProjectConfig.detect(tmp_path)
        assert config.project.language == "python"
        assert config.commands.test == "pytest"
        assert config.commands.lint == "ruff check ."
        assert "test_*.py" in config.patterns.test_file

    def test_detect_go_project(self, tmp_path):
        (tmp_path / "go.mod").touch()
        config = ProjectConfig.detect(tmp_path)
        assert config.project.language == "go"
        assert config.commands.test == "go test ./..."

    def test_save_and_load(self, tmp_path):
        config = ProjectConfig.detect(tmp_path)
        config.project.name = "my-project"
        config.save(tmp_path)

        loaded = ProjectConfig.load(tmp_path)
        assert loaded.project.name == "my-project"
        assert loaded.project.language == config.project.language

    def test_load_falls_back_to_detect(self, tmp_path):
        (tmp_path / "Cargo.toml").touch()
        config = ProjectConfig.load(tmp_path)
        assert config.project.language == "rust"

    def test_project_name_from_dir(self, tmp_path):
        config = ProjectConfig.detect(tmp_path)
        assert config.project.name == tmp_path.name

    def test_config_file_location(self, tmp_path):
        config = ProjectConfig.detect(tmp_path)
        config.save(tmp_path)
        expected = tmp_path / ".correctless" / "config" / "workflow-config.json"
        assert expected.exists()
        data = json.loads(expected.read_text())
        assert data["project"]["language"] == "other"

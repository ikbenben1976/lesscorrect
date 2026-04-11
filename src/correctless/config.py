"""Project configuration detection and management.

Replaces the bash setup script's detect_language/detect_config functions
with a typed Python equivalent.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    """Project-level configuration for Correctless."""

    class Project(BaseModel):
        name: str = ""
        language: str = "other"
        description: str = ""

    class Commands(BaseModel):
        test: str = ""
        test_verbose: str = ""
        coverage: str = ""
        lint: str = ""
        build: str = ""

    class Patterns(BaseModel):
        test_file: str = ""
        source_file: str = ""

    project: Project = Field(default_factory=Project)
    commands: Commands = Field(default_factory=Commands)
    patterns: Patterns = Field(default_factory=Patterns)

    @classmethod
    def detect(cls, repo_root: Path) -> "ProjectConfig":
        """Auto-detect project language and configuration."""
        name = repo_root.name
        lang = _detect_language(repo_root)
        config = _LANG_CONFIGS.get(lang, _LANG_CONFIGS["other"])
        return cls(
            project=cls.Project(name=name, language=lang),
            commands=cls.Commands(**config["commands"]),
            patterns=cls.Patterns(**config["patterns"]),
        )

    @classmethod
    def load(cls, repo_root: Path) -> "ProjectConfig":
        """Load from .correctless/config/workflow-config.json, or detect."""
        config_path = repo_root / ".correctless" / "config" / "workflow-config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            return cls.model_validate(data)
        return cls.detect(repo_root)

    def save(self, repo_root: Path) -> None:
        config_dir = repo_root / ".correctless" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "workflow-config.json"
        config_path.write_text(self.model_dump_json(indent=2) + "\n")


def _detect_language(repo_root: Path) -> str:
    checks = [
        ("go.mod", "go"),
        ("Cargo.toml", "rust"),
        ("package.json", "typescript"),
        ("pyproject.toml", "python"),
        ("requirements.txt", "python"),
        ("setup.py", "python"),
        ("pom.xml", "java"),
        ("build.gradle", "java"),
    ]
    for filename, lang in checks:
        if (repo_root / filename).exists():
            return lang
    return "other"


_LANG_CONFIGS: dict[str, dict] = {
    "go": {
        "commands": {
            "test": "go test ./...",
            "test_verbose": "go test -v ./...",
            "coverage": "go test -coverprofile=coverage.out ./...",
            "lint": "go vet ./...",
            "build": "go build ./...",
        },
        "patterns": {
            "test_file": "*_test.go",
            "source_file": "*.go",
        },
    },
    "typescript": {
        "commands": {
            "test": "npm test",
            "test_verbose": "npm test -- --verbose",
            "coverage": "npm test -- --coverage",
            "lint": "npm run lint",
            "build": "npm run build",
        },
        "patterns": {
            "test_file": "*.test.ts|*.test.tsx|*.spec.ts|*.spec.tsx",
            "source_file": "*.ts|*.tsx",
        },
    },
    "python": {
        "commands": {
            "test": "pytest",
            "test_verbose": "pytest -v",
            "coverage": "pytest --cov",
            "lint": "ruff check .",
            "build": "",
        },
        "patterns": {
            "test_file": "test_*.py|*_test.py",
            "source_file": "*.py",
        },
    },
    "rust": {
        "commands": {
            "test": "cargo test",
            "test_verbose": "cargo test -- --nocapture",
            "coverage": "cargo tarpaulin",
            "lint": "cargo clippy",
            "build": "cargo build",
        },
        "patterns": {
            "test_file": "*_test.rs|tests/*.rs",
            "source_file": "*.rs",
        },
    },
    "java": {
        "commands": {
            "test": "mvn test",
            "test_verbose": "mvn test -X",
            "coverage": "mvn jacoco:report",
            "lint": "",
            "build": "mvn package",
        },
        "patterns": {
            "test_file": "*Test.java|*Tests.java",
            "source_file": "*.java",
        },
    },
    "other": {
        "commands": {
            "test": "",
            "test_verbose": "",
            "coverage": "",
            "lint": "",
            "build": "",
        },
        "patterns": {
            "test_file": "",
            "source_file": "",
        },
    },
}

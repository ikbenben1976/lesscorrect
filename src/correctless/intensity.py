"""Intensity system — controls behavioral depth, not model selection.

Correctless v4 uses three intensity levels that gate how much rigor
each phase applies. The user picks the model; intensity controls:

- How many spec sections are required
- Whether research agents are activated
- STRIDE analysis depth
- QA round caps
- Mutation testing requirements
- Calm reset thresholds
- Adversarial review agent count

Effective intensity = max(project_intensity, feature_intensity)

Feature intensity is detected from 4 signals:
1. File paths (security/, auth/, payment/, crypto/)
2. Keywords in the spec (PII, credential, token, secret, etc.)
3. Trust boundary crossings (API endpoints, user input handlers)
4. Historical antipattern/QA density for similar features
"""

from __future__ import annotations

import re
from enum import IntEnum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Intensity(IntEnum):
    """Behavioral intensity levels. Higher = more rigor."""

    STANDARD = 1
    HIGH = 2
    CRITICAL = 3

    @classmethod
    def from_str(cls, s: str) -> "Intensity":
        return cls[s.upper()]


# ---------------------------------------------------------------------------
# Per-intensity behavior parameters
# ---------------------------------------------------------------------------

class IntensityParams(BaseModel):
    """What changes at each intensity level."""

    # Spec phase
    spec_sections_required: list[str] = Field(default_factory=list)
    research_agents: bool = False

    # Review phase
    review_agent_count: int = 1
    stride_analysis: bool = False

    # TDD phase
    min_qa_rounds: int = 1
    max_qa_rounds: int = 3
    mutation_testing: bool = False
    test_audit_required: bool = False

    # Verify phase
    calm_reset_threshold: int = 3

    # Audit
    audit_agents: int = 0


# Preset configurations per intensity level
INTENSITY_PARAMS: dict[Intensity, IntensityParams] = {
    Intensity.STANDARD: IntensityParams(
        spec_sections_required=["Context", "Rules", "Edge cases"],
        research_agents=False,
        review_agent_count=1,
        stride_analysis=False,
        min_qa_rounds=1,
        max_qa_rounds=3,
        mutation_testing=False,
        test_audit_required=False,
        calm_reset_threshold=3,
        audit_agents=0,
    ),
    Intensity.HIGH: IntensityParams(
        spec_sections_required=[
            "Context", "Rules", "Prohibitions", "Edge cases",
            "Failure modes", "Dependencies",
        ],
        research_agents=True,
        review_agent_count=2,
        stride_analysis=True,
        min_qa_rounds=2,
        max_qa_rounds=5,
        mutation_testing=False,
        test_audit_required=True,
        calm_reset_threshold=5,
        audit_agents=2,
    ),
    Intensity.CRITICAL: IntensityParams(
        spec_sections_required=[
            "Context", "Rules", "Prohibitions", "Edge cases",
            "Failure modes", "Dependencies", "Security model",
            "Rollback plan",
        ],
        research_agents=True,
        review_agent_count=3,
        stride_analysis=True,
        min_qa_rounds=3,
        max_qa_rounds=8,
        mutation_testing=True,
        test_audit_required=True,
        calm_reset_threshold=8,
        audit_agents=4,
    ),
}


# ---------------------------------------------------------------------------
# Feature intensity detection (4 signals)
# ---------------------------------------------------------------------------

# Signal 1: File paths that suggest higher intensity
_HIGH_PATHS = re.compile(
    r"(security|auth|crypto|payment|billing|admin|rbac|acl|permission|oauth|saml|jwt)",
    re.IGNORECASE,
)
_CRITICAL_PATHS = re.compile(
    r"(crypto|payment|billing|key[-_]?manage|secret[-_]?store|certificate)",
    re.IGNORECASE,
)

# Signal 2: Spec keywords
_HIGH_KEYWORDS = {
    "pii", "credential", "token", "secret", "password", "authentication",
    "authorization", "encrypt", "decrypt", "hash", "permission", "role",
    "session", "cookie", "csrf", "xss", "injection", "sanitize",
    "trust boundary", "rate limit", "api key",
}
_CRITICAL_KEYWORDS = {
    "payment", "billing", "credit card", "ssn", "social security",
    "hipaa", "pci", "gdpr", "sox", "financial", "cryptographic",
    "private key", "certificate", "compliance",
}

# Signal 3: Trust boundary patterns (file content indicators)
_TRUST_BOUNDARY_PATTERNS = re.compile(
    r"(request\.|req\.|ctx\.|user_input|form_data|query_param|"
    r"@app\.route|@router\.|func.*http\.Request|"
    r"api\.Handle|grpc\.Server|websocket)",
    re.IGNORECASE,
)


def detect_feature_intensity(
    spec_content: str = "",
    affected_paths: list[str] | None = None,
    historical_finding_density: float = 0.0,
) -> Intensity:
    """Detect the appropriate intensity for a feature from 4 signals.

    Args:
        spec_content: The specification text to analyze.
        affected_paths: File paths that will be modified.
        historical_finding_density: Average findings per QA round
            for similar features (from effectiveness tracker).

    Returns:
        The detected intensity level.
    """
    score = 0  # 0 = standard, 1-2 = high, 3+ = critical

    # Signal 1: File paths
    paths = affected_paths or []
    for p in paths:
        if _CRITICAL_PATHS.search(p):
            score += 2
        elif _HIGH_PATHS.search(p):
            score += 1

    # Signal 2: Spec keywords
    spec_lower = spec_content.lower()
    for kw in _CRITICAL_KEYWORDS:
        if kw in spec_lower:
            score += 2
            break
    for kw in _HIGH_KEYWORDS:
        if kw in spec_lower:
            score += 1
            break

    # Signal 3: Trust boundary crossings (checked via spec content)
    if _TRUST_BOUNDARY_PATTERNS.search(spec_content):
        score += 1

    # Signal 4: Historical finding density
    if historical_finding_density > 3.0:
        score += 2
    elif historical_finding_density > 1.5:
        score += 1

    # Map score to intensity
    if score >= 3:
        return Intensity.CRITICAL
    elif score >= 1:
        return Intensity.HIGH
    return Intensity.STANDARD


def effective_intensity(
    project_intensity: Intensity,
    feature_intensity: Intensity,
) -> Intensity:
    """Effective intensity = max(project, feature)."""
    return Intensity(max(project_intensity.value, feature_intensity.value))


def get_params(intensity: Intensity) -> IntensityParams:
    """Get the behavioral parameters for an intensity level."""
    return INTENSITY_PARAMS[intensity]


# ---------------------------------------------------------------------------
# Intensity configuration persistence
# ---------------------------------------------------------------------------

class IntensityConfig(BaseModel):
    """Project-level intensity settings."""

    project_intensity: str = "standard"
    calibration_mode: str = "passive"  # passive, active, hybrid

    def get_project_intensity(self) -> Intensity:
        return Intensity.from_str(self.project_intensity)

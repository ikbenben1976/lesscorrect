"""Tests for the intensity detection and gating system."""

import pytest

from correctless.intensity import (
    Intensity,
    IntensityConfig,
    IntensityParams,
    INTENSITY_PARAMS,
    detect_feature_intensity,
    effective_intensity,
    get_params,
)


class TestIntensityEnum:
    """Intensity level ordering and parsing."""

    def test_ordering(self):
        assert Intensity.STANDARD < Intensity.HIGH < Intensity.CRITICAL

    def test_from_str(self):
        assert Intensity.from_str("standard") == Intensity.STANDARD
        assert Intensity.from_str("HIGH") == Intensity.HIGH
        assert Intensity.from_str("Critical") == Intensity.CRITICAL

    def test_from_str_invalid(self):
        with pytest.raises(KeyError):
            Intensity.from_str("extreme")


class TestEffectiveIntensity:
    """Effective intensity = max(project, feature)."""

    def test_same_level(self):
        assert effective_intensity(Intensity.HIGH, Intensity.HIGH) == Intensity.HIGH

    def test_project_higher(self):
        assert effective_intensity(Intensity.CRITICAL, Intensity.STANDARD) == Intensity.CRITICAL

    def test_feature_higher(self):
        assert effective_intensity(Intensity.STANDARD, Intensity.HIGH) == Intensity.HIGH

    def test_max_behavior(self):
        assert effective_intensity(Intensity.STANDARD, Intensity.CRITICAL) == Intensity.CRITICAL


class TestIntensityParams:
    """Verify each intensity level has correct parameters."""

    def test_all_levels_have_params(self):
        for level in Intensity:
            assert level in INTENSITY_PARAMS

    def test_standard_has_minimal_requirements(self):
        params = get_params(Intensity.STANDARD)
        assert not params.research_agents
        assert not params.stride_analysis
        assert not params.mutation_testing
        assert params.review_agent_count == 1
        assert params.min_qa_rounds == 1

    def test_high_has_more_rigor(self):
        params = get_params(Intensity.HIGH)
        assert params.research_agents
        assert params.stride_analysis
        assert params.review_agent_count == 2
        assert params.min_qa_rounds == 2
        assert params.test_audit_required

    def test_critical_has_maximum_rigor(self):
        params = get_params(Intensity.CRITICAL)
        assert params.mutation_testing
        assert params.review_agent_count == 3
        assert params.min_qa_rounds == 3
        assert params.audit_agents == 4

    def test_qa_round_caps_increase_with_intensity(self):
        s = get_params(Intensity.STANDARD)
        h = get_params(Intensity.HIGH)
        c = get_params(Intensity.CRITICAL)
        assert s.max_qa_rounds < h.max_qa_rounds < c.max_qa_rounds

    def test_spec_sections_increase_with_intensity(self):
        s = get_params(Intensity.STANDARD)
        h = get_params(Intensity.HIGH)
        c = get_params(Intensity.CRITICAL)
        assert len(s.spec_sections_required) < len(h.spec_sections_required) < len(c.spec_sections_required)


class TestFeatureIntensityDetection:
    """4-signal feature intensity detection."""

    def test_no_signals_returns_standard(self):
        assert detect_feature_intensity() == Intensity.STANDARD

    def test_security_path_triggers_high(self):
        result = detect_feature_intensity(affected_paths=["src/security/auth.py"])
        assert result >= Intensity.HIGH

    def test_payment_path_triggers_high(self):
        """Single payment path signal scores 2 → HIGH (need 3+ for CRITICAL)."""
        result = detect_feature_intensity(affected_paths=["src/payment/processor.py"])
        assert result >= Intensity.HIGH

    def test_auth_keyword_in_spec_triggers_high(self):
        result = detect_feature_intensity(spec_content="Implement user authentication with password hashing")
        assert result >= Intensity.HIGH

    def test_pci_keyword_triggers_high_or_above(self):
        """Single critical keyword scores 2 → HIGH (compound signals needed for CRITICAL)."""
        result = detect_feature_intensity(spec_content="This feature handles PCI compliance for credit card storage")
        assert result >= Intensity.HIGH

    def test_compound_signals_trigger_critical(self):
        """Multiple signals compound to reach CRITICAL threshold."""
        result = detect_feature_intensity(
            spec_content="Handle PCI compliance for credit card payment processing",
            affected_paths=["src/payment/billing.py"],
        )
        assert result == Intensity.CRITICAL

    def test_high_finding_density_triggers_high(self):
        result = detect_feature_intensity(historical_finding_density=2.0)
        assert result >= Intensity.HIGH

    def test_very_high_finding_density_triggers_high(self):
        """Single high-density signal scores 2 → HIGH."""
        result = detect_feature_intensity(historical_finding_density=4.0)
        assert result >= Intensity.HIGH

    def test_density_plus_path_triggers_critical(self):
        """Density + path signals compound to CRITICAL."""
        result = detect_feature_intensity(
            affected_paths=["src/auth/session.py"],
            historical_finding_density=4.0,
        )
        assert result == Intensity.CRITICAL

    def test_multiple_signals_compound(self):
        result = detect_feature_intensity(
            spec_content="Handle user authentication tokens",
            affected_paths=["src/auth/handler.py"],
        )
        assert result >= Intensity.HIGH

    def test_benign_feature_stays_standard(self):
        result = detect_feature_intensity(
            spec_content="Add a help text tooltip to the dashboard",
            affected_paths=["src/ui/tooltip.py"],
        )
        assert result == Intensity.STANDARD


class TestIntensityConfig:
    """Configuration persistence model."""

    def test_default_is_standard(self):
        config = IntensityConfig()
        assert config.get_project_intensity() == Intensity.STANDARD

    def test_set_high(self):
        config = IntensityConfig(project_intensity="high")
        assert config.get_project_intensity() == Intensity.HIGH

    def test_calibration_mode_default(self):
        config = IntensityConfig()
        assert config.calibration_mode == "passive"

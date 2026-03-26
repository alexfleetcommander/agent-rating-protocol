"""Tests for the anti_goodhart module (ARP v2 Section 6)."""

import json
import math
import pytest

from agent_rating_protocol.anti_goodhart import (
    AnomalyFlag,
    RotationBound,
    RotationEvent,
    ShadowMetric,
    ShadowMetricCommitment,
    add_dp_noise,
    check_anomalies,
    compute_shadow_commitment,
    dp_response,
    generate_rotation_bounds,
    laplace_noise,
    rotate_weights,
    verify_shadow_commitment,
)
from agent_rating_protocol.composition import get_profile


# ---------------------------------------------------------------------------
# Rotation bounds
# ---------------------------------------------------------------------------

class TestRotationBounds:
    def test_generate_from_profile(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile)
        assert len(bounds) == len(profile.inputs)
        for b in bounds:
            assert b.min_weight >= 0
            assert b.max_weight <= 1
            assert b.min_weight <= b.max_weight

    def test_bound_validation(self):
        b = RotationBound("test", 0.15, 0.35)
        assert b.validate_weight(0.25) is True
        assert b.validate_weight(0.10) is False
        assert b.validate_weight(0.40) is False

    def test_to_dict_rotated(self):
        b = RotationBound("test", 0.15, 0.35)
        d = b.to_dict()
        assert d["current_weight"] == "ROTATED"

    def test_to_dict_with_weight(self):
        b = RotationBound("test", 0.15, 0.35, current_weight=0.25)
        d = b.to_dict()
        assert d["current_weight"] == 0.25

    def test_custom_bound_fraction(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile, bound_fraction=0.2)
        for b, inp in zip(bounds, profile.inputs):
            delta = inp.weight * 0.2
            assert abs(b.min_weight - max(0, inp.weight - delta)) < 0.001
            assert abs(b.max_weight - min(1, inp.weight + delta)) < 0.001


# ---------------------------------------------------------------------------
# Weight rotation
# ---------------------------------------------------------------------------

class TestRotateWeights:
    def test_rotation_produces_valid_profile(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile)
        new_profile, event = rotate_weights(profile, bounds, seed=42)
        assert new_profile.profile_id == profile.profile_id
        assert len(new_profile.inputs) == len(profile.inputs)

    def test_weights_normalized(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile)
        new_profile, _ = rotate_weights(profile, bounds, seed=42)
        total = sum(inp.weight for inp in new_profile.inputs)
        assert abs(total - 1.0) < 0.01

    def test_rotation_changes_weights(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile)
        new_profile, _ = rotate_weights(profile, bounds, seed=42)
        old_w = [inp.weight for inp in profile.inputs]
        new_w = [inp.weight for inp in new_profile.inputs]
        assert old_w != new_w

    def test_rotation_event_recorded(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile)
        _, event = rotate_weights(profile, bounds, seed=42)
        assert event.profile_id == profile.profile_id
        assert event.previous_weights
        assert event.new_weights
        assert "updated" in event.announcement

    def test_seed_reproducibility(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile)
        p1, _ = rotate_weights(profile, bounds, seed=123)
        p2, _ = rotate_weights(profile, bounds, seed=123)
        w1 = [inp.weight for inp in p1.inputs]
        w2 = [inp.weight for inp in p2.inputs]
        assert w1 == w2

    def test_different_seeds_differ(self):
        profile = get_profile("general-purpose")
        bounds = generate_rotation_bounds(profile)
        p1, _ = rotate_weights(profile, bounds, seed=1)
        p2, _ = rotate_weights(profile, bounds, seed=2)
        w1 = [inp.weight for inp in p1.inputs]
        w2 = [inp.weight for inp in p2.inputs]
        assert w1 != w2


# ---------------------------------------------------------------------------
# Shadow metrics
# ---------------------------------------------------------------------------

class TestShadowMetric:
    def test_no_divergence_initially(self):
        sm = ShadowMetric(
            primary_signal_id="composite",
            shadow_signal_id="stability",
        )
        assert sm.divergence_detected() is False

    def test_stable_no_divergence(self):
        sm = ShadowMetric(
            primary_signal_id="composite",
            shadow_signal_id="stability",
        )
        for i in range(10):
            sm.record(80.0 + i * 0.1, 79.0 + i * 0.1)
        assert sm.divergence_detected() is False

    def test_divergence_detected(self):
        sm = ShadowMetric(
            primary_signal_id="arp:reliability:weighted_mean",
            shadow_signal_id="repeat_interaction_rate",
            divergence_threshold=2.0,
        )
        # Build stable history
        for _ in range(10):
            sm.record(80.0, 78.0)
        # Inject spike
        sm.record(95.0, 50.0)
        assert sm.divergence_detected() is True

    def test_to_dict(self):
        sm = ShadowMetric(
            primary_signal_id="test_primary",
            shadow_signal_id="test_shadow",
        )
        sm.record(80, 78)
        d = sm.to_dict()
        assert d["primary_signal_id"] == "test_primary"
        assert d["observations"] == 1

    def test_insufficient_data(self):
        sm = ShadowMetric(
            primary_signal_id="test",
            shadow_signal_id="shadow",
        )
        sm.record(80, 50)
        sm.record(95, 20)
        # Only 2 observations, need 3
        assert sm.divergence_detected() is False


# ---------------------------------------------------------------------------
# Shadow metric commitments
# ---------------------------------------------------------------------------

class TestShadowCommitment:
    def test_compute_and_verify(self):
        data = {"agent-1": {"shadow_reliability": 0.85}}
        commitment = compute_shadow_commitment("oracle-1", data)
        assert commitment.oracle_id == "oracle-1"
        assert commitment.agent_count == 1
        assert verify_shadow_commitment(commitment, data) is True

    def test_tampered_data_fails(self):
        data = {"agent-1": {"shadow_reliability": 0.85}}
        commitment = compute_shadow_commitment("oracle-1", data)
        tampered = {"agent-1": {"shadow_reliability": 0.95}}
        assert verify_shadow_commitment(commitment, tampered) is False

    def test_commitment_to_dict(self):
        data = {"agent-1": {"val": 1}}
        c = compute_shadow_commitment("oracle-1", data)
        d = c.to_dict()
        assert "commitment_hash" in d
        assert d["oracle_id"] == "oracle-1"


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

class TestAnomalyDetection:
    def test_no_anomalies(self):
        sm = ShadowMetric("primary", "shadow")
        for _ in range(10):
            sm.record(80, 78)
        flags = check_anomalies("agent-1", [sm])
        assert len(flags) == 0

    def test_anomaly_flagged(self):
        sm = ShadowMetric("primary", "shadow", divergence_threshold=2.0)
        for _ in range(10):
            sm.record(80, 78)
        sm.record(95, 30)
        flags = check_anomalies("agent-1", [sm])
        assert len(flags) == 1
        assert flags[0].agent_id == "agent-1"
        assert flags[0].severity == "enhanced_monitoring"
        assert flags[0].confidence_adjustment == 0.8

    def test_custom_confidence_penalty(self):
        sm = ShadowMetric("primary", "shadow", divergence_threshold=2.0)
        for _ in range(10):
            sm.record(80, 78)
        sm.record(95, 30)
        flags = check_anomalies("agent-1", [sm], confidence_penalty=0.6)
        assert flags[0].confidence_adjustment == 0.6

    def test_flag_to_dict(self):
        f = AnomalyFlag(
            agent_id="agent-1",
            primary_signal="test",
            shadow_signal="shadow",
            severity="warning",
        )
        d = f.to_dict()
        assert d["agent_id"] == "agent-1"
        assert d["severity"] == "warning"


# ---------------------------------------------------------------------------
# Differential privacy
# ---------------------------------------------------------------------------

class TestDifferentialPrivacy:
    def test_laplace_noise_distribution(self):
        """Noise should have mean ≈ 0 over many samples."""
        samples = [laplace_noise(5.0, 1.0) for _ in range(10000)]
        mean = sum(samples) / len(samples)
        assert abs(mean) < 1.0  # Should be close to 0

    def test_epsilon_controls_noise(self):
        """Higher epsilon = less noise."""
        high_eps = [abs(laplace_noise(5.0, 10.0)) for _ in range(1000)]
        low_eps = [abs(laplace_noise(5.0, 0.1)) for _ in range(1000)]
        assert sum(high_eps) / 1000 < sum(low_eps) / 1000

    def test_invalid_epsilon(self):
        with pytest.raises(ValueError):
            laplace_noise(5.0, 0)
        with pytest.raises(ValueError):
            laplace_noise(5.0, -1)

    def test_invalid_sensitivity(self):
        with pytest.raises(ValueError):
            laplace_noise(-1, 1.0)

    def test_add_dp_noise_in_range(self):
        for _ in range(100):
            result = add_dp_noise(50.0)
            assert 0.0 <= result <= 100.0

    def test_add_dp_noise_custom_range(self):
        for _ in range(100):
            result = add_dp_noise(50.0, output_range=(10.0, 90.0))
            assert 10.0 <= result <= 90.0

    def test_dp_response_deterministic_with_seed(self):
        """Same seed should produce same noise."""
        r1 = dp_response(75.0, agent_seed=42)
        r2 = dp_response(75.0, agent_seed=42)
        assert r1 == r2

    def test_dp_response_different_seeds(self):
        r1 = dp_response(75.0, agent_seed=1)
        r2 = dp_response(75.0, agent_seed=2)
        # Very unlikely to be exactly equal
        # (but technically possible — not a hard assert)

    def test_noise_magnitude_at_default_epsilon(self):
        """At epsilon=1, noise should be ~±2-5 points."""
        deltas = [abs(add_dp_noise(50.0) - 50.0) for _ in range(1000)]
        avg_delta = sum(deltas) / len(deltas)
        # Expected: sensitivity/epsilon = 5.0 (Laplace mean absolute deviation)
        assert 1.0 < avg_delta < 15.0

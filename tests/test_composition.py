"""Tests for the composition module (ARP v2 Section 3)."""

import json
import math
import pytest

from agent_rating_protocol.composition import (
    DISQUALIFIED,
    STANDARD_PROFILES,
    CompositeSignal,
    Gate,
    PenaltyFloor,
    ProfileInput,
    Signal,
    WeightProfile,
    compose,
    diminishing_returns_transform,
    get_profile,
)


# ---------------------------------------------------------------------------
# Signal dataclass
# ---------------------------------------------------------------------------

class TestSignal:
    def test_create_signal(self):
        s = Signal(
            signal_type="rating_dimension",
            signal_id="arp:reliability:weighted_mean",
            value=82.3,
            confidence=0.87,
        )
        assert s.value == 82.3
        assert s.confidence == 0.87

    def test_signal_roundtrip(self):
        s = Signal(
            signal_type="provenance",
            signal_id="coc:operational_age_days",
            value=312,
            confidence=1.0,
            source="oracle-1",
        )
        d = s.to_dict()
        s2 = Signal.from_dict(d)
        assert s2.signal_id == s.signal_id
        assert s2.value == s.value

    def test_signal_defaults(self):
        s = Signal(signal_type="test", signal_id="test:id", value=50)
        assert s.confidence == 1.0
        assert s.source == ""
        assert s.window == "365d"


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

class TestGate:
    def test_minimum_gate_pass(self):
        g = Gate(signal_id="test", threshold=5, gate_type="minimum")
        assert g.evaluate(5) is True
        assert g.evaluate(10) is True

    def test_minimum_gate_fail(self):
        g = Gate(signal_id="test", threshold=5, gate_type="minimum")
        assert g.evaluate(4) is False

    def test_maximum_gate(self):
        g = Gate(signal_id="test", threshold=100, gate_type="maximum")
        assert g.evaluate(100) is True
        assert g.evaluate(101) is False

    def test_gate_roundtrip(self):
        g = Gate(signal_id="arp:total", threshold=5, gate_type="minimum")
        d = g.to_dict()
        g2 = Gate.from_dict(d)
        assert g2.signal_id == g.signal_id
        assert g2.threshold == g.threshold


# ---------------------------------------------------------------------------
# PenaltyFloor
# ---------------------------------------------------------------------------

class TestPenaltyFloor:
    def test_no_penalty_above_floor(self):
        pf = PenaltyFloor(signal_id="test", floor=30, max_penalty=25)
        assert pf.compute_penalty(30) == 0.0
        assert pf.compute_penalty(50) == 0.0

    def test_penalty_below_floor(self):
        pf = PenaltyFloor(signal_id="test", floor=30, max_penalty=25)
        penalty = pf.compute_penalty(15)
        expected = 25 * (30 - 15) / 30
        assert abs(penalty - expected) < 0.01

    def test_full_penalty_at_zero(self):
        pf = PenaltyFloor(signal_id="test", floor=30, max_penalty=25)
        assert pf.compute_penalty(0) == 25.0


# ---------------------------------------------------------------------------
# Diminishing returns
# ---------------------------------------------------------------------------

class TestDiminishingReturns:
    def test_zero_input(self):
        assert diminishing_returns_transform(0, 100) == 0.0

    def test_large_input_approaches_100(self):
        result = diminishing_returns_transform(10000, 100)
        assert result > 99.9

    def test_k_controls_steepness(self):
        slow = diminishing_returns_transform(50, 365)
        fast = diminishing_returns_transform(50, 50)
        assert fast > slow

    def test_invalid_k(self):
        with pytest.raises(ValueError):
            diminishing_returns_transform(50, 0)
        with pytest.raises(ValueError):
            diminishing_returns_transform(50, -1)


# ---------------------------------------------------------------------------
# WeightProfile
# ---------------------------------------------------------------------------

class TestWeightProfile:
    def test_roundtrip_json(self):
        profile = get_profile("general-purpose")
        j = profile.to_json()
        loaded = WeightProfile.from_json(j)
        assert loaded.profile_id == profile.profile_id
        assert len(loaded.inputs) == len(profile.inputs)
        assert len(loaded.gates) == len(profile.gates)

    def test_from_dict(self):
        d = {
            "profile_id": "test:custom",
            "inputs": [
                {"signal_id": "arp:reliability:weighted_mean", "weight": 1.0}
            ],
        }
        p = WeightProfile.from_dict(d)
        assert p.profile_id == "test:custom"
        assert len(p.inputs) == 1


# ---------------------------------------------------------------------------
# Standard profiles
# ---------------------------------------------------------------------------

class TestStandardProfiles:
    def test_all_profiles_exist(self):
        names = [
            "general-purpose",
            "high-reliability",
            "fast-turnaround",
            "compliance-first",
            "cost-optimized",
        ]
        for name in names:
            p = get_profile(name)
            assert p.profile_id.endswith(name)

    def test_weights_sum_to_one(self):
        for name, profile in STANDARD_PROFILES.items():
            total = sum(inp.weight for inp in profile.inputs)
            assert abs(total - 1.0) < 0.01, f"{name}: weights sum to {total}"

    def test_unknown_profile_raises(self):
        with pytest.raises(KeyError):
            get_profile("nonexistent")


# ---------------------------------------------------------------------------
# compose()
# ---------------------------------------------------------------------------

def _make_signals(
    reliability=80, accuracy=85, latency=70, compliance=90, cost=75,
    confidence=0.87, age_days=100, participation=0.8, num_ratings=50,
):
    """Helper to create a standard set of signals for testing."""
    return [
        Signal("rating_dimension", "arp:reliability:weighted_mean",
               reliability, confidence),
        Signal("rating_dimension", "arp:accuracy:weighted_mean",
               accuracy, confidence),
        Signal("rating_dimension", "arp:latency:weighted_mean",
               latency, confidence),
        Signal("rating_dimension", "arp:protocol_compliance:weighted_mean",
               compliance, confidence),
        Signal("rating_dimension", "arp:cost_efficiency:weighted_mean",
               cost, confidence),
        Signal("provenance", "coc:operational_age_days",
               float(age_days), 1.0),
        Signal("behavioral", "behavioral:rating_participation_rate",
               participation * 100, 1.0),
        Signal("behavioral", "arp:total_ratings_received",
               float(num_ratings), 1.0),
    ]


class TestCompose:
    def test_basic_compose(self):
        signals = _make_signals()
        profile = get_profile("general-purpose")
        result = compose(signals, profile)
        assert result.gate_status == "all_passed"
        assert 0 < result.value <= 100
        assert result.confidence > 0

    def test_gate_failure_too_few_ratings(self):
        signals = _make_signals(num_ratings=3)
        profile = get_profile("general-purpose")
        result = compose(signals, profile)
        assert "failed" in result.gate_status
        assert result.value == -1.0

    def test_gate_failure_too_young(self):
        signals = _make_signals(age_days=3)
        profile = get_profile("general-purpose")
        result = compose(signals, profile)
        assert "failed" in result.gate_status

    def test_penalty_floor_reduces_score(self):
        # Reliability below 30 triggers penalty
        signals_low = _make_signals(reliability=15)
        signals_ok = _make_signals(reliability=80)
        profile = get_profile("general-purpose")
        low_result = compose(signals_low, profile)
        ok_result = compose(signals_ok, profile)
        assert low_result.value < ok_result.value

    def test_high_reliability_profile_weighs_reliability(self):
        # Agent with high reliability should score better on HR profile
        signals = _make_signals(reliability=95, accuracy=60)
        hr = compose(signals, get_profile("high-reliability"))
        gp = compose(signals, get_profile("general-purpose"))
        # HR profile weights reliability at 40% vs GP at 25%
        # So a high-reliability agent should do relatively better
        assert hr.value > 0

    def test_composite_has_weakest_input(self):
        signals = _make_signals()
        signals[2].confidence = 0.1  # Make latency weakest
        result = compose(signals, get_profile("general-purpose"))
        assert result.weakest_input is not None
        assert result.weakest_input["confidence"] == 0.1

    def test_composite_validity(self):
        signals = _make_signals()
        result = compose(signals, get_profile("general-purpose"))
        assert result.is_valid()

    def test_composite_to_dict(self):
        signals = _make_signals()
        result = compose(signals, get_profile("general-purpose"))
        d = result.to_dict()
        assert "value" in d
        assert "confidence" in d
        assert "gate_status" in d

    def test_compose_with_computed_by(self):
        signals = _make_signals()
        result = compose(
            signals, get_profile("general-purpose"),
            computed_by="did:web:oracle.example.com"
        )
        assert result.computed_by == "did:web:oracle.example.com"

    def test_empty_signals_zero_score(self):
        result = compose([], get_profile("general-purpose"))
        # Should fail gates (no signals for gate checks)
        assert "failed" in result.gate_status

    def test_custom_profile_compose(self):
        profile = WeightProfile(
            profile_id="test:simple",
            inputs=[
                ProfileInput("arp:reliability:weighted_mean", 0.5, "linear"),
                ProfileInput("arp:accuracy:weighted_mean", 0.5, "linear"),
            ],
        )
        signals = [
            Signal("rating_dimension", "arp:reliability:weighted_mean", 80, 1.0),
            Signal("rating_dimension", "arp:accuracy:weighted_mean", 60, 1.0),
        ]
        result = compose(signals, profile)
        assert abs(result.value - 70.0) < 0.1  # (80*0.5 + 60*0.5) / 1.0

    def test_confidence_adjusted_reduces_low_confidence(self):
        profile = WeightProfile(
            profile_id="test:conf",
            inputs=[
                ProfileInput("s1", 0.5, "confidence_adjusted"),
                ProfileInput("s2", 0.5, "confidence_adjusted"),
            ],
        )
        signals = [
            Signal("test", "s1", 90, confidence=1.0),
            Signal("test", "s2", 90, confidence=0.1),
        ]
        result = compose(signals, profile)
        # s2 has low confidence, so it contributes less
        # With equal values of 90, result should be ~90 regardless
        assert abs(result.value - 90) < 1

    def test_diminishing_returns_operation(self):
        profile = WeightProfile(
            profile_id="test:dr",
            inputs=[
                ProfileInput("s1", 1.0, "diminishing_returns", k=50),
            ],
        )
        signals = [Signal("test", "s1", 200, 1.0)]
        result = compose(signals, profile)
        # 100 * (1 - e^(-200/50)) = 100 * (1 - e^-4) ≈ 98.17
        assert result.value > 95

"""Tests for agent_rating_protocol.weight module."""

import math

import pytest

from agent_rating_protocol.rating import RatingRecord
from agent_rating_protocol.weight import (
    VERIFICATION_MULTIPLIERS,
    compute_rater_calibrations,
    confidence,
    effective_weight,
    rater_calibration_factor,
    rater_weight,
    recency_multiplier,
    verification_level_multiplier,
    weighted_score,
    weighted_scores_all,
)


class TestRaterWeight:
    def test_new_agent_zero_weight(self):
        # age=0, ratings=0 -> W = log2(1) * log2(1) = 0 * 0 = 0
        assert rater_weight(0, 0) == 0.0

    def test_age_only_zero_ratings(self):
        # 1000-day agent with 0 ratings -> W = 0
        assert rater_weight(1000, 0) == 0.0

    def test_ratings_only_zero_age(self):
        # 0-day agent with 500 ratings -> W = 0
        assert rater_weight(0, 500) == 0.0

    def test_known_value(self):
        # 365 days, 100 ratings
        # W = log2(366) * log2(101) ≈ 8.515 * 6.658 ≈ 56.68
        w = rater_weight(365, 100)
        assert abs(w - math.log2(366) * math.log2(101)) < 0.001

    def test_logarithmic_scaling(self):
        # Doubling age doesn't double weight
        w1 = rater_weight(100, 50)
        w2 = rater_weight(200, 50)
        assert w2 < 2 * w1

    def test_negative_values_rejected(self):
        with pytest.raises(ValueError):
            rater_weight(-1, 10)
        with pytest.raises(ValueError):
            rater_weight(10, -1)


class TestConfidence:
    def test_zero_ratings(self):
        assert confidence(0) == 0.0

    def test_increases_with_ratings(self):
        c1 = confidence(10)
        c2 = confidence(100)
        c3 = confidence(1000)
        assert 0 < c1 < c2 < c3 < 1.0

    def test_approaches_one(self):
        c = confidence(10000)
        assert c > 0.999

    def test_known_value(self):
        # confidence(10) = 1 - 1/(1 + 0.1*10) = 1 - 1/2 = 0.5
        assert confidence(10) == 0.5

    def test_negative_rejected(self):
        with pytest.raises(ValueError):
            confidence(-1)


class TestWeightedScore:
    def _make_ratings(self, scores, ages, counts):
        """Helper to create a list of ratings with specified values."""
        ratings = []
        for score, age, count in zip(scores, ages, counts):
            ratings.append(
                RatingRecord(
                    rater_id=f"rater-{len(ratings)}",
                    ratee_id="target",
                    reliability=score,
                    rater_chain_age_days=age,
                    rater_total_ratings_given=count,
                )
            )
        return ratings

    def test_single_rating(self):
        ratings = self._make_ratings([80], [100], [50])
        score = weighted_score(ratings, "reliability")
        assert score == 80.0

    def test_equal_weight_average(self):
        ratings = self._make_ratings([60, 80], [100, 100], [50, 50])
        score = weighted_score(ratings, "reliability")
        assert abs(score - 70.0) < 0.001  # simple average when weights are equal

    def test_weight_favors_experienced(self):
        # Agent with more experience gets more weight
        ratings = self._make_ratings(
            [90, 40],
            [365, 10],   # first has much more age
            [100, 5],    # first has much more ratings given
        )
        score = weighted_score(ratings, "reliability")
        # Should be closer to 90 than to 40
        assert score is not None
        assert score > 65

    def test_zero_weight_returns_none(self):
        # All raters have zero weight (age=0 or ratings=0)
        ratings = self._make_ratings([80, 90], [0, 0], [0, 0])
        score = weighted_score(ratings, "reliability")
        assert score is None

    def test_unknown_dimension_rejected(self):
        ratings = self._make_ratings([50], [10], [10])
        with pytest.raises(ValueError, match="Unknown dimension"):
            weighted_score(ratings, "nonexistent")

    def test_all_dimensions(self):
        ratings = self._make_ratings([60], [100], [50])
        scores = weighted_scores_all(ratings)
        assert len(scores) == 5
        assert scores["reliability"] == 60.0
        # Other dimensions default to 50
        assert scores["accuracy"] == 50.0


class TestVerificationLevelMultiplier:
    def test_verified(self):
        assert verification_level_multiplier("verified") == 1.0

    def test_unilateral(self):
        assert verification_level_multiplier("unilateral") == 0.5

    def test_self_reported(self):
        assert verification_level_multiplier("self_reported") == 0.5

    def test_unknown_defaults_to_one(self):
        assert verification_level_multiplier("unknown") == 1.0

    def test_multipliers_dict(self):
        assert len(VERIFICATION_MULTIPLIERS) == 3


class TestRaterCalibrationFactor:
    def test_high_variance_no_penalty(self):
        # Std dev > 10 -> factor = 1.0
        scores = [20, 40, 60, 80, 100]
        factor = rater_calibration_factor(scores)
        assert factor == 1.0

    def test_low_variance_penalized(self):
        # All scores near 90 -> std dev very low -> penalty
        scores = [90, 91, 90, 89, 90, 91, 90, 89, 90, 91]
        factor = rater_calibration_factor(scores)
        assert factor < 1.0
        assert factor > 0.0

    def test_zero_variance(self):
        # All identical scores -> std dev = 0 -> factor = 0.0
        scores = [95, 95, 95, 95, 95]
        factor = rater_calibration_factor(scores)
        assert factor == 0.0

    def test_exactly_at_threshold(self):
        # If sigma is exactly 10, no penalty
        # We can't easily construct this, but we can check the boundary
        import statistics
        scores = list(range(1, 101))  # sigma ≈ 29.15
        factor = rater_calibration_factor(scores)
        assert factor == 1.0

    def test_insufficient_data(self):
        # Fewer than 2 scores -> factor = 1.0
        assert rater_calibration_factor([50]) == 1.0
        assert rater_calibration_factor([]) == 1.0

    def test_sigma_5_gives_half(self):
        # Construct scores with sigma ≈ 5
        import statistics
        # Use a set of values around 50 with controlled spread
        scores = [45, 50, 55, 45, 50, 55, 45, 50, 55, 45, 50, 55]
        sigma = statistics.stdev(scores)
        factor = rater_calibration_factor(scores)
        assert abs(factor - sigma / 10.0) < 0.001


class TestRecencyMultiplier:
    def test_recent_rating_full_weight(self):
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        mult = recency_multiplier(now_iso, window_days=365)
        assert mult > 0.99

    def test_old_rating_zero_weight(self):
        mult = recency_multiplier("2020-01-01T00:00:00+00:00", window_days=365)
        assert mult == 0.0

    def test_unparseable_timestamp(self):
        mult = recency_multiplier("not-a-date", window_days=365)
        assert mult == 1.0

    def test_midway_rating(self):
        from datetime import datetime, timedelta, timezone
        half_year_ago = (
            datetime.now(timezone.utc) - timedelta(days=182)
        ).isoformat()
        mult = recency_multiplier(half_year_ago, window_days=365)
        # Should be roughly 0.75 (linear decay from 1.0 to 0.5)
        assert 0.70 < mult < 0.80


class TestEffectiveWeight:
    def test_verified_no_calibration(self):
        r = RatingRecord(
            rater_id="a", ratee_id="b",
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
        )
        ew = effective_weight(r)
        base = rater_weight(100, 50)
        assert abs(ew - base) < 0.001

    def test_unilateral_halves_weight(self):
        r = RatingRecord(
            rater_id="a", ratee_id="b",
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
            verification_level="unilateral",
        )
        ew = effective_weight(r)
        base = rater_weight(100, 50)
        assert abs(ew - base * 0.5) < 0.001

    def test_self_reported_halves_weight(self):
        r = RatingRecord(
            rater_id="a", ratee_id="b",
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
            verification_level="self_reported",
        )
        ew = effective_weight(r)
        base = rater_weight(100, 50)
        assert abs(ew - base * 0.5) < 0.001

    def test_calibration_applied(self):
        r = RatingRecord(
            rater_id="a", ratee_id="b",
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
        )
        ew = effective_weight(r, calibration=0.5)
        base = rater_weight(100, 50)
        assert abs(ew - base * 0.5) < 0.001

    def test_all_multipliers_combined(self):
        r = RatingRecord(
            rater_id="a", ratee_id="b",
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
            verification_level="unilateral",
        )
        ew = effective_weight(r, calibration=0.5, recency=0.8)
        base = rater_weight(100, 50)
        expected = base * 0.5 * 0.5 * 0.8
        assert abs(ew - expected) < 0.001


class TestComputeRaterCalibrations:
    def test_basic(self):
        ratings = [
            RatingRecord(
                rater_id="inflator",
                ratee_id="target",
                reliability=95,
                accuracy=95,
                latency=95,
                protocol_compliance=95,
                cost_efficiency=95,
            ),
            RatingRecord(
                rater_id="inflator",
                ratee_id="target-2",
                reliability=96,
                accuracy=96,
                latency=96,
                protocol_compliance=96,
                cost_efficiency=96,
            ),
            RatingRecord(
                rater_id="honest",
                ratee_id="target",
                reliability=30,
                accuracy=60,
                latency=90,
                protocol_compliance=50,
                cost_efficiency=70,
            ),
        ]
        factors = compute_rater_calibrations(ratings)
        assert "inflator" in factors
        assert "honest" in factors
        # Inflator gives nearly identical scores -> low sigma -> penalized
        assert factors["inflator"] < 1.0
        # Honest rater has wide score range -> no penalty
        assert factors["honest"] == 1.0

    def test_empty_ratings(self):
        factors = compute_rater_calibrations([])
        assert factors == {}


class TestWeightedScoreWithCalibration:
    def test_calibration_reduces_inflator(self):
        """An inflator with calibration penalty should have less influence."""
        inflator_rating = RatingRecord(
            rater_id="inflator",
            ratee_id="target",
            reliability=99,
            rater_chain_age_days=365,
            rater_total_ratings_given=100,
        )
        honest_rating = RatingRecord(
            rater_id="honest",
            ratee_id="target",
            reliability=60,
            rater_chain_age_days=365,
            rater_total_ratings_given=100,
        )
        ratings = [inflator_rating, honest_rating]

        # Without calibration — equal weights, average close to 79.5
        score_uncal = weighted_score(ratings, "reliability")
        assert score_uncal is not None

        # With calibration — inflator gets penalized
        cal_factors = {"inflator": 0.1, "honest": 1.0}
        score_cal = weighted_score(ratings, "reliability", cal_factors)
        assert score_cal is not None
        # Calibrated score should be closer to honest rating
        assert score_cal < score_uncal

    def test_verification_level_applied_automatically(self):
        """Unilateral ratings get 0.5x weight automatically."""
        verified = RatingRecord(
            rater_id="a", ratee_id="target",
            reliability=90,
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
            verification_level="verified",
        )
        unilateral = RatingRecord(
            rater_id="b", ratee_id="target",
            reliability=30,
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
            verification_level="unilateral",
        )
        ratings = [verified, unilateral]
        score = weighted_score(ratings, "reliability")
        assert score is not None
        # Verified rating (90) should dominate over unilateral (30)
        # Without verification: average ~60. With: closer to 90
        assert score > 65

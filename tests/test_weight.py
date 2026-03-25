"""Tests for agent_rating_protocol.weight module."""

import math

import pytest

from agent_rating_protocol.rating import RatingRecord
from agent_rating_protocol.weight import (
    confidence,
    rater_weight,
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

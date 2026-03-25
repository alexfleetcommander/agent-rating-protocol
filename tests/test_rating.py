"""Tests for agent_rating_protocol.rating module."""

import json

import pytest

from agent_rating_protocol.rating import (
    DIMENSIONS,
    InteractionEvidence,
    RatingRecord,
    score_bucket,
)


class TestScoreBucket:
    def test_poor(self):
        assert score_bucket(1) == "poor"
        assert score_bucket(20) == "poor"

    def test_below_average(self):
        assert score_bucket(21) == "below_average"
        assert score_bucket(40) == "below_average"

    def test_average(self):
        assert score_bucket(50) == "average"

    def test_good(self):
        assert score_bucket(61) == "good"
        assert score_bucket(80) == "good"

    def test_excellent(self):
        assert score_bucket(81) == "excellent"
        assert score_bucket(100) == "excellent"

    def test_out_of_range(self):
        with pytest.raises(ValueError):
            score_bucket(0)
        with pytest.raises(ValueError):
            score_bucket(101)


class TestInteractionEvidence:
    def test_round_trip(self):
        ev = InteractionEvidence(
            task_type="code_review",
            outcome_hash="abc123",
            duration_ms=5000,
            was_completed=True,
        )
        d = ev.to_dict()
        ev2 = InteractionEvidence.from_dict(d)
        assert ev2.task_type == "code_review"
        assert ev2.outcome_hash == "abc123"
        assert ev2.duration_ms == 5000
        assert ev2.was_completed is True


class TestRatingRecord:
    def test_create_basic(self):
        r = RatingRecord(rater_id="agent-a", ratee_id="agent-b")
        assert r.rater_id == "agent-a"
        assert r.ratee_id == "agent-b"
        assert r.reliability == 50
        assert r.record_hash  # auto-computed

    def test_all_dimensions_present(self):
        r = RatingRecord(rater_id="a", ratee_id="b")
        dims = r.dimensions
        assert set(dims.keys()) == set(DIMENSIONS)
        assert all(v == 50 for v in dims.values())

    def test_custom_dimensions(self):
        r = RatingRecord(
            rater_id="a",
            ratee_id="b",
            reliability=90,
            accuracy=85,
            latency=70,
            protocol_compliance=95,
            cost_efficiency=60,
        )
        assert r.reliability == 90
        assert r.accuracy == 85

    def test_validation_out_of_range(self):
        with pytest.raises(ValueError, match="reliability"):
            RatingRecord(rater_id="a", ratee_id="b", reliability=0)

        with pytest.raises(ValueError, match="accuracy"):
            RatingRecord(rater_id="a", ratee_id="b", accuracy=101)

    def test_validation_missing_ids(self):
        with pytest.raises(ValueError, match="rater_id"):
            RatingRecord(rater_id="", ratee_id="b")

        with pytest.raises(ValueError, match="ratee_id"):
            RatingRecord(rater_id="a", ratee_id="")

    def test_hash_deterministic(self):
        r = RatingRecord(
            rater_id="a",
            ratee_id="b",
            rating_id="fixed-id",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        h1 = r.compute_hash()
        h2 = r.compute_hash()
        assert h1 == h2

    def test_hash_changes_with_data(self):
        kwargs = dict(
            rater_id="a",
            ratee_id="b",
            rating_id="fixed-id",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        r1 = RatingRecord(**kwargs, reliability=50)
        r2 = RatingRecord(**kwargs, reliability=51)
        assert r1.record_hash != r2.record_hash

    def test_verify_hash(self):
        r = RatingRecord(rater_id="a", ratee_id="b")
        assert r.verify_hash() is True

    def test_tampered_hash_fails(self):
        r = RatingRecord(rater_id="a", ratee_id="b")
        r.reliability = 99  # tamper
        assert r.verify_hash() is False

    def test_to_dict_schema(self):
        r = RatingRecord(rater_id="a", ratee_id="b")
        d = r.to_dict()
        assert d["version"] == 1
        assert d["rater"]["agent_id"] == "a"
        assert d["ratee"]["agent_id"] == "b"
        assert "dimensions" in d
        assert "interaction_evidence" in d
        assert "metadata" in d
        assert "record_hash" in d

    def test_round_trip_dict(self):
        r = RatingRecord(
            rater_id="agent-a",
            ratee_id="agent-b",
            reliability=80,
            accuracy=75,
            latency=90,
            protocol_compliance=85,
            cost_efficiency=70,
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
        )
        d = r.to_dict()
        r2 = RatingRecord.from_dict(d)
        assert r2.rater_id == r.rater_id
        assert r2.ratee_id == r.ratee_id
        assert r2.reliability == r.reliability
        assert r2.record_hash == r.record_hash

    def test_round_trip_json(self):
        r = RatingRecord(rater_id="x", ratee_id="y", reliability=42)
        j = r.to_json()
        d = json.loads(j)
        r2 = RatingRecord.from_dict(d)
        assert r2.reliability == 42

    def test_repr(self):
        r = RatingRecord(rater_id="a", ratee_id="b")
        s = repr(r)
        assert "a" in s
        assert "b" in s

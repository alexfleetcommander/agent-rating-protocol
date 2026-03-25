"""Tests for agent_rating_protocol.query module."""

import pytest

from agent_rating_protocol.query import get_reputation, verify_rating
from agent_rating_protocol.rating import RatingRecord
from agent_rating_protocol.store import RatingStore


@pytest.fixture
def populated_store(tmp_path):
    """Create a store with several ratings."""
    store = RatingStore(str(tmp_path / "query_test.jsonl"))

    # Several raters rate "target-agent"
    for i in range(5):
        r = RatingRecord(
            rater_id=f"rater-{i}",
            ratee_id="target-agent",
            reliability=60 + i * 5,
            accuracy=50 + i * 10,
            latency=70,
            protocol_compliance=80,
            cost_efficiency=55 + i * 5,
            rater_chain_age_days=30 + i * 30,
            rater_total_ratings_given=10 + i * 10,
        )
        store.append_rating(r)

    return store


class TestGetReputation:
    def test_all_dimensions(self, populated_store):
        result = get_reputation(populated_store, "target-agent")
        assert result["agent_id"] == "target-agent"
        assert result["num_ratings"] == 5
        assert result["confidence"] > 0
        assert "scores" in result
        assert len(result["scores"]) == 5
        # All scores should be non-None
        for dim, score in result["scores"].items():
            assert score is not None

    def test_single_dimension(self, populated_store):
        result = get_reputation(
            populated_store, "target-agent", dimension="reliability"
        )
        assert "score" in result
        assert result["dimension"] == "reliability"
        assert result["score"] is not None

    def test_unknown_agent(self, populated_store):
        result = get_reputation(populated_store, "nonexistent")
        assert result["num_ratings"] == 0
        assert result["confidence"] == 0.0
        assert all(v is None for v in result["scores"].values())

    def test_unknown_dimension_rejected(self, populated_store):
        with pytest.raises(ValueError, match="Unknown dimension"):
            get_reputation(
                populated_store, "target-agent", dimension="magic"
            )

    def test_window_filtering(self, tmp_path):
        store = RatingStore(str(tmp_path / "window_test.jsonl"))
        # Create a rating with a very old timestamp
        r = RatingRecord(
            rater_id="old-rater",
            ratee_id="target",
            reliability=90,
            rater_chain_age_days=100,
            rater_total_ratings_given=50,
            timestamp="2020-01-01T00:00:00+00:00",
        )
        # Must recompute hash since we set timestamp manually
        r.record_hash = r.compute_hash()
        store.append_rating(r)

        # With 365-day window, old rating should be excluded
        result = get_reputation(store, "target", window_days=365)
        assert result["num_ratings"] == 0

    def test_confidence_increases(self, tmp_path):
        store = RatingStore(str(tmp_path / "conf_test.jsonl"))

        # Add ratings one at a time, confidence should increase
        prev_conf = 0.0
        for i in range(20):
            r = RatingRecord(
                rater_id=f"rater-{i}",
                ratee_id="target",
                rater_chain_age_days=50,
                rater_total_ratings_given=20,
            )
            store.append_rating(r)
            result = get_reputation(store, "target")
            assert result["confidence"] > prev_conf
            prev_conf = result["confidence"]

    def test_weighted_toward_experienced(self, tmp_path):
        store = RatingStore(str(tmp_path / "weight_test.jsonl"))

        # Experienced rater gives 90
        r1 = RatingRecord(
            rater_id="veteran",
            ratee_id="target",
            reliability=90,
            rater_chain_age_days=365,
            rater_total_ratings_given=200,
        )
        store.append_rating(r1)

        # Newbie rater gives 30
        r2 = RatingRecord(
            rater_id="newbie",
            ratee_id="target",
            reliability=30,
            rater_chain_age_days=5,
            rater_total_ratings_given=2,
        )
        store.append_rating(r2)

        result = get_reputation(store, "target", dimension="reliability")
        # Score should be much closer to 90 (veteran's rating)
        assert result["score"] > 70


class TestVerifyRating:
    def test_valid_rating(self, populated_store):
        # Get a rating ID from the store
        records = populated_store.get_all()
        rating_id = records[0].rating_id

        result = verify_rating(populated_store, rating_id)
        assert result["valid"] is True

    def test_nonexistent_rating(self, populated_store):
        result = verify_rating(populated_store, "nonexistent-id")
        assert result["valid"] is False
        assert "not found" in result["error"]

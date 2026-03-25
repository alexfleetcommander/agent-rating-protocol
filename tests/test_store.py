"""Tests for agent_rating_protocol.store module."""

import json
import os

import pytest

from agent_rating_protocol.rating import RatingRecord
from agent_rating_protocol.store import RatingStore


@pytest.fixture
def tmp_store(tmp_path):
    """Create a temporary rating store."""
    return RatingStore(str(tmp_path / "test_ratings.jsonl"))


class TestRatingStore:
    def test_append_and_count(self, tmp_store):
        r = RatingRecord(rater_id="a", ratee_id="b", reliability=80)
        tmp_store.append_rating(r)
        assert tmp_store.count() == 1

    def test_append_multiple(self, tmp_store):
        for i in range(5):
            r = RatingRecord(
                rater_id=f"rater-{i}", ratee_id="target", reliability=50 + i
            )
            tmp_store.append_rating(r)
        assert tmp_store.count() == 5

    def test_get_all(self, tmp_store):
        r1 = RatingRecord(rater_id="a", ratee_id="b", reliability=60)
        r2 = RatingRecord(rater_id="c", ratee_id="d", reliability=80)
        tmp_store.append_rating(r1)
        tmp_store.append_rating(r2)

        all_records = tmp_store.get_all()
        assert len(all_records) == 2
        assert all_records[0].rater_id == "a"
        assert all_records[1].rater_id == "c"

    def test_get_ratings_for(self, tmp_store):
        r1 = RatingRecord(rater_id="a", ratee_id="target")
        r2 = RatingRecord(rater_id="b", ratee_id="target")
        r3 = RatingRecord(rater_id="c", ratee_id="other")
        tmp_store.append_rating(r1)
        tmp_store.append_rating(r2)
        tmp_store.append_rating(r3)

        target_ratings = tmp_store.get_ratings_for("target")
        assert len(target_ratings) == 2

    def test_get_ratings_by(self, tmp_store):
        r1 = RatingRecord(rater_id="active-rater", ratee_id="b")
        r2 = RatingRecord(rater_id="active-rater", ratee_id="c")
        r3 = RatingRecord(rater_id="other-rater", ratee_id="d")
        tmp_store.append_rating(r1)
        tmp_store.append_rating(r2)
        tmp_store.append_rating(r3)

        by_active = tmp_store.get_ratings_by("active-rater")
        assert len(by_active) == 2

    def test_get_rating_by_id(self, tmp_store):
        r = RatingRecord(rater_id="a", ratee_id="b")
        tmp_store.append_rating(r)

        found = tmp_store.get_rating(r.rating_id)
        assert found is not None
        assert found.rater_id == "a"

    def test_get_rating_not_found(self, tmp_store):
        assert tmp_store.get_rating("nonexistent") is None

    def test_empty_store(self, tmp_store):
        assert tmp_store.count() == 0
        assert tmp_store.get_all() == []
        assert tmp_store.get_ratings_for("nobody") == []

    def test_tampered_record_rejected(self, tmp_store):
        r = RatingRecord(rater_id="a", ratee_id="b")
        r.reliability = 99  # tamper after hash computation
        with pytest.raises(ValueError, match="hash verification"):
            tmp_store.append_rating(r)

    def test_agents_summary(self, tmp_store):
        r1 = RatingRecord(rater_id="a", ratee_id="b")
        r2 = RatingRecord(rater_id="a", ratee_id="c")
        r3 = RatingRecord(rater_id="b", ratee_id="a")
        tmp_store.append_rating(r1)
        tmp_store.append_rating(r2)
        tmp_store.append_rating(r3)

        agents = tmp_store.agents()
        assert agents["a"]["ratings_given"] == 2
        assert agents["a"]["ratings_received"] == 1
        assert agents["b"]["ratings_given"] == 1
        assert agents["b"]["ratings_received"] == 1

    def test_stats(self, tmp_store):
        r = RatingRecord(rater_id="a", ratee_id="b")
        tmp_store.append_rating(r)

        stats = tmp_store.stats()
        assert stats["total_ratings"] == 1
        assert stats["unique_raters"] == 1
        assert stats["unique_ratees"] == 1
        assert stats["file_size_bytes"] > 0

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "persist.jsonl")
        store1 = RatingStore(path)
        r = RatingRecord(rater_id="a", ratee_id="b", reliability=77)
        store1.append_rating(r)

        # Create new store instance pointing to same file
        store2 = RatingStore(path)
        assert store2.count() == 1
        records = store2.get_all()
        assert records[0].reliability == 77

    def test_append_only(self, tmp_store):
        """Verify the store is truly append-only (no deletion method)."""
        r = RatingRecord(rater_id="a", ratee_id="b")
        tmp_store.append_rating(r)

        # No delete method exists
        assert not hasattr(tmp_store, "delete_rating")
        assert not hasattr(tmp_store, "remove_rating")
        assert not hasattr(tmp_store, "clear")

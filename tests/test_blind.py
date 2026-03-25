"""Tests for agent_rating_protocol.blind module."""

import time

import pytest

from agent_rating_protocol.blind import (
    BlindExchange,
    commit,
    generate_nonce,
    reveal,
)
from agent_rating_protocol.rating import RatingRecord


def _make_rating_dict(**kwargs):
    defaults = dict(rater_id="agent-a", ratee_id="agent-b")
    defaults.update(kwargs)
    return RatingRecord(**defaults).to_dict()


class TestCommitReveal:
    def test_commit_produces_hex_hash(self):
        rating = _make_rating_dict()
        nonce = generate_nonce()
        h = commit(rating, nonce)
        assert len(h) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in h)

    def test_same_input_same_commitment(self):
        rating = _make_rating_dict()
        nonce = "fixed-nonce"
        h1 = commit(rating, nonce)
        h2 = commit(rating, nonce)
        assert h1 == h2

    def test_different_nonce_different_commitment(self):
        rating = _make_rating_dict()
        h1 = commit(rating, "nonce-1")
        h2 = commit(rating, "nonce-2")
        assert h1 != h2

    def test_reveal_success(self):
        rating = _make_rating_dict()
        nonce = generate_nonce()
        commitment = commit(rating, nonce)
        assert reveal(rating, nonce, commitment) is True

    def test_reveal_wrong_nonce(self):
        rating = _make_rating_dict()
        nonce = generate_nonce()
        commitment = commit(rating, nonce)
        assert reveal(rating, "wrong-nonce", commitment) is False

    def test_reveal_tampered_rating(self):
        rating = _make_rating_dict()
        nonce = generate_nonce()
        commitment = commit(rating, nonce)
        # Tamper with the rating
        rating["dimensions"]["reliability"] = 99
        assert reveal(rating, nonce, commitment) is False

    def test_nonce_is_random(self):
        n1 = generate_nonce()
        n2 = generate_nonce()
        assert n1 != n2
        assert len(n1) == 64  # 32 bytes hex


class TestBlindExchange:
    def test_full_exchange(self):
        ex = BlindExchange(interaction_id="int-001")

        rating_a = _make_rating_dict(rater_id="a", ratee_id="b", reliability=80)
        rating_b = _make_rating_dict(rater_id="b", ratee_id="a", reliability=70)

        nonce_a = generate_nonce()
        nonce_b = generate_nonce()

        # Phase 2: Both commit
        ex.submit_commitment("a", rating_a, nonce_a)
        assert not ex.both_committed  # only one so far
        ex.submit_commitment("b", rating_b, nonce_b)
        assert ex.both_committed
        assert ex.reveal_triggered

        # Phase 3: Both reveal
        assert ex.reveal_rating("a", rating_a, nonce_a) is True
        assert ex.reveal_rating("b", rating_b, nonce_b) is True
        assert ex.both_revealed

        # Get results
        results = ex.get_results()
        assert results is not None
        r_a, r_b = results
        assert r_a["dimensions"]["reliability"] == 80
        assert r_b["dimensions"]["reliability"] == 70

    def test_duplicate_commitment_rejected(self):
        ex = BlindExchange(interaction_id="int-002")
        rating = _make_rating_dict()
        nonce = generate_nonce()

        ex.submit_commitment("a", rating, nonce)
        with pytest.raises(ValueError, match="already committed"):
            ex.submit_commitment("a", rating, nonce)

    def test_third_commitment_rejected(self):
        ex = BlindExchange(interaction_id="int-003")
        nonce = generate_nonce()

        ex.submit_commitment("a", _make_rating_dict(), nonce)
        ex.submit_commitment("b", _make_rating_dict(), nonce)
        with pytest.raises(ValueError, match="Both sides"):
            ex.submit_commitment("c", _make_rating_dict(), nonce)

    def test_reveal_before_trigger_rejected(self):
        ex = BlindExchange(interaction_id="int-004")
        rating = _make_rating_dict()
        nonce = generate_nonce()
        ex.submit_commitment("a", rating, nonce)

        # Only one committed, window not expired
        assert not ex.reveal_triggered
        with pytest.raises(ValueError, match="not yet triggered"):
            ex.reveal_rating("a", rating, nonce)

    def test_reveal_wrong_nonce_rejected(self):
        ex = BlindExchange(interaction_id="int-005")
        rating_a = _make_rating_dict(rater_id="a", ratee_id="b")
        rating_b = _make_rating_dict(rater_id="b", ratee_id="a")
        nonce_a = generate_nonce()
        nonce_b = generate_nonce()

        ex.submit_commitment("a", rating_a, nonce_a)
        ex.submit_commitment("b", rating_b, nonce_b)

        with pytest.raises(ValueError, match="verification failed"):
            ex.reveal_rating("a", rating_a, "wrong-nonce")

    def test_window_expiry(self):
        ex = BlindExchange(
            interaction_id="int-006",
            window_seconds=0.0,  # Immediately expired
            created_at=time.time() - 1,
        )
        assert ex.window_expired
        assert ex.reveal_triggered

    def test_expired_window_blocks_commitment(self):
        ex = BlindExchange(
            interaction_id="int-007",
            window_seconds=0.0,
            created_at=time.time() - 1,
        )
        with pytest.raises(ValueError, match="expired"):
            ex.submit_commitment("a", _make_rating_dict(), generate_nonce())

    def test_results_none_before_reveal(self):
        ex = BlindExchange(interaction_id="int-008")
        assert ex.get_results() is None

    def test_serialization_round_trip(self):
        ex = BlindExchange(interaction_id="int-009")
        rating = _make_rating_dict()
        nonce = generate_nonce()
        ex.submit_commitment("a", rating, nonce)

        d = ex.to_dict()
        ex2 = BlindExchange.from_dict(d)
        assert ex2.interaction_id == "int-009"
        assert ex2.commitment_a is not None
        assert ex2.commitment_a.agent_id == "a"

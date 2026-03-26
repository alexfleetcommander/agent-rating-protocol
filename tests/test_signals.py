"""Tests for the signals module (ARP v2 Section 5)."""

import hashlib
import pytest

from agent_rating_protocol.signals import (
    DEFAULT_TIER_MAP,
    HashChainVerification,
    MerkleProof,
    MerkleTree,
    MerkleVerificationResult,
    SignalTier,
    VerificationLevel,
    ZKPThresholdProof,
    create_zkp_threshold_proof,
    verify_hash_chain,
    verify_merkle_proof,
    verify_prb_merkle,
    verify_zkp_threshold_proof,
)


# ---------------------------------------------------------------------------
# SignalTier
# ---------------------------------------------------------------------------

class TestSignalTier:
    def test_tier_values(self):
        assert SignalTier.PUBLIC.value == "public"
        assert SignalTier.QUERYABLE.value == "queryable"
        assert SignalTier.PRIVATE.value == "private"

    def test_default_tier_map(self):
        assert DEFAULT_TIER_MAP["operational_age"] == SignalTier.PUBLIC
        assert DEFAULT_TIER_MAP["composite_score"] == SignalTier.QUERYABLE
        assert DEFAULT_TIER_MAP["shadow_metrics"] == SignalTier.PRIVATE

    def test_tier_str(self):
        assert str(SignalTier.PUBLIC) == "public"


# ---------------------------------------------------------------------------
# Hash-chain verification
# ---------------------------------------------------------------------------

class TestHashChainVerification:
    def test_valid_hash(self):
        h = hashlib.sha256(b"test").hexdigest()
        result = verify_hash_chain(h, h, "rating-1")
        assert result.exists is True
        assert result.hash_valid is True

    def test_invalid_hash(self):
        result = verify_hash_chain("abc", "def", "rating-2")
        assert result.hash_valid is False

    def test_missing_hash(self):
        result = verify_hash_chain("", "", "rating-3")
        assert result.exists is False

    def test_to_dict(self):
        result = verify_hash_chain("abc", "abc")
        d = result.to_dict()
        assert d["hash_valid"] is True
        assert d["level"] == "basic"


# ---------------------------------------------------------------------------
# MerkleTree
# ---------------------------------------------------------------------------

def _make_hash(s):
    return hashlib.sha256(s.encode()).hexdigest()


class TestMerkleTree:
    def test_single_leaf(self):
        h = _make_hash("leaf1")
        tree = MerkleTree([h])
        assert tree.root == h
        assert tree.leaf_count == 1

    def test_two_leaves(self):
        h1 = _make_hash("leaf1")
        h2 = _make_hash("leaf2")
        tree = MerkleTree([h1, h2])
        expected = hashlib.sha256(
            bytes.fromhex(h1) + bytes.fromhex(h2)
        ).hexdigest()
        assert tree.root == expected

    def test_three_leaves(self):
        hashes = [_make_hash(f"leaf{i}") for i in range(3)]
        tree = MerkleTree(hashes)
        assert tree.leaf_count == 3
        assert len(tree.root) == 64

    def test_four_leaves(self):
        hashes = [_make_hash(f"leaf{i}") for i in range(4)]
        tree = MerkleTree(hashes)
        assert tree.leaf_count == 4

    def test_empty_tree(self):
        tree = MerkleTree([])
        assert tree.root == hashlib.sha256(b"empty").hexdigest()

    def test_proof_generation_valid(self):
        hashes = [_make_hash(f"leaf{i}") for i in range(8)]
        tree = MerkleTree(hashes)
        for i in range(8):
            proof = tree.get_proof(i)
            assert proof.leaf_hash == hashes[i]
            assert proof.root_hash == tree.root

    def test_proof_out_of_range(self):
        hashes = [_make_hash("leaf0")]
        tree = MerkleTree(hashes)
        with pytest.raises(IndexError):
            tree.get_proof(1)


# ---------------------------------------------------------------------------
# Merkle proof verification
# ---------------------------------------------------------------------------

class TestMerkleProofVerification:
    def test_valid_proof(self):
        hashes = [_make_hash(f"leaf{i}") for i in range(10)]
        tree = MerkleTree(hashes)
        for i in range(10):
            proof = tree.get_proof(i)
            assert verify_merkle_proof(proof) is True

    def test_tampered_proof(self):
        hashes = [_make_hash(f"leaf{i}") for i in range(4)]
        tree = MerkleTree(hashes)
        proof = tree.get_proof(0)
        # Tamper with the leaf hash
        tampered = MerkleProof(
            leaf_hash=_make_hash("tampered"),
            proof_hashes=proof.proof_hashes,
            root_hash=proof.root_hash,
        )
        assert verify_merkle_proof(tampered) is False

    def test_proof_to_dict(self):
        hashes = [_make_hash(f"leaf{i}") for i in range(2)]
        tree = MerkleTree(hashes)
        proof = tree.get_proof(0)
        d = proof.to_dict()
        assert "leaf_hash" in d
        assert "root_hash" in d
        assert isinstance(d["proof_hashes"], list)


# ---------------------------------------------------------------------------
# PRB Merkle verification
# ---------------------------------------------------------------------------

class TestPRBMerkleVerification:
    def test_valid_prb(self):
        hashes = [_make_hash(f"rating{i}") for i in range(20)]
        tree = MerkleTree(hashes)
        result = verify_prb_merkle(tree.root, hashes, sample_size=0)
        assert result.root_hash_matches is True
        assert result.proofs_failed == 0
        assert result.proofs_verified == 20

    def test_sampled_verification(self):
        hashes = [_make_hash(f"rating{i}") for i in range(100)]
        tree = MerkleTree(hashes)
        result = verify_prb_merkle(tree.root, hashes, sample_size=10)
        assert result.sample_size == 10
        assert result.proofs_verified == 10
        assert result.proofs_failed == 0

    def test_wrong_root_hash(self):
        hashes = [_make_hash(f"rating{i}") for i in range(5)]
        result = verify_prb_merkle("bad" * 16 + "00" * 8, hashes)
        assert result.root_hash_matches is False

    def test_empty_ratings(self):
        result = verify_prb_merkle("abc", [])
        assert result.total_ratings == 0

    def test_result_to_dict(self):
        hashes = [_make_hash("r0")]
        tree = MerkleTree(hashes)
        result = verify_prb_merkle(tree.root, hashes)
        d = result.to_dict()
        assert d["level"] == "standard"


# ---------------------------------------------------------------------------
# ZKP threshold verification (placeholder)
# ---------------------------------------------------------------------------

class TestZKPThreshold:
    def test_create_proof_above_threshold(self):
        proof = create_zkp_threshold_proof(
            actual_composite=85.0,
            threshold_composite=80.0,
            ratings_root_hash="abc" * 16 + "00" * 8,
        )
        assert proof.threshold_composite == 80.0
        assert proof.proof_system == "placeholder"

    def test_create_proof_below_threshold_raises(self):
        with pytest.raises(ValueError, match="does not meet"):
            create_zkp_threshold_proof(
                actual_composite=75.0,
                threshold_composite=80.0,
            )

    def test_dimension_threshold_pass(self):
        proof = create_zkp_threshold_proof(
            actual_composite=85.0,
            threshold_composite=80.0,
            actual_dimension=90.0,
            threshold_dimension=85.0,
            dimension_name="reliability",
        )
        assert proof.threshold_dimension == 85.0

    def test_dimension_threshold_fail(self):
        with pytest.raises(ValueError, match="reliability"):
            create_zkp_threshold_proof(
                actual_composite=85.0,
                threshold_composite=80.0,
                actual_dimension=80.0,
                threshold_dimension=85.0,
                dimension_name="reliability",
            )

    def test_verify_placeholder_warns(self):
        proof = create_zkp_threshold_proof(85.0, 80.0)
        result = verify_zkp_threshold_proof(proof)
        assert result["verified"] is False
        assert "placeholder" in result["warning"]

    def test_proof_to_dict(self):
        proof = create_zkp_threshold_proof(
            85.0, 80.0,
            ratings_root_hash="ab" * 32,
        )
        d = proof.to_dict()
        assert d["public_inputs"]["threshold_composite"] == 80.0
        assert d["level"] == "privacy_preserving"

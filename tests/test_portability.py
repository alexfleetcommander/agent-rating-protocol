"""Tests for the portability module (ARP v2 Section 4)."""

import json
import pytest

from agent_rating_protocol.composition import CompositeSignal, Signal, compose, get_profile
from agent_rating_protocol.portability import (
    BehavioralSummary,
    DimensionSummary,
    OracleAttestation,
    PortableReputationBundle,
    ProvenanceSummary,
    compute_ratings_root_hash,
    generate_prb,
    multi_oracle_attestation,
    trust_discount,
)


# ---------------------------------------------------------------------------
# DimensionSummary
# ---------------------------------------------------------------------------

class TestDimensionSummary:
    def test_roundtrip(self):
        ds = DimensionSummary(mean=82.3, stddev=11.2, confidence=0.87, count=247)
        d = ds.to_dict()
        ds2 = DimensionSummary.from_dict(d)
        assert ds2.mean == 82.3
        assert ds2.count == 247


# ---------------------------------------------------------------------------
# ProvenanceSummary
# ---------------------------------------------------------------------------

class TestProvenanceSummary:
    def test_roundtrip(self):
        ps = ProvenanceSummary(
            coc_chain_age=312,
            coc_chain_length=48721,
            last_anchor_timestamp="2026-03-25T18:00:00Z",
        )
        d = ps.to_dict()
        assert d["cocChainAge"] == 312
        ps2 = ProvenanceSummary.from_dict(d)
        assert ps2.coc_chain_length == 48721


# ---------------------------------------------------------------------------
# BehavioralSummary
# ---------------------------------------------------------------------------

class TestBehavioralSummary:
    def test_roundtrip(self):
        bs = BehavioralSummary(
            total_interactions=1847,
            rating_participation_rate=0.89,
            dispute_rate=0.003,
            average_response_time_ms=4200,
        )
        d = bs.to_dict()
        assert d["totalInteractions"] == 1847
        bs2 = BehavioralSummary.from_dict(d)
        assert bs2.dispute_rate == 0.003


# ---------------------------------------------------------------------------
# Merkle root hash
# ---------------------------------------------------------------------------

class TestMerkleRoot:
    def test_empty_returns_hash(self):
        result = compute_ratings_root_hash([])
        assert len(result) == 64  # SHA-256 hex

    def test_single_leaf(self):
        h = "a" * 64
        result = compute_ratings_root_hash([h])
        assert len(result) == 64

    def test_deterministic(self):
        hashes = ["ab" * 32, "cd" * 32, "ef" * 32]
        r1 = compute_ratings_root_hash(hashes)
        r2 = compute_ratings_root_hash(hashes)
        assert r1 == r2

    def test_order_matters(self):
        hashes = ["ab" * 32, "cd" * 32]
        r1 = compute_ratings_root_hash(hashes)
        r2 = compute_ratings_root_hash(list(reversed(hashes)))
        assert r1 != r2

    def test_two_leaves(self):
        hashes = ["ab" * 32, "cd" * 32]
        result = compute_ratings_root_hash(hashes)
        assert len(result) == 64


# ---------------------------------------------------------------------------
# PRB generation
# ---------------------------------------------------------------------------

class TestGeneratePRB:
    def _make_composite(self):
        return CompositeSignal(
            profile_id="urn:absupport:arp:v2:profile:general-purpose",
            value=78.4,
            confidence=0.83,
            input_count=7,
        )

    def _make_dimensions(self):
        return {
            "reliability": DimensionSummary(82.3, 11.2, 0.87, 247),
            "accuracy": DimensionSummary(88.1, 8.7, 0.89, 241),
        }

    def test_generate_prb_basic(self):
        prb = generate_prb(
            issuer_id="did:web:oracle.example.com",
            subject_id="did:web:agent.example.com",
            composite=self._make_composite(),
            dimensions=self._make_dimensions(),
            rating_hashes=["ab" * 32],
        )
        assert prb.issuer_id == "did:web:oracle.example.com"
        assert prb.subject_id == "did:web:agent.example.com"
        assert prb.ratings_root_hash

    def test_prb_to_vc_format(self):
        prb = generate_prb(
            issuer_id="did:web:oracle.example.com",
            subject_id="did:web:agent.example.com",
            composite=self._make_composite(),
            dimensions=self._make_dimensions(),
            rating_hashes=["ab" * 32],
            issuer_name="Test Oracle",
            issuer_reliability=94.0,
            issuer_confidence=0.97,
        )
        vc = prb.to_vc()
        assert "VerifiableCredential" in vc["type"]
        assert "AgentReputationBundle" in vc["type"]
        assert vc["issuer"]["id"] == "did:web:oracle.example.com"
        assert "reputationSummary" in vc["credentialSubject"]
        assert vc["proof"]["type"] == "DataIntegrityProof"

    def test_prb_roundtrip_vc(self):
        prb = generate_prb(
            issuer_id="did:web:oracle.example.com",
            subject_id="did:web:agent.example.com",
            composite=self._make_composite(),
            dimensions=self._make_dimensions(),
            rating_hashes=["ab" * 32, "cd" * 32],
            provenance=ProvenanceSummary(312, 48721),
            behavioral=BehavioralSummary(1847, 0.89, 0.003, 4200),
        )
        vc = prb.to_vc()
        prb2 = PortableReputationBundle.from_vc(vc)
        assert prb2.issuer_id == prb.issuer_id
        assert prb2.subject_id == prb.subject_id
        assert prb2.ratings_root_hash == prb.ratings_root_hash

    def test_prb_validity(self):
        prb = generate_prb(
            issuer_id="did:web:oracle",
            subject_id="did:web:agent",
            composite=self._make_composite(),
            dimensions={},
            rating_hashes=[],
        )
        assert prb.is_valid()

    def test_prb_to_json(self):
        prb = generate_prb(
            issuer_id="did:web:oracle",
            subject_id="did:web:agent",
            composite=self._make_composite(),
            dimensions={},
            rating_hashes=[],
        )
        j = prb.to_json(indent=2)
        parsed = json.loads(j)
        assert parsed["type"] == ["VerifiableCredential", "AgentReputationBundle"]


# ---------------------------------------------------------------------------
# Multi-oracle attestation
# ---------------------------------------------------------------------------

class TestMultiOracleAttestation:
    def test_consensus_median(self):
        attestations = [
            OracleAttestation("oracle-a", 78.4),
            OracleAttestation("oracle-b", 77.9),
            OracleAttestation("oracle-c", 78.1),
        ]
        result = multi_oracle_attestation(attestations)
        assert result["consensusValue"] == 78.1
        assert result["consensusMethod"] == "median"
        assert result["status"] == "consensus"

    def test_divergence_flagged(self):
        attestations = [
            OracleAttestation("oracle-a", 78.0),
            OracleAttestation("oracle-b", 95.0),
            OracleAttestation("oracle-c", 77.0),
        ]
        result = multi_oracle_attestation(attestations, max_divergence=10.0)
        assert result["status"] == "disputed"
        assert result["maxDivergence"] == 18.0

    def test_insufficient_attestations(self):
        with pytest.raises(ValueError, match="Need at least"):
            multi_oracle_attestation(
                [OracleAttestation("oracle-a", 78.0)],
                threshold=3,
            )

    def test_custom_threshold(self):
        attestations = [
            OracleAttestation("a", 80),
            OracleAttestation("b", 81),
        ]
        result = multi_oracle_attestation(attestations, threshold=2)
        assert result["threshold"] == 2

    def test_attestation_roundtrip(self):
        a = OracleAttestation("oracle-x", 85.5, "sig123")
        d = a.to_dict()
        a2 = OracleAttestation.from_dict(d)
        assert a2.oracle_id == "oracle-x"
        assert a2.composite_value == 85.5


# ---------------------------------------------------------------------------
# Trust discount
# ---------------------------------------------------------------------------

class TestTrustDiscount:
    def test_full_trust(self):
        result = trust_discount(80.0, oracle_trust=1.0, domain_overlap=1.0)
        assert result == 80.0

    def test_partial_trust(self):
        result = trust_discount(80.0, oracle_trust=0.5, domain_overlap=1.0)
        assert abs(result - 40.0) < 0.01

    def test_single_oracle_steady_state(self):
        result = trust_discount(80.0, is_single_oracle=True)
        assert abs(result - 40.0) < 0.01  # 80 * 0.5

    def test_single_oracle_bootstrap(self):
        result = trust_discount(
            80.0, is_single_oracle=True, is_bootstrap_period=True
        )
        assert abs(result - 56.0) < 0.01  # 80 * 0.7

    def test_domain_mismatch(self):
        result = trust_discount(80.0, domain_overlap=0.3)
        assert result < 30

    def test_zero_trust(self):
        result = trust_discount(80.0, oracle_trust=0.0)
        assert result == 0.0

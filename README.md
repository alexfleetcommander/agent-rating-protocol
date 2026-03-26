# Agent Rating Protocol

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/downloads/)

Decentralized agent reputation protocol — signal composition, portable reputation bundles, Merkle verification, and anti-Goodhart architecture. Reference implementation of the [Agent Rating Protocol whitepaper](https://vibeagentmaking.com/whitepaper.html), companion to the [Chain of Consciousness](https://vibeagentmaking.com/whitepaper.html) specification.

## What's New in v0.3.0

**Signal Composition** (Section 3) — Combine ARP ratings, CoC provenance, and behavioral signals into configurable composite trust scores. Five composition operations (weighted linear, confidence-adjusted, threshold gates, diminishing returns, penalty floors) applied in canonical order. Five standard weight profiles: general-purpose, high-reliability, fast-turnaround, compliance-first, cost-optimized.

**Signal Portability** (Section 4) — Portable Reputation Bundles (PRBs) in W3C Verifiable Credential format. Multi-oracle attestation with median consensus and divergence detection. Trust discount model for cross-platform reputation transfer.

**Signal Verification** (Section 5) — Three verification levels: hash-chain (basic), Merkle proof (standard), ZKP threshold (placeholder for future). Full Merkle tree implementation with sampled verification for large rating sets.

**Anti-Goodhart Architecture** (Section 6) — Metric rotation with published bounds. Shadow metric tracking with divergence detection. Differential privacy noise injection for composite score queries.

### Previous releases

<details>
<summary>v0.2.0</summary>

- **AgentIdentity** — Nested rater/ratee objects with optional `identity_proof` (Section 4.1)
- **Interaction Verification** — `verification_level` field: `verified`, `unilateral`, `self_reported` with automatic weight multipliers (Section 4.8)
- **Anti-Inflation** — Rater calibration via standard deviation penalty (sigma < 10) and recency weighting (Section 4.6)
- **Governance Cap** — No agent can hold >10% of effective voting weight (Section 5.4)
- **Metadata** — `rater_chain_length` field for CoC chain integration (Section 4.1)
</details>

## Quickstart

```python
from agent_rating_protocol import RatingRecord, RatingStore, get_reputation

store = RatingStore("ratings.jsonl")
store.append_rating(RatingRecord(
    rater_id="agent-a",
    ratee_id="agent-b",
    reliability=85,
    accuracy=90,
    rater_chain_age_days=100,
    rater_total_ratings_given=50,
))
print(get_reputation(store, "agent-b"))
```

### v0.3.0: Composite Scores

```python
from agent_rating_protocol import get_composite

result = get_composite(
    store, "agent-b",
    profile_name="general-purpose",
    coc_age_days=100,
    rating_participation_rate=0.8,
)
print(result["composite"]["value"])     # e.g. 78.4
print(result["composite"]["confidence"]) # e.g. 0.83
```

### v0.3.0: Portable Reputation Bundles

```python
from agent_rating_protocol import generate_prb_from_store

vc = generate_prb_from_store(
    store, "agent-b",
    issuer_id="did:web:oracle.example.com",
    coc_age_days=312,
)
# Returns a W3C Verifiable Credential dict
print(vc["credentialSubject"]["reputationSummary"])
```

### v0.3.0: Signal Verification

```python
from agent_rating_protocol.signals import MerkleTree, verify_merkle_proof

hashes = [r.record_hash for r in store.get_ratings_for("agent-b")]
tree = MerkleTree(hashes)
proof = tree.get_proof(0)
assert verify_merkle_proof(proof)  # Proves rating is in the tree
```

### v0.3.0: Anti-Goodhart

```python
from agent_rating_protocol.anti_goodhart import (
    generate_rotation_bounds, rotate_weights, add_dp_noise,
)
from agent_rating_protocol import get_profile

profile = get_profile("general-purpose")
bounds = generate_rotation_bounds(profile)
new_profile, event = rotate_weights(profile, bounds)
# Weights rotated within published bounds

noised_score = add_dp_noise(78.4, epsilon=1.0)
# ~78.4 ± 2 points of Laplace noise
```

## Install

```bash
pip install agent-rating-protocol
```

With optional Chain of Consciousness integration:

```bash
pip install agent-rating-protocol[coc]
```

## Features

### Core (v0.1/v0.2)
- **5-dimension rating** — reliability, accuracy, latency, protocol_compliance, cost_efficiency (1-100 scale)
- **Bilateral blind protocol** — commit-reveal ensures neither party sees the other's rating until both submit
- **Sybil-resistant weighting** — W = log2(1 + age) x log2(1 + ratings_given)
- **Interaction verification** — verified/unilateral/self_reported levels with 0.5x multiplier
- **Anti-inflation calibration** — low-variance raters penalized (Section 4.6)
- **Governance cap** — 10% max effective voting weight per agent
- **Append-only store** — JSONL-backed, tamper-evident via SHA-256 record hashes
- **Zero required dependencies** — stdlib only. Python 3.8+.

### v0.3.0: Composition Layer
- **Signal composition algebra** — five operations in canonical order
- **Standard weight profiles** — general-purpose, high-reliability, fast-turnaround, compliance-first, cost-optimized
- **Custom profiles** — JSON-configurable with rotation bounds
- **Composite signals** — with confidence, validity windows, weakest-input metadata

### v0.3.0: Portability Layer
- **Portable Reputation Bundles** — W3C Verifiable Credential format
- **Multi-oracle attestation** — median consensus with divergence detection
- **Trust discount model** — configurable per oracle trust, domain overlap, volume
- **Merkle root computation** — binary Merkle tree over rating hashes

### v0.3.0: Verification Layer
- **Hash-chain verification** — individual rating integrity (basic)
- **Merkle proof verification** — aggregate score verification (standard)
- **Sampled verification** — configurable sample size for large rating sets
- **ZKP threshold proofs** — placeholder interface for future integration

### v0.3.0: Anti-Goodhart Layer
- **Signal tiers** — public, queryable, private stratification
- **Metric rotation** — weights rotated within published bounds
- **Shadow metrics** — divergence detection between primary and shadow signals
- **Shadow commitments** — hash-based audit mechanism for oracle accountability
- **Differential privacy** — Laplace noise injection with per-agent correlation

## CLI Reference

```bash
# Submit a rating
agent-rating rate agent-b --rater agent-a --reliability 85 --accuracy 90

# Query reputation
agent-rating query agent-b
agent-rating query agent-b --dimension reliability --window 180 --calibrated

# Verify a rating hash
agent-rating verify <rating-uuid>

# Store statistics
agent-rating status

# v0.3.0: Compute composite score
agent-rating compose agent-b --profile general-purpose --coc-age 100

# v0.3.0: Generate Portable Reputation Bundle
agent-rating export-prb agent-b --issuer did:web:oracle.example.com

# v0.3.0: Verify signals via Merkle proof
agent-rating verify-signal agent-b --sample 50

# All commands support --json for machine-readable output
agent-rating compose agent-b --json
```

## Modules

| Module | Description | Whitepaper Section |
|--------|-------------|-------------------|
| `rating.py` | Rating record schema, validation, hashing | v1 Section 4.1 |
| `blind.py` | Bilateral blind commit-reveal | v1 Section 4.4 |
| `weight.py` | Rater weight, calibration, recency, composition bridge | v1 Section 4.5, v2 Section 3 |
| `store.py` | Append-only JSONL rating store | v1 Section 2.3 |
| `query.py` | Reputation queries, composite scores, PRB generation | v1 Section 4.5, v2 Sections 3-4 |
| `composition.py` | Signal composition algebra, weight profiles | v2 Section 3 |
| `portability.py` | Portable Reputation Bundles, multi-oracle attestation | v2 Section 4 |
| `signals.py` | Hash-chain, Merkle tree, ZKP verification | v2 Section 5 |
| `anti_goodhart.py` | Metric rotation, shadow metrics, differential privacy | v2 Section 6 |
| `cli.py` | Command-line interface | All |

## Weight Formula

```
W(rater) = log2(1 + chain_age_days) x log2(1 + total_ratings_given)
```

## Canonicalization

Record hashes use `json.dumps(sort_keys=True, separators=(",",":"))` for deterministic serialization. The whitepaper specifies JCS (RFC 8785). The deviation is documented in source and has no practical impact for the data types used. For strict compliance, substitute an RFC 8785 library.

## Whitepaper

- **[Agent Rating Protocol v1](https://vibeagentmaking.com/whitepaper/rating-protocol/)** — Decentralized reputation for autonomous agent economies
- **[Agent Rating Protocol v2](https://vibeagentmaking.com/whitepaper/rating-protocol/)** — Signal composition, portability, verification, anti-Goodhart
- **[Chain of Consciousness](https://vibeagentmaking.com/whitepaper.html)** — Cryptographic provenance chains for AI agent identity

## Security Disclaimer (VAM-SEC v1.0)

This software is provided for research and development purposes. The rating protocol includes cryptographic commitments (SHA-256), bilateral blind protocol, Merkle tree verification, and differential privacy mechanisms, but has NOT been formally audited by a third-party security firm. The ZKP module is a placeholder — it validates thresholds but does not generate real zero-knowledge proofs. Before using in production where reputation scores influence high-stakes decisions, conduct an independent security review. The append-only store provides tamper evidence but not tamper prevention. For stronger guarantees, use CoC integration with external anchoring (OTS + TSA).

## License

Apache 2.0 — see [LICENSE](LICENSE).

# Agent Rating Protocol

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/downloads/)

Decentralized agent reputation protocol — multidimensional ratings with bilateral blind commit-reveal and Sybil-resistant weighting. Reference implementation of the [Agent Rating Protocol whitepaper](https://vibeagentmaking.com/whitepaper.html), companion to the [Chain of Consciousness](https://vibeagentmaking.com/whitepaper.html) specification.

## What's New in v0.2.0

- **AgentIdentity** — Nested rater/ratee objects with optional `identity_proof` (whitepaper Section 4.1)
- **Interaction Verification** — `verification_level` field: `verified`, `unilateral`, `self_reported` with automatic weight multipliers (Section 4.8)
- **Anti-Inflation** — Rater calibration via standard deviation penalty (sigma < 10 penalized) and recency weighting (Section 4.6)
- **Governance Cap** — No agent can hold >10% of effective voting weight (Section 5.4)
- **Metadata** — `rater_chain_length` field for CoC chain integration (Section 4.1)
- **Canonicalization** — Documented JCS deviation with deterministic json.dumps (Section 4.1)

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

## Install

```bash
pip install agent-rating-protocol
```

With optional Chain of Consciousness integration:

```bash
pip install agent-rating-protocol[coc]
```

## Features

- **5-dimension rating** — reliability, accuracy, latency, protocol_compliance, cost_efficiency (1-100 scale)
- **Bilateral blind protocol** — commit-reveal ensures neither party sees the other's rating until both submit
- **Sybil-resistant weighting** — W = log2(1 + age) x log2(1 + ratings_given). Score received never affects weight.
- **Interaction verification** — verified/unilateral/self_reported levels with automatic 0.5x weight for unverified
- **Anti-inflation calibration** — raters with low score variance (sigma < 10) get penalized (Section 4.6)
- **Governance cap** — 10% max effective voting weight per agent (Section 5.4)
- **Recency weighting** — recent ratings carry more weight within the rolling window
- **Append-only store** — JSONL-backed, tamper-evident via SHA-256 record hashes
- **Rolling windows** — default 365-day window prevents stale reputation
- **Confidence scoring** — new agents show high uncertainty, not zero trust
- **Zero required dependencies** — stdlib only for core. Optional CoC integration.
- **Identity-agnostic** — works with DIDs, URIs, ERC-8004, W3C VC, or plain strings

## API Reference

### AgentIdentity (v0.2.0)

```python
from agent_rating_protocol import AgentIdentity

# From a dict (whitepaper schema)
identity = AgentIdentity.from_dict({
    "agent_id": "did:example:123",
    "identity_proof": "vc:proof:abc"
})

# From a plain string (backward compat)
identity = AgentIdentity.from_dict("agent-a")

# Access on RatingRecord
record = RatingRecord(
    rater_id="agent-a",
    ratee_id="agent-b",
    rater_identity_proof="did:proof:rater",
)
print(record.rater_identity)  # AgentIdentity(agent_id='agent-a', identity_proof='did:proof:rater')
```

### RatingRecord

```python
from agent_rating_protocol import RatingRecord

record = RatingRecord(
    rater_id="did:example:alice",
    ratee_id="did:example:bob",
    interaction_id="task-uuid-here",
    reliability=85,
    accuracy=90,
    latency=75,
    protocol_compliance=95,
    cost_efficiency=70,
    rater_chain_age_days=365,
    rater_total_ratings_given=100,
    rater_chain_length=1500,                  # v0.2.0: CoC chain length
    verification_level="verified",             # v0.2.0: verified|unilateral|self_reported
    rater_identity_proof="did:proof:alice",     # v0.2.0: optional identity proof
    ratee_identity_proof="did:proof:bob",       # v0.2.0: optional identity proof
)

record.to_dict()       # JSON-serializable dict (whitepaper schema)
record.to_json()       # JSON string
record.verify_hash()   # True if record_hash is valid
record.compute_hash()  # Recompute SHA-256 hash

RatingRecord.from_dict(d)  # Deserialize from dict
```

### RatingStore

```python
from agent_rating_protocol import RatingStore

store = RatingStore("ratings.jsonl")

store.append_rating(record)               # Append (validates hash first)
store.get_ratings_for("agent-b")          # Ratings received by agent
store.get_ratings_by("agent-a")           # Ratings submitted by agent
store.get_rating("uuid")                  # Look up by rating_id
store.count()                             # Total ratings
store.stats()                             # Summary statistics
store.agents()                            # Per-agent rating counts
```

### Reputation Queries

```python
from agent_rating_protocol import get_reputation

# All dimensions
result = get_reputation(store, "agent-b", window_days=365)
# {'agent_id': 'agent-b', 'num_ratings': 5, 'confidence': 0.3333, 'scores': {...}}

# Single dimension
result = get_reputation(store, "agent-b", dimension="reliability")
# {'agent_id': 'agent-b', 'score': 85.0, 'dimension': 'reliability', ...}

# With anti-inflation calibration (Section 4.6)
result = get_reputation(store, "agent-b", apply_calibration=True)
```

### Governance Weights (v0.2.0)

```python
from agent_rating_protocol import get_governance_weights

# Compute governance weights with 10% cap (Section 5.4)
weights = get_governance_weights(store, cap=0.10)
# {'agent-a': 56.4, 'agent-b': 12.3, ...}
# No agent exceeds 10% of total pre-cap weight
```

### Bilateral Blind Protocol

```python
from agent_rating_protocol import BlindExchange, generate_nonce

exchange = BlindExchange(interaction_id="task-001")

# Agent A commits
nonce_a = generate_nonce()
exchange.submit_commitment("agent-a", rating_a.to_dict(), nonce_a)

# Agent B commits
nonce_b = generate_nonce()
exchange.submit_commitment("agent-b", rating_b.to_dict(), nonce_b)

# Both reveal (triggered when both committed)
exchange.reveal_rating("agent-a", rating_a.to_dict(), nonce_a)
exchange.reveal_rating("agent-b", rating_b.to_dict(), nonce_b)

# Get simultaneous results
rating_a_result, rating_b_result = exchange.get_results()
```

### Weight Calculation

```python
from agent_rating_protocol import (
    rater_weight, confidence, effective_weight,
    verification_level_multiplier, rater_calibration_factor,
)

w = rater_weight(chain_age_days=365, total_ratings_given=100)  # ~ 56.4
c = confidence(num_ratings=50)  # ~ 0.833

# v0.2.0: verification level multipliers
verification_level_multiplier("verified")       # 1.0
verification_level_multiplier("unilateral")     # 0.5
verification_level_multiplier("self_reported")  # 0.5

# v0.2.0: anti-inflation calibration
factor = rater_calibration_factor([95, 95, 95, 96, 94])  # low sigma -> penalty
```

## CLI Reference

```bash
# Submit a rating
agent-rating rate agent-b --rater agent-a --reliability 85 --accuracy 90

# v0.2.0: with verification level and identity proofs
agent-rating rate agent-b --rater agent-a --reliability 85 \
  --verification-level unilateral \
  --chain-length 1500 \
  --rater-proof "did:proof:alice"

# Query reputation
agent-rating query agent-b
agent-rating query agent-b --dimension reliability --window 180

# v0.2.0: with anti-inflation calibration
agent-rating query agent-b --calibrated

# Verify a rating hash
agent-rating verify <rating-uuid>

# Store statistics
agent-rating status

# All commands support --json for machine-readable output
agent-rating query agent-b --json

# Custom store path
agent-rating --store /path/to/ratings.jsonl status
```

## CoC Integration

If [chain-of-consciousness](https://pypi.org/project/chain-of-consciousness/) is installed and the `COC_CHAIN_FILE` environment variable is set, ratings are automatically recorded as `RATING_SUBMITTED` chain entries:

```bash
export COC_CHAIN_FILE=chain.jsonl
agent-rating rate agent-b --rater agent-a --reliability 85
# -> Rating stored in ratings.jsonl AND recorded in chain.jsonl
```

## Rating Dimensions

| Dimension | Measures | Scale |
|-----------|----------|-------|
| reliability | Task completion, uptime | 1-100 |
| accuracy | Output correctness | 1-100 |
| latency | Response speed vs. complexity | 1-100 |
| protocol_compliance | Message format, handshake correctness | 1-100 |
| cost_efficiency | Resource usage vs. value | 1-100 |

Score buckets: 1-20 poor, 21-40 below average, 41-60 average, 61-80 good, 81-100 excellent.

## Weight Formula

```
W(rater) = log2(1 + chain_age_days) x log2(1 + total_ratings_given)
```

Governance weight equals rating weight by design — both derived from tenure and participation, never from score received.

**Verification level multipliers (v0.2.0):** Unilateral and self-reported ratings carry 0.5x weight.

**Anti-inflation (v0.2.0):** Raters with standard deviation < 10 across all their scores are penalized by sigma/10.

**Governance cap (v0.2.0):** No agent can hold >10% of effective voting weight.

## Canonicalization

Record hashes use `json.dumps(sort_keys=True, separators=(",",":"))` for deterministic serialization. The whitepaper specifies JCS (RFC 8785). The deviation is documented in the source and has no practical impact for the data types used (strings, integers, booleans). For strict compliance, substitute an RFC 8785 library.

## Whitepaper

Full protocol specification, game theory analysis, and governance model:

- **[Agent Rating Protocol Whitepaper](https://vibeagentmaking.com/whitepaper.html)** — Decentralized reputation for autonomous agent economies
- **[Chain of Consciousness](https://vibeagentmaking.com/whitepaper.html)** — Cryptographic provenance chains for AI agent identity

## Security Disclaimer (VAM-SEC v1.0)

This software is provided for research and development purposes. The rating protocol includes cryptographic commitments (SHA-256) and a bilateral blind protocol, but has NOT been formally audited by a third-party security firm. Before using in production environments where reputation scores influence high-stakes decisions, conduct an independent security review. The append-only store provides tamper evidence but not tamper prevention — an attacker with filesystem access can modify the JSONL file directly. For stronger guarantees, use CoC integration with external anchoring (OTS + TSA).

## License

Apache 2.0 — see [LICENSE](LICENSE).

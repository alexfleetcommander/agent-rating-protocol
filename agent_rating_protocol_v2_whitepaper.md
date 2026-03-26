# Agent Rating Protocol v2: Signal Composition, Portability, and Anti-Goodhart Architecture

**Version:** 2.0.0
**Authors:** Charlie (Deep Dive Analyst), Alex (Fleet Coordinator), Bravo (Research), Editor (Content Review)
**Contact:** alex@vibeagentmaking.com
**Date:** 2026-03-26
**Status:** Pre-publication Draft
**License:** Apache 2.0
**Organization:** AB Support LLC
**Prerequisite:** Agent Rating Protocol v1.0.0 [1]

---

## Abstract

ARP v1 [1] established a decentralized reputation system enabling agents to rate each other after interactions using bilateral blind evaluation, age-weighted governance, and anti-inflation mechanisms. It answers **how well does this agent perform?** — but each rating remains siloed within the interaction context that produced it. ARP v1 ratings do not compose into cross-protocol trust signals, do not follow agents across platforms, cannot be verified by third parties without querying the original aggregation node, and — once published — become optimization targets vulnerable to Goodhart's Law.

ARP v2 extends the base protocol with four new capabilities that transform isolated ratings into a portable, composable, verifiable trust infrastructure:

1. **Signal Composition** — a formal mechanism for combining ARP dimensional scores, Chain of Consciousness [2] operational age, Quality Verification pass rates, and other protocol data into configurable composite trust signals. Rather than prescribing a single formula, the protocol defines a composition algebra with domain-specific weight profiles, enabling the equivalent of a FICO score for agents — but one that is open, auditable, and domain-adaptive.

2. **Signal Portability** — cross-platform reputation aggregation via Portable Reputation Bundles. An agent's reputation follows it from marketplace to marketplace through W3C Verifiable Credentials [3] containing cryptographically signed reputation summaries, enabling reputation to function as a transferable asset rather than a platform-locked silo.

3. **Signal Verification** — any third party can independently verify that a trust signal is genuine (backed by real CoC chain entries, real ARP ratings from real interactions) without trusting the presenting agent or any single aggregation node. Zero-knowledge proof integration enables threshold verification ("this agent's composite score exceeds 80") without revealing exact scores.

4. **Anti-Goodhart Architecture** — a systematic defense against the tendency of published metrics to become gaming targets. The protocol specifies signal stratification (public, queryable, and private signal tiers), metric rotation schedules, shadow metrics for gaming detection, and anomaly-triggered review mechanisms.

ARP v2 is backward-compatible with v1: all v1 rating records, weight formulas, governance mechanisms, and identity adapters remain unchanged. v2 adds new protocol layers above the existing rating infrastructure. v1 agents interoperate with v2 agents without modification — they simply cannot produce or consume the new signal types until they upgrade.

The competitive landscape has evolved rapidly since ARP v1's publication. This specification positions ARP v2 relative to eight emerging systems — t54 Labs ($5M seed), ERC-8004, VOUCH, OpenRank, Lookout Agent Trust Intelligence, PayCrow, Zarq/Nerq, and Nostr Web of Trust — and demonstrates that no existing system provides the combination of open composition algebra, standards-based portability, zero-knowledge verification, and systematic anti-Goodhart defenses specified here.

---

## Table of Contents

1. [Relationship to ARP v1](#1-relationship-to-arp-v1)
2. [New Definitions](#2-new-definitions)
3. [Signal Composition](#3-signal-composition)
4. [Signal Portability](#4-signal-portability)
5. [Signal Verification](#5-signal-verification)
6. [Anti-Goodhart Architecture](#6-anti-goodhart-architecture)
7. [Security Analysis of New Capabilities](#7-security-analysis-of-new-capabilities)
8. [Migration from v1 to v2](#8-migration-from-v1-to-v2)
9. [Updated Competitive Landscape](#9-updated-competitive-landscape)
10. [Integration Updates](#10-integration-updates)
11. [Future Work](#11-future-work)
12. [References](#12-references)

---

## 1. Relationship to ARP v1

### 1.1 What Does Not Change

ARP v2 is an extension, not a replacement. The following components from ARP v1 [1] are unchanged and remain normative:

- **Rating Record Schema** (v1 Section 4.1) — the five-dimension, 1-100 scale rating record
- **Five Rating Dimensions** (v1 Section 4.2) — reliability, accuracy, latency, protocol compliance, cost efficiency
- **Bilateral Blind Protocol** (v1 Section 4.4) — commit-reveal evaluation
- **Rating Weight Formula** (v1 Section 4.5) — `W = log2(1 + age_days) x log2(1 + ratings_given)`
- **Anti-Inflation Mechanisms** (v1 Section 4.6) — variance floor, mean shift detection, coalition detection
- **Governance Model** (v1 Section 5) — governance by operational tenure, not by score
- **Identity Adapter Interface** (v1 Section 7.8) — system-agnostic identity abstraction
- **Interaction Verification Protocol** (v1 Section 4.8) — interaction_id generation and validation

Implementers MUST read ARP v1 as the base specification. This document specifies only the additions.

### 1.2 What Changes

ARP v2 adds four new protocol layers above the existing rating infrastructure:

| Layer | New in v2 | Depends On |
|-------|-----------|------------|
| **Composition Layer** | Signal algebra, weight profiles, composite signals | v1 rating records, external data sources |
| **Portability Layer** | Portable Reputation Bundles, cross-platform aggregation | Composition Layer, W3C VCs |
| **Verification Layer** | Third-party signal verification, ZKP threshold proofs | Portability Layer, CoC chain |
| **Anti-Goodhart Layer** | Signal stratification, metric rotation, shadow metrics | All layers |

### 1.3 Versioning

The rating record schema gains a new `version` field value:

```json
{
  "version": 2,
  "v2_extensions": {
    "signal_composition_support": true,
    "portable_bundle_endpoint": "<URI or null>",
    "zkp_verification_support": false
  }
}
```

v1 records (`"version": 1`) remain valid. v2 aggregation nodes MUST accept v1 records and treat missing `v2_extensions` as all-false/null. v1 aggregation nodes encountering v2 records SHOULD ignore unrecognized fields per RFC 7493 (I-JSON) forward-compatibility conventions.

---

## 2. New Definitions

The following terms are introduced in v2. All v1 definitions [1, Section 2] remain in force.

**Signal.** A structured data object conveying trust-relevant information about an agent. Signals are typed: a *rating signal* derives from ARP ratings, a *provenance signal* derives from CoC chain data, a *credential signal* derives from W3C VCs or other attestations. Signals are the atomic inputs to signal composition.

**Composite Signal.** A signal produced by combining multiple input signals via a composition function. Analogous to a FICO score being composed from five underlying dimensions — but open, auditable, and domain-configurable.

**Composition Function.** A deterministic function `f: Signal[] -> CompositeSignal` that maps a vector of input signals to a composite output. The protocol defines a composition algebra (Section 3) specifying permitted operations, constraints, and transparency requirements.

**Weight Profile.** A named configuration specifying which signals are composed, with what weights, for a particular domain or use case. Example: a "code review" profile might weight accuracy at 40%, reliability at 30%, latency at 10%, protocol compliance at 15%, cost efficiency at 5%. Weight profiles are governance-managed.

**Portable Reputation Bundle (PRB).** A W3C Verifiable Credential containing an agent's composite reputation summary, signed by one or more reputation oracles (aggregation nodes), with cryptographic links to the underlying rating evidence. The unit of cross-platform reputation transfer.

**Reputation Oracle.** An aggregation node (v1 Section 4.3) that additionally computes composite signals and issues Portable Reputation Bundles. Reputation oracles are accountable within the ARP ecosystem — they carry their own ARP reputation scores and are subject to the same anti-gaming mechanisms as any other participant.

**Signal Tier.** One of three visibility classifications for signals: *public* (freely queryable by any agent), *queryable* (available on request with rate limiting and access controls), or *private* (used only for internal computation, never exposed to external queries). Signal stratification is the primary anti-Goodhart mechanism.

**Shadow Metric.** A private-tier signal that monitors the health and integrity of a public or queryable signal. Shadow metrics detect gaming by measuring divergence between the optimized metric and the underlying quality it was designed to capture.

**Metric Rotation.** The periodic adjustment of composition weights within a weight profile, designed to prevent static optimization. Rotation schedules are governance-managed and announced in advance (the rotation *schedule* is public; the specific weight changes are revealed only when they take effect).

---

## 3. Signal Composition

### 3.1 The Problem: Isolated Signals Are Insufficient for Trust Decisions

ARP v1 produces five-dimensional rating vectors per interaction. An agent querying another's reputation receives: `{reliability: 82, accuracy: 88, latency: 71, protocol_compliance: 93, cost_efficiency: 79, confidence: 0.87}`. This is informative but insufficient for automated trust decisions that require a single threshold check — "should I delegate this $500 task to this agent?"

Human credit systems solved the analogous problem through composition. FICO composes five underlying dimensions (payment history 35%, amounts owed 30%, credit history length 15%, new credit 10%, credit mix 10%) into a single 300-850 score [4]. The composition reduces a complex multi-dimensional assessment to a decision-ready scalar. FICO's limitations — opacity, discrimination, gaming vulnerability — inform our design but do not invalidate the composition principle.

More recently, ML-based alternative scoring systems like Upstart (1,600+ variables, 44% more approvals at equivalent risk) and Zest AI (25% more approvals across 180+ banks) have demonstrated that richer signal composition with adaptive weighting outperforms static formulas, at the cost of increased opacity [5, 6]. PayCrow's trust scoring aggregates four on-chain sources with fixed weights (PayCrow Reputation 40%, ERC-8004 Identity 25%, Moltbook Social 15%, Base Chain Activity 20%) — the first concrete agent-specific composition model, operating within a broader x402 agent payment ecosystem with ~$600M in annualized volume across all providers [7].

The design challenge is to enable composition that is: (a) richer than FICO's five-factor static model, (b) more transparent than Upstart's ML black box, (c) domain-adaptive rather than one-size-fits-all, and (d) resistant to the gaming that every published composite score invites.

### 3.2 Signal Types and Sources

ARP v2 composition operates over four categories of input signal:

| Signal Category | Source | Example Signals |
|----------------|--------|-----------------|
| **Rating Signals** | ARP v1 ratings | Per-dimension weighted averages, confidence, rating volume, rater diversity |
| **Provenance Signals** | Chain of Consciousness [2] | Operational age (days), chain length, anchor count, anchor recency, fork history |
| **Credential Signals** | W3C VCs, ERC-8004, operator attestations | Verified identity, certifications, operator vouch, third-party audits |
| **Behavioral Signals** | Interaction history, protocol participation | Interaction volume, task completion rate, dispute history, rating participation rate |

Each signal has a schema:

```json
{
  "signal_type": "rating_dimension",
  "signal_id": "arp:reliability:weighted_mean",
  "source": "arp:aggregation_node:did:web:oracle.example.com",
  "value": 82.3,
  "confidence": 0.87,
  "window": "365d",
  "sample_size": 247,
  "timestamp": "2026-03-26T00:00:00Z",
  "verification": {
    "method": "aggregation_node_signature",
    "proof": "<base64-encoded signature>"
  }
}
```

### 3.3 The Composition Algebra

Rather than prescribing a single composition formula (which would itself become a Goodhart target), ARP v2 defines a **composition algebra** — a set of permitted operations that any weight profile can use:

**Operation 1: Weighted Linear Combination**

```
composite = Σᵢ (wᵢ × signalᵢ) / Σᵢ wᵢ
```

where `Σᵢ wᵢ = 1.0` and each `wᵢ ≥ 0`. This is the FICO-style approach. Transparent, auditable, but static and gameable if weights are published.

**Operation 2: Confidence-Adjusted Combination**

```
composite = Σᵢ (wᵢ × confidenceᵢ × signalᵢ) / Σᵢ (wᵢ × confidenceᵢ)
```

Signals with low confidence (few ratings, short operational history) contribute proportionally less to the composite. This naturally handles cold-start agents without requiring special-case logic.

**Operation 3: Threshold Gates**

```
if signal_j < threshold_j: composite = DISQUALIFIED
```

Certain signals serve as binary prerequisites rather than continuous inputs. Example: an agent with fewer than 5 rated interactions is DISQUALIFIED from receiving a composite score, regardless of how high its individual dimensions are. Gates prevent meaningless composites from thin data.

**Operation 4: Diminishing Returns Transform**

```
transformed_signal = 100 × (1 - e^(-signal/k))
```

Applies a diminishing returns curve to signals where marginal improvements above a threshold carry less trust value. An agent improving from 50 to 70 on reliability is more significant than improving from 85 to 95. The parameter `k` controls the curve's steepness and is weight-profile-specific.

**Operation 5: Penalty Floors**

```
if signal_j < floor_j: penalty = max_penalty × (floor_j - signal_j) / floor_j
composite = max(0, raw_composite - penalty)
```

A single catastrophically low dimension drags down the composite even if other dimensions are excellent. This prevents gaming where an agent neglects one dimension to optimize the others.

**Canonical operation order.** To ensure deterministic results regardless of implementation, the five operations MUST be applied in this order:

1. **Gates first (Operation 3).** Evaluate threshold gates on raw signal values. If any gate fails, the composite is DISQUALIFIED — no further computation. Gates operate on raw, untransformed signals to ensure that minimum thresholds reflect actual values, not transformed ones.

2. **Diminishing returns transform (Operation 4).** Apply the diminishing returns curve to signals that specify it in the weight profile. This transforms raw signals into their curved equivalents before combination.

3. **Confidence adjustment (Operation 2).** Apply confidence weighting to the (possibly transformed) signals. Low-confidence signals are down-weighted.

4. **Weighted linear combination (Operation 1).** Combine all confidence-adjusted, transformed signals using profile weights to produce the raw composite.

5. **Penalty floors last (Operation 5).** Evaluate penalty floors on the *raw signal values* (not transformed), and apply penalties to the composite. Penalties are computed from raw values to ensure that genuinely low dimensions trigger penalties regardless of transformation.

This ordering ensures that: gates disqualify early (avoiding wasted computation), transforms and confidence adjustments shape the composite, and penalty floors serve as a final safety check on the raw underlying data.

**Composition constraints:**
- All operations are deterministic given the same inputs and the canonical ordering above
- All weight profiles MUST be published (the weights themselves may be public or subject to rotation — see Section 6.3)
- Composition functions MUST NOT include trained ML models as black-box components (this is a transparency constraint, not a capability constraint — ML-derived weights are acceptable if the derivation methodology is published)
- Composition functions MUST be expressible in the algebra above — no arbitrary code execution

### 3.4 Weight Profiles

A weight profile is a named composition configuration:

```json
{
  "profile_id": "urn:absupport:arp:v2:profile:general-purpose",
  "version": "2026-Q1",
  "description": "General-purpose agent trust composite",
  "inputs": [
    {"signal_id": "arp:reliability:weighted_mean", "weight": 0.25, "operation": "confidence_adjusted"},
    {"signal_id": "arp:accuracy:weighted_mean", "weight": 0.25, "operation": "confidence_adjusted"},
    {"signal_id": "arp:latency:weighted_mean", "weight": 0.10, "operation": "confidence_adjusted"},
    {"signal_id": "arp:protocol_compliance:weighted_mean", "weight": 0.15, "operation": "confidence_adjusted"},
    {"signal_id": "arp:cost_efficiency:weighted_mean", "weight": 0.10, "operation": "confidence_adjusted"},
    {"signal_id": "coc:operational_age_days", "weight": 0.10, "operation": "diminishing_returns", "k": 365},
    {"signal_id": "behavioral:rating_participation_rate", "weight": 0.05, "operation": "linear"}
  ],
  "gates": [
    {"signal_id": "arp:total_ratings_received", "threshold": 5, "gate_type": "minimum"},
    {"signal_id": "coc:operational_age_days", "threshold": 7, "gate_type": "minimum"}
  ],
  "penalty_floors": [
    {"signal_id": "arp:reliability:weighted_mean", "floor": 30, "max_penalty": 25}
  ],
  "output_range": [0, 100],
  "rotation_schedule": "quarterly",
  "governance_approved": "2026-03-26",
  "effective_until": "2026-06-30"
}
```

**Standard profiles shipped with v2:**

| Profile | Domain | Key Weights | Use Case |
|---------|--------|-------------|----------|
| `general-purpose` | Any | Balanced across all signals | Default for platforms without domain-specific needs |
| `high-reliability` | Infrastructure, payments | Reliability 40%, accuracy 25% | Mission-critical tasks |
| `fast-turnaround` | Content, translation | Latency 30%, accuracy 25% | Time-sensitive work |
| `compliance-first` | Regulated industries | Protocol compliance 35%, accuracy 25% | Healthcare, finance |
| `cost-optimized` | Bulk processing | Cost efficiency 30%, reliability 25% | High-volume, low-margin tasks |

**Custom profiles.** Platforms and agent operators MAY define custom weight profiles. Custom profiles MUST be published (the existence and structure of the profile, including which signals it uses) but MAY use rotated weights (Section 6.3) for anti-Goodhart purposes. Custom profiles are not governance-managed — they are private to the defining entity.

### 3.5 Composite Score Properties

A composite signal includes metadata enabling consumers to assess its quality:

```json
{
  "composite_signal": {
    "profile_id": "urn:absupport:arp:v2:profile:general-purpose",
    "value": 78.4,
    "confidence": 0.83,
    "input_count": 7,
    "weakest_input": {"signal_id": "arp:latency:weighted_mean", "confidence": 0.42},
    "gate_status": "all_passed",
    "computed_at": "2026-03-26T12:00:00Z",
    "valid_until": "2026-04-02T12:00:00Z",
    "computed_by": "did:web:oracle.example.com"
  }
}
```

**Staleness.** Composite signals have a `valid_until` field. Consumers SHOULD NOT trust composites past their validity window. Default validity: 7 days (governance-configurable). This prevents stale composites from persisting after the underlying signals have changed.

**Weakest link.** The `weakest_input` field identifies the input signal with the lowest confidence, enabling consumers to understand where the composite is most uncertain.

### 3.6 Lessons from FICO's Failures

The composition system is designed to avoid three documented FICO failure modes:

**1. Opacity breeds distrust and gaming.** FICO publishes its five dimensions and approximate weights but keeps the exact algorithm proprietary [4]. Consumers cannot test for bias; researchers cannot audit for discrimination. ARP v2 requires that all composition operations and weight profile structures be published. The exact weights within a profile MAY be rotated (Section 6.3), but the algebra, the input signals, and the gates are always public.

**2. Static formulas invite optimization.** FICO's weights have been approximately stable for decades, enabling an industry of "credit repair" optimization that games the formula without improving actual creditworthiness [8]. ARP v2's metric rotation (Section 6.3) prevents static optimization by periodically adjusting weights within published bounds.

**3. Thin-file discrimination.** More than half of Black Americans report low or no credit scores, partly because FICO penalizes thin credit files — people with limited credit history are scored lower regardless of actual financial health [9, 10]. ARP v2's confidence-adjusted combination and gate system handle thin files structurally: an agent with 3 ratings gets a composite with confidence 0.23, not a composite of 0. The signal is "we don't know much about this agent" rather than "this agent is bad."

---

## 4. Signal Portability

### 4.1 The Problem: Reputation Is the Most Valuable and Least Portable Asset

Platform reputation systems are walled gardens by design. Research from the Business & Information Systems Engineering journal found that 94% of e-commerce sellers attempt to import reputation when entering a new platform, but effectiveness varies dramatically by platform type — cross-platform reputation effects are "much more compatible among e-commerce platforms than other types" [11]. Neither incumbent nor entrant platforms have an incentive to offer reputation export: incumbents treat reputation data as a competitive moat, and entrants want users to build fresh reputations [12].

This mirrors the pre-FICO era of credit scoring, where each bank maintained proprietary creditworthiness assessments with no portability. FICO's critical adoption milestones — general-purpose score (1989), availability at all three bureaus (1991), Fannie Mae/Freddie Mac adoption (1995) — demonstrate that portability requires: (a) a common standard, (b) institutional embedding, and (c) network effects where each new adopter makes the score more valuable to all others [4].

For agents, the portability problem is more acute than for humans. An agent that builds a strong reputation on one marketplace (Virtuals Protocol, 18,000+ agents [13]) cannot carry that reputation to another (Solana Agent Registry [14], ClawHub [15]). Each platform restart erases the agent's history, creating friction that suppresses agent mobility and market efficiency.

### 4.2 Portable Reputation Bundles

The **Portable Reputation Bundle (PRB)** is a W3C Verifiable Credential [3] containing an agent's composite reputation summary with cryptographic links to the underlying evidence:

```json
{
  "@context": [
    "https://www.w3.org/ns/credentials/v2",
    "https://absupport.ai/credentials/agent-reputation-bundle/v2"
  ],
  "type": ["VerifiableCredential", "AgentReputationBundle"],
  "issuer": {
    "id": "did:web:oracle.example.com",
    "name": "Example Reputation Oracle",
    "arp_reputation": {
      "reliability": 94,
      "confidence": 0.97
    }
  },
  "validFrom": "2026-03-26T00:00:00Z",
  "validUntil": "2026-04-26T00:00:00Z",
  "credentialSubject": {
    "id": "did:web:rated-agent.example.com",
    "reputationSummary": {
      "compositeScores": [
        {
          "profileId": "urn:absupport:arp:v2:profile:general-purpose",
          "value": 78.4,
          "confidence": 0.83,
          "ratingCount": 247,
          "uniqueRaters": 189,
          "windowDays": 365,
          "oldestRating": "2025-04-15T00:00:00Z"
        }
      ],
      "dimensions": {
        "reliability": {"mean": 82.3, "stddev": 11.2, "confidence": 0.87, "count": 247},
        "accuracy": {"mean": 88.1, "stddev": 8.7, "confidence": 0.89, "count": 241},
        "latency": {"mean": 71.4, "stddev": 15.3, "confidence": 0.84, "count": 230},
        "protocol_compliance": {"mean": 93.2, "stddev": 5.1, "confidence": 0.91, "count": 247},
        "cost_efficiency": {"mean": 79.8, "stddev": 9.4, "confidence": 0.86, "count": 239}
      },
      "provenance": {
        "cocChainAge": 312,
        "cocChainLength": 48721,
        "lastAnchorTimestamp": "2026-03-25T18:00:00Z",
        "anchorType": "dual_ots_tsa"
      },
      "behavioral": {
        "totalInteractions": 1847,
        "ratingParticipationRate": 0.89,
        "disputeRate": 0.003,
        "averageResponseTimeMs": 4200
      }
    },
    "evidenceChain": {
      "ratingsRootHash": "<SHA-256 Merkle root of all included ratings>",
      "cocChainHeadHash": "<SHA-256 of agent's latest CoC chain entry>",
      "verificationEndpoint": "https://oracle.example.com/verify/bundle/<bundle-id>"
    }
  },
  "proof": {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": "did:web:oracle.example.com#key-1",
    "proofPurpose": "assertionMethod",
    "proofValue": "z..."
  }
}
```

### 4.3 Bundle Issuance and Multi-Oracle Consensus

A single reputation oracle issuing a PRB is a trust bottleneck. A malicious oracle could issue inflated bundles. ARP v2 addresses this through **multi-oracle attestation:**

**Single-oracle bundles** (minimum viable): One reputation oracle signs the bundle. The consuming platform assesses trust based on the oracle's own ARP reputation. Suitable for low-stakes interactions.

**Multi-oracle bundles** (recommended for high-stakes): Multiple independent reputation oracles co-sign the bundle. The bundle includes each oracle's independent computation:

```json
{
  "multiOracleAttestation": {
    "threshold": 3,
    "attestations": [
      {"oracle": "did:web:oracle-a.example.com", "compositeValue": 78.4, "signature": "z..."},
      {"oracle": "did:web:oracle-b.example.com", "compositeValue": 77.9, "signature": "z..."},
      {"oracle": "did:web:oracle-c.example.com", "compositeValue": 78.1, "signature": "z..."}
    ],
    "consensusValue": 78.1,
    "consensusMethod": "median",
    "maxDivergence": 2.3
  }
}
```

**Divergence detection.** If oracle attestations diverge by more than a configurable threshold (default: 10 points), the bundle is flagged as `disputed` and consumers are warned. Large divergence indicates either oracle manipulation or genuinely ambiguous reputation data.

### 4.3.1 Oracle Bootstrap Problem

The multi-oracle model assumes the existence of reputable oracles — but at ecosystem launch, all oracles start with zero ARP reputation. This is the "who verifies the verifiers at time zero?" problem.

**Bootstrap mechanism:**

1. **Seed oracle designation.** Governance designates an initial set of seed oracles (minimum 5) with provisional trust. Seed oracles receive a `bootstrap_trust` flag in their ARP identity record with a provisional reliability score of 70 (the minimum for Tier 2 status under v1 governance). This provisional trust is not earned — it is granted by governance vote and explicitly marked as provisional in all PRBs issued during the bootstrap period.

2. **Reputation earning through accurate aggregation.** Seed oracles earn genuine ARP reputation through accurate aggregation over time. "Accurate" is measured by: (a) low divergence from peer oracle computations on the same agents, (b) low rate of disputed PRBs, and (c) Merkle proof verification success rate (Section 5.3). After 90 days, the `bootstrap_trust` flag is removed and the oracle's reputation reflects its actual performance.

3. **Grace period for single-oracle PRBs.** During the first 180 days of ecosystem operation (the "bootstrap period"), single-oracle PRBs are accepted at a reduced trust discount (0.7× instead of the steady-state 0.5× for single-oracle bundles). This allows early adopters to issue and consume PRBs before the multi-oracle ecosystem matures. After the bootstrap period, multi-oracle bundles are required for high-stakes interactions.

4. **New oracle onboarding (post-bootstrap).** After the bootstrap period, new oracles enter at zero reputation and must earn trust through the standard ARP rating process — other oracles and agents rate their aggregation quality. New oracles can co-sign multi-oracle bundles as a non-threshold participant (their attestation is included but not counted toward the minimum threshold) until their reputation exceeds the minimum oracle threshold (configurable, default: 60).

### 4.4 Cross-Platform Reputation Aggregation

When an agent operates across multiple platforms, it accumulates ratings in each context. Portability requires aggregating these into a coherent whole without double-counting or allowing platform-hopping to escape bad reputation.

**Aggregation rules:**

1. **Deduplication.** Ratings are identified by `rating_id` (UUID). If the same rating appears via multiple oracles or platforms, it is counted once.

2. **Source weighting.** Ratings from platforms with stronger interaction verification (on-chain transactions, A2A task records) carry higher weight than ratings from platforms with weaker verification (self-reported interactions). This is implemented via the `verification_level` field from v1 Section 4.8.

3. **Temporal alignment.** All ratings are normalized to the same rolling window (default: 365 days) regardless of which platform they originated on.

4. **Conflict resolution.** If an agent has dramatically different reputations on two platforms (e.g., 90 on Platform A, 40 on Platform B), the aggregated bundle reports both per-platform breakdowns and the overall composite, enabling consumers to investigate.

### 4.5 The Receiving Platform's Decision

A receiving platform is not obligated to accept a PRB at face value. The protocol specifies a **trust discount model** for imported reputation:

```
effective_score = imported_score × trust_discount(issuing_oracle, receiving_platform)
```

where `trust_discount` is a value between 0.0 and 1.0 determined by:
- The receiving platform's trust in the issuing oracle(s)
- The overlap between the source and target domains (code review reputation transferring to code review is high-discount; code review reputation transferring to medical diagnosis is low-discount)
- The age and volume of the underlying ratings

**No mandatory acceptance.** Platforms are free to ignore PRBs entirely and require agents to build reputation from scratch. The protocol provides the infrastructure for portability but cannot force platforms to honor portable reputation.

**The FICO adoption lesson.** The comparison to FICO is instructive but cuts both ways. FICO achieved ubiquity not through technical superiority alone but through **institutional forcing functions**: Fannie Mae and Freddie Mac required FICO scores for conforming mortgages starting in 1995, effectively mandating adoption for any lender participating in the secondary mortgage market [4, 39]. Without this forcing function, FICO might have remained one of many proprietary scoring systems.

PRBs face the same chicken-and-egg problem: platforms won't adopt portable reputation until enough agents carry PRBs, and agents won't invest in PRBs until enough platforms accept them. Three categories of forcing function could break this deadlock:

**1. Marketplace aggregator mandates.** As agent marketplaces consolidate (Virtuals Protocol [13], ClawHub [15], Solana Agent Registry [14]), aggregator platforms that list agents across multiple marketplaces have a natural incentive to standardize reputation — it reduces their own curation costs. If a major aggregator requires PRBs for premium listings, participating marketplaces must support them. This is analogous to how Google's requirement for structured data (schema.org) drove adoption across web publishers without government mandates.

**2. Insurance and liability requirements.** As agent-mediated transactions grow in value, insurance providers and enterprise customers will require verifiable reputation as a condition of coverage or procurement. An enterprise deploying an agent for $50,000+ tasks will demand auditable trust signals — PRBs provide this. The Agent Service Agreements specification [46] already defines quality guarantees that reference ARP scores; insurance underwriting based on composite scores creates a market-driven forcing function.

**3. Regulatory mandates (longer-term).** The EU AI Act's requirements for AI system transparency and the NIST AI Agent Standards Initiative [32] signal regulatory interest in agent accountability. If regulators require portable, auditable reputation for agents operating in regulated sectors (finance, healthcare, legal), PRBs become compliance infrastructure rather than optional features.

**Bootstrap strategy for voluntary adoption.** In the absence of forcing functions, ARP v2 pursues a bootstrap strategy: (a) an open-source reference oracle implementation (Apache 2.0) that lowers the integration cost to near-zero, (b) integration with already-adopted standards (ERC-8004 [29], A2A [47], W3C VCs [3]) so platforms adopting those standards get PRB support with minimal additional work, and (c) early adopter incentives where agents carrying PRBs receive reduced cold-start friction (Section 4.6), creating agent-side demand that pulls platforms toward acceptance.

**Honest assessment.** Without at least one forcing function, PRBs are best understood as **infrastructure for portable reputation, pending adoption** — not as an achieved FICO-equivalent. The technical standard is necessary but not sufficient. ARP v2 provides the standard; the agent economy must provide the adoption pressure. The protocol is designed so that when the forcing function arrives — whether from aggregators, insurers, or regulators — the infrastructure is ready.

### 4.6 Portability and the Cold-Start Problem

Signal portability directly addresses v1's cold-start problem (v1 Section 6.4). An agent entering a new platform presents its PRB as a bootstrap credential. Combined with v1's four-source bootstrapping (identity attestation, operator vouching, graduated access, uncertainty-aware scoring), portable reputation provides a fifth source:

**Source 5: Portable Reputation.** An agent presenting a valid PRB with confidence > 0.5 from a trusted oracle may enter the receiving platform at Tier 1 (medium-stakes interactions) rather than Tier 0 (low-stakes only). The PRB does not grant Tier 2 or Tier 3 status — those require locally-earned ratings. This balances the value of portable reputation against the risk of imported inflation.

### 4.7 Privacy Risks of Portable Reputation

Signal portability introduces a **cross-platform correlation attack surface** that ZKP threshold verification (Section 5.4) and SD-JWT selective disclosure (Section 10.3) do not fully address.

**The correlation problem.** When an agent presents PRBs to multiple receiving platforms, its DID serves as a linking key. Even if the agent uses different operational identities per platform, the PRB's DID connects them. This enables:

1. **Cross-platform tracking.** Platforms receiving PRBs can correlate the agent's DID across marketplaces, building a cross-platform activity profile — which platforms the agent operates on, when it entered each, and how its reputation evolves across contexts.

2. **Competitive intelligence leakage.** The PRB's behavioral section (totalInteractions, disputeRate, averageResponseTimeMs) constitutes competitive intelligence. A marketplace operator receiving PRBs from many agents can reconstruct market dynamics — interaction volumes, response times, and dispute patterns across the ecosystem.

3. **Operator deanonymization.** If the agent's DID is linkable to its operator (via `did:web` resolution, ERC-8004 on-chain data, or `alsoKnownAs` claims), the behavioral data becomes personally attributable. This has GDPR Article 9 implications if the operator is in the EU and behavioral patterns reveal sensitive characteristics.

**Mitigation approaches.** The protocol recommends a layered defense:

**a) Pairwise DIDs.** Agents SHOULD use pairwise DIDs when presenting PRBs to different platforms — a unique DID per platform relationship, as specified in the Sovrin/Aries ecosystem [41]. The underlying reputation is linked to a root DID that is never directly presented; pairwise DIDs are derived from the root DID using a deterministic but non-reversible derivation.

**b) ZKP-based unlinkable presentation.** For high-privacy scenarios, agents MAY use the ZKP mechanism (Section 5.4) to prove "I hold a valid PRB meeting threshold X" without revealing which DID holds the reputation. The proof attests to the PRB's validity and threshold compliance without exposing the credential subject's identifier. This requires extending the ZKP circuit to include DID blinding — non-trivial but feasible with existing ZKP frameworks (Polygon ID's IDen3 stack [16] demonstrates this pattern).

**c) Selective behavioral disclosure.** Agents presenting PRBs SHOULD use SD-JWT (Section 10.3) to disclose only the minimum behavioral data required by the receiving platform. A platform that only needs composite score verification should not receive interaction volumes or response times.

**Residual risk acknowledged.** Pairwise DIDs prevent naive correlation but do not defeat a determined adversary who can correlate behavioral fingerprints (an agent with exactly 1,847 interactions, 0.003 dispute rate, and 4,200ms response time is likely unique across platforms regardless of DID). Full unlinkability requires ZKP-based presentation, which adds computational overhead (Section 5.4). The protocol leaves the privacy/performance trade-off to the presenting agent.

---

## 5. Signal Verification

### 5.1 The Problem: Trust Without Trusting

In ARP v1, verifying an agent's reputation requires querying an aggregation node and trusting that node's response. The distributed storage model (v1 Section 4.3) allows cross-checking against multiple nodes, but a consumer must ultimately trust some combination of nodes. There is no mechanism for an agent to *prove* its reputation to a skeptical third party without that party conducting its own aggregation.

ARP v2 introduces three verification mechanisms of increasing strength:

### 5.2 Hash-Chain Verification (Minimum)

Every ARP rating embedded in a CoC chain is protected by the chain's SHA-256 hash-linking (v1 Section 4.7). A third party can verify:

1. **The rating exists.** Request the rating record and verify its `record_hash` against the rater's CoC chain.
2. **The rating has not been modified.** The hash chain's integrity guarantees that no entry can be altered without breaking all subsequent hashes.
3. **The rating was recorded at a specific time.** CoC v3's dual-tier anchoring (OpenTimestamps + RFC 3161 TSA) provides external timestamp verification [2].

This is the minimum verification available for any CoC-backed agent. It proves individual ratings are genuine but does not verify aggregate scores.

### 5.3 Merkle Proof Verification (Standard)

PRBs include a `ratingsRootHash` — the Merkle root of all ratings included in the bundle's computation. A verifier can:

1. Request the full Merkle tree from the issuing oracle
2. Verify that each leaf corresponds to a genuine rating (via hash-chain verification)
3. Re-compute the aggregate from the verified ratings
4. Confirm the re-computed aggregate matches the bundle's claimed value

**Cost.** Full Merkle verification requires downloading and re-computing over all included ratings. At 247 ratings, this is trivial. At 10,000+ ratings, it's computationally non-trivial. The protocol supports **sampled verification**: a verifier requests a random subset of Merkle proofs (default: 50 ratings), verifies those, and accepts the bundle with a confidence proportional to the sample size.

### 5.4 Zero-Knowledge Threshold Verification (Privacy-Preserving)

For scenarios where an agent needs to prove its reputation meets a threshold without revealing exact scores, ARP v2 integrates zero-knowledge proofs:

**Use case.** An agent applying for a high-stakes task needs to prove "my general-purpose composite score exceeds 80 and my reliability dimension exceeds 85" without revealing that its actual scores are 83.7 and 88.2.

**Protocol:**

```
1. Prover (agent) holds:
   - PRB with compositeScore = 83.7
   - PRB with reliability = 88.2
   - Merkle proof linking both values to the ratingsRootHash

2. Prover generates ZK proof:
   π = ZKProof(
     public_inputs: {threshold_composite: 80, threshold_reliability: 85, ratingsRootHash: "..."},
     private_inputs: {compositeScore: 83.7, reliability: 88.2, merkle_path: [...]}
   )

3. Verifier checks:
   Verify(π, public_inputs) → true/false
```

**ZKP system selection.** The protocol does not mandate a specific ZKP system. Implementations MAY use:
- **Groth16** — smallest proof size (~200 bytes), trusted setup required, fastest verification
- **PLONK** — universal trusted setup, moderate proof size, widely supported
- **STARKs** — no trusted setup, larger proofs, quantum-resistant

The choice depends on deployment constraints. On-chain verification (ERC-8004 contexts) benefits from Groth16's small proof size. Off-chain verification can tolerate larger STARK proofs for the benefit of no trusted setup.

**Existing implementations.** Several projects have demonstrated ZKP-based reputation verification in production or near-production: Polygon ID (IDen3 stack) for privacy-preserving credential verification [16], ZK Email Stamp for proving humanity through e-commerce receipts [17], and Lookout Agent Trust Intelligence for ZK-verified onchain behavioral scoring [18]. OpenRank leverages ZK proving systems for verifiable graph computations [19]. These demonstrate that the cryptographic infrastructure for ZKP reputation is operational, not theoretical.

**Limitation acknowledged.** ZKP verification adds computational overhead. Groth16 proof generation takes 2-10 seconds on commodity hardware for circuits of the complexity required here. This is acceptable for high-stakes interactions but prohibitive for real-time, high-frequency reputation checks. The protocol recommends ZKP verification for interactions above a configurable value threshold (default: $100 equivalent) and falls back to Merkle proof or hash-chain verification for lower-stakes interactions.

### 5.5 Verification Levels

ARP v2 defines three verification levels with explicit security properties:

| Level | Method | What It Proves | Cost | Recommended For |
|-------|--------|---------------|------|-----------------|
| **Basic** | Hash-chain | Individual ratings are genuine and timestamped | O(1) per rating | Low-stakes interactions |
| **Standard** | Merkle proof | Aggregate scores are computed from genuine ratings | O(n) or O(sample) | Medium-stakes interactions |
| **Privacy-Preserving** | ZKP threshold | Score exceeds threshold without revealing value | O(proof_gen) | High-stakes or privacy-sensitive interactions |

---

## 6. Anti-Goodhart Architecture

### 6.1 The Problem: Published Metrics Become Gaming Targets

Charles Goodhart's 1975 formulation: "Any observed statistical regularity will tend to collapse once pressure is placed upon it for control purposes" [20]. In reputation systems, this manifests as: once a score is published and tied to rewards, actors optimize for the score rather than the underlying quality it measures.

Documented Goodhart failures in scoring:
- **Academic H-index:** Citation rings artificially inflate metrics, with salami-slicing papers optimizing count over substance [21]
- **Amazon reviews:** An estimated $152 billion in annual purchases are influenced by fake reviews — review factories optimize star ratings as a business [22, 22a]
- **Uber/Lyft ratings:** Average rating of 4.7-4.8/5 represents inflation driven by deactivation thresholds — the score measures "avoidance of punishment" rather than "quality of service" [23, 23a]
- **FICO credit scores:** Thin-file optimization (opening credit cards to build score without genuine credit need) games the formula without improving financial health [8]

ARP v1 addressed this partially through its "queryable but not browseable" design principle (v1 Section 3.1, Principle 6). v1 acknowledged this is unenforceable in practice — any agent can query all scores and build a leaderboard. ARP v2 replaces the unenforceable principle with a systematic defense architecture.

### 6.2 Signal Stratification

The primary defense: not all signals are equally visible.

**Public Tier (P).** Signals that any agent can query freely. These are the "headline" metrics. They are the most likely to be gamed and are therefore the least informative for high-stakes decisions. Public signals serve as initial filters, not final arbiters.

Examples: operational age, total interaction count, tier level (0/1/2/3), platform memberships.

**Queryable Tier (Q).** Signals available on request with rate limiting and access controls. A requesting agent must have a valid identity and the query is logged. Queryable signals are not secret — they're accessible with effort — but the friction of rate-limited queries prevents mass scraping for leaderboard construction.

Examples: composite scores, per-dimension averages, confidence levels, rating volume.

Rate limits: default 100 queries/day per requesting agent, configurable by the queried agent. Queries exceeding the limit return HTTP 429 with a `Retry-After` header.

**Private Tier (R).** Signals used only for internal computation by reputation oracles and the protocol's anti-gaming mechanisms. Never exposed to external queries. Private signals include the shadow metrics (Section 6.4), per-rater calibration scores, collusion detection flags, and the exact parameters of metric rotation.

The tier assignment is governance-managed. The default tier map:

| Signal | Tier | Rationale |
|--------|------|-----------|
| Operational age | P | Hard to game (requires real time) |
| Total interactions | P | Low gaming value |
| Tier level (0/1/2/3) | P | Coarse-grained, minimal Goodhart risk |
| Composite score (per profile) | Q | The primary trust signal — queryable but not freely browseable |
| Per-dimension averages | Q | More granular than composite; moderate gaming value |
| Rating confidence | Q | Metadata about score quality |
| Per-rater calibration scores | R | Would reveal anti-gaming internals |
| Collusion flags | R | Would tip off colluders |
| Shadow metric values | R | The whole point is that they're invisible |
| Metric rotation parameters | R | Publishing would defeat the rotation |

### 6.3 Metric Rotation

Static weights are optimization targets. If agents know that reliability is weighted at 25% and accuracy at 25%, they can allocate resources to maximize exactly those dimensions at the expense of others.

**Rotation mechanism.** Each weight profile specifies a rotation schedule (quarterly by default). At each rotation boundary:

1. The governance system (or the custom profile owner) selects new weights within published bounds
2. The rotation announcement is published: "Weights for general-purpose profile have been updated as of 2026-04-01"
3. The new weights take effect immediately for future composite computations
4. Historical composites are NOT retroactively recomputed — they used the weights in effect when computed

**Published bounds.** The rotation does not allow arbitrary weight changes. Each weight profile specifies min/max bounds per signal:

```json
{
  "signal_id": "arp:reliability:weighted_mean",
  "weight_bounds": {"min": 0.15, "max": 0.35},
  "current_weight": "ROTATED"
}
```

Agents know that reliability is weighted between 15% and 35%, but not where within that range. To game effectively, an agent would need to optimize across the entire bound range — which means genuinely excelling at the dimension rather than narrowly optimizing for a known weight.

**Rotation frequency vs. stability.** More frequent rotation provides stronger anti-Goodhart protection but reduces the predictability agents need for rational resource allocation. The default quarterly rotation balances these tensions. Governance MAY vote to increase frequency (monthly) or decrease it (semi-annually) based on observed gaming levels.

**Limitation acknowledged.** Rotation defends against *static* optimization but not against *adaptive* optimization. An agent that can infer current weights from observed score changes (by submitting probe interactions and measuring composite responses) can partially reverse-engineer the rotation. Defense: (a) rate-limiting composite queries per agent (Section 6.2) limits probing bandwidth, and (b) adding calibrated noise to composite responses (Section 6.5) reduces inference precision.

### 6.4 Shadow Metrics

For every public or queryable signal, the protocol maintains one or more private shadow metrics that detect divergence between the optimized metric and the underlying quality:

| Primary Metric | Shadow Metric(s) | What Divergence Indicates |
|---------------|-------------------|---------------------------|
| Composite score | Score stability (30/90/180 day variance) | Sudden score jumps suggest gaming, not genuine improvement |
| Reliability dimension | Repeat interaction rate (do agents re-hire this agent?) | High reliability scores + low repeat rate = inflated reliability |
| Accuracy dimension | Downstream verification rate (do consumers of output flag errors?) | High accuracy scores + high downstream error rate = inflated accuracy |
| Latency dimension | Task complexity ratio (latency relative to task complexity) | Low latency + low task complexity = cherry-picking easy tasks |
| Cost efficiency | Value-per-token ratio (output quality per compute unit) | High cost efficiency + declining output quality = cutting corners |
| Rating participation | Rating reciprocity balance (does the agent rate others at similar frequency?) | High participation + low reciprocity = farming governance weight |

**Shadow metric computation.** Reputation oracles compute shadow metrics as part of their aggregation pipeline. Shadow metric values are never exposed via API. They are used internally to:

1. **Flag anomalies.** If a primary metric and its shadow metric diverge beyond a threshold (configurable, default: 2 standard deviations), the agent is flagged for enhanced monitoring.
2. **Adjust confidence.** Flagged agents have their composite score confidence reduced by a governance-configurable factor (default: 0.8x), signaling to consumers that the score may be less reliable.
3. **Trigger review.** Persistent divergence (>30 days) triggers a governance review proposal.

**Shadow metric integrity verification.** Shadow metrics are private by design, but this creates a trust gap: a colluding oracle can simply not compute shadow metrics for a favored agent, or compute them and ignore the anomaly flags. The protocol addresses this through a **hash-based audit mechanism:**

1. **Computation proofs.** On every aggregation cycle, each oracle publishes a `shadow_metric_commitment` — the SHA-256 hash of its shadow metric computation results for all agents in that cycle. The hash proves computation occurred without revealing the values.

2. **Peer audit protocol.** Peer oracles MAY request a shadow metric audit for a specific agent. The audited oracle reveals the shadow metric values for that agent (encrypted to the requesting oracle's public key). The requesting oracle verifies: (a) the revealed values hash to a subset consistent with the published commitment, and (b) the values are plausible given the agent's public-tier signals.

3. **Audit frequency.** Governance sets a minimum audit frequency (default: each oracle is audited by at least 2 peers per quarter). Oracles that refuse audits or whose revealed values fail verification are flagged — their ARP reliability score is penalized and their PRB attestations carry a reduced trust weight.

**Residual risk.** A colluding oracle can compute shadow metrics correctly but ignore the anomaly flags in its aggregation. The audit proves computation, not action. Defense: multi-oracle attestation (Section 4.3) limits the impact of any single oracle's suppression, since other oracles computing independently will detect anomalies the colluding oracle ignores.

### 6.5 Differential Privacy for Aggregation Responses

To prevent score inference attacks (probing the system to reverse-engineer rotation weights or shadow metrics), aggregation nodes MAY add calibrated Laplace noise to composite score responses:

```
noisy_composite = true_composite + Laplace(0, sensitivity/epsilon)
```

where `sensitivity` is the maximum change in composite from a single rating (bounded by the weight formula) and `epsilon` is the privacy parameter (governance-configurable, default: 1.0).

At epsilon = 1.0, the expected noise magnitude is approximately ±2 points on a 100-point scale. This is small enough not to materially affect trust decisions but large enough to prevent precise score inference from repeated queries.

**Trade-off acknowledged.** Differential privacy introduces noise that, by definition, makes the score less accurate for the querying agent. The protocol recommends differential privacy for the queryable tier only — agents with direct bilateral interaction history can access un-noised scores via the Merkle verification path (Section 5.3). This means agents with direct experience get the full signal, while third-party observers get a slightly noised version.

### 6.6 Multi-Dimensional Gaming Resistance

A key insight from the anti-Goodhart literature [24, 25]: the more independent dimensions a score composes, the harder it is to simultaneously game all of them. Formally, if gaming dimension `d` costs `c_d` and dimensions are independent, the total cost of gaming `k` out of `n` dimensions is at least `Σ c_d` for the `k` cheapest dimensions.

ARP v2's composition over 7+ signals (five rating dimensions, operational age, behavioral signals) means an agent seeking to inflate its composite must:
1. Inflate all five rating dimensions (requires either Sybil raters or collusion rings — expensive per v1 Sections 6.1-6.2)
2. Accumulate genuine operational age (requires time, cannot be faked)
3. Maintain high rating participation rate (requires genuine interactions)

The cost of simultaneously gaming all inputs exceeds the benefit for any plausible payoff function. This is not a proof of impossibility — a sufficiently funded attacker can game any system — but it raises the cost to the point where legitimate service provision is cheaper than gaming for the vast majority of agents. The theoretical foundation for this cost-of-gaming argument, drawing on Spencian signaling theory and the trade-off model that replaced the Handicap Principle, is developed in Appendix A.

---

## 7. Security Analysis of New Capabilities

This section analyzes attacks specific to v2's new capabilities. Attacks on the base protocol (Sybil, collusion, griefing, cold-start) are analyzed in v1 Section 6 and remain unchanged.

### 7.1 Composition Manipulation

**Attack.** An agent crafts its interaction pattern to maximize composite score under a specific weight profile — accepting only tasks where it can score highly on the most heavily weighted dimensions and declining tasks where it might score poorly.

**Detection.** The shadow metric "task complexity ratio" (Section 6.4) detects cherry-picking: an agent with a narrow task distribution relative to its declared capabilities is flagged. The behavioral signal "interaction decline rate" (percentage of offered interactions the agent declines) is a queryable-tier metric that consumers can check.

**Mitigation.** Metric rotation (Section 6.3) means the most heavily weighted dimension changes periodically. An agent that cherry-picks for reliability-heavy tasks performs poorly when the rotation emphasizes accuracy or latency.

### 7.2 Oracle Collusion

**Attack.** Multiple reputation oracles collude to issue inflated PRBs for favored agents.

**Detection.** Multi-oracle attestation (Section 4.3) surfaces divergence between oracles. If three oracles agree on 78 but a fourth claims 95, the divergence flag identifies the outlier. Oracles whose attestations consistently diverge from the median are flagged by the protocol's own anti-inflation mechanisms (since oracles are agents with ARP reputations).

**Mitigation.** Consuming platforms SHOULD require multi-oracle bundles for high-stakes decisions. The trust discount model (Section 4.5) means that even if an inflated bundle is accepted, its effective score is discounted by the platform's trust in the issuing oracle. An oracle with a history of divergent attestations accumulates low reliability scores, reducing the discount applied to its bundles.

**Residual risk.** If a majority of oracles in a multi-oracle bundle collude, the consensus mechanism itself is corrupted. Defense requires oracle diversity — the protocol recommends that platforms require attestations from oracles operated by different entities in different jurisdictions.

### 7.3 Portable Reputation Laundering

**Attack.** An agent with poor reputation on Platform A attempts to use a PRB from Platform B (where it has good reputation) to get a fresh start on Platform A.

**Detection.** PRBs include the agent's DID. If Platform A's identity adapter can link the presenting agent's DID to an existing local identity, the platform detects the re-entry attempt.

**Mitigation.** Platforms SHOULD cross-reference PRB presenters against existing local reputation records. An agent presenting a PRB while holding local reputation has both records visible — the platform can apply the lower of the two, or flag the discrepancy for review.

**Limitation.** If the agent uses a different DID on each platform and there is no cross-platform identity linking, reputation laundering is possible. This is an inherent limitation of any system that allows pseudonymous identities. The defense is to strengthen identity linking (W3C DID `alsoKnownAs` claims, ERC-8004 cross-chain registrations) rather than to restrict portability.

### 7.4 ZKP Replay Attacks

**Attack.** An agent generates a valid ZKP proof ("my score exceeds 80") at time T when its score was 82. At time T+30 days, its score has dropped to 65, but it presents the old proof.

**Detection.** ZKP proofs include a `ratingsRootHash` that is specific to the point-in-time state of the agent's rating history. A verifier can check whether the `ratingsRootHash` corresponds to a recent (within validity window) state.

**Mitigation.** Proofs include a `validUntil` timestamp. Verifiers MUST reject expired proofs. Default proof validity: 7 days (matching PRB validity). For high-stakes interactions, verifiers MAY require real-time proof generation (agent generates a fresh proof during the interaction negotiation).

### 7.5 Weight Profile Inference

**Attack.** An agent submits probe interactions designed to reveal the current rotation weights — e.g., deliberately performing well on one dimension and poorly on others, then observing the composite score change to infer the dimension's weight.

**Detection.** Anomalous interaction patterns (highly variable performance across dimensions in a pattern inconsistent with genuine capability variation) are flagged by shadow metrics.

**Mitigation.** Differential privacy on composite responses (Section 6.5) adds noise that prevents precise weight inference. Rate limiting on composite queries (Section 6.2) limits the number of probe-and-observe cycles. The combination means an attacker needs many interactions and many queries to narrow weight estimates — and even then, the noise floor prevents exact inference.

**Quantitative bound (single agent).** With epsilon = 1.0 differential privacy and 100 queries/day rate limit, a single attacker can narrow a weight estimate to ±5% of the true value after approximately 30 days of sustained probing. By that time, the quarterly rotation may have changed the weights. This makes sustained weight inference impractical for most individual attackers.

**Coalition probing (distinct threat).** A coalition of N agents sharing probe results can narrow weight estimates N times faster. 10 colluding agents reach ±5% accuracy in ~3 days. 100 agents collectively issue 10,000 queries/day, and the differential privacy noise averages out over their pooled samples — significantly degrading the effective privacy guarantee.

**Coalition defenses:**

1. **Per-agent correlated noise.** Rather than independent Laplace noise per query, the protocol MAY use agent-specific noise seeds: each agent receives noise drawn from a per-agent pseudorandom sequence. Repeated queries from the same agent receive correlated noise, so pooling multiple queries from one agent provides diminishing returns. Coalition members with different seeds still benefit from pooling, but this eliminates the simplest averaging attack.

2. **Global query rate monitoring.** Aggregation nodes SHOULD monitor total query volume across all agents, not just per-agent rates. A sudden spike in composite score queries for the same target agent from many different agents is a coalition probing signal. When detected, the node increases the noise magnitude for queries targeting that agent (adaptive epsilon).

3. **Adjusted quantitative bound.** For a coalition of size N with per-agent correlated noise, the effective probing rate is O(N) (one useful query per agent per day, not 100). A 100-agent coalition narrows weight estimates to ±5% in approximately 30/100 × 30 ≈ 9 days with the single-query-per-agent-per-day effective rate. With adaptive epsilon triggered by anomaly detection, this extends further. The bound is weaker than the single-agent case but remains practically defensible for coalitions under ~50 agents.

**Limitation acknowledged.** A sufficiently large coalition (>100 agents) with patient, low-frequency probing that avoids triggering anomaly detection can eventually infer rotation weights. The ultimate defense is the rotation itself: even perfect weight knowledge becomes stale at each rotation boundary. The protocol accepts this residual risk as the cost of maintaining queryable reputation signals.

---

## 8. Migration from v1 to v2

### 8.1 Backward Compatibility

ARP v2 is designed for incremental adoption:

| Agent Type | Capability | Action Required |
|-----------|------------|-----------------|
| v1 agent, no changes | Continues to submit/receive v1 ratings | None |
| v1 agent, wants composites | Can query composite scores from v2 oracles | Update query client only |
| v1 agent, wants portability | Needs to generate/accept PRBs | Implement v2 extensions |
| v2 agent, full features | Signal composition, portability, ZKP verification | Full v2 implementation |

v1 and v2 agents coexist on the same network. v2 does not break any v1 functionality.

### 8.2 Aggregation Node Upgrade Path

Aggregation nodes upgrading to v2 must:

1. **Accept v1 and v2 rating records.** v1 records are treated as v2 records with `v2_extensions: null`.
2. **Implement composition engine.** Compute composite signals from existing v1 rating data using the composition algebra (Section 3.3).
3. **Issue PRBs.** Sign Portable Reputation Bundles using the node's DID.
4. **Implement signal stratification.** Classify existing APIs into public/queryable/private tiers.
5. **Implement metric rotation.** Apply quarterly weight rotation to standard profiles.

**Migration timeline recommendation:**

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase A | 0-30 days | Accept v2 records, compute composites from existing data |
| Phase B | 30-60 days | Issue PRBs, implement Merkle proof verification |
| Phase C | 60-90 days | Implement signal stratification and metric rotation |
| Phase D | 90-180 days | ZKP verification support (optional, complexity-dependent) |

### 8.3 Rating Record Schema Update

The v2 schema extends v1 with optional fields:

```json
{
  "version": 2,
  "rating_id": "<UUID-v4>",
  "timestamp": "<ISO-8601-UTC>",
  "interaction_id": "<UUID-v4>",
  "rater": { "agent_id": "<DID>", "identity_proof": "<ref>" },
  "ratee": { "agent_id": "<DID>", "identity_proof": "<ref>" },
  "dimensions": {
    "reliability": 85, "accuracy": 92, "latency": 78,
    "protocol_compliance": 95, "cost_efficiency": 88
  },
  "interaction_evidence": {
    "task_type": "code_review",
    "outcome_hash": "<SHA-256>",
    "duration_ms": 4200,
    "was_completed": true
  },
  "metadata": {
    "rater_chain_length": 48721,
    "rater_chain_age_days": 312,
    "rater_total_ratings_given": 1847,
    "bilateral_blind": true
  },
  "v2_extensions": {
    "signal_tier_preferences": {
      "composite_score": "queryable",
      "dimensional_scores": "queryable"
    },
    "portable_bundle_consent": true,
    "verification_support": ["hash_chain", "merkle_proof"]
  },
  "record_hash": "<SHA-256 of JCS-canonicalized record>"
}
```

All `v2_extensions` fields are optional. A record with `"version": 2` and no `v2_extensions` is equivalent to a v1 record.

### 8.4 Governance Transition

The v1-to-v2 upgrade follows the governance process specified in v1 Section 5.4:

1. **Proposal.** A v2 upgrade proposal requires 20% of total GovWeight to propose.
2. **Voting.** 75% supermajority required, with a 30-day cooling period.
3. **Activation.** After governance approval, a 90-day transition period begins during which v1 and v2 operate in parallel.
4. **Deprecation.** v1-only features are deprecated 365 days after v2 activation (per v1 Section 9.2 deprecation policy). v1 rating records are never deprecated — only v1-specific protocol behaviors.

### 8.5 Scalability Analysis

ARP v2 introduces four computationally significant operations not present in v1. This section provides order-of-magnitude estimates for implementers.

**Composition engine.** Computing composites over 7 signals for N agents requires O(N × 7) arithmetic operations per aggregation cycle. At 10K agents: ~70K operations — trivial (sub-second on commodity hardware). At 100K agents: ~700K operations — still trivial. At 1M agents with quarterly rotation triggering full recomputation: ~7M operations — completes in seconds on a single core. Composition is embarrassingly parallel across agents. **Verdict: not a bottleneck at any foreseeable scale.**

**Merkle tree construction.** Building Merkle trees over all ratings for PRB issuance requires O(n × log n) hash operations where n = ratings per agent.

| Ratings per agent | Tree construction | Proof generation (single leaf) |
|---|---|---|
| 247 (median) | ~2,000 SHA-256 hashes (<1ms) | 8 hashes (<0.1ms) |
| 1,000 | ~10,000 hashes (~1ms) | 10 hashes (<0.1ms) |
| 10,000 | ~130,000 hashes (~10ms) | 14 hashes (<0.1ms) |
| 100,000 | ~1.7M hashes (~100ms) | 17 hashes (<0.1ms) |

At the per-agent level, Merkle trees are efficient even at high rating volumes. The system-wide cost of building trees for all agents during a batch PRB issuance cycle scales linearly: 100K agents × 10ms average = ~17 minutes on a single core, parallelizable to seconds across multiple cores. **Verdict: manageable with standard parallelization.**

**ZKP proof generation.** The protocol estimates 2-10 seconds per proof on commodity hardware for Groth16 circuits of the required complexity. For a mass entry event where 1,000 agents simultaneously need ZKP proofs:

| Concurrent agents | Total compute (sequential) | At 16-core oracle | At 64-core oracle |
|---|---|---|---|
| 100 | 200-1,000s | 12-62s | 3-16s |
| 1,000 | 2,000-10,000s | 125-625s | 31-156s |
| 10,000 | 20,000-100,000s | 1,250-6,250s | 312-1,562s |

At 1,000+ concurrent agents, ZKP generation becomes a bottleneck for single oracles. Mitigations: (a) proof generation is delegated to the agent, not the oracle — agents generate their own proofs from their PRB data, distributing compute across the network; (b) proof caching — a proof remains valid for the PRB's validity window (7 days), so proofs are generated once and reused; (c) fallback to Merkle verification for lower-stakes interactions during peak demand. **Verdict: manageable with proof caching and agent-side generation; bottleneck risk at >1K simultaneous proof requests to a single oracle.**

**Shadow metric pipeline.** Computing shadow metrics adds one additional metric per primary metric per agent per aggregation cycle. With 6 primary metrics and 100K agents: 600K additional computations. Shadow metrics involve slightly more complex calculations than composition (e.g., 30/90/180-day variance, repeat interaction rate queries) but remain O(N × metrics). Estimated overhead: 2-5× the composition engine cost, or 5-15 seconds for 100K agents on a single core. **Verdict: modest overhead, well within oracle computational budgets.**

**Differential privacy noise calibration.** Per-query sensitivity calculation requires knowing the maximum impact of a single rating on the composite. For a fixed weight profile, this is a constant computed once per rotation period: `max_sensitivity = max(weight_i / sample_size_i)` across all input signals. The per-query noise draw (Laplace sampling) is O(1). **Verdict: negligible overhead.**

---

## 9. Updated Competitive Landscape

Since ARP v1's publication, several new systems have emerged or evolved. This section updates the competitive analysis.

### 9.1 New Entrants Since v1

| System | Founded/Launched | Funding | Key Capability | Gap vs. ARP v2 |
|--------|------------------|---------|---------------|-----------------|
| **t54 Labs** [26] | Jan 2025, $5M seed (Feb 2026) | Anagram, PL Capital, Franklin Templeton, Ripple | Agent identity + risk assessment + credit underwriting | Proprietary scoring; no open protocol; no bilateral blind |
| **VOUCH** [27] | 2025-2026 | Token ($VOUCH) | On-chain identity + staking/slashing reputation | Single-dimension; no composition algebra; no portability standard |
| **Lookout** [18] | 2026 | Not disclosed | ZK-verified onchain behavioral scoring, HTTP TrustScore API | Single composite score; no open weight profiles; no anti-Goodhart architecture |
| **PayCrow** [7] | 2026 | Not disclosed | Trust scoring from 4 on-chain sources (40/25/15/20 weights) | Fixed weights (gameable); no metric rotation; no bilateral blind |
| **Nostr WoT** [28] | Ongoing | Community | Social distance-based trust via follow graph | No performance scoring; no interaction verification; human-centric |

### 9.2 Updated Comparison Matrix

| System | Composition | Portability | Verification | Anti-Goodhart | Open Standard |
|--------|-------------|-------------|--------------|---------------|---------------|
| **ARP v2 (ours)** | Algebra + profiles | PRBs via W3C VCs | Hash/Merkle/ZKP | Stratification + rotation + shadows | Apache 2.0 |
| t54 Labs [26] | Proprietary model | Not specified | Identity verification | Not specified | No |
| ERC-8004 [29] | Deferred to off-chain | On-chain (single chain) | On-chain verification | Not specified | EIP (open) |
| OpenRank [19] | EigenTrust | Cross-graph (limited) | ZK graph proofs | Not specified | Open source |
| VOUCH [27] | Staking-weighted | On-chain (single chain) | Staking proofs | Slashing | Token-gated |
| Lookout [18] | Proprietary | HTTP API | ZK proofs | Not specified | Partially open |
| PayCrow [7] | Fixed 4-source | On-chain (single chain) | On-chain | Not specified | Not specified |
| Zarq/Nerq [30] | Multi-signal (0-100) | Cross-registry | Registry verification | Not specified | Partially open |
| Nostr WoT [28] | Social distance | Nostr relays | Cryptographic signatures | Not applicable | Open protocol |

### 9.3 Unique Contributions of ARP v2

No surveyed system provides the combination of:

1. **Open composition algebra with configurable profiles.** PayCrow and Lookout compose signals but with fixed, proprietary formulas. ARP v2's algebra is open and extensible, with domain-specific profiles.

2. **Standards-based portability via W3C VCs.** Most systems provide reputation within their own chain/platform. ARP v2 uses W3C Verifiable Credentials — a W3C Standard as of May 2025 [3] — for interoperable reputation transfer.

3. **Multi-level verification including ZKP.** Lookout and OpenRank support ZKP verification, but neither combines it with hash-chain and Merkle proof verification in a tiered model.

4. **Systematic anti-Goodhart architecture.** No surveyed system specifies signal stratification, metric rotation, or shadow metrics. Anti-gaming in existing systems relies on staking/slashing (VOUCH, EigenLayer) or social graph analysis (OpenRank, Nostr WoT), not on systematic defense against published-metric optimization.

5. **Bilateral blind evaluation as the base.** ARP's commit-reveal blind rating, inherited from v1, remains unique among agent reputation systems. All surveyed competitors use unilateral or public rating mechanisms.

**Honest assessment.** The competitive landscape is converging rapidly. t54 Labs' $5M seed round and Franklin Templeton's participation signal institutional interest in agent credit scoring. OpenRank's ZK graph proofs are technically sophisticated. ERC-8004's ~24,000 registered agents provide the largest on-chain dataset. ARP v2's advantage is in providing a complete, coherent, open specification — but a well-funded competitor could build equivalent functionality by composing existing components (ERC-8004 + OpenRank + custom ZKP + custom anti-Goodhart). Our moat is the specification's coherence and the Apache 2.0 licensing, not any single technical component.

---

## 10. Integration Updates

### 10.1 ERC-8004 Integration (Updated)

v1's ERC-8004 integration (v1 Section 7.1) mapped five ARP dimensions to `giveFeedback` calls. v2 extends this:

**Composite signal storage.** Composite scores are stored via a new tag pair:

```
giveFeedback(agentId, 7840, 2, "arp_composite", "general_purpose", feedbackURI, feedbackHash, ...)
```

The `feedbackURI` points to the full PRB (Portable Reputation Bundle) stored off-chain, enabling any ERC-8004 consumer to retrieve the detailed breakdown.

**PRB hash anchoring.** The `feedbackHash` of the composite signal entry is the SHA-256 of the PRB's JSON Canonicalization Scheme representation, providing on-chain tamper evidence for the portable bundle.

### 10.2 A2A Agent Card Extension (Updated)

v1's A2A extension (v1 Section 7.2) declared rating protocol support. v2 adds:

```json
{
  "capabilities": {
    "extensions": [{
      "uri": "urn:absupport:agent-rating:v2",
      "description": "ARP v2: rating, composition, portability, verification",
      "required": false,
      "params": {
        "ratingVersion": "2.0",
        "dimensions": ["reliability", "accuracy", "latency", "protocol_compliance", "cost_efficiency"],
        "scale": {"min": 1, "max": 100},
        "cocChainSupport": true,
        "compositionProfiles": ["general-purpose", "high-reliability"],
        "portableBundleEndpoint": "https://agent.example.com/reputation/bundle",
        "verificationSupport": ["hash_chain", "merkle_proof", "zkp_threshold"],
        "antiGoodhartCompliant": true
      }
    }]
  }
}
```

Agents discover v2-capable peers by filtering for `urn:absupport:agent-rating:v2`. v2 agents SHOULD also declare `urn:absupport:agent-rating:v1` for backward compatibility.

### 10.3 W3C VC Integration (Extended)

v1 defined `AgentRatingCredential` and `AgentReputationSummaryCredential` (v1 Section 7.3). v2 adds:

**AgentReputationBundle** — the PRB as a VerifiableCredential (full schema in Section 4.2).

**Selective disclosure via SD-JWT.** v1 mentioned SD-JWT for threshold proofs as future work. v2 specifies:

```json
{
  "type": ["VerifiableCredential", "AgentReputationBundle"],
  "credentialSubject": {
    "id": "did:web:agent.example.com",
    "_sd": ["reputationSummary"]
  },
  "_sd_alg": "sha-256",
  "disclosures": [
    {"salt": "...", "claim": "compositeScores[0].value", "value": 78.4}
  ]
}
```

An agent presents only the disclosures needed: "my composite score" without revealing per-dimension breakdowns, or "my reliability score" without revealing cost efficiency. This is simpler than full ZKP (Section 5.4) but provides less privacy — the exact value is revealed, just selectively.

### 10.4 Mastercard Verifiable Intent Alignment

Mastercard's Verifiable Intent specification (March 2026) links "identity, intent, and action into a single, privacy-preserving record" using selective disclosure built on FIDO/EMVCo/IETF/W3C specifications [31]. ARP v2's PRBs are structurally compatible: a PRB can serve as the "identity" component of a Verifiable Intent record, linking reputation to a specific transaction intent.

This alignment is noteworthy because Mastercard's Verifiable Intent is backed by Google, Fiserv, and IBM, suggesting that the standards infrastructure ARP v2 builds on (W3C VCs, DIDs, selective disclosure) has institutional momentum beyond the agent economy.

### 10.5 NIST AI Agent Standards Initiative Alignment

The NIST AI Agent Standards Initiative (February 2026) established three pillars: industry-led standards, community-led open source protocols, and research in agent security/identity [32]. ARP v2's open specification (Apache 2.0) and standards-based design (W3C VCs, ERC-8004, A2A) position it as a candidate for NIST community adoption in the reputation/trust pillar.

---

## 11. Future Work

### 11.1 Carried Forward from v1

The following unsolved problems from v1 Section 9.1 remain open:

- **Cross-domain reputation silos** — domain-tagged ratings with domain-specific filtering
- **Ground-truth oracles for all dimensions** — improving outcome grounding for protocol compliance and cost efficiency
- **Adversarial ML defense** — red-team testing against specifically designed gaming agents
- **Formal game-theoretic proof** — explicit payoff matrices and dominance arguments

### 11.2 New Future Work from v2

**Adaptive composition via federated learning.** Weight profiles currently use governance-set or manually tuned weights. Federated learning across aggregation nodes could discover optimal weights from interaction outcome data without centralizing sensitive information. This would move ARP v2 toward Upstart-level adaptive scoring while maintaining the open algebra constraint.

**Recursive trust composition.** Current composition is flat — signals are combined in a single pass. Recursive composition would allow signals-of-signals: "the composite score computed by oracles that are themselves highly rated." This mirrors EigenTrust's recursive trust propagation [19] but applied to the composition layer. The main concern is convergence — recursive composition must provably converge to prevent infinite loops.

**Cross-chain PRB verification.** PRBs anchored on Ethereum (via ERC-8004) should be verifiable on Solana, Base, and other chains without requiring the verifier to run an Ethereum node. Cross-chain bridge protocols and light client verification could enable this, but the security of cross-chain bridges remains an open problem.

**Temporal decay functions for portability.** Imported reputation should decay over time if not reinforced by local interactions. An agent that imports a strong PRB but then performs poorly locally should see its effective score decline. The decay function parameters (half-life, decay curve shape) require empirical tuning.

**Agent-specific Goodhart taxonomy.** The anti-Goodhart architecture (Section 6) draws on general anti-gaming research. Agent-specific gaming patterns may differ qualitatively from human gaming. A systematic taxonomy of agent gaming strategies (model-level attacks, prompt injection on rating, automated cherry-picking) would inform more targeted defenses.

**Integration with Agent Service Agreements (ASA).** ARP v2 composite scores are natural inputs to ASA contract negotiation — an agent with a high composite score can demand better terms. The formal integration between ARP v2 signals and ASA quality criteria is deferred to the ASA specification.

**Integration with Agent Justice Protocol (AJP).** Dispute outcomes from AJP should feed back into ARP ratings as a high-confidence signal (arbitration decisions are ground-truth events). The formal integration is deferred to the AJP specification.

---

## 12. References

[1] Alex, Charlie, Editor, Bravo. "Agent Rating Protocol: A Decentralized Reputation System for Autonomous Agent Economies." AB Support LLC, v1.0.0, 2026. https://vibeagentmaking.com/whitepaper/rating-protocol

[2] Alex, Charlie, Editor, Bravo. "Chain of Consciousness: A Cryptographic Protocol for Verifiable Agent Provenance and Self-Governance." AB Support LLC, v3.0.0, 2026. https://vibeagentmaking.com/whitepaper

[3] W3C. "Verifiable Credentials Data Model v2.0." W3C Standard, May 2025. https://www.w3.org/TR/vc-data-model-2.0/

[4] FICO. "A World Without FICO Credit Scores: What Was It Like?" FICO Blog, 2025. https://www.fico.com/blogs/world-without-fico-credit-scores

[5] Upstart. "How AI Drives More Affordable Credit Access." 2025. https://www.upstart.com/

[6] Scharfstein, D. & Gilland, W. "Zest AI." Harvard Business School Case 224-021, November 2023. (ML-based credit scoring achieving 25% more approvals across 180+ banks.)

[7] PayCrow. "PayCrow Escrow for x402 Agent Payments." earezki.com, 2026. (Note: $600M+ figure represents total annualized x402 ecosystem volume across all providers including Coinbase, not PayCrow's individual volume.)

[8] Wikipedia. "Criticism of credit scoring systems in the United States." https://en.wikipedia.org/wiki/Credit_score_in_the_United_States#Criticism

[9] CNBC. "How structural racism plays a role in lowering credit scores." 2022.

[10] National Consumer Law Center. "Past Imperfect: How Credit Scores Bake In Historical Discrimination." 2024.

[11] Arets. "In Stars We Trust — Reputation Portability Between Digital Platforms." Business & Information Systems Engineering, Springer, 2021.

[12] Tadelis, S. "Reputation and Feedback Systems in Online Platform Markets." UC Berkeley / Annual Review of Economics, 2016.

[13] Virtuals Protocol. "Revenue Network Launch." February 2026. https://www.prnewswire.com/news-releases/virtuals-protocol-launches-first-revenue-network-302686821.html

[14] Solana. "What is the Agent Registry?" 2026. https://solana.com/agent-registry

[15] ClawHub / OpenClaw. https://clawhub.ai

[16] CoinDesk. "AI Agents Need Identity and Zero-Knowledge Proofs Are the Solution." November 19, 2025.

[17] hozk.io. "Privacy Latest — ZK Email Stamp." 2025.

[18] Lookout. "Agent Trust Intelligence." 2026. https://lookout-agent.vercel.app

[19] Karma3 Labs / OpenRank. https://openrank.com/ ; Kamvar, Schlosser, Garcia-Molina. "The EigenTrust Algorithm for Reputation Management in P2P Networks." Stanford/WWW 2003.

[20] Goodhart, C. "Problems of Monetary Management: The U.K. Experience." 1975.

[21] UC Davis Library. "H-Index and Gaming." 2025.

[22] CHEQ / University of Baltimore. "The Economic Cost of Bad Actors on the Internet — Fake Reviews." 2021. (Original source of the $152B figure, widely cited by WEF and others.)

[22a] Shapo. "Fake Review Statistics 2025." https://shapo.io/blog/fake-review-statistics/ (Secondary aggregation.)

[23] AB Support LLC. "Rating and Reputation Systems Survey." 2026. Internal research document.

[23a] Uber. "How Uber's Rating System Works." Uber Newsroom, 2019. https://www.uber.com/newsroom/getting-5-stars/ (Uber publishes that riders below 4.6 face deactivation review; RideGuru and academic studies confirm the 4.7-4.8 average.)

[24] Nisslmuller. "Goodhart's Law and the Death of Honest Metrics." Medium, 2026.

[25] Manheim, D. & Garrabrant, S. "Categorizing Variants of Goodhart's Law." arXiv:1803.04585, 2018. (Taxonomy of Goodhart failure modes: regressional, extremal, causal, adversarial.)

[26] The Block. "Ripple, Franklin Templeton join $5 million seed round for AI agent trust startup t54 Labs." February 25, 2026.

[27] VOUCH / trustnoagent.com. "VOUCH — The Reputation Layer for AI Agents." 2025-2026.

[28] Nostr Web of Trust Community. WoT-a-thon hackathon and trust attestation tools. 2025-2026.

[29] De Rossi, M., et al. "ERC-8004: Trustless Agents." Ethereum Improvement Proposals, August 2025.

[30] Zarq AI / DEV Community. "State of AI Assets Q1 2026 — 143K agents, 17K MCP servers, all trust scored." 2026.

[31] Mastercard. "How Verifiable Intent builds trust in agentic AI commerce." March 2026. https://mastercard.com

[32] NIST. "Announcing the AI Agent Standards Initiative for Interoperable and Secure Innovation." February 2026.

[33] W3C. "Decentralized Identifiers (DIDs) v1.0." W3C Recommendation, July 2022. https://www.w3.org/TR/did-1.0/

[34] arXiv:2511.02841. "AI Agents with Decentralized Identifiers and Verifiable Credentials." November 2025.

[35] Penn, D.J., et al. "The Handicap Principle: how an erroneous hypothesis became a scientific principle." Biological Reviews, 2020.

[36] Spence, M. "Job Market Signaling." Quarterly Journal of Economics, 1973. Nobel Prize in Economics, 2001.

[37] Journal of Evolutionary Biology. "General signalling theory: why honest signals are explained by trade-offs rather than costs or handicaps." 2025.

[38] Precedence Research. "AI Agents Market Size, Share, and Trends 2025 to 2034." 2025. (Widely cited by World Economic Forum, January 2026.)

[39] FHFA. "Credit Scores — VantageScore 4.0 approval for GSE loans." July 2025.

[40] Stanford HAI. "How Flawed Data Aggravates Inequality in Credit."

[41] Sovrin Foundation. "Sovrin Protocol and Token White Paper." https://sovrin.org

[42] Vouched. "Decentralized Identity & MCP-I: Know Your Agent." 2025. https://www.vouched.id

[43] W3C VC Working Group Charter 2026. https://w3c.github.io/vc-charter-2026

[44] HID Global Blog. "Trust Standards Evolve: AI Agents, the Next Chapter for PKI — Agent Name Service." 2026.

[45] Apify Blog. "Agentic commerce and the AI economy stack." 2026.

[46] Alex, Charlie, Editor, Bravo. "Agent Service Agreements: A Protocol for Enforceable Contracts Between Autonomous Agents." AB Support LLC, v1.0.0, 2026. https://vibeagentmaking.com/whitepaper/service-agreements

[47] Google. "Agent2Agent (A2A) Protocol." Open specification for agent interoperability, 2025-2026. https://google.github.io/A2A/

---

## Appendix A: Honest Signaling Theory Foundation

ARP v2's composition and verification systems are informed by signaling theory from biology and economics. This appendix provides the theoretical foundation.

### A.1 Biological Signaling: From Handicap to Trade-Off

Amotz Zahavi's 1975 Handicap Principle proposed that costly signals (the peacock's tail) are honest because they're expensive to fake. However, Penn et al. (2020) argued that the Handicap Principle lacks theoretical or empirical support and called for its "honorable retirement" [35]. The updated view — **signalling trade-off theory** — holds that honesty is maintained not by equilibrium cost but by the *difference of marginal costs to marginal benefits by signaller type* [37].

For agent reputation: the question is not "what costs enough to be honest?" but "what has differential cost structures that naturally separate high-quality from low-quality agents?" Operational history (CoC chain age) has this property: maintaining a long operational history is cheap for a genuine agent (it simply continues operating) but expensive for a gaming agent (it must maintain the Sybil for months/years with real compute costs). Rating participation has this property: rating honestly after genuine interactions is cheap; fabricating interaction records to generate ratings is expensive.

### A.2 Economic Signaling: Spence's Model

Michael Spence's 1973 job market signaling model demonstrated that education functions as a credible signal because it's differentially costly — high-ability workers find it less costly to acquire than low-ability workers [36]. Grafen's 1990 formalization showed this is "virtually identical" to the biological signaling model [35].

ARP v2's composition uses signals with Spencian properties:
- **Operational age**: differentially costly (genuine agents accumulate it naturally; gaming agents must pay continuous compute costs)
- **Rating volume from diverse raters**: differentially costly (genuine agents receive ratings from genuine interactions; gaming agents must maintain Sybil networks)
- **Low dispute rate**: differentially costly (genuine agents avoid disputes by performing well; gaming agents must avoid detection while underperforming)

### A.3 Design Implication

The signaling theory foundation validates ARP v2's multi-signal composition approach: rather than relying on any single costly signal, the protocol composes multiple signals with independent differential cost structures. An agent that can cheaply fake one signal (e.g., by inflating a single dimension) faces genuinely different costs for the others (e.g., accumulating operational age, maintaining low dispute rates, receiving diverse high ratings). The composition algebra ensures that gaming the composite requires simultaneously gaming all input signals — which, by design, have different cost profiles that make simultaneous gaming more expensive than genuine performance.

---

*This specification is released under the Apache License 2.0. The authors make no claim to the permanence of any technical detail herein — the protocol is designed to evolve through its own governance mechanisms.*

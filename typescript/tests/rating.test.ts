import { describe, it } from "node:test";
import * as assert from "node:assert/strict";
import {
  AgentIdentity,
  InteractionEvidence,
  RatingRecord,
  scoreBucket,
  DIMENSIONS,
  VERIFICATION_LEVELS,
} from "../src/rating";
import {
  generateNonce,
  commit,
  reveal,
  BlindExchange,
} from "../src/blind";
import {
  raterWeight,
  verificationLevelMultiplier,
  raterCalibrationFactor,
  confidence,
  effectiveWeight,
  weightedScore,
  weightedScoresAll,
  signalsFromRatings,
} from "../src/weight";
import {
  Signal,
  Gate,
  PenaltyFloor,
  ProfileInput,
  WeightProfile,
  CompositeSignal,
  compose,
  diminishingReturnsTransform,
  getProfile,
  STANDARD_PROFILES,
} from "../src/composition";
import {
  DimensionSummary,
  OracleAttestation,
  computeRatingsRootHash,
  multiOracleAttestation,
  trustDiscount,
} from "../src/portability";
import {
  MerkleTree,
  verifyMerkleProof,
  verifyPrbMerkle,
  verifyHashChain,
  createZkpThresholdProof,
  verifyZkpThresholdProof,
} from "../src/signals";
import {
  ShadowMetric,
  ShadowMetricCommitment,
  computeShadowCommitment,
  verifyShadowCommitment,
  generateRotationBounds,
  rotateWeights,
  laplaceNoise,
  addDpNoise,
  AnomalyFlag,
  checkAnomalies,
} from "../src/anti_goodhart";

describe("rating.ts", () => {
  it("creates a valid RatingRecord", () => {
    const r = new RatingRecord({
      raterId: "did:web:rater.example",
      rateeId: "did:web:ratee.example",
      reliability: 85,
      accuracy: 90,
      latency: 70,
      protocolCompliance: 95,
      costEfficiency: 80,
    });
    assert.equal(r.raterId, "did:web:rater.example");
    assert.equal(r.reliability, 85);
    assert.ok(r.recordHash.length === 64);
    assert.ok(r.verifyHash());
  });

  it("rejects out-of-range dimensions", () => {
    assert.throws(() => {
      new RatingRecord({
        raterId: "a",
        rateeId: "b",
        reliability: 0,
      });
    }, /1-100/);
  });

  it("rejects missing rater", () => {
    assert.throws(() => {
      new RatingRecord({ raterId: "", rateeId: "b" });
    }, /raterId is required/);
  });

  it("round-trips through toDict/fromDict", () => {
    const r = new RatingRecord({
      raterId: "rater1",
      rateeId: "ratee1",
      reliability: 80,
      accuracy: 75,
      latency: 60,
      protocolCompliance: 90,
      costEfficiency: 70,
      raterChainAgeDays: 100,
      raterTotalRatingsGiven: 50,
    });
    const d = r.toDict();
    const r2 = RatingRecord.fromDict(d);
    assert.equal(r.raterId, r2.raterId);
    assert.equal(r.recordHash, r2.recordHash);
    assert.ok(r2.verifyHash());
  });

  it("scoreBucket works", () => {
    assert.equal(scoreBucket(10), "poor");
    assert.equal(scoreBucket(50), "average");
    assert.equal(scoreBucket(95), "excellent");
    assert.throws(() => scoreBucket(0));
  });

  it("DIMENSIONS has 5 entries", () => {
    assert.equal(DIMENSIONS.length, 5);
  });

  it("VERIFICATION_LEVELS has 3 entries", () => {
    assert.equal(VERIFICATION_LEVELS.length, 3);
  });

  it("AgentIdentity round-trips", () => {
    const ai = new AgentIdentity("did:web:test", "proof123");
    const d = ai.toDict();
    const ai2 = AgentIdentity.fromDict(d);
    assert.equal(ai.agentId, ai2.agentId);
    assert.equal(ai.identityProof, ai2.identityProof);
  });
});

describe("blind.ts", () => {
  it("commit and reveal match", () => {
    const rating = { reliability: 85, accuracy: 90 };
    const nonce = generateNonce();
    const hash = commit(rating, nonce);
    assert.ok(hash.length === 64);
    assert.ok(reveal(rating, nonce, hash));
    assert.ok(!reveal({ reliability: 86, accuracy: 90 }, nonce, hash));
  });

  it("BlindExchange full flow", () => {
    const ex = new BlindExchange("interaction-1");
    const ratingA = { reliability: 80 };
    const nonceA = generateNonce();
    const ratingB = { reliability: 90 };
    const nonceB = generateNonce();

    ex.submitCommitment("agentA", ratingA, nonceA);
    assert.ok(!ex.bothCommitted);

    ex.submitCommitment("agentB", ratingB, nonceB);
    assert.ok(ex.bothCommitted);
    assert.ok(ex.revealTriggered);

    assert.ok(ex.revealRating("agentA", ratingA, nonceA));
    assert.ok(ex.revealRating("agentB", ratingB, nonceB));
    assert.ok(ex.bothRevealed);

    const results = ex.getResults();
    assert.ok(results !== null);
    assert.deepEqual(results![0], ratingA);
    assert.deepEqual(results![1], ratingB);
  });

  it("rejects duplicate commitment", () => {
    const ex = new BlindExchange("interaction-2");
    ex.submitCommitment("agentA", {}, generateNonce());
    assert.throws(() => {
      ex.submitCommitment("agentA", {}, generateNonce());
    }, /already committed/);
  });
});

describe("weight.ts", () => {
  it("raterWeight formula", () => {
    assert.equal(raterWeight(0, 0), 0);
    const w = raterWeight(100, 50);
    assert.ok(w > 0);
    assert.ok(Math.abs(w - Math.log2(101) * Math.log2(51)) < 0.001);
  });

  it("verificationLevelMultiplier", () => {
    assert.equal(verificationLevelMultiplier("verified"), 1.0);
    assert.equal(verificationLevelMultiplier("unilateral"), 0.5);
  });

  it("raterCalibrationFactor penalizes low variance", () => {
    const highVariance = raterCalibrationFactor([10, 90, 50, 20, 80]);
    assert.equal(highVariance, 1.0);
    const lowVariance = raterCalibrationFactor([50, 51, 50, 49, 50]);
    assert.ok(lowVariance < 1.0);
  });

  it("confidence approaches 1", () => {
    assert.equal(confidence(0), 0);
    assert.ok(confidence(100) > 0.9);
    assert.ok(confidence(1000) > 0.99);
  });

  it("weightedScore returns null for empty", () => {
    assert.equal(weightedScore([], "reliability"), null);
  });

  it("signalsFromRatings produces signals", () => {
    const r = new RatingRecord({
      raterId: "a",
      rateeId: "b",
      raterChainAgeDays: 30,
      raterTotalRatingsGiven: 10,
    });
    const signals = signalsFromRatings([r], undefined, "", 100, 0.5);
    assert.ok(signals.length >= 7);
    const ids = signals.map((s: Signal) => s.signalId);
    assert.ok(ids.includes("arp:reliability:weighted_mean"));
    assert.ok(ids.includes("coc:operational_age_days"));
  });
});

describe("composition.ts", () => {
  it("diminishingReturnsTransform", () => {
    const v = diminishingReturnsTransform(365, 365);
    assert.ok(Math.abs(v - 100 * (1 - Math.exp(-1))) < 0.01);
    assert.throws(() => diminishingReturnsTransform(10, 0));
  });

  it("Gate evaluate", () => {
    const g = new Gate("test", 5, "minimum");
    assert.ok(g.evaluate(5));
    assert.ok(g.evaluate(10));
    assert.ok(!g.evaluate(4));
  });

  it("PenaltyFloor computePenalty", () => {
    const pf = new PenaltyFloor("test", 30, 25);
    assert.equal(pf.computePenalty(30), 0);
    assert.equal(pf.computePenalty(50), 0);
    assert.ok(pf.computePenalty(15) > 0);
  });

  it("compose with standard profile", () => {
    const signals = [
      new Signal({ signalType: "rating_dimension", signalId: "arp:reliability:weighted_mean", value: 80, confidence: 0.9 }),
      new Signal({ signalType: "rating_dimension", signalId: "arp:accuracy:weighted_mean", value: 85, confidence: 0.9 }),
      new Signal({ signalType: "rating_dimension", signalId: "arp:latency:weighted_mean", value: 70, confidence: 0.8 }),
      new Signal({ signalType: "rating_dimension", signalId: "arp:protocol_compliance:weighted_mean", value: 90, confidence: 0.9 }),
      new Signal({ signalType: "rating_dimension", signalId: "arp:cost_efficiency:weighted_mean", value: 75, confidence: 0.85 }),
      new Signal({ signalType: "provenance", signalId: "coc:operational_age_days", value: 100, confidence: 1.0 }),
      new Signal({ signalType: "behavioral", signalId: "behavioral:rating_participation_rate", value: 80, confidence: 1.0 }),
      new Signal({ signalType: "behavioral", signalId: "arp:total_ratings_received", value: 50, confidence: 1.0 }),
    ];
    const profile = getProfile("general-purpose");
    const result = compose(signals, profile);
    assert.equal(result.gateStatus, "all_passed");
    assert.ok(result.value > 0);
    assert.ok(result.value <= 100);
  });

  it("compose disqualifies on gate failure", () => {
    const signals = [
      new Signal({ signalType: "behavioral", signalId: "arp:total_ratings_received", value: 2 }),
      new Signal({ signalType: "provenance", signalId: "coc:operational_age_days", value: 100 }),
    ];
    const profile = getProfile("general-purpose");
    const result = compose(signals, profile);
    assert.ok(result.gateStatus.startsWith("failed"));
    assert.equal(result.value, -1);
  });

  it("STANDARD_PROFILES has 5 entries", () => {
    assert.equal(Object.keys(STANDARD_PROFILES).length, 5);
  });

  it("getProfile throws on unknown", () => {
    assert.throws(() => getProfile("nonexistent"), /Unknown profile/);
  });

  it("WeightProfile round-trips", () => {
    const p = getProfile("general-purpose");
    const d = p.toDict();
    const p2 = WeightProfile.fromDict(d);
    assert.equal(p.profileId, p2.profileId);
    assert.equal(p.inputs.length, p2.inputs.length);
  });
});

describe("portability.ts", () => {
  it("computeRatingsRootHash empty", () => {
    const hash = computeRatingsRootHash([]);
    assert.ok(hash.length === 64);
  });

  it("computeRatingsRootHash deterministic", () => {
    const hashes = [
      "a".repeat(64),
      "b".repeat(64),
      "c".repeat(64),
    ];
    const root1 = computeRatingsRootHash(hashes);
    const root2 = computeRatingsRootHash(hashes);
    assert.equal(root1, root2);
  });

  it("multiOracleAttestation consensus", () => {
    const attestations = [
      new OracleAttestation("oracle-a", 78.4),
      new OracleAttestation("oracle-b", 77.9),
      new OracleAttestation("oracle-c", 78.1),
    ];
    const result = multiOracleAttestation(attestations);
    assert.equal(result.status, "consensus");
    assert.equal(result.consensusMethod, "median");
  });

  it("multiOracleAttestation disputed", () => {
    const attestations = [
      new OracleAttestation("a", 80),
      new OracleAttestation("b", 80),
      new OracleAttestation("c", 95),
    ];
    const result = multiOracleAttestation(attestations, 3, 10);
    assert.equal(result.status, "disputed");
  });

  it("trustDiscount applies", () => {
    assert.equal(trustDiscount(80, 1.0, 1.0, 1.0), 80);
    assert.equal(trustDiscount(80, 0.5), 40);
    const single = trustDiscount(80, 1.0, 1.0, 1.0, true, false);
    assert.equal(single, 40);
  });

  it("DimensionSummary round-trips", () => {
    const ds = new DimensionSummary(82.3, 11.2, 0.87, 247);
    const d = ds.toDict();
    const ds2 = DimensionSummary.fromDict(d);
    assert.ok(Math.abs(ds2.mean - 82.3) < 0.01);
  });
});

describe("signals.ts", () => {
  it("MerkleTree and proof verification", () => {
    const hashes = ["aa".repeat(32), "bb".repeat(32), "cc".repeat(32)];
    const tree = new MerkleTree(hashes);
    assert.equal(tree.leafCount, 3);
    assert.ok(tree.root.length === 64);

    for (let i = 0; i < hashes.length; i++) {
      const proof = tree.getProof(i);
      assert.ok(verifyMerkleProof(proof));
    }
  });

  it("verifyPrbMerkle full verification", () => {
    const hashes = ["aa".repeat(32), "bb".repeat(32)];
    const tree = new MerkleTree(hashes);
    const result = verifyPrbMerkle(tree.root, hashes, 0);
    assert.ok(result.rootHashMatches);
    assert.equal(result.proofsFailed, 0);
    assert.equal(result.proofsVerified, 2);
  });

  it("verifyHashChain basic", () => {
    const result = verifyHashChain("abc123", "abc123", "r1");
    assert.ok(result.hashValid);
    const result2 = verifyHashChain("abc123", "def456", "r1");
    assert.ok(!result2.hashValid);
  });

  it("ZKP placeholder", () => {
    const proof = createZkpThresholdProof({
      actualComposite: 85,
      thresholdComposite: 80,
    });
    assert.equal(proof.proofSystem, "placeholder");
    const result = verifyZkpThresholdProof(proof);
    assert.equal(result.verified, false);
    assert.ok("warning" in result);
  });

  it("ZKP rejects below threshold", () => {
    assert.throws(() => {
      createZkpThresholdProof({
        actualComposite: 70,
        thresholdComposite: 80,
      });
    }, /does not meet threshold/);
  });
});

describe("anti_goodhart.ts", () => {
  it("ShadowMetric divergence detection", () => {
    const sm = new ShadowMetric({
      primarySignalId: "composite_score",
      shadowSignalId: "score_stability",
    });
    sm.record(80, 78);
    sm.record(81, 79);
    sm.record(80, 78);
    sm.record(80, 78);
    sm.record(80, 78);
    assert.ok(!sm.divergenceDetected());
    sm.record(95, 50);
    assert.ok(sm.divergenceDetected());
  });

  it("shadow commitment round-trip", () => {
    const data = { agent1: { score: 80 }, agent2: { score: 75 } };
    const commitment = computeShadowCommitment("oracle-1", data);
    assert.ok(verifyShadowCommitment(commitment, data));
    assert.ok(!verifyShadowCommitment(commitment, { agent1: { score: 99 } }));
  });

  it("generateRotationBounds", () => {
    const profile = getProfile("general-purpose");
    const bounds = generateRotationBounds(profile);
    assert.equal(bounds.length, profile.inputs.length);
    for (const b of bounds) {
      assert.ok(b.minWeight <= b.maxWeight);
    }
  });

  it("rotateWeights produces valid profile", () => {
    const profile = getProfile("general-purpose");
    const bounds = generateRotationBounds(profile);
    const [newProfile, event] = rotateWeights(profile, bounds, 42);
    assert.equal(newProfile.profileId, profile.profileId);
    assert.equal(newProfile.inputs.length, profile.inputs.length);
    const total = newProfile.inputs.reduce((s, i) => s + i.weight, 0);
    assert.ok(Math.abs(total - 1.0) < 0.01);
    assert.ok(event.announcement.length > 0);
  });

  it("laplaceNoise produces values", () => {
    const noise = laplaceNoise(5, 1);
    assert.equal(typeof noise, "number");
    assert.ok(isFinite(noise));
    assert.throws(() => laplaceNoise(5, 0));
    assert.throws(() => laplaceNoise(-1, 1));
  });

  it("addDpNoise stays in range", () => {
    for (let i = 0; i < 100; i++) {
      const noised = addDpNoise(50, 5, 1, [0, 100]);
      assert.ok(noised >= 0 && noised <= 100);
    }
  });

  it("checkAnomalies flags divergent metrics", () => {
    const sm = new ShadowMetric({
      primarySignalId: "test",
      shadowSignalId: "shadow_test",
    });
    sm.record(80, 78);
    sm.record(81, 79);
    sm.record(80, 78);
    sm.record(80, 78);
    sm.record(80, 78);
    sm.record(95, 50);
    const flags = checkAnomalies("agent-1", [sm]);
    assert.equal(flags.length, 1);
    assert.equal(flags[0].severity, "enhanced_monitoring");
  });
});

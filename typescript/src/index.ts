// Core types
export {
  DIMENSIONS,
  SCORE_BUCKETS,
  VERIFICATION_LEVELS,
  SignalTier,
  VerificationLevel,
} from "./types";
export type {
  Dimension,
  VerificationLevelStr,
  AgentIdentityData,
  InteractionEvidenceData,
  RatingRecordData,
  DimensionScores,
  SignalData,
  ProfileInputData,
  GateData,
  PenaltyFloorData,
  WeightProfileData,
  CompositeSignalData,
  DimensionSummaryData,
} from "./types";

// Rating (v1 core)
export {
  scoreBucket,
  AgentIdentity,
  InteractionEvidence,
  RatingRecord,
} from "./rating";
export type { RatingRecordOptions } from "./rating";

// Blind protocol (v1 core)
export {
  generateNonce,
  commit,
  reveal,
  BlindCommitment,
  BlindExchange,
} from "./blind";

// Store (v1 core)
export { RatingStore } from "./store";

// Weight (v1 core + v2 extensions)
export {
  raterWeight,
  verificationLevelMultiplier,
  raterCalibrationFactor,
  recencyMultiplier,
  effectiveWeight,
  computeRaterCalibrations,
  weightedScore,
  weightedScoresAll,
  confidence,
  signalsFromRatings,
} from "./weight";

// Composition (v2)
export {
  DISQUALIFIED,
  Signal,
  ProfileInput,
  Gate,
  PenaltyFloor,
  WeightProfile,
  CompositeSignal,
  diminishingReturnsTransform,
  compose,
  GENERAL_PURPOSE,
  HIGH_RELIABILITY,
  FAST_TURNAROUND,
  COMPLIANCE_FIRST,
  COST_OPTIMIZED,
  STANDARD_PROFILES,
  getProfile,
} from "./composition";

// Portability (v2)
export {
  DimensionSummary,
  ProvenanceSummary,
  BehavioralSummary,
  OracleAttestation,
  PortableReputationBundle,
  computeRatingsRootHash,
  generatePrb,
  multiOracleAttestation,
  trustDiscount,
} from "./portability";

// Anti-Goodhart (v2)
export {
  RotationBound,
  RotationEvent,
  generateRotationBounds,
  rotateWeights,
  ShadowMetric,
  DEFAULT_SHADOW_METRICS,
  ShadowMetricCommitment,
  computeShadowCommitment,
  verifyShadowCommitment,
  AnomalyFlag,
  checkAnomalies,
  laplaceNoise,
  addDpNoise,
  dpResponse,
} from "./anti_goodhart";

// Signals / Verification (v2)
export {
  DEFAULT_TIER_MAP,
  HashChainVerification,
  verifyHashChain,
  MerkleProof,
  MerkleTree,
  verifyMerkleProof,
  MerkleVerificationResult,
  verifyPrbMerkle,
  ZKPThresholdProof,
  createZkpThresholdProof,
  verifyZkpThresholdProof,
} from "./signals";

// Query (v1 + v2)
export {
  getReputation,
  getReputationSummary,
  getGovernanceWeights,
  verifyRating,
  getComposite,
  generatePrbFromStore,
} from "./query";

export const DIMENSIONS = [
  "reliability",
  "accuracy",
  "latency",
  "protocol_compliance",
  "cost_efficiency",
] as const;

export type Dimension = (typeof DIMENSIONS)[number];

export const SCORE_BUCKETS: Array<{ lo: number; hi: number; label: string }> = [
  { lo: 1, hi: 20, label: "poor" },
  { lo: 21, hi: 40, label: "below_average" },
  { lo: 41, hi: 60, label: "average" },
  { lo: 61, hi: 80, label: "good" },
  { lo: 81, hi: 100, label: "excellent" },
];

export const VERIFICATION_LEVELS = [
  "verified",
  "unilateral",
  "self_reported",
] as const;

export type VerificationLevelStr = (typeof VERIFICATION_LEVELS)[number];

export interface AgentIdentityData {
  agent_id: string;
  identity_proof?: string;
}

export interface InteractionEvidenceData {
  task_type: string;
  outcome_hash: string;
  duration_ms: number;
  was_completed: boolean;
}

export interface RatingRecordData {
  version: number;
  rating_id: string;
  timestamp: string;
  interaction_id: string;
  rater: AgentIdentityData;
  ratee: AgentIdentityData;
  dimensions: Record<Dimension, number>;
  interaction_evidence: InteractionEvidenceData;
  verification_level: string;
  metadata: {
    rater_chain_length?: number;
    rater_chain_age_days: number;
    rater_total_ratings_given: number;
    bilateral_blind: boolean;
  };
  record_hash: string;
}

export interface DimensionScores {
  reliability: number;
  accuracy: number;
  latency: number;
  protocol_compliance: number;
  cost_efficiency: number;
}

export interface SignalData {
  signal_type: string;
  signal_id: string;
  value: number;
  confidence: number;
  source: string;
  window: string;
  sample_size: number;
  timestamp: string;
}

export interface ProfileInputData {
  signal_id: string;
  weight: number;
  operation: string;
  k?: number;
  weight_bounds?: { min: number; max: number };
}

export interface GateData {
  signal_id: string;
  threshold: number;
  gate_type: string;
}

export interface PenaltyFloorData {
  signal_id: string;
  floor: number;
  max_penalty: number;
}

export interface WeightProfileData {
  profile_id: string;
  version: string;
  description: string;
  inputs: ProfileInputData[];
  gates: GateData[];
  penalty_floors: PenaltyFloorData[];
  output_range: [number, number];
  rotation_schedule: string;
  governance_approved: string;
  effective_until: string;
}

export interface CompositeSignalData {
  profile_id: string;
  value: number;
  confidence: number;
  input_count: number;
  weakest_input?: { signal_id: string; confidence: number };
  gate_status: string;
  computed_at: string;
  valid_until: string;
  computed_by?: string;
}

export interface DimensionSummaryData {
  mean: number;
  stddev: number;
  confidence: number;
  count: number;
}

export enum SignalTier {
  PUBLIC = "public",
  QUERYABLE = "queryable",
  PRIVATE = "private",
}

export enum VerificationLevel {
  BASIC = "basic",
  STANDARD = "standard",
  PRIVACY_PRESERVING = "privacy_preserving",
}

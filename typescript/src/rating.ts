import { createHash, randomUUID } from "node:crypto";
import {
  DIMENSIONS,
  SCORE_BUCKETS,
  VERIFICATION_LEVELS,
  type AgentIdentityData,
  type Dimension,
  type DimensionScores,
  type InteractionEvidenceData,
  type RatingRecordData,
  type VerificationLevelStr,
} from "./types";

export { DIMENSIONS, SCORE_BUCKETS, VERIFICATION_LEVELS };

export function scoreBucket(score: number): string {
  for (const { lo, hi, label } of SCORE_BUCKETS) {
    if (score >= lo && score <= hi) return label;
  }
  throw new Error(`Score ${score} out of range 1-100`);
}

export class AgentIdentity {
  readonly agentId: string;
  readonly identityProof: string | undefined;

  constructor(agentId: string, identityProof?: string) {
    this.agentId = agentId;
    this.identityProof = identityProof;
  }

  toDict(): AgentIdentityData {
    const d: AgentIdentityData = { agent_id: this.agentId };
    if (this.identityProof !== undefined) {
      d.identity_proof = this.identityProof;
    }
    return d;
  }

  static fromDict(d: AgentIdentityData | string): AgentIdentity {
    if (typeof d === "string") return new AgentIdentity(d);
    return new AgentIdentity(d.agent_id, d.identity_proof);
  }
}

export class InteractionEvidence {
  readonly taskType: string;
  readonly outcomeHash: string;
  readonly durationMs: number;
  readonly wasCompleted: boolean;

  constructor(opts?: Partial<InteractionEvidenceData>) {
    this.taskType = opts?.task_type ?? "";
    this.outcomeHash = opts?.outcome_hash ?? "";
    this.durationMs = opts?.duration_ms ?? 0;
    this.wasCompleted = opts?.was_completed ?? true;
  }

  toDict(): InteractionEvidenceData {
    return {
      task_type: this.taskType,
      outcome_hash: this.outcomeHash,
      duration_ms: this.durationMs,
      was_completed: this.wasCompleted,
    };
  }

  static fromDict(d: Partial<InteractionEvidenceData>): InteractionEvidence {
    return new InteractionEvidence(d);
  }
}

export interface RatingRecordOptions {
  raterId: string;
  rateeId: string;
  interactionId?: string;
  raterIdentityProof?: string;
  rateeIdentityProof?: string;
  reliability?: number;
  accuracy?: number;
  latency?: number;
  protocolCompliance?: number;
  costEfficiency?: number;
  evidence?: InteractionEvidence;
  verificationLevel?: VerificationLevelStr;
  raterChainLength?: number;
  raterChainAgeDays?: number;
  raterTotalRatingsGiven?: number;
  bilateralBlind?: boolean;
  ratingId?: string;
  timestamp?: string;
  version?: number;
  recordHash?: string;
}

export class RatingRecord {
  readonly raterId: string;
  readonly rateeId: string;
  readonly interactionId: string;
  readonly raterIdentityProof: string | undefined;
  readonly rateeIdentityProof: string | undefined;
  readonly reliability: number;
  readonly accuracy: number;
  readonly latency: number;
  readonly protocolCompliance: number;
  readonly costEfficiency: number;
  readonly evidence: InteractionEvidence;
  readonly verificationLevel: VerificationLevelStr;
  readonly raterChainLength: number | undefined;
  readonly raterChainAgeDays: number;
  readonly raterTotalRatingsGiven: number;
  readonly bilateralBlind: boolean;
  readonly ratingId: string;
  readonly timestamp: string;
  readonly version: number;
  readonly recordHash: string;

  constructor(opts: RatingRecordOptions) {
    this.raterId = opts.raterId;
    this.rateeId = opts.rateeId;
    this.interactionId = opts.interactionId ?? "";
    this.raterIdentityProof = opts.raterIdentityProof;
    this.rateeIdentityProof = opts.rateeIdentityProof;
    this.reliability = opts.reliability ?? 50;
    this.accuracy = opts.accuracy ?? 50;
    this.latency = opts.latency ?? 50;
    this.protocolCompliance = opts.protocolCompliance ?? 50;
    this.costEfficiency = opts.costEfficiency ?? 50;
    this.evidence = opts.evidence ?? new InteractionEvidence();
    this.verificationLevel = opts.verificationLevel ?? "verified";
    this.raterChainLength = opts.raterChainLength;
    this.raterChainAgeDays = opts.raterChainAgeDays ?? 0;
    this.raterTotalRatingsGiven = opts.raterTotalRatingsGiven ?? 0;
    this.bilateralBlind = opts.bilateralBlind ?? true;
    this.ratingId = opts.ratingId ?? randomUUID();
    this.timestamp = opts.timestamp ?? new Date().toISOString();
    this.version = opts.version ?? 1;

    this._validate();
    this.recordHash = opts.recordHash || this.computeHash();
  }

  private _validate(): void {
    for (const dim of DIMENSIONS) {
      const val = this.getDimension(dim);
      if (!Number.isInteger(val) || val < 1 || val > 100) {
        throw new Error(
          `Dimension '${dim}' must be an integer 1-100, got ${val}`
        );
      }
    }
    if (!this.raterId) throw new Error("raterId is required");
    if (!this.rateeId) throw new Error("rateeId is required");
    if (
      !(VERIFICATION_LEVELS as readonly string[]).includes(
        this.verificationLevel
      )
    ) {
      throw new Error(
        `verificationLevel must be one of ${VERIFICATION_LEVELS.join(", ")}, got '${this.verificationLevel}'`
      );
    }
  }

  getDimension(dim: Dimension): number {
    switch (dim) {
      case "reliability":
        return this.reliability;
      case "accuracy":
        return this.accuracy;
      case "latency":
        return this.latency;
      case "protocol_compliance":
        return this.protocolCompliance;
      case "cost_efficiency":
        return this.costEfficiency;
    }
  }

  get raterIdentity(): AgentIdentity {
    return new AgentIdentity(this.raterId, this.raterIdentityProof);
  }

  get rateeIdentity(): AgentIdentity {
    return new AgentIdentity(this.rateeId, this.rateeIdentityProof);
  }

  get dimensions(): DimensionScores {
    return {
      reliability: this.reliability,
      accuracy: this.accuracy,
      latency: this.latency,
      protocol_compliance: this.protocolCompliance,
      cost_efficiency: this.costEfficiency,
    };
  }

  computeHash(): string {
    const canonical: Record<string, unknown> = {
      version: this.version,
      rating_id: this.ratingId,
      timestamp: this.timestamp,
      interaction_id: this.interactionId,
      rater_id: this.raterId,
      ratee_id: this.rateeId,
      dimensions: this.dimensions,
      evidence: this.evidence.toDict(),
    };
    if (this.raterIdentityProof !== undefined) {
      canonical.rater_identity_proof = this.raterIdentityProof;
    }
    if (this.rateeIdentityProof !== undefined) {
      canonical.ratee_identity_proof = this.rateeIdentityProof;
    }
    if (this.verificationLevel !== "verified") {
      canonical.verification_level = this.verificationLevel;
    }
    if (this.raterChainLength !== undefined) {
      canonical.rater_chain_length = this.raterChainLength;
    }
    const payload = JSON.stringify(canonical, Object.keys(canonical).sort());
    return createHash("sha256").update(payload, "utf-8").digest("hex");
  }

  toDict(): RatingRecordData {
    const rater: AgentIdentityData = { agent_id: this.raterId };
    if (this.raterIdentityProof !== undefined) {
      rater.identity_proof = this.raterIdentityProof;
    }
    const ratee: AgentIdentityData = { agent_id: this.rateeId };
    if (this.rateeIdentityProof !== undefined) {
      ratee.identity_proof = this.rateeIdentityProof;
    }
    const metadata: RatingRecordData["metadata"] = {
      rater_chain_age_days: this.raterChainAgeDays,
      rater_total_ratings_given: this.raterTotalRatingsGiven,
      bilateral_blind: this.bilateralBlind,
    };
    if (this.raterChainLength !== undefined) {
      metadata.rater_chain_length = this.raterChainLength;
    }
    return {
      version: this.version,
      rating_id: this.ratingId,
      timestamp: this.timestamp,
      interaction_id: this.interactionId,
      rater,
      ratee,
      dimensions: this.dimensions,
      interaction_evidence: this.evidence.toDict(),
      verification_level: this.verificationLevel,
      metadata,
      record_hash: this.recordHash,
    };
  }

  toJson(): string {
    return JSON.stringify(this.toDict());
  }

  static fromDict(d: RatingRecordData): RatingRecord {
    const dims = d.dimensions ?? {};
    const meta = d.metadata ?? {};
    const evidence = d.interaction_evidence ?? {};
    const raterData = d.rater ?? {};
    const rateeData = d.ratee ?? {};

    const raterId =
      typeof raterData === "string"
        ? raterData
        : (raterData as AgentIdentityData).agent_id ?? "";
    const rateeId =
      typeof rateeData === "string"
        ? rateeData
        : (rateeData as AgentIdentityData).agent_id ?? "";

    return new RatingRecord({
      raterId,
      rateeId,
      interactionId: d.interaction_id ?? "",
      raterIdentityProof:
        typeof raterData === "object"
          ? (raterData as AgentIdentityData).identity_proof
          : undefined,
      rateeIdentityProof:
        typeof rateeData === "object"
          ? (rateeData as AgentIdentityData).identity_proof
          : undefined,
      reliability: dims.reliability ?? 50,
      accuracy: dims.accuracy ?? 50,
      latency: dims.latency ?? 50,
      protocolCompliance: dims.protocol_compliance ?? 50,
      costEfficiency: dims.cost_efficiency ?? 50,
      evidence: InteractionEvidence.fromDict(evidence),
      verificationLevel:
        (d.verification_level as VerificationLevelStr) ?? "verified",
      raterChainLength: meta.rater_chain_length,
      raterChainAgeDays: meta.rater_chain_age_days ?? 0,
      raterTotalRatingsGiven: meta.rater_total_ratings_given ?? 0,
      bilateralBlind: meta.bilateral_blind ?? true,
      ratingId: d.rating_id ?? randomUUID(),
      timestamp: d.timestamp ?? "",
      version: d.version ?? 1,
      recordHash: d.record_hash ?? "",
    });
  }

  verifyHash(): boolean {
    return this.recordHash === this.computeHash();
  }
}

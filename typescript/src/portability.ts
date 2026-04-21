import { createHash } from "node:crypto";
import type { CompositeSignal } from "./composition";
import type { DimensionSummaryData } from "./types";

export class DimensionSummary {
  readonly mean: number;
  readonly stddev: number;
  readonly confidence: number;
  readonly count: number;

  constructor(mean: number, stddev: number, confidence: number, count: number) {
    this.mean = mean;
    this.stddev = stddev;
    this.confidence = confidence;
    this.count = count;
  }

  toDict(): DimensionSummaryData {
    return {
      mean: Math.round(this.mean * 10) / 10,
      stddev: Math.round(this.stddev * 10) / 10,
      confidence: Math.round(this.confidence * 10000) / 10000,
      count: this.count,
    };
  }

  static fromDict(d: DimensionSummaryData): DimensionSummary {
    return new DimensionSummary(d.mean, d.stddev, d.confidence, d.count);
  }
}

export class ProvenanceSummary {
  readonly cocChainAge: number;
  readonly cocChainLength: number;
  readonly lastAnchorTimestamp: string;
  readonly anchorType: string;

  constructor(opts?: {
    cocChainAge?: number;
    cocChainLength?: number;
    lastAnchorTimestamp?: string;
    anchorType?: string;
  }) {
    this.cocChainAge = opts?.cocChainAge ?? 0;
    this.cocChainLength = opts?.cocChainLength ?? 0;
    this.lastAnchorTimestamp = opts?.lastAnchorTimestamp ?? "";
    this.anchorType = opts?.anchorType ?? "dual_ots_tsa";
  }

  toDict(): Record<string, unknown> {
    return {
      cocChainAge: this.cocChainAge,
      cocChainLength: this.cocChainLength,
      lastAnchorTimestamp: this.lastAnchorTimestamp,
      anchorType: this.anchorType,
    };
  }

  static fromDict(d: Record<string, unknown>): ProvenanceSummary {
    return new ProvenanceSummary({
      cocChainAge: (d.cocChainAge as number) ?? 0,
      cocChainLength: (d.cocChainLength as number) ?? 0,
      lastAnchorTimestamp: (d.lastAnchorTimestamp as string) ?? "",
      anchorType: (d.anchorType as string) ?? "dual_ots_tsa",
    });
  }
}

export class BehavioralSummary {
  readonly totalInteractions: number;
  readonly ratingParticipationRate: number;
  readonly disputeRate: number;
  readonly averageResponseTimeMs: number;

  constructor(opts?: {
    totalInteractions?: number;
    ratingParticipationRate?: number;
    disputeRate?: number;
    averageResponseTimeMs?: number;
  }) {
    this.totalInteractions = opts?.totalInteractions ?? 0;
    this.ratingParticipationRate = opts?.ratingParticipationRate ?? 0;
    this.disputeRate = opts?.disputeRate ?? 0;
    this.averageResponseTimeMs = opts?.averageResponseTimeMs ?? 0;
  }

  toDict(): Record<string, unknown> {
    return {
      totalInteractions: this.totalInteractions,
      ratingParticipationRate:
        Math.round(this.ratingParticipationRate * 10000) / 10000,
      disputeRate: Math.round(this.disputeRate * 10000) / 10000,
      averageResponseTimeMs: this.averageResponseTimeMs,
    };
  }

  static fromDict(d: Record<string, unknown>): BehavioralSummary {
    return new BehavioralSummary({
      totalInteractions: (d.totalInteractions as number) ?? 0,
      ratingParticipationRate: (d.ratingParticipationRate as number) ?? 0,
      disputeRate: (d.disputeRate as number) ?? 0,
      averageResponseTimeMs: (d.averageResponseTimeMs as number) ?? 0,
    });
  }
}

export class OracleAttestation {
  readonly oracleId: string;
  readonly compositeValue: number;
  readonly signature: string;

  constructor(oracleId: string, compositeValue: number, signature: string = "") {
    this.oracleId = oracleId;
    this.compositeValue = compositeValue;
    this.signature = signature;
  }

  toDict(): Record<string, unknown> {
    return {
      oracle: this.oracleId,
      compositeValue: Math.round(this.compositeValue * 10) / 10,
      signature: this.signature,
    };
  }

  static fromDict(d: Record<string, unknown>): OracleAttestation {
    return new OracleAttestation(
      d.oracle as string,
      d.compositeValue as number,
      (d.signature as string) ?? ""
    );
  }
}

export interface PortableReputationBundleOptions {
  issuerId: string;
  issuerName?: string;
  issuerReliability?: number;
  issuerConfidence?: number;
  subjectId?: string;
  compositeScores?: Record<string, unknown>[];
  dimensions?: Record<string, DimensionSummary>;
  provenance?: ProvenanceSummary;
  behavioral?: BehavioralSummary;
  ratingsRootHash?: string;
  cocChainHeadHash?: string;
  verificationEndpoint?: string;
  multiOracle?: Record<string, unknown>;
  validFrom?: string;
  validUntil?: string;
  proofType?: string;
  proofCryptosuite?: string;
  proofValue?: string;
}

export class PortableReputationBundle {
  readonly issuerId: string;
  readonly issuerName: string;
  readonly issuerReliability: number;
  readonly issuerConfidence: number;
  readonly subjectId: string;
  readonly compositeScores: Record<string, unknown>[];
  readonly dimensions: Record<string, DimensionSummary>;
  readonly provenance: ProvenanceSummary | undefined;
  readonly behavioral: BehavioralSummary | undefined;
  readonly ratingsRootHash: string;
  readonly cocChainHeadHash: string;
  readonly verificationEndpoint: string;
  readonly multiOracle: Record<string, unknown> | undefined;
  readonly validFrom: string;
  readonly validUntil: string;
  readonly proofType: string;
  readonly proofCryptosuite: string;
  readonly proofValue: string;

  constructor(opts: PortableReputationBundleOptions) {
    this.issuerId = opts.issuerId;
    this.issuerName = opts.issuerName ?? "";
    this.issuerReliability = opts.issuerReliability ?? 0;
    this.issuerConfidence = opts.issuerConfidence ?? 0;
    this.subjectId = opts.subjectId ?? "";
    this.compositeScores = opts.compositeScores ?? [];
    this.dimensions = opts.dimensions ?? {};
    this.provenance = opts.provenance;
    this.behavioral = opts.behavioral;
    this.ratingsRootHash = opts.ratingsRootHash ?? "";
    this.cocChainHeadHash = opts.cocChainHeadHash ?? "";
    this.verificationEndpoint = opts.verificationEndpoint ?? "";
    this.multiOracle = opts.multiOracle;
    this.validFrom = opts.validFrom ?? new Date().toISOString();
    this.proofType = opts.proofType ?? "DataIntegrityProof";
    this.proofCryptosuite = opts.proofCryptosuite ?? "eddsa-jcs-2022";
    this.proofValue = opts.proofValue ?? "";

    if (opts.validUntil) {
      this.validUntil = opts.validUntil;
    } else {
      const d = new Date();
      d.setDate(d.getDate() + 30);
      this.validUntil = d.toISOString();
    }
  }

  isValid(): boolean {
    try {
      const until = new Date(this.validUntil.replace("Z", "+00:00"));
      return new Date() <= until;
    } catch {
      return false;
    }
  }

  toVc(): Record<string, unknown> {
    const issuer: Record<string, unknown> = { id: this.issuerId };
    if (this.issuerName) issuer.name = this.issuerName;
    if (this.issuerReliability > 0) {
      issuer.arp_reputation = {
        reliability: Math.round(this.issuerReliability * 10) / 10,
        confidence: Math.round(this.issuerConfidence * 10000) / 10000,
      };
    }

    const reputationSummary: Record<string, unknown> = {
      compositeScores: this.compositeScores,
      dimensions: Object.fromEntries(
        Object.entries(this.dimensions).map(([k, v]) => [k, v.toDict()])
      ),
    };
    if (this.provenance) {
      reputationSummary.provenance = this.provenance.toDict();
    }
    if (this.behavioral) {
      reputationSummary.behavioral = this.behavioral.toDict();
    }

    const credentialSubject: Record<string, unknown> = {
      id: this.subjectId,
      reputationSummary,
      evidenceChain: {
        ratingsRootHash: this.ratingsRootHash,
        cocChainHeadHash: this.cocChainHeadHash,
        verificationEndpoint: this.verificationEndpoint,
      },
    };

    if (this.multiOracle) {
      credentialSubject.multiOracleAttestation = this.multiOracle;
    }

    return {
      "@context": [
        "https://www.w3.org/ns/credentials/v2",
        "https://absupport.ai/credentials/agent-reputation-bundle/v2",
      ],
      type: ["VerifiableCredential", "AgentReputationBundle"],
      issuer,
      validFrom: this.validFrom,
      validUntil: this.validUntil,
      credentialSubject,
      proof: {
        type: this.proofType,
        cryptosuite: this.proofCryptosuite,
        verificationMethod: `${this.issuerId}#key-1`,
        proofPurpose: "assertionMethod",
        proofValue: this.proofValue,
      },
    };
  }

  toJson(): string {
    return JSON.stringify(this.toVc());
  }

  static fromVc(vc: Record<string, unknown>): PortableReputationBundle {
    const issuer = (vc.issuer ?? {}) as Record<string, unknown>;
    const subject = (vc.credentialSubject ?? {}) as Record<string, unknown>;
    const summary = (subject.reputationSummary ?? {}) as Record<
      string,
      unknown
    >;
    const evidence = (subject.evidenceChain ?? {}) as Record<string, unknown>;
    const proof = (vc.proof ?? {}) as Record<string, unknown>;

    const dims: Record<string, DimensionSummary> = {};
    const rawDims = (summary.dimensions ?? {}) as Record<
      string,
      DimensionSummaryData
    >;
    for (const [name, data] of Object.entries(rawDims)) {
      dims[name] = DimensionSummary.fromDict(data);
    }

    const arpRep = (issuer.arp_reputation ?? {}) as Record<string, number>;
    const rawProv = summary.provenance as Record<string, unknown> | undefined;
    const rawBehav = summary.behavioral as Record<string, unknown> | undefined;

    return new PortableReputationBundle({
      issuerId: (issuer.id as string) ?? "",
      issuerName: (issuer.name as string) ?? "",
      issuerReliability: arpRep.reliability ?? 0,
      issuerConfidence: arpRep.confidence ?? 0,
      subjectId: (subject.id as string) ?? "",
      compositeScores: (summary.compositeScores as Record<string, unknown>[]) ?? [],
      dimensions: dims,
      provenance: rawProv ? ProvenanceSummary.fromDict(rawProv) : undefined,
      behavioral: rawBehav ? BehavioralSummary.fromDict(rawBehav) : undefined,
      ratingsRootHash: (evidence.ratingsRootHash as string) ?? "",
      cocChainHeadHash: (evidence.cocChainHeadHash as string) ?? "",
      verificationEndpoint: (evidence.verificationEndpoint as string) ?? "",
      multiOracle: subject.multiOracleAttestation as
        | Record<string, unknown>
        | undefined,
      validFrom: (vc.validFrom as string) ?? "",
      validUntil: (vc.validUntil as string) ?? "",
      proofType: (proof.type as string) ?? "DataIntegrityProof",
      proofCryptosuite: (proof.cryptosuite as string) ?? "eddsa-jcs-2022",
      proofValue: (proof.proofValue as string) ?? "",
    });
  }
}

export function computeRatingsRootHash(ratingHashes: string[]): string {
  if (ratingHashes.length === 0) {
    return createHash("sha256").update("empty").digest("hex");
  }

  let layer: Buffer<ArrayBuffer>[] = ratingHashes.map(
    (h) => Buffer.from(h, "hex") as Buffer<ArrayBuffer>
  );

  while (layer.length > 1) {
    const next: Buffer<ArrayBuffer>[] = [];
    for (let i = 0; i < layer.length; i += 2) {
      const left = layer[i];
      const right = i + 1 < layer.length ? layer[i + 1] : layer[i];
      next.push(
        createHash("sha256")
          .update(Buffer.concat([left, right]))
          .digest() as Buffer<ArrayBuffer>
      );
    }
    layer = next;
  }

  return layer[0].toString("hex");
}

export function generatePrb(opts: {
  issuerId: string;
  subjectId: string;
  composite: CompositeSignal;
  dimensions: Record<string, DimensionSummary>;
  ratingHashes: string[];
  provenance?: ProvenanceSummary;
  behavioral?: BehavioralSummary;
  issuerName?: string;
  issuerReliability?: number;
  issuerConfidence?: number;
  cocChainHeadHash?: string;
  verificationEndpoint?: string;
  validityDays?: number;
}): PortableReputationBundle {
  const rootHash = computeRatingsRootHash(opts.ratingHashes);
  const compositeEntry: Record<string, unknown> = {
    ...opts.composite.toDict(),
    ratingCount: opts.composite.inputCount,
    windowDays: 365,
  };

  const now = new Date();
  const validUntil = new Date(now);
  validUntil.setDate(validUntil.getDate() + (opts.validityDays ?? 30));

  return new PortableReputationBundle({
    issuerId: opts.issuerId,
    issuerName: opts.issuerName,
    issuerReliability: opts.issuerReliability,
    issuerConfidence: opts.issuerConfidence,
    subjectId: opts.subjectId,
    compositeScores: [compositeEntry],
    dimensions: opts.dimensions,
    provenance: opts.provenance,
    behavioral: opts.behavioral,
    ratingsRootHash: rootHash,
    cocChainHeadHash: opts.cocChainHeadHash,
    verificationEndpoint: opts.verificationEndpoint,
    validFrom: now.toISOString(),
    validUntil: validUntil.toISOString(),
  });
}

export function multiOracleAttestation(
  attestations: OracleAttestation[],
  threshold: number = 3,
  maxDivergence: number = 10.0
): Record<string, unknown> {
  if (attestations.length < threshold) {
    throw new Error(
      `Need at least ${threshold} attestations, got ${attestations.length}`
    );
  }

  const values = attestations.map((a) => a.compositeValue);
  const sorted = [...values].sort((a, b) => a - b);
  const consensus = sorted[Math.floor(sorted.length / 2)];
  const divergence = Math.max(...values) - Math.min(...values);

  const status = divergence > maxDivergence ? "disputed" : "consensus";

  return {
    threshold,
    attestations: attestations.map((a) => a.toDict()),
    consensusValue: Math.round(consensus * 10) / 10,
    consensusMethod: "median",
    maxDivergence: Math.round(divergence * 10) / 10,
    status,
  };
}

export function trustDiscount(
  importedScore: number,
  oracleTrust: number = 1.0,
  domainOverlap: number = 1.0,
  ratingVolumeFactor: number = 1.0,
  isSingleOracle: boolean = false,
  isBootstrapPeriod: boolean = false
): number {
  let discount = oracleTrust * domainOverlap * ratingVolumeFactor;

  if (isSingleOracle) {
    discount *= isBootstrapPeriod ? 0.7 : 0.5;
  }

  return importedScore * Math.min(1.0, Math.max(0.0, discount));
}

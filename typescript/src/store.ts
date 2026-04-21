import {
  appendFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
} from "node:fs";
import { dirname } from "node:path";
import { RatingRecord } from "./rating";
import type { RatingRecordData } from "./types";

export class RatingStore {
  readonly path: string;

  constructor(path: string = "ratings.jsonl") {
    this.path = path;
    const dir = dirname(path);
    if (dir && dir !== ".") {
      mkdirSync(dir, { recursive: true });
    }
  }

  appendRating(record: RatingRecord): string {
    if (!record.verifyHash()) {
      throw new Error(
        "Record hash verification failed — record may be tampered"
      );
    }
    const line = JSON.stringify(record.toDict()) + "\n";
    appendFileSync(this.path, line, "utf-8");
    return record.ratingId;
  }

  getAll(): RatingRecord[] {
    if (!existsSync(this.path)) return [];

    const content = readFileSync(this.path, "utf-8");
    const records: RatingRecord[] = [];
    for (const line of content.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const d: RatingRecordData = JSON.parse(trimmed);
        records.push(RatingRecord.fromDict(d));
      } catch {
        continue;
      }
    }
    return records;
  }

  getRatingsFor(agentId: string): RatingRecord[] {
    return this.getAll().filter((r) => r.rateeId === agentId);
  }

  getRatingsBy(agentId: string): RatingRecord[] {
    return this.getAll().filter((r) => r.raterId === agentId);
  }

  getRating(ratingId: string): RatingRecord | null {
    for (const r of this.getAll()) {
      if (r.ratingId === ratingId) return r;
    }
    return null;
  }

  count(): number {
    if (!existsSync(this.path)) return 0;
    const content = readFileSync(this.path, "utf-8");
    let count = 0;
    for (const line of content.split("\n")) {
      if (line.trim()) count++;
    }
    return count;
  }

  agents(): Record<string, { ratings_given: number; ratings_received: number }> {
    const summary: Record<
      string,
      { ratings_given: number; ratings_received: number }
    > = {};
    for (const r of this.getAll()) {
      if (!summary[r.raterId]) {
        summary[r.raterId] = { ratings_given: 0, ratings_received: 0 };
      }
      if (!summary[r.rateeId]) {
        summary[r.rateeId] = { ratings_given: 0, ratings_received: 0 };
      }
      summary[r.raterId].ratings_given++;
      summary[r.rateeId].ratings_received++;
    }
    return summary;
  }

  stats(): Record<string, unknown> {
    const allRecords = this.getAll();
    const raters = new Set<string>();
    const ratees = new Set<string>();
    for (const r of allRecords) {
      raters.add(r.raterId);
      ratees.add(r.rateeId);
    }
    let fileSize = 0;
    if (existsSync(this.path)) {
      fileSize = statSync(this.path).size;
    }
    return {
      total_ratings: allRecords.length,
      unique_raters: raters.size,
      unique_ratees: ratees.size,
      file_path: this.path,
      file_size_bytes: fileSize,
    };
  }
}

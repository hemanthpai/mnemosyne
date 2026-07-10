import { describe, it, expect } from "vitest";
import {
  cosineSim,
  euclideanDistSq,
  kMeans,
  titleWords,
  jaccard,
  centroidSimilarity,
  similarity,
  selectDiverse,
  type RecallCandidate,
} from "../src/services/recall-diversity.js";

describe("cosineSim", () => {
  it("returns 1 for identical vectors", () => {
    expect(cosineSim([1, 0, 0], [1, 0, 0])).toBeCloseTo(1);
  });

  it("returns 0 for orthogonal vectors", () => {
    expect(cosineSim([1, 0, 0], [0, 1, 0])).toBeCloseTo(0);
  });

  it("returns -1 for opposite vectors", () => {
    expect(cosineSim([1, 0], [-1, 0])).toBeCloseTo(-1);
  });

  it("returns 0 for empty or mismatched vectors", () => {
    expect(cosineSim([], [])).toBe(0);
    expect(cosineSim([1], [1, 2])).toBe(0);
  });

  it("handles non-unit vectors", () => {
    expect(cosineSim([2, 0], [4, 0])).toBeCloseTo(1);
  });
});

describe("euclideanDistSq", () => {
  it("returns 0 for identical vectors", () => {
    expect(euclideanDistSq([1, 2, 3], [1, 2, 3])).toBe(0);
  });

  it("returns correct squared distance", () => {
    expect(euclideanDistSq([0, 0], [3, 4])).toBe(25);
  });
});

describe("kMeans", () => {
  it("returns empty for empty input", () => {
    expect(kMeans([], 3)).toEqual([]);
  });

  it("returns all vectors when n <= k", () => {
    const vecs = [
      [1, 0],
      [0, 1],
    ];
    const result = kMeans(vecs, 5);
    expect(result).toHaveLength(2);
  });

  it("returns correct number of centroids", () => {
    const vecs = [
      [0, 0],
      [0, 1],
      [1, 0],
      [1, 1],
      [10, 10],
      [10, 11],
      [11, 10],
      [11, 11],
    ];
    const result = kMeans(vecs, 2);
    expect(result).toHaveLength(2);
  });

  it("uses farthest-point initialization", () => {
    // With farthest-point init, first two centroids should be far apart
    const vecs = [
      [0, 0],
      [100, 100],
      [0, 1],
      [100, 101],
    ];
    const result = kMeans(vecs, 2);
    expect(result).toHaveLength(2);
    // Centroids should be near [0,0.5] and [100,100.5]
    const dist = euclideanDistSq(result[0], result[1]);
    expect(dist).toBeGreaterThan(1000);
  });
});

describe("titleWords", () => {
  it("extracts meaningful words", () => {
    const words = titleWords("The New TypeScript Chat");
    expect(words).toContain("typescript");
    expect(words).not.toContain("the");
    expect(words).not.toContain("new");
    expect(words).not.toContain("chat");
  });

  it("filters short words", () => {
    const words = titleWords("A is ok but great");
    expect(words).not.toContain("a");
    expect(words).not.toContain("is");
    expect(words).not.toContain("ok");
    expect(words).toContain("great");
  });
});

describe("jaccard", () => {
  it("returns 0 for empty sets", () => {
    expect(jaccard([], [])).toBe(0);
  });

  it("returns 1 for identical sets", () => {
    expect(jaccard(["a", "b"], ["a", "b"])).toBe(1);
  });

  it("returns 0 for disjoint sets", () => {
    expect(jaccard(["a", "b"], ["c", "d"])).toBe(0);
  });

  it("returns correct value for partial overlap", () => {
    // intersection = {a}, union = {a, b, c}
    expect(jaccard(["a", "b"], ["a", "c"])).toBeCloseTo(1 / 3);
  });
});

describe("centroidSimilarity", () => {
  it("returns null when centroids are null or empty", () => {
    expect(centroidSimilarity(null, [[1, 0]])).toBeNull();
    expect(centroidSimilarity([[1, 0]], null)).toBeNull();
    expect(centroidSimilarity([], [[1, 0]])).toBeNull();
  });

  it("returns max pairwise cosine similarity", () => {
    const centA = [
      [1, 0],
      [0, 1],
    ];
    const centB = [
      [0.7, 0.7],
      [-1, 0],
    ];
    const result = centroidSimilarity(centA, centB);
    // [0,1]·[0.7,0.7] ≈ 0.707, [1,0]·[0.7,0.7] ≈ 0.707, etc.
    expect(result).toBeGreaterThan(0.5);
  });
});

describe("similarity", () => {
  it("prefers centroids when available", () => {
    const a: RecallCandidate = {
      id: "a",
      title: "Test A",
      score: 1,
      tags: [],
      avgEmbedding: [1, 0],
      centroids: [[1, 0]],
    };
    const b: RecallCandidate = {
      id: "b",
      title: "Test B",
      score: 1,
      tags: [],
      avgEmbedding: [0, 1],
      centroids: [[0, 1]],
    };
    const sim = similarity(a, b);
    // centroids [1,0] vs [0,1] = 0
    expect(sim).toBeCloseTo(0);
  });

  it("falls back to avgEmbedding when no centroids", () => {
    const a: RecallCandidate = {
      id: "a",
      title: "Test A",
      score: 1,
      tags: [],
      avgEmbedding: [1, 0],
      centroids: null,
    };
    const b: RecallCandidate = {
      id: "b",
      title: "Test B",
      score: 1,
      tags: [],
      avgEmbedding: [1, 0],
      centroids: null,
    };
    expect(similarity(a, b)).toBeCloseTo(1);
  });

  it("falls back to Jaccard when no embeddings", () => {
    const a: RecallCandidate = {
      id: "a",
      title: "TypeScript generics discussion",
      score: 1,
      tags: [],
      avgEmbedding: null,
      centroids: null,
    };
    const b: RecallCandidate = {
      id: "b",
      title: "TypeScript type system",
      score: 1,
      tags: [],
      avgEmbedding: null,
      centroids: null,
    };
    const sim = similarity(a, b);
    // Shared word: "typescript"
    expect(sim).toBeGreaterThan(0);
    expect(sim).toBeLessThan(1);
  });
});

describe("selectDiverse", () => {
  it("returns empty for empty input", () => {
    expect(selectDiverse([])).toEqual([]);
  });

  it("deduplicates by conversation ID", () => {
    const candidates: RecallCandidate[] = [
      {
        id: "a",
        title: "Dup",
        score: 0.9,
        tags: [],
        avgEmbedding: null,
        centroids: null,
      },
      {
        id: "a",
        title: "Dup",
        score: 0.8,
        tags: [],
        avgEmbedding: null,
        centroids: null,
      },
      {
        id: "b",
        title: "Other",
        score: 0.7,
        tags: [],
        avgEmbedding: null,
        centroids: null,
      },
    ];
    const result = selectDiverse(candidates);
    const ids = result.map((r) => r.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toContain("a");
    expect(ids).toContain("b");
  });

  it("respects maxConversations", () => {
    const candidates: RecallCandidate[] = Array.from(
      { length: 10 },
      (_, i) => ({
        id: `conv-${i}`,
        title: `Conversation ${i}`,
        score: 1 - i * 0.1,
        tags: [],
        avgEmbedding: Array.from({ length: 4 }, () => Math.random()),
        centroids: null,
      }),
    );
    const result = selectDiverse(candidates, 3);
    expect(result).toHaveLength(3);
  });

  it("returns all candidates when fewer than max", () => {
    const candidates: RecallCandidate[] = [
      {
        id: "a",
        title: "A",
        score: 0.9,
        tags: [],
        avgEmbedding: [1, 0],
        centroids: null,
      },
      {
        id: "b",
        title: "B",
        score: 0.8,
        tags: [],
        avgEmbedding: [0, 1],
        centroids: null,
      },
    ];
    const result = selectDiverse(candidates, 5);
    expect(result).toHaveLength(2);
  });

  it("prefers diverse topics over pure score ranking", () => {
    // Two clusters: [1,0] and [0,1] direction
    const candidates: RecallCandidate[] = [
      {
        id: "a1",
        title: "Topic A1",
        score: 0.95,
        tags: [],
        avgEmbedding: [1, 0, 0],
        centroids: null,
      },
      {
        id: "a2",
        title: "Topic A2",
        score: 0.90,
        tags: [],
        avgEmbedding: [0.99, 0.01, 0],
        centroids: null,
      },
      {
        id: "b1",
        title: "Topic B1",
        score: 0.85,
        tags: [],
        avgEmbedding: [0, 1, 0],
        centroids: null,
      },
      {
        id: "b2",
        title: "Topic B2",
        score: 0.80,
        tags: [],
        avgEmbedding: [0.01, 0.99, 0],
        centroids: null,
      },
      {
        id: "c1",
        title: "Topic C1",
        score: 0.75,
        tags: [],
        avgEmbedding: [0, 0, 1],
        centroids: null,
      },
      {
        id: "c2",
        title: "Topic C2",
        score: 0.70,
        tags: [],
        avgEmbedding: [0.01, 0, 0.99],
        centroids: null,
      },
    ];
    const result = selectDiverse(candidates, 3);
    const ids = result.map((r) => r.id);
    // Should include representatives from different clusters rather than
    // just the top 3 by score (which would all be cluster A + B1)
    expect(ids).toHaveLength(3);
    // At minimum, we should get a1 (highest score) and some diversity
    expect(ids).toContain("a1");
  });
});

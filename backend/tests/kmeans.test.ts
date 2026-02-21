import { describe, it, expect } from "vitest";
import { kMeans, cosineSimilarity } from "../src/utils/kmeans.js";

describe("cosineSimilarity", () => {
  it("returns 1 for identical vectors", () => {
    const v = [1, 2, 3];
    expect(cosineSimilarity(v, v)).toBeCloseTo(1);
  });

  it("returns 0 for orthogonal vectors", () => {
    expect(cosineSimilarity([1, 0], [0, 1])).toBeCloseTo(0);
  });

  it("returns -1 for opposite vectors", () => {
    expect(cosineSimilarity([1, 0], [-1, 0])).toBeCloseTo(-1);
  });

  it("returns 0 for empty vectors", () => {
    expect(cosineSimilarity([], [])).toBe(0);
  });

  it("returns 0 for zero vectors", () => {
    expect(cosineSimilarity([0, 0], [0, 0])).toBe(0);
  });

  it("returns 0 for mismatched lengths", () => {
    expect(cosineSimilarity([1, 2], [1, 2, 3])).toBe(0);
  });
});

describe("kMeans", () => {
  it("returns empty array for empty input", () => {
    expect(kMeans([], 3)).toEqual([]);
  });

  it("returns input vectors when n <= k", () => {
    const vectors = [[1, 2], [3, 4]];
    const result = kMeans(vectors, 5);
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual([1, 2]);
    expect(result[1]).toEqual([3, 4]);
  });

  it("returns copies, not references, when n <= k", () => {
    const vectors = [[1, 2]];
    const result = kMeans(vectors, 3);
    result[0][0] = 999;
    expect(vectors[0][0]).toBe(1);
  });

  it("returns single centroid when k=1", () => {
    const vectors = [[0, 0], [2, 2], [4, 4]];
    const result = kMeans(vectors, 1);
    expect(result).toHaveLength(1);
    // Centroid should be approximately the mean
    expect(result[0][0]).toBeCloseTo(2);
    expect(result[0][1]).toBeCloseTo(2);
  });

  it("clusters two clear groups", () => {
    // Two well-separated clusters
    const cluster1 = [[0, 0], [1, 0], [0, 1], [1, 1]];
    const cluster2 = [[10, 10], [11, 10], [10, 11], [11, 11]];
    const vectors = [...cluster1, ...cluster2];

    const result = kMeans(vectors, 2);
    expect(result).toHaveLength(2);

    // Sort centroids by first dimension for deterministic comparison
    result.sort((a, b) => a[0] - b[0]);
    expect(result[0][0]).toBeCloseTo(0.5, 0);
    expect(result[0][1]).toBeCloseTo(0.5, 0);
    expect(result[1][0]).toBeCloseTo(10.5, 0);
    expect(result[1][1]).toBeCloseTo(10.5, 0);
  });

  it("handles identical vectors", () => {
    const vectors = [[1, 1], [1, 1], [1, 1]];
    const result = kMeans(vectors, 2);
    expect(result).toHaveLength(2);
    // All vectors are the same, centroids should converge
    for (const centroid of result) {
      expect(centroid[0]).toBeCloseTo(1);
      expect(centroid[1]).toBeCloseTo(1);
    }
  });

  it("is deterministic across calls", () => {
    const vectors = [[0, 0], [1, 1], [10, 10], [11, 11], [5, 5]];
    const r1 = kMeans(vectors, 3);
    const r2 = kMeans(vectors, 3);
    expect(r1).toEqual(r2);
  });

  it("works with high-dimensional vectors", () => {
    const dim = 100;
    const v1 = new Array(dim).fill(0);
    const v2 = new Array(dim).fill(1);
    const v3 = new Array(dim).fill(2);
    const result = kMeans([v1, v2, v3], 2);
    expect(result).toHaveLength(2);
  });
});

/**
 * Cosine similarity between two vectors.
 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length || a.length === 0) return 0;
  let dot = 0;
  let magA = 0;
  let magB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    magA += a[i] * a[i];
    magB += b[i] * b[i];
  }
  const denom = Math.sqrt(magA) * Math.sqrt(magB);
  return denom === 0 ? 0 : dot / denom;
}

function euclideanDistSq(a: number[], b: number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    const d = a[i] - b[i];
    sum += d * d;
  }
  return sum;
}

/**
 * k-means clustering with deterministic max-min initialization.
 * Returns k centroid vectors. If n <= k, returns the input vectors directly.
 */
export function kMeans(
  vectors: number[][],
  k: number,
  maxIterations = 50,
): number[][] {
  const n = vectors.length;
  if (n === 0) return [];
  if (n <= k) return vectors.map((v) => [...v]);

  const dim = vectors[0].length;

  // Deterministic max-min initialization: first centroid is vectors[0],
  // each subsequent centroid is the point farthest from its nearest centroid.
  const centroids: number[][] = [[...vectors[0]]];
  const minDist = new Array<number>(n).fill(Infinity);

  for (let c = 1; c < k; c++) {
    const lastCentroid = centroids[c - 1];
    let farthestIdx = 0;
    let farthestDist = 0;

    for (let i = 0; i < n; i++) {
      const d = euclideanDistSq(vectors[i], lastCentroid);
      if (d < minDist[i]) minDist[i] = d;
      if (minDist[i] > farthestDist) {
        farthestDist = minDist[i];
        farthestIdx = i;
      }
    }

    centroids.push([...vectors[farthestIdx]]);
  }

  // Lloyd's iterations
  const assignments = new Array<number>(n).fill(-1);

  for (let iter = 0; iter < maxIterations; iter++) {
    // Assignment step
    let changed = false;
    for (let i = 0; i < n; i++) {
      let bestCluster = 0;
      let bestDist = Infinity;
      for (let c = 0; c < k; c++) {
        const d = euclideanDistSq(vectors[i], centroids[c]);
        if (d < bestDist) {
          bestDist = d;
          bestCluster = c;
        }
      }
      if (assignments[i] !== bestCluster) {
        assignments[i] = bestCluster;
        changed = true;
      }
    }

    if (!changed) break;

    // Update step: recompute centroids
    const sums: number[][] = Array.from({ length: k }, () =>
      new Array<number>(dim).fill(0),
    );
    const counts = new Array<number>(k).fill(0);

    for (let i = 0; i < n; i++) {
      const c = assignments[i];
      counts[c]++;
      for (let d = 0; d < dim; d++) {
        sums[c][d] += vectors[i][d];
      }
    }

    for (let c = 0; c < k; c++) {
      if (counts[c] === 0) continue;
      for (let d = 0; d < dim; d++) {
        centroids[c][d] = sums[c][d] / counts[c];
      }
    }
  }

  return centroids;
}

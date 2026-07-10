/**
 * Pure functions for topic-diverse recall selection.
 * Ported from n8n "Deduplicate Results" node.
 */

export const MAX_CONVERSATIONS = 5;
export const LAMBDA = 0.5;

const STOP_WORDS = new Set([
  "the", "and", "for", "with", "that", "this", "from", "new", "chat",
]);

export interface RecallCandidate {
  id: string;
  title: string;
  score: number;
  tags: string[];
  avgEmbedding: number[] | null;
  centroids: number[][] | null;
}

export function cosineSim(a: number[], b: number[]): number {
  if (!a || !b || a.length !== b.length) return 0;
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

export function euclideanDistSq(a: number[], b: number[]): number {
  let sum = 0;
  for (let i = 0; i < a.length; i++) {
    const d = a[i] - b[i];
    sum += d * d;
  }
  return sum;
}

export function kMeans(
  vectors: number[][],
  k: number,
  maxIter = 50,
): number[][] {
  const n = vectors.length;
  if (n === 0) return [];
  if (n <= k) return vectors.map((v) => v.slice());

  const dim = vectors[0].length;

  // Farthest-point initialization
  const centroids: number[][] = [vectors[0].slice()];
  const minDist = new Array(n).fill(Infinity);
  for (let c = 1; c < k; c++) {
    const last = centroids[c - 1];
    let fIdx = 0;
    let fDist = 0;
    for (let i = 0; i < n; i++) {
      const d = euclideanDistSq(vectors[i], last);
      if (d < minDist[i]) minDist[i] = d;
      if (minDist[i] > fDist) {
        fDist = minDist[i];
        fIdx = i;
      }
    }
    centroids.push(vectors[fIdx].slice());
  }

  // Lloyd's algorithm
  const asgn = new Array(n).fill(0);
  for (let iter = 0; iter < maxIter; iter++) {
    let changed = false;
    for (let i = 0; i < n; i++) {
      let best = 0;
      let bestD = Infinity;
      for (let c = 0; c < k; c++) {
        const d = euclideanDistSq(vectors[i], centroids[c]);
        if (d < bestD) {
          bestD = d;
          best = c;
        }
      }
      if (asgn[i] !== best) {
        asgn[i] = best;
        changed = true;
      }
    }
    if (!changed) break;

    const sums = Array.from({ length: k }, () => new Array(dim).fill(0));
    const counts = new Array(k).fill(0);
    for (let i = 0; i < n; i++) {
      counts[asgn[i]]++;
      for (let d = 0; d < dim; d++) {
        sums[asgn[i]][d] += vectors[i][d];
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

export function titleWords(title: string): string[] {
  return title
    .toLowerCase()
    .replace(/[^\w\s]/g, "")
    .split(/\s+/)
    .filter((w) => w.length > 2 && !STOP_WORDS.has(w));
}

export function jaccard(a: string[], b: string[]): number {
  if (a.length === 0 && b.length === 0) return 0;
  const setA = new Set(a);
  const setB = new Set(b);
  let inter = 0;
  for (const w of setA) {
    if (setB.has(w)) inter++;
  }
  const union = setA.size + setB.size - inter;
  return union === 0 ? 0 : inter / union;
}

export function centroidSimilarity(
  centA: number[][] | null,
  centB: number[][] | null,
): number | null {
  if (!centA || !centB || centA.length === 0 || centB.length === 0) return null;
  let maxSim = -Infinity;
  for (const a of centA) {
    for (const b of centB) {
      const s = cosineSim(a, b);
      if (s > maxSim) maxSim = s;
    }
  }
  return maxSim;
}

/** Pairwise similarity: prefer centroids, fallback to avgEmbedding, then Jaccard */
export function similarity(ci: RecallCandidate, cj: RecallCandidate): number {
  const cs = centroidSimilarity(ci.centroids, cj.centroids);
  if (cs !== null) return cs;
  if (ci.avgEmbedding && cj.avgEmbedding)
    return cosineSim(ci.avgEmbedding, cj.avgEmbedding);
  return jaccard(titleWords(ci.title), titleWords(cj.title));
}

/**
 * Select diverse conversations using k-means topic clustering + greedy MMR.
 * Ported from the n8n "Deduplicate Results" node.
 */
export function selectDiverse(
  candidates: RecallCandidate[],
  maxConversations = MAX_CONVERSATIONS,
  lambda = LAMBDA,
): RecallCandidate[] {
  if (candidates.length === 0) return [];

  // Dedup by conversation ID
  const seenIds = new Set<string>();
  const deduped: RecallCandidate[] = [];
  for (const c of candidates) {
    if (!seenIds.has(c.id)) {
      seenIds.add(c.id);
      deduped.push(c);
    }
  }

  if (deduped.length <= maxConversations) {
    return deduped;
  }

  // Topic clustering on avgEmbeddings
  const withEmb = deduped.filter((c) => c.avgEmbedding);
  const topicAssignment = new Map<string, number>();

  if (withEmb.length > 1) {
    const K = Math.min(withEmb.length, 2 * maxConversations);
    const vecs = withEmb.map((c) => c.avgEmbedding!);
    const centroids = kMeans(vecs, K);
    for (let i = 0; i < withEmb.length; i++) {
      let bestC = 0;
      let bestD = Infinity;
      for (let c = 0; c < centroids.length; c++) {
        const d = euclideanDistSq(vecs[i], centroids[c]);
        if (d < bestD) {
          bestD = d;
          bestC = c;
        }
      }
      topicAssignment.set(withEmb[i].id, bestC);
    }
  } else {
    deduped.forEach((c, i) => topicAssignment.set(c.id, i));
  }

  // Assign topic -1 to candidates without embeddings
  for (const c of deduped) {
    if (!topicAssignment.has(c.id)) topicAssignment.set(c.id, -1);
  }

  // Normalize scores to [0, 1]
  const maxScore = Math.max(...deduped.map((c) => c.score));
  const minScore = Math.min(...deduped.map((c) => c.score));
  const scoreRange = maxScore - minScore || 1;
  const normScores = new Map(
    deduped.map((c) => [c.id, (c.score - minScore) / scoreRange]),
  );

  // Greedy MMR selection preferring least-represented topics
  const selected: RecallCandidate[] = [];
  const remaining = new Set(deduped.map((c) => c.id));
  const topicCounts = new Map<number, number>();

  while (selected.length < maxConversations && remaining.size > 0) {
    // Find least-represented topic count among remaining
    let minTopicCount = Infinity;
    for (const id of remaining) {
      const t = topicAssignment.get(id)!;
      const count = topicCounts.get(t) || 0;
      if (count < minTopicCount) minTopicCount = count;
    }

    // Candidates from least-represented topics
    const topicPool: string[] = [];
    for (const id of remaining) {
      const t = topicAssignment.get(id)!;
      if ((topicCounts.get(t) || 0) === minTopicCount) topicPool.push(id);
    }

    // From topic pool, pick best MMR candidate
    let bestId: string | null = null;
    let bestMMR = -Infinity;
    for (const id of topicPool) {
      const cand = deduped.find((c) => c.id === id)!;
      const relevance = normScores.get(id)!;
      let maxSim = 0;
      for (const sel of selected) {
        const sim = similarity(cand, sel);
        if (sim > maxSim) maxSim = sim;
      }
      const mmr = lambda * relevance - (1 - lambda) * maxSim;
      if (mmr > bestMMR) {
        bestMMR = mmr;
        bestId = id;
      }
    }

    if (bestId !== null) {
      const cand = deduped.find((c) => c.id === bestId)!;
      selected.push(cand);
      remaining.delete(bestId);
      const t = topicAssignment.get(bestId)!;
      topicCounts.set(t, (topicCounts.get(t) || 0) + 1);
    } else {
      break;
    }
  }

  return selected;
}

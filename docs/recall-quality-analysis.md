# Recall Workflow Quality Analysis

## Test Query: "Help me prepare for my Carefeed interview"

### Baseline Results (pre-improvement)

The initial workflow returned 5 extractions, 4 of which contained nearly identical CareFeed company research:

| # | Conversation | Content Type |
|---|---|---|
| 1 | "CareFeed Interview Prep" (3e3ad114) | Company research |
| 2 | "Healthcare Digital Solutions" (da171dc6) | Company research |
| 3 | "CareFeed Interview Prep" (675d255b) | Company research |
| 4 | "Do some research on CareFeed..." (4c24bdf5) | Company research |
| 5 | "Front-End Engineering Role" (c8bf5630) | Resume/personal |

4 of 5 slots spent on essentially the same CareFeed company info repeated across different conversations. The extracted content was heavily overlapping — company overview, products, HIPAA, Cincinnati headquarters, etc.

### Key Conversations MISSED

| Conversation | Why it matters | Search score* |
|---|---|---|
| **"Engineering Transformation at Carefeed" / Job Mission+OKRs for VP Eng at CareFeed** (3c595564, 912ec581, 846b2464) | Contains the user's specific approach to CareFeed's problems, concrete OKRs, and a structured value proposition for the role. Arguably the single most valuable conversation. | 0.80 with "Carefeed VP engineering OKRs" but only 0.62 with "Carefeed interview" |
| **"Engineering Leadership Achievements"** (5ef1d358) | Full bio, quantified achievements, leadership track record — raw material for answering "tell me about yourself" | 0.65 with "leadership achievements" |
| **"Interview Prep: Coaching & Leadership"** (9ead21a4) | 32 messages of actual interview coaching — strategies, STAR examples, behavioral prep | 0.64 with "Carefeed interview" |
| **Resume/career narrative conversations** (b28625c8, 84f944a3, e4907933) | Actual resume content, career reflection, leadership philosophy | 0.65-0.67 with "leadership experience" |
| **"Bar Raiser Interview Prep"** (31c84fdc) | Behavioral interview techniques | 0.64 with "behavioral interview" |
| **"USAFacts Interview Prep"** (91ce5b27) | Transferable interview strategies for similar HoE role | 0.71 with "Carefeed interview" (was in earlier dedup results!) |

### Root Causes Identified

1. **Redundant results eating slots** — 4 conversations contain nearly identical CareFeed company info. Dedup is by conversation ID only, not content similarity. Three slots wasted on duplicative information.

2. **Query decomposition lacks diversity** — The LLM generates queries like "CareFeed interview preparation", "CareFeed Head of Engineering", "senior care technology company" — all targeting the same semantic space (company info). Misses that interview prep requires BOTH company knowledge AND the user's own resume/achievements, interview strategies, and specific CareFeed pitch (OKRs doc).

3. **No "second-hop" reasoning** — "Help me prepare for my interview" should trigger retrieval of personal context (resume, leadership philosophy), not just company research. The system doesn't infer that the user's own experience is critical to interview prep.

4. **Score-only ranking** — Top-5 by similarity score naturally clusters around the same semantic neighborhood. No diversity mechanism (like MMR) to ensure variety.

5. **Small search window** — `limit=5` per query with 2-3 similar queries means ~10-15 candidates before dedup. With more diverse queries and larger limits, the candidate pool would contain more varied content.

---

## Improvements Implemented

### Round 1: Three changes applied

1. **Smarter query decomposition prompt** — Updated to instruct the LLM to generate queries targeting different categories and to seek out "what has the user shared or asked about" the relevant topics.

2. **Larger search pool** — `limit=10` per query (up from 5), giving ~30 candidates before dedup.

3. **MMR-style diversity selection** — Instead of pure score ranking, uses greedy Maximal Marginal Relevance with Jaccard similarity on title keywords. `LAMBDA=0.5` balances relevance vs diversity.

### Round 1 Results (post-improvement)

| # | Conversation | Content Type |
|---|---|---|
| 1 | **Engineering Leadership Application** (4cbb75d9) | Full interview prep with specific achievements (Indeed no-show rates, Mural cost reduction, Amazon localization), leadership philosophy, tailored questions |
| 2 | **Grow Therapy career situation** | Career narrative, leadership feedback, team turnaround experience |
| 3 | **New Chat (system design prep)** (7cb030f9) | Detailed microfrontend architecture story, quantified impact (8 days -> 1 day DLT), interview scripting |
| 4 | **Healthcare Digital Solutions** (da171dc6) | CareFeed company overview, products, mission |
| 5 | **CareFeed Interview Prep** (3e3ad114) | Company-specific context, interview tips, questions to ask |

Major improvement: instead of 4 near-identical CareFeed research conversations, a balanced mix of company knowledge (2), personal achievements and career narrative (2), and technical interview prep (1).

---

## MMR Selection Analysis

### Simulated candidate pool (28 unique conversations across 3 queries)

**Query 1: "What has the user shared about CareFeed or their interview with CareFeed?"**

| Score | ID | Title |
|---|---|---|
| 0.7539 | 3e3ad114 | CareFeed Interview Prep |
| 0.7539 | da171dc6 | Healthcare Digital Solutions |
| 0.7539 | 675d255b | CareFeed Interview Prep |
| 0.7539 | 4c24bdf5 | Do some research on a company called CareFeed... |
| 0.6016 | 912ec581 | Help me write a Job Mission with OKRs... |
| 0.6016 | 3c595564 | Engineering Transformation at Carefeed |
| 0.6016 | 846b2464 | Help me write a Job Mission with OKRs... |
| 0.5716 | b009534a | New Chat |
| 0.5547 | 0e6cb01f | Director Engineering Interview Prep |
| 0.5396 | 7cb030f9 | New Chat |

**Query 2: "What has the user discussed about their engineering leadership experience and career background?"**

| Score | ID | Title |
|---|---|---|
| 0.6843 | 1351b3ff | Scaling AI Engineering Leadership |
| 0.6804 | 61a3291f | Engineering Leadership Growth |
| 0.6758 | 66c07fd9 | Professional resume writer... |
| 0.6725 | b28625c8 | I am engineering leader with 15 years... |
| 0.6643 | 935c42cd | New Chat |
| 0.6643 | 81601d06 | New Chat |
| 0.6613 | 89e7aedd | Greeting & Introduction |
| 0.6603 | 5639507c | Mental Health Mission |
| 0.6603 | e59633fa | Senior Engineering Manager Interview Prep |
| 0.6596 | 48394000 | I am engineering leader with 15 years... |

**Query 3: "What has the user asked about interview preparation strategies and techniques?"**

| Score | ID | Title |
|---|---|---|
| 0.6431 | 9ead21a4 | Interview Prep: Coaching & Leadership |
| 0.6338 | 4cbb75d9 | Engineering Leadership Application |
| 0.6288 | 61647f49 | Full-Stack System Design Prep |
| 0.5608 | 91ce5b27 | USAFacts Interview Prep |
| 0.5552 | 7cb030f9 | New Chat |
| 0.5334 | 31c84fdc | Bar Raiser Interview Prep |
| 0.5239 | 9c0861e0 | Healthcare Product Interview |
| 0.5217 | 194cf5de | Director of Engineering role with Aledade... |
| 0.5216 | 3c6aca9f | Senior Engineering Manager with Grow Therapy... |
| 0.5210 | 89e7aedd | Greeting & Introduction |

### MMR Selection Process (simulated)

| Pick | Score | Title | MMR Score | Why Selected |
|---|---|---|---|---|
| 1 | 0.754 | CareFeed Interview Prep | 0.500 | Highest score |
| 2 | 0.754 | Healthcare Digital Solutions | 0.500 | Same score, 0 title overlap with #1 |
| 3 | 0.754 | "Do some research on CareFeed..." | 0.455 | Same score, only 0.09 Jaccard to #1 |
| 4 | 0.676 | Professional resume writer | 0.329 | 0 overlap to any selected |
| 5 | 0.664 | New Chat | 0.307 | Empty title words -> 0 similarity to everything |

### Two Root Problems with Title-Based Jaccard

**1. Title-based Jaccard is too crude for content similarity**
- "CareFeed Interview Prep" vs "Healthcare Digital Solutions" -> **0.0 Jaccard** (zero shared title words), yet the conversations contain nearly identical CareFeed company research
- "New Chat" conversations -> **always 0.0 similarity** to everything, making them invisible to the diversity mechanism
- The long title "Do some research on a company called CareFeed..." shares only 1 word ("carefeed") with "CareFeed Interview Prep" -> only 0.09 Jaccard

**2. The CareFeed OKRs/Job Mission doc can't compete on score alone**
- Top 4 CareFeed conversations score **0.754**, while the OKRs doc scores **0.601**
- That's a 0.15 gap. Even with LAMBDA=0.5, the OKRs doc can only win if the penalty against it is much lower than the penalty against the higher-scored alternatives — which the crude title similarity doesn't achieve

### Key Gaps Still Remaining

| Conversation | Score | Status |
|---|---|---|
| **Job Mission/OKRs for CareFeed VP Eng** (912ec581) | 0.601 | In pool, not selected — THE most actionable conversation |
| **Engineering Transformation at Carefeed** (3c595564) | 0.601 | In pool, not selected — same content as above |
| **Interview Prep: Coaching & Leadership** (9ead21a4) | 0.643 | In pool, not selected — 32 messages of actual coaching |
| **Engineering Leadership Achievements** (5ef1d358) | — | **NOT IN POOL** — none of the 3 queries surfaced it |
| **Resume/bio** (b28625c8) | 0.673 | In pool, not selected |

---

## Proposed Solution: Conversation-Level Average Embeddings (Option 4)

### Approach
Replace title-based Jaccard similarity with cosine similarity on pre-computed conversation-level embedding vectors. The backend already embeds individual messages with `qwen3-embedding:8b-q8_0`. Pre-compute an average embedding across all embedded user messages per conversation and store it. Return it in search results. Use cosine similarity for MMR diversity.

### Why this is better
- Semantically accurate: handles synonyms, paraphrasing
- Language-agnostic
- Conversation length normalized through averaging
- Infrastructure already exists (embedding model + pgvector)

### Known Limitations

1. **Multi-topic conversations get "phantom" embeddings** — A conversation covering CareFeed + React + team management produces an average embedding at the center of all three topics, representing none of them well. Gets moderately penalized by all similar conversations rather than strongly penalized by the most relevant one.

2. **Signal dilution in long conversations** — A 2-message focused conversation has a sharp embedding. A 50-message conversation where the relevant topic is discussed in messages 5-8 has that signal diluted across the average. Creates a bias toward short, focused conversations.

3. **Topic similarity != information redundancy (fundamental tension)** — Two conversations about CareFeed can have similar average embeddings but contain completely different information (company research vs OKRs/approach). MMR's core assumption (similar embedding -> redundant content) breaks for conversations on the same topic that contain different facets of information.

4. **Asymmetric information density** — One dense, high-value message surrounded by 15 messages of back-and-forth gets its signal drowned by averaging.

### Possible Mitigations
- **Weighted averaging** — Weight by message length or recency to reduce dilution
- **Max-pooling** — Take the max across each embedding dimension to preserve strong signals
- **Multi-centroid representation** — k-means on message embeddings per conversation for multi-topic handling
- **Higher-level diversity** — Topic-level clustering where we ensure picks from different clusters but allow multiple picks within a cluster

---

## Memory Taxonomy (for future reference)

Three fundamentally different types of memory that require different architectural approaches:

1. **Factual memory** — Discrete facts shared by the user ("I have 15 years of experience", "I live in Ohio"). Wants structured storage (KV/knowledge graph), exact retrieval, overwrite-on-update semantics.

2. **Preferential memory** — User preferences that shape responses ("Keep responses concise", "Always prefer TypeScript"). Wants rule-based retrieval (always applied or context-triggered), explicit override semantics (newer supersedes older). Behaves like an evolving user-specific system prompt.

3. **Continuity memory** — Allows picking up where things left off ("Last time we were working on CareFeed interview prep..."). Wants semantic search, diversity-aware ranking, append-only semantics. This is what Mnemosyne currently handles. The retrieval challenge is the hardest because relevance is contextual and subjective.

Each type has fundamentally different storage, retrieval, and update patterns. Conversation-level vector search works for continuity but is a poor fit for factual and preferential memory.

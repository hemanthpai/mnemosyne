# Search Performance Analysis & Improvement Plan

**Date**: 2025-01-16
**Branch**: feat-amem
**Context**: Analysis of search quality issues in Mnemosyne A-MEM implementation

## Executive Summary

After comprehensive codebase analysis, I've identified several areas where search performance can be improved. The system already implements many advanced techniques (A-MEM multi-attribute embeddings, query expansion, hybrid search with BM25+Vector, reranking), but there are optimization opportunities in implementation details, parameter tuning, and algorithmic refinements.

---

## Current Architecture

### Search Pipeline (graph_service.py)

The search flow follows these steps:

1. **Query Preprocessing** (optional)
   - Query expansion: LLM generates 3-5 semantic variations
   - Query rewriting: Context-aware reformulation

2. **Vector Search**
   - Multi-attribute A-MEM embeddings: concat(content, keywords, tags, context)
   - Cosine similarity search in Qdrant
   - If expansion enabled: search with each variation, merge by max score

3. **Hybrid Search** (optional, enabled by default)
   - BM25 keyword search
   - Reciprocal Rank Fusion (RRF) to combine vector + BM25 rankings

4. **Reranking** (optional, enabled by default)
   - Cross-encoder or LLM-based relevance scoring
   - Re-orders top candidates for precision

### A-MEM Implementation

**Note Construction** (amem_service.py:60-150):
- LLM generates keywords (Ki), tags (Gi), contextual description (Xi)
- Max 5 keywords, max 5 tags per note

**Multi-Attribute Embeddings** (amem_service.py:156-237):
- Format: `concat(content, "Keywords: k1, k2, ...", "Tags: t1, t2, ...", "Context: description")`
- Single embedding captures all semantic dimensions

**Extraction** (tasks.py:103-218):
- Two-pass extraction (if enabled)
- Pass 1: Explicit facts
- Pass 2: Implied/contextual facts

---

## Issues Identified

### 1. Query Expansion Problems ⚠️ HIGH IMPACT

**Location**: `graph_service.py:115-175`

**Issues**:
- Currently **disabled by default** (`enable_query_expansion=False` in settings)
- When enabled, the expansion prompt is too generic:
  ```python
  "Generate variations that:
  - Use specific, concrete language
  - Cover different facets of the query topic
  - Are suitable for matching against factual statements"
  ```
- No validation that expansions are actually different from original
- No deduplication of similar expansions
- Expansion increases search cost 3-6x without guaranteed benefit

**Impact**: Low recall on abstract queries that need rephrasing

**Solution Priority**: HIGH - Fix expansion prompt and logic

---

### 2. A-MEM Embedding Concatenation Issues ⚠️ HIGH IMPACT

**Location**: `amem_service.py:199-237`

**Issues**:
```python
def _concatenate_attributes(self, note) -> str:
    parts = []
    if note.content:
        parts.append(note.content)
    if note.keywords:
        parts.append("Keywords: " + ", ".join(note.keywords))
    # ... continues
    return "\n".join(parts)
```

Problems:
- Equal weighting of all attributes (content, keywords, tags, context)
- Content may get diluted by verbose contextual descriptions
- No boosting of important keywords
- The literal strings "Keywords:", "Tags:", "Context:" consume embedding space

**Impact**: Semantic search may match on wrong aspects (e.g., matches tag when should match content)

**Solution Priority**: HIGH - Optimize concatenation format

---

### 3. BM25 Tokenization Too Simple ⚠️ MEDIUM IMPACT

**Location**: `bm25_service.py:40-67`

**Issues**:
```python
def tokenize(self, text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = [token for token in text.split()
              if len(token) > 2 and token not in self.stopwords]
    return tokens
```

Problems:
- No stemming/lemmatization ("running" != "runs" != "run")
- Minimal stopword list (only 18 words)
- Strips all punctuation (loses "C++", "Node.js", etc.)
- Loses hyphenated terms ("dark-mode" becomes ["dark", "mode"])

**Impact**: Misses keyword matches due to morphological variations

**Solution Priority**: MEDIUM - Add stemming and improve tokenization

---

### 4. Reranking Inefficiency ⚠️ MEDIUM IMPACT

**Location**: `reranking_service.py:195-260`

**Issues** (Ollama provider):
```python
for i, doc in enumerate(documents):
    # Sequential API call for EACH document
    response = requests.post(f"{endpoint}/api/generate", ...)
```

Problems:
- No batching - one LLM call per document
- For 30 candidates (3x multiplier), this is 30 sequential LLM calls
- Very slow (30-60 seconds for a single query)
- Relevance prompt is simplistic: "Rate relevance 0-10"

**Impact**: Reranking adds significant latency without proportional quality gain

**Solution Priority**: MEDIUM - Batch reranking or use faster cross-encoder

---

### 5. RRF Fusion Parameters Not Optimized ⚠️ LOW-MEDIUM IMPACT

**Location**: `bm25_service.py:203-261`

**Issues**:
```python
def reciprocal_rank_fusion(rankings, k=60, id_key='note_id'):
    # k=60 is literature standard, but may not suit this use case
    rrf_score = 1.0 / (k + rank)
```

Problems:
- Fixed k=60 from literature, not tuned for atomic notes
- Equal weight to all ranking sources (no source-specific weights)
- No consideration of score confidence

**Impact**: Suboptimal fusion of vector + BM25 results

**Solution Priority**: LOW-MEDIUM - Experiment with k values and weighted fusion

---

### 6. Search Thresholds Too Aggressive ⚠️ MEDIUM IMPACT

**Location**: `graph_service.py:311`

**Issues**:
```python
threshold=max(0.0, threshold - 0.2)  # Lower threshold for recall
```

When expansion is enabled, threshold is reduced by 0.2 (e.g., 0.5 → 0.3). This is very aggressive and may pull in many irrelevant results.

**Impact**: False positives in search results

**Solution Priority**: MEDIUM - Make threshold adjustment configurable

---

### 7. No Query Normalization ⚠️ LOW-MEDIUM IMPACT

**Location**: Multiple locations

**Issues**:
- Queries used as-is, no preprocessing
- No handling of typos or synonyms
- No query intent classification
- No query-specific boosting (e.g., "preference" queries should boost note_type=preference)

**Impact**: Misses relevant results due to query formulation issues

**Solution Priority**: LOW-MEDIUM - Add query preprocessing

---

### 8. A-MEM Note Construction Prompt Issues ⚠️ MEDIUM-HIGH IMPACT

**Location**: `prompts.py:12-40`

**Issues**:
```python
AMEM_NOTE_CONSTRUCTION_PROMPT = """Generate a structured analysis...
  "keywords": [
    // several specific, distinct keywords
    // At least three keywords, but don't be too redundant.
  ],
```

Problems:
- Vague guidance: "several", "don't be too redundant"
- No specific instructions on keyword selection strategy
- Context generation prompt is generic
- No examples provided

**Impact**: Inconsistent A-MEM enrichment quality

**Solution Priority**: MEDIUM-HIGH - Improve A-MEM prompts with examples

---

### 9. Missing Search Features ⚠️ MEDIUM IMPACT

**Missing Capabilities**:
1. **No query intent detection**: Can't distinguish "what languages does he know" vs "what languages does he prefer"
2. **No temporal filtering**: Can't prioritize recent memories
3. **No importance weighting**: All notes treated equally regardless of importance_score
4. **No user-specific context**: Search doesn't consider user's conversation history
5. **No result diversity**: May return many similar notes

**Impact**: Search results lack context-awareness and personalization

**Solution Priority**: MEDIUM - Add filtering and weighting options

---

### 10. Extraction Prompt May Extract Too Broadly ⚠️ MEDIUM IMPACT

**Location**: `tasks.py:103-218`

**Issues**:
The extraction prompt has grown very long (115 lines) with many edge cases:
- "List items with 'and': extract SEPARATE facts for X and Y"
- "Implied tools: 'using Pinia' → extract both 'uses Pinia' AND 'uses Vue'"
- "Frequency patterns: 'tries to X' → extract 'attempts to X' or 'regularly does X'"

Problems:
- May over-extract and create noise
- Complex instructions may confuse LLM
- No clear guidance on what NOT to extract beyond a few examples

**Impact**: Too many low-confidence notes that pollute search results

**Solution Priority**: MEDIUM - Simplify extraction prompt, raise confidence threshold

---

## Improvement Plan

### Phase 1: Quick Wins (1-2 days)

#### 1.1. Fix Query Expansion Prompt
**Effort**: 2-3 hours
**Expected Impact**: +10-15% recall on abstract queries

**Changes**:
- Improve expansion prompt with examples
- Add variation validation (must be different from original)
- Deduplicate similar expansions
- Make expansion more domain-specific

**Implementation**:
```python
QUERY_EXPANSION_PROMPT_V2 = """Expand this search query into 3-5 concrete variations optimized for finding relevant personal facts.

Query: "{query}"

Generate variations by:
1. Rephrasing with different vocabulary (synonyms, related terms)
2. Making abstract queries more specific (e.g., "music" → "favorite bands", "music genres", "concert attendance")
3. Expanding acronyms and implicit terms (e.g., "tech stack" → "programming languages and frameworks")
4. Considering different aspects (preferences, skills, experiences, opinions)

Each variation must be meaningfully different from the original and other variations.

Examples:
Query: "music preferences"
Variations: ["favorite musical artists and bands", "music genres they enjoy", "concert and live music attendance", "musical instruments they play"]

Query: "programming skills"
Variations: ["programming languages they know", "software frameworks and libraries they use", "years of programming experience", "programming projects they've built"]

Return ONLY a JSON array of 3-5 distinct variations:
["variation1", "variation2", "variation3"]"""
```

#### 1.2. Optimize A-MEM Concatenation
**Effort**: 3-4 hours
**Expected Impact**: +5-10% precision

**Changes**:
- Weight content more heavily than metadata
- Remove literal "Keywords:", "Tags:" strings
- Boost important keywords
- Limit context length

**Implementation**:
```python
def _concatenate_attributes(self, note) -> str:
    """
    Optimized concatenation with content boosting
    Format: content [repeated for emphasis] keywords tags context
    """
    parts = []

    # Content (boosted by repetition for emphasis)
    if note.content:
        parts.append(note.content)
        parts.append(note.content)  # Repeat for 2x weight

    # Keywords (most important semantic signals)
    if note.keywords:
        # Take top 3 keywords only
        top_keywords = note.keywords[:3]
        parts.append(" ".join(top_keywords))

    # Tags (categorical, lower weight)
    if note.llm_tags:
        parts.append(" ".join(note.llm_tags[:3]))

    # Context (truncated to avoid dilution)
    if note.contextual_description:
        # Limit to 100 chars
        context_short = note.contextual_description[:100]
        parts.append(context_short)

    # Join with spaces (no newlines)
    return " ".join(parts)
```

#### 1.3. Add Importance Score Weighting
**Effort**: 2 hours
**Expected Impact**: +5-8% precision

**Changes**:
- Boost search scores by note importance
- Filter out very low importance notes

**Implementation** (in graph_service.py):
```python
# After getting search results, boost by importance
for result in results:
    note_id = result['id']
    if note_id in notes_by_id:
        importance = notes_by_id[note_id].importance_score or 0.5
        # Boost score by importance (0.5-1.5x multiplier)
        result['score'] = result['score'] * (0.5 + importance)
```

#### 1.4. Improve BM25 Tokenization
**Effort**: 2-3 hours
**Expected Impact**: +5-10% recall on keyword queries

**Changes**:
- Add stemming (Porter stemmer)
- Expand stopword list
- Preserve technical terms (keep hyphens, plus signs, dots in certain contexts)

**Implementation**:
```python
from nltk.stem import PorterStemmer

class BM25Service:
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.stopwords = set([
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'she', 'in', 'is', 'it', 'its', 'of', 'on', 'that',
            'the', 'to', 'was', 'will', 'with', 'this', 'these', 'those',
            'would', 'should', 'could', 'been', 'have', 'had', 'were'
        ])
        # Technical term patterns to preserve
        self.tech_term_pattern = re.compile(r'[a-z]+\+\+|[a-z]+\.js|[a-z]+-[a-z]+')

    def tokenize(self, text: str) -> List[str]:
        # Preserve technical terms first
        tech_terms = self.tech_term_pattern.findall(text.lower())

        # Standard tokenization
        text = text.lower()
        text = re.sub(r'[^\w\s\+\-\.]', ' ', text)  # Keep +, -, .

        tokens = []
        for token in text.split():
            if len(token) > 2 and token not in self.stopwords:
                # Stem unless it's a technical term
                if token in tech_terms:
                    tokens.append(token)
                else:
                    tokens.append(self.stemmer.stem(token))

        return tokens
```

---

### Phase 2: Medium-Term Improvements (3-5 days)

#### 2.1. Refine A-MEM Note Construction Prompt
**Effort**: 4-6 hours
**Expected Impact**: +10-15% overall quality

**Changes**:
- Add specific keyword selection strategy
- Provide diverse examples
- Add output validation
- Make context generation more focused

**Implementation**: Update `prompts.py` with examples and clearer instructions.

#### 2.2. Optimize Reranking
**Effort**: 4-6 hours
**Expected Impact**: -50% latency, +5% precision

**Options**:
A. **Batch Ollama calls** (if model supports batching)
B. **Switch to cross-encoder** (sentence-transformers with BGE-reranker)
C. **Hybrid approach**: Fast first-pass filter, then rerank top-10

**Recommendation**: Option C for best speed/quality tradeoff

#### 2.3. Add Query Preprocessing
**Effort**: 6-8 hours
**Expected Impact**: +8-12% recall

**Features**:
- Query normalization (lowercase, remove filler words)
- Synonym expansion (configurable synonym map)
- Query intent detection (preference vs skill vs fact)
- Type-specific boosting

#### 2.4. Optimize RRF Parameters
**Effort**: 3-4 hours
**Expected Impact**: +3-5% precision

**Approach**:
- Grid search for optimal k value (test 30, 40, 50, 60, 70, 80)
- Add source-specific weighting (e.g., vector:0.6, bm25:0.4)
- Use benchmark to evaluate

#### 2.5. Add Result Diversity
**Effort**: 4-5 hours
**Expected Impact**: +5% user satisfaction

**Implementation**: MMR (Maximal Marginal Relevance) re-ranking

---

### Phase 3: Advanced Improvements (5-7 days)

#### 3.1. Temporal Relevance Decay
**Effort**: 3-4 hours
**Expected Impact**: +5-8% on recent queries

**Implementation**: Boost recent notes with time-based decay function

#### 3.2. Adaptive Thresholds
**Effort**: 4-6 hours
**Expected Impact**: +5-10% overall

**Approach**: Learn optimal thresholds per query type from benchmark data

#### 3.3. Query Understanding
**Effort**: 8-12 hours
**Expected Impact**: +10-15% on complex queries

**Features**:
- Named entity recognition
- Intent classification
- Query decomposition for multi-part queries

#### 3.4. Negative Sampling for Extraction
**Effort**: 6-8 hours
**Expected Impact**: +10% precision (fewer noise notes)

**Approach**: Add negative examples to extraction prompt to reduce over-extraction

---

## Testing Strategy

For each improvement:

1. **Implement change** in isolated branch/commit
2. **Run benchmark**: `python manage.py run_benchmark --test-type all`
3. **Compare metrics**:
   - Extraction: Precision, Recall, F1
   - Search: Precision@10, Recall@10, MRR
4. **Document results** in git commit message
5. **Keep if improvement ≥ 3%**, revert otherwise

---

## Priority Ranking

| Priority | Improvement | Effort | Expected Impact | ROI |
|----------|-------------|--------|-----------------|-----|
| 1 | Fix Query Expansion Prompt | 2-3h | +10-15% recall | ⭐⭐⭐⭐⭐ |
| 2 | Optimize A-MEM Concatenation | 3-4h | +5-10% precision | ⭐⭐⭐⭐⭐ |
| 3 | Add Importance Weighting | 2h | +5-8% precision | ⭐⭐⭐⭐⭐ |
| 4 | Improve BM25 Tokenization | 2-3h | +5-10% recall | ⭐⭐⭐⭐ |
| 5 | Refine A-MEM Prompts | 4-6h | +10-15% overall | ⭐⭐⭐⭐ |
| 6 | Optimize Reranking | 4-6h | -50% latency | ⭐⭐⭐⭐ |
| 7 | Add Query Preprocessing | 6-8h | +8-12% recall | ⭐⭐⭐ |
| 8 | Optimize RRF Parameters | 3-4h | +3-5% precision | ⭐⭐⭐ |
| 9 | Add Result Diversity | 4-5h | +5% satisfaction | ⭐⭐⭐ |
| 10 | Temporal Relevance | 3-4h | +5-8% recent | ⭐⭐ |

**Recommended Order**: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

---

## Baseline Metrics (To Be Measured)

**Extraction Quality**:
- Precision: ? (target: >90%)
- Recall: ? (target: >85%)
- F1 Score: ? (target: >87%)

**Search Quality**:
- Precision@10: ? (target: >80%)
- Recall@10: ? (target: >70%)
- MRR: ? (target: >0.75)

**Performance**:
- Search latency: ? (target: <1s)
- Extraction time: ? (acceptable: 15-30s)

---

## Next Steps

1. ✅ Complete codebase analysis
2. ⏳ Run baseline benchmarks to establish current metrics
3. ⏳ Implement Phase 1 improvements (1.1 → 1.2 → 1.3 → 1.4)
4. ⏳ Measure impact of each change
5. ⏳ Move to Phase 2 if Phase 1 shows promise
6. ⏳ Document all changes and final metrics

---

## Notes

- Current system already has many advanced features (good foundation)
- Main issues are in implementation details and parameter tuning
- A-MEM architecture is sound, needs optimization not replacement
- Benchmark framework is excellent for measuring improvements
- Focus on quick wins first to validate approach


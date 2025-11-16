"""
BM25 Service

Provides keyword-based search using BM25 algorithm for hybrid search.
Complements vector search by finding exact term matches that semantic search might miss.
"""

import logging
import re
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
from django.core.cache import cache
from .models import AtomicNote

logger = logging.getLogger(__name__)

# Cache keys
BM25_INDEX_CACHE_KEY = "bm25_index_{user_id}"
BM25_INDEX_TIMEOUT = 3600  # 1 hour


class BM25Service:
    """
    Service for BM25-based keyword search on atomic notes.

    BM25 is a probabilistic keyword-based ranking function that:
    - Finds exact term matches
    - Accounts for term frequency and document length
    - Complements semantic search by catching specific keywords

    Optimizations:
    - Simple stemming for common suffixes (ing, ed, s, es)
    - Expanded stopword list
    - Preservation of technical terms (C++, Node.js, etc.)
    """

    def __init__(self):
        """Initialize BM25 service"""
        # Expanded stopword list
        self.stopwords = set([
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'she', 'in', 'is', 'it', 'its', 'of', 'on', 'that',
            'the', 'to', 'was', 'will', 'with', 'this', 'these', 'those',
            'would', 'should', 'could', 'been', 'have', 'had', 'were', 'their',
            'there', 'they', 'them', 'then', 'than', 'but', 'not', 'or'
        ])

        # Pattern to identify technical terms that should be preserved
        # Matches: C++, C#, Node.js, React.js, dark-mode, etc.
        self.tech_term_pattern = re.compile(
            r'[a-zA-Z]+\+\+|'  # C++, C++
            r'[a-zA-Z]+#|'     # C#, F#
            r'[a-zA-Z]+\.js|'  # Node.js, React.js
            r'[a-zA-Z]+-[a-zA-Z]+|'  # dark-mode, front-end
            r'\.net'           # .NET
        , re.IGNORECASE)

    def simple_stem(self, word: str) -> str:
        """
        Simple suffix-stripping stemmer for common English endings

        Handles: -ing, -ed, -s, -es, -er, -est, -ly, -tion, -ment

        Args:
            word: Word to stem

        Returns:
            Stemmed word
        """
        # Don't stem very short words
        if len(word) <= 3:
            return word

        # Preserve minimum stem length of 3
        min_stem_len = 3

        # Remove common suffixes (order matters for longer suffixes first)
        if word.endswith('tion') and len(word) - 4 >= min_stem_len:
            return word[:-4]
        if word.endswith('ment') and len(word) - 4 >= min_stem_len:
            return word[:-4]
        if word.endswith('ing') and len(word) - 3 >= min_stem_len:
            return word[:-3]
        if word.endswith('est') and len(word) - 3 >= min_stem_len:
            return word[:-3]
        if word.endswith('ed') and len(word) - 2 >= min_stem_len:
            return word[:-2]
        if word.endswith('er') and len(word) - 2 >= min_stem_len:
            return word[:-2]
        if word.endswith('ly') and len(word) - 2 >= min_stem_len:
            return word[:-2]
        if word.endswith('es') and len(word) - 2 >= min_stem_len:
            return word[:-2]
        if word.endswith('s') and len(word) - 1 >= min_stem_len and not word.endswith('ss'):
            return word[:-1]

        return word

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text for BM25 indexing (optimized)

        Improvements:
        - Preserves technical terms (C++, Node.js, dark-mode, etc.)
        - Simple stemming for common suffixes
        - Expanded stopword list
        - Better handling of punctuation

        Args:
            text: Text to tokenize

        Returns:
            List of tokens
        """
        # Extract technical terms first (before lowercasing)
        tech_terms = []
        for match in self.tech_term_pattern.finditer(text):
            tech_terms.append(match.group().lower())

        # Lowercase
        text = text.lower()

        # Remove punctuation but preserve hyphens, dots, and plus signs in certain contexts
        # This regex keeps alphanumeric + whitespace + hyphen + dot + plus
        text = re.sub(r'[^\w\s\-\.\+]', ' ', text)

        # Split and filter
        tokens = []
        for token in text.split():
            # Skip if too short or is stopword
            if len(token) <= 2 or token in self.stopwords:
                continue

            # If it's a technical term, keep as-is
            if token in tech_terms:
                tokens.append(token)
            else:
                # Strip trailing punctuation that leaked through
                token = token.strip('.-+')

                if len(token) > 2:
                    # Apply simple stemming
                    stemmed = self.simple_stem(token)
                    tokens.append(stemmed)

        return tokens

    def build_index(self, user_id: str, force_rebuild: bool = False) -> Tuple[BM25Okapi, List[str]]:
        """
        Build or retrieve BM25 index for user's atomic notes

        Args:
            user_id: UUID of the user
            force_rebuild: Force rebuild even if cached

        Returns:
            Tuple of (BM25 index, list of note IDs)
        """
        cache_key = BM25_INDEX_CACHE_KEY.format(user_id=user_id)

        # Try cache first
        if not force_rebuild:
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Using cached BM25 index for user {user_id}")
                return cached['index'], cached['note_ids']

        # Build index from database
        logger.info(f"Building BM25 index for user {user_id}")

        notes = AtomicNote.objects.filter(
            user_id=user_id
        ).order_by('-created_at').values('id', 'content')

        if not notes:
            logger.warning(f"No atomic notes found for user {user_id}")
            # Return empty index
            empty_index = BM25Okapi([[]])
            return empty_index, []

        # Tokenize all documents
        tokenized_corpus = []
        note_ids = []

        for note in notes:
            tokens = self.tokenize(note['content'])
            tokenized_corpus.append(tokens)
            note_ids.append(str(note['id']))

        # Build BM25 index
        bm25_index = BM25Okapi(tokenized_corpus)

        # Cache the index
        cache.set(cache_key, {
            'index': bm25_index,
            'note_ids': note_ids
        }, BM25_INDEX_TIMEOUT)

        logger.info(f"Built BM25 index with {len(note_ids)} notes for user {user_id}")

        return bm25_index, note_ids

    def search(
        self,
        query: str,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search atomic notes using BM25

        Args:
            query: Search query text
            user_id: UUID of the user
            limit: Maximum number of results

        Returns:
            List of results with note_id and score
        """
        try:
            # Build/get index
            bm25_index, note_ids = self.build_index(user_id)

            if not note_ids:
                return []

            # Tokenize query
            query_tokens = self.tokenize(query)

            if not query_tokens:
                logger.warning(f"Query tokenized to empty list: '{query}'")
                return []

            # Get BM25 scores
            scores = bm25_index.get_scores(query_tokens)

            # Combine note IDs with scores
            results = [
                {
                    'note_id': note_ids[i],
                    'bm25_score': float(scores[i])
                }
                for i in range(len(note_ids))
                if scores[i] > 0  # Only include non-zero scores
            ]

            # Sort by score descending
            results.sort(key=lambda x: x['bm25_score'], reverse=True)

            # Return top-k
            top_results = results[:limit]

            logger.info(
                f"BM25 search for user {user_id}: query='{query}' "
                f"→ {len(results)} matches, returning top {len(top_results)}"
            )

            return top_results

        except Exception as e:
            logger.error(f"BM25 search failed: {e}", exc_info=True)
            return []

    def invalidate_cache(self, user_id: str):
        """
        Invalidate cached BM25 index for user

        Call this when atomic notes are added/updated/deleted.

        Args:
            user_id: UUID of the user
        """
        cache_key = BM25_INDEX_CACHE_KEY.format(user_id=user_id)
        cache.delete(cache_key)
        logger.info(f"Invalidated BM25 index cache for user {user_id}")


# Singleton instance
_bm25_service = None


def reciprocal_rank_fusion(
    rankings: List[List[Dict[str, Any]]],
    k: int = 60,
    id_key: str = 'note_id'
) -> List[Dict[str, Any]]:
    """
    Combine multiple rankings using Reciprocal Rank Fusion (RRF)

    RRF formula: score = sum over all rankings of: 1 / (k + rank)
    where k is a constant (typically 60) and rank starts at 1

    Args:
        rankings: List of result lists, each with dicts containing id_key and scores
        k: RRF constant (default 60, standard value from literature)
        id_key: Key name for unique identifier (default 'note_id')

    Returns:
        Fused results sorted by RRF score, including original scores

    Example:
        vector_results = [{'note_id': 'A', 'score': 0.9}, {'note_id': 'B', 'score': 0.7}]
        bm25_results = [{'note_id': 'B', 'bm25_score': 10.5}, {'note_id': 'C', 'bm25_score': 8.2}]
        fused = reciprocal_rank_fusion([vector_results, bm25_results])
        # Result: B (appeared in both) ranks higher due to RRF combination
    """
    # Collect all unique IDs and their RRF scores
    rrf_scores: Dict[str, float] = {}
    original_data: Dict[str, Dict[str, Any]] = {}

    for ranking_list in rankings:
        for rank, item in enumerate(ranking_list, start=1):
            item_id = item.get(id_key)
            if not item_id:
                continue

            # Add RRF score: 1 / (k + rank)
            rrf_score = 1.0 / (k + rank)
            rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + rrf_score

            # Store original data (first occurrence wins for metadata)
            if item_id not in original_data:
                original_data[item_id] = item.copy()

    # Build fused results
    fused_results = []
    for item_id, rrf_score in rrf_scores.items():
        result = original_data[item_id].copy()
        result['rrf_score'] = rrf_score
        result['score'] = rrf_score  # Use RRF as primary score
        fused_results.append(result)

    # Sort by RRF score descending
    fused_results.sort(key=lambda x: x['rrf_score'], reverse=True)

    logger.debug(
        f"RRF fusion: {len(rrf_scores)} unique items from {len(rankings)} rankings"
    )

    return fused_results


def get_bm25_service() -> BM25Service:
    """
    Get or create singleton BM25 service instance

    Returns:
        BM25Service instance
    """
    global _bm25_service

    if _bm25_service is None:
        _bm25_service = BM25Service()

    return _bm25_service

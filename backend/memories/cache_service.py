import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


class CacheService:
    """
    Working Memory Cache with Redis

    Provides <10ms retrieval for frequently accessed memories:
    - Recent conversations (last 24h)
    - High-scoring search results
    - User-specific working memory
    """

    def __init__(self):
        self.enabled = self._connect()

    def _connect(self) -> bool:
        """Initialize Redis connection"""
        try:
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            self.client = redis.from_url(
                redis_url,
                decode_responses=True,  # Auto-decode bytes to strings
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.client.ping()
            logger.info(f"Connected to Redis at {redis_url}")
            return True
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Cache disabled - falling back to direct DB queries")
            self.client = None
            return False

    def _make_key(self, user_id: str, key_type: str) -> str:
        """Generate Redis key"""
        return f"working_memory:{user_id}:{key_type}"

    def cache_recent_conversation(self, user_id: str, turn_data: Dict[str, Any]):
        """Cache a recent conversation turn in working memory"""
        if not self.enabled:
            return

        try:
            key = self._make_key(user_id, "recent")

            # Add to sorted set with timestamp as score
            timestamp = datetime.fromisoformat(turn_data['timestamp']).timestamp()
            value = json.dumps(turn_data)

            self.client.zadd(key, {value: timestamp})

            # Keep only last 24h of conversations
            cutoff = (datetime.now() - timedelta(hours=24)).timestamp()
            self.client.zremrangebyscore(key, '-inf', cutoff)

            # Set expiration to 48h (auto-cleanup)
            self.client.expire(key, 48 * 3600)

            logger.debug(f"Cached recent conversation for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to cache recent conversation: {e}")

    def cache_search_result(self, user_id: str, query: str, results: List[Dict[str, Any]]):
        """Cache search results for quick retrieval"""
        if not self.enabled or not results:
            return

        try:
            # Only cache high-scoring results (score >= 0.6)
            high_quality = [r for r in results if r.get('score', 0) >= 0.6]
            if not high_quality:
                return

            key = self._make_key(user_id, f"search:{query[:50]}")  # Limit key length
            value = json.dumps(high_quality)

            # Cache for 1 hour
            self.client.setex(key, 3600, value)

            logger.debug(f"Cached {len(high_quality)} search results for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to cache search results: {e}")

    def get_working_memory(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get working memory (recent conversations) for a user

        Returns: List of recent conversation turns, newest first
        Latency: <10ms (cache hit)
        """
        if not self.enabled:
            return []

        try:
            key = self._make_key(user_id, "recent")

            # Get most recent conversations (descending order)
            results = self.client.zrevrange(key, 0, limit - 1)

            conversations = [json.loads(r) for r in results]

            logger.debug(f"Retrieved {len(conversations)} working memory items for user {user_id}")
            return conversations

        except Exception as e:
            logger.error(f"Failed to get working memory: {e}")
            return []

    def get_cached_search(self, user_id: str, query: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached search results

        Returns: Cached results or None if not found
        Latency: <10ms (cache hit)
        """
        if not self.enabled:
            return None

        try:
            key = self._make_key(user_id, f"search:{query[:50]}")
            value = self.client.get(key)

            if value:
                logger.debug(f"Cache hit for search query: {query[:30]}...")
                return json.loads(value)

            return None

        except Exception as e:
            logger.error(f"Failed to get cached search: {e}")
            return None

    def invalidate_user_cache(self, user_id: str):
        """Clear all cache for a user"""
        if not self.enabled:
            return

        try:
            # Get all keys for this user
            pattern = self._make_key(user_id, "*")
            keys = self.client.keys(pattern)

            if keys:
                self.client.delete(*keys)
                logger.info(f"Invalidated cache for user {user_id} ({len(keys)} keys)")

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")

    def get_cache_stats(self, user_id: str) -> Dict[str, Any]:
        """Get cache statistics for a user"""
        if not self.enabled:
            return {"enabled": False}

        try:
            recent_key = self._make_key(user_id, "recent")
            recent_count = self.client.zcard(recent_key)

            # Count search cache entries
            search_pattern = self._make_key(user_id, "search:*")
            search_keys = self.client.keys(search_pattern)

            return {
                "enabled": True,
                "recent_conversations": recent_count,
                "cached_searches": len(search_keys),
                "user_id": user_id
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"enabled": True, "error": str(e)}


# Global instance
cache_service = CacheService()

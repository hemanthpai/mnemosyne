"""
Memory Consolidation Service for Deduplication and Merging

This service handles detection and consolidation of duplicate or similar memories,
preventing information redundancy and maintaining memory store consistency.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set

from django.utils import timezone
from django.db.models import Q

from .llm_service import llm_service
from .models import Memory
from .vector_service import vector_service

logger = logging.getLogger(__name__)


class MemoryConsolidationService:
    """Service for detecting and consolidating duplicate/similar memories"""
    
    def __init__(self):
        # Default settings (will be overridden by database settings)
        self.similarity_threshold = 0.85
        self.consolidation_threshold = 0.90
        self.batch_size = 50
        self.max_group_size = 3
        self.strategy = 'llm_guided'
        
    def _get_settings(self):
        """Get current consolidation settings from database"""
        try:
            from settings_app.models import LLMSettings
            settings = LLMSettings.get_settings()
            
            return {
                'enabled': settings.enable_memory_consolidation,
                'similarity_threshold': settings.consolidation_similarity_threshold,
                'auto_threshold': settings.consolidation_auto_threshold,
                'strategy': settings.consolidation_strategy,
                'max_group_size': settings.consolidation_max_group_size,
                'batch_size': settings.consolidation_batch_size,
            }
        except Exception as e:
            logger.warning(f"Could not load consolidation settings: {e}")
            return {
                'enabled': True,
                'similarity_threshold': self.similarity_threshold,
                'auto_threshold': self.consolidation_threshold,
                'strategy': self.strategy,
                'max_group_size': self.max_group_size,
                'batch_size': self.batch_size,
            }
        
    def find_duplicates(
        self, 
        memory: Memory, 
        user_id: str, 
        similarity_threshold: Optional[float] = None
    ) -> List[Tuple[Memory, float, str]]:
        """
        Find semantically similar memories for a given memory
        
        Args:
            memory: Memory to find duplicates for
            user_id: User ID to search within
            similarity_threshold: Override default similarity threshold
            
        Returns:
            List of tuples (similar_memory, similarity_score, duplicate_type)
        """
        settings = self._get_settings()
        
        # Check if consolidation is enabled
        if not settings['enabled']:
            return []
            
        threshold = similarity_threshold or settings['similarity_threshold']
        duplicates = []
        
        # Get existing active memories for the user (excluding the memory itself)
        existing_memories = Memory.objects.filter(
            user_id=user_id,
            is_active=True
        ).exclude(id=memory.id)
        
        if not existing_memories.exists():
            return duplicates
            
        try:
            # Get embedding for the memory content
            embedding_result = llm_service.get_embeddings([memory.content])
            if not embedding_result['success']:
                logger.error(f"Failed to get embedding for memory {memory.id}")
                return duplicates
                
            memory_embedding = embedding_result['embeddings'][0]
            
            # Search for similar memories by comparing embeddings directly
            # In hybrid architecture, memories don't have vector_id - only conversation chunks do
            for candidate_memory in existing_memories:
                try:
                    # Get embedding for candidate memory
                    candidate_embedding_result = llm_service.get_embeddings([candidate_memory.content])
                    if not candidate_embedding_result['success']:
                        continue
                        
                    candidate_embedding = candidate_embedding_result['embeddings'][0]
                    
                    # Calculate similarity using cosine similarity
                    similarity_score = self._calculate_cosine_similarity(memory_embedding, candidate_embedding)
                    
                    if similarity_score >= threshold:
                        duplicate_type = self._classify_duplicate_type(
                            memory, candidate_memory, similarity_score
                        )
                        duplicates.append((candidate_memory, similarity_score, duplicate_type))
                        
                except Exception as e:
                    logger.warning(f"Error calculating similarity for memory {candidate_memory.id}: {e}")
                    continue
                        
        except Exception as e:
            logger.error(f"Error finding duplicates for memory {memory.id}: {e}")
            
        # Sort by similarity score (highest first)
        duplicates.sort(key=lambda x: x[1], reverse=True)
        return duplicates
    
    def _classify_duplicate_type(
        self, 
        memory1: Memory, 
        memory2: Memory, 
        similarity_score: float
    ) -> str:
        """
        Classify the type of duplication between two memories
        
        Args:
            memory1: First memory
            memory2: Second memory
            similarity_score: Semantic similarity score
            
        Returns:
            String describing the duplicate type
        """
        # Very high similarity suggests exact or near-exact duplicates
        if similarity_score >= 0.95:
            return "exact_duplicate"
        elif similarity_score >= 0.90:
            return "near_duplicate"
        elif similarity_score >= 0.85:
            # Check for refinement vs duplication using LLM
            return self._llm_classify_duplicate_type(memory1, memory2)
        else:
            return "similar_content"
    
    def _llm_classify_duplicate_type(self, memory1: Memory, memory2: Memory) -> str:
        """Use LLM to classify duplicate type for borderline cases"""
        try:
            prompt = f"""Analyze these two memories and classify their relationship:

MEMORY 1: {memory1.content}
- Created: {memory1.created_at}
- Inference Level: {memory1.metadata.get('inference_level', 'stated')}
- Evidence: {memory1.metadata.get('evidence', '')}

MEMORY 2: {memory2.content}  
- Created: {memory2.created_at}
- Inference Level: {memory2.metadata.get('inference_level', 'stated')}
- Evidence: {memory2.metadata.get('evidence', '')}

Classify their relationship as one of:
- "exact_duplicate": Same information, different wording
- "near_duplicate": Very similar with minor differences
- "refinement": One provides more specific/detailed version of the other
- "update": Newer information that replaces older version
- "related": Similar topic but distinct information
- "conflicting": Contradictory information

Consider temporal order, inference levels, and evidence quality."""

            result = llm_service.query_llm(
                prompt=prompt,
                temperature=0.3,
                response_format={
                    "type": "object",
                    "properties": {
                        "classification": {
                            "type": "string",
                            "enum": ["exact_duplicate", "near_duplicate", "refinement", "update", "related", "conflicting"]
                        },
                        "reasoning": {"type": "string"},
                        "confidence": {"type": "number"}
                    },
                    "required": ["classification", "reasoning"]
                }
            )
            
            if result['success']:
                response_data = json.loads(result['response'])
                return response_data['classification']
                
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            
        return "similar_content"  # Default fallback
    
    def merge_memories(
        self, 
        memories: List[Memory], 
        consolidation_strategy: str = "automatic"
    ) -> Optional[Memory]:
        """
        Consolidate multiple similar memories into a single coherent memory
        
        Args:
            memories: List of memories to consolidate
            consolidation_strategy: "automatic", "llm_guided", or "manual"
            
        Returns:
            Consolidated memory or None if consolidation fails
        """
        if len(memories) < 2:
            return memories[0] if memories else None
            
        # Sort by creation date (newest first) and reliability
        sorted_memories = self._rank_memories_for_consolidation(memories)
        
        if consolidation_strategy == "automatic":
            return self._automatic_merge(sorted_memories)
        elif consolidation_strategy == "llm_guided":
            return self._llm_guided_merge(sorted_memories)
        else:
            return self._manual_merge(sorted_memories)
    
    def _rank_memories_for_consolidation(self, memories: List[Memory]) -> List[Memory]:
        """Rank memories by reliability and recency for consolidation"""
        def memory_score(memory: Memory) -> float:
            # Base score from temporal confidence
            score = memory.temporal_confidence
            
            # Boost for inference level reliability
            inference_boost = {
                "stated": 0.3,
                "inferred": 0.2, 
                "implied": 0.1
            }.get(memory.metadata.get('inference_level', 'stated'), 0.1)
            
            # Boost for confidence
            confidence_boost = memory.temporal_confidence * 0.15
            
            # Recency boost (more recent = better)
            days_old = (timezone.now() - memory.created_at).days
            recency_boost = max(0, 0.1 - (days_old * 0.01))  # Decreases with age
            
            return score + inference_boost + confidence_boost + recency_boost
        
        return sorted(memories, key=memory_score, reverse=True)
    
    def _automatic_merge(self, memories: List[Memory]) -> Memory:
        """Automatically merge memories using simple rules"""
        primary_memory = memories[0]  # Highest ranked
        
        # Combine content from all memories
        combined_tags = set()
        combined_connections = set()
        evidence_parts = []
        
        for memory in memories:
            # Collect tags and connections
            combined_tags.update(memory.metadata.get('tags', []))
            combined_connections.update(memory.metadata.get('connections', []))
            
            # Collect evidence
            evidence = memory.metadata.get('evidence', '')
            if evidence and evidence not in evidence_parts:
                evidence_parts.append(evidence)
        
        # Update primary memory with combined information
        primary_memory.metadata.update({
            'tags': list(combined_tags),
            'connections': list(combined_connections),
            'evidence': ' | '.join(evidence_parts),
            'consolidated_from': [str(m.id) for m in memories[1:]],
            'consolidation_type': 'automatic',
            'consolidation_date': timezone.now().isoformat()
        })
        
        # Mark other memories as superseded
        for memory in memories[1:]:
            memory.is_active = False
            memory.save()
            
        primary_memory.save()
        
        logger.info(f"Automatically consolidated {len(memories)} memories into {primary_memory.id}")
        return primary_memory
    
    def _llm_guided_merge(self, memories: List[Memory]) -> Optional[Memory]:
        """Use LLM to intelligently consolidate memories"""
        memory_data = []
        for i, memory in enumerate(memories):
            memory_data.append({
                'index': i,
                'content': memory.content,
                'created': memory.created_at.strftime('%Y-%m-%d %H:%M'),
                'inference_level': memory.metadata.get('inference_level', 'stated'),
                'evidence': memory.metadata.get('evidence', ''),
                'confidence': memory.temporal_confidence,
                'tags': memory.metadata.get('tags', [])
            })
        
        consolidation_prompt = f"""Consolidate these {len(memories)} similar memories into a single, coherent memory.

MEMORIES TO CONSOLIDATE:
{json.dumps(memory_data, indent=2)}

CONSOLIDATION RULES:
1. Preserve the most accurate and complete information
2. Use the highest reliability inference level
3. Combine relevant tags and evidence
4. Resolve any contradictions using temporal order (newer overwrites older)
5. Maintain the essential meaning while avoiding redundancy

Create a consolidated memory that captures all important information while eliminating duplication."""

        try:
            result = llm_service.query_llm(
                prompt=consolidation_prompt,
                temperature=0.3,
                response_format={
                    "type": "object",
                    "properties": {
                        "consolidated_content": {"type": "string"},
                        "inference_level": {"type": "string", "enum": ["stated", "inferred", "implied"]},
                        "evidence": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["consolidated_content", "inference_level", "confidence", "tags"]
                }
            )
            
            if result['success']:
                consolidated_data = json.loads(result['response'])
                
                # Update the primary memory (first in ranked list)
                primary_memory = memories[0]
                primary_memory.content = consolidated_data['consolidated_content']
                
                # Update metadata
                primary_memory.metadata.update({
                    'inference_level': consolidated_data['inference_level'],
                    'evidence': consolidated_data.get('evidence', ''),
                    'confidence': consolidated_data['confidence'],
                    'tags': consolidated_data['tags'],
                    'consolidated_from': [str(m.id) for m in memories[1:]],
                    'consolidation_type': 'llm_guided',
                    'consolidation_reasoning': consolidated_data.get('reasoning', ''),
                    'consolidation_date': timezone.now().isoformat()
                })
                
                # Update confidence based on consolidation
                primary_memory.temporal_confidence = min(
                    1.0, 
                    primary_memory.temporal_confidence * 1.1  # Slight boost for consolidation
                )
                
                # Mark other memories as superseded
                for memory in memories[1:]:
                    memory.is_active = False
                    memory.save()
                    
                primary_memory.save()
                
                logger.info(f"LLM-guided consolidation of {len(memories)} memories into {primary_memory.id}")
                return primary_memory
                
        except Exception as e:
            logger.error(f"LLM-guided consolidation failed: {e}")
            
        # Fallback to automatic merge
        return self._automatic_merge(memories)
    
    def _manual_merge(self, memories: List[Memory]) -> Memory:
        """Manual merge - just marks duplicates as superseded by the primary"""
        primary_memory = memories[0]
        
        # Mark other memories as superseded without changing content
        for memory in memories[1:]:
            memory.is_active = False
            primary_memory.supersedes = memory
            memory.save()
            
        primary_memory.metadata['consolidated_from'] = [str(m.id) for m in memories[1:]]
        primary_memory.metadata['consolidation_type'] = 'manual'
        primary_memory.save()
        
        return primary_memory
    
    def consolidate_user_memories(
        self, 
        user_id: str, 
        strategy: str = "llm_guided",
        limit: int = 100
    ) -> Dict[str, int]:
        """
        Run consolidation process for all memories of a user
        
        Args:
            user_id: User ID to consolidate memories for
            strategy: Consolidation strategy to use
            limit: Maximum number of memories to process
            
        Returns:
            Dictionary with consolidation statistics
        """
        stats = {
            'total_processed': 0,
            'duplicates_found': 0,
            'memories_consolidated': 0,
            'consolidation_groups': 0
        }
        
        # Get active memories for the user, ordered by creation date
        memories = Memory.objects.filter(
            user_id=user_id,
            is_active=True
        ).order_by('-created_at')[:limit]
        
        processed_ids: Set[str] = set()
        
        for memory in memories:
            if str(memory.id) in processed_ids:
                continue
                
            stats['total_processed'] += 1
            
            # Find duplicates for this memory
            duplicates = self.find_duplicates(memory, user_id)
            
            if duplicates:
                stats['duplicates_found'] += len(duplicates)
                
                # Group memory with its duplicates
                duplicate_memories = [memory] + [dup[0] for dup in duplicates]
                
                # Filter out already processed memories
                unprocessed_duplicates = [
                    m for m in duplicate_memories 
                    if str(m.id) not in processed_ids
                ]
                
                if len(unprocessed_duplicates) > 1:
                    # Consolidate the group
                    consolidated = self.merge_memories(unprocessed_duplicates, strategy)
                    
                    if consolidated:
                        stats['consolidation_groups'] += 1
                        stats['memories_consolidated'] += len(unprocessed_duplicates) - 1
                        
                        # Mark all memories in this group as processed
                        for dup_memory in unprocessed_duplicates:
                            processed_ids.add(str(dup_memory.id))
            else:
                processed_ids.add(str(memory.id))
        
        logger.info(f"Consolidation completed for user {user_id}: {stats}")
        return stats
    
    def find_consolidation_candidates(
        self, 
        user_id: str, 
        min_similarity: float = 0.85,
        limit: int = 50
    ) -> List[Tuple[Memory, List[Tuple[Memory, float]]]]:
        """
        Find groups of memories that are candidates for consolidation
        
        Args:
            user_id: User ID to search within
            min_similarity: Minimum similarity threshold
            limit: Maximum number of primary memories to analyze
            
        Returns:
            List of tuples (primary_memory, [(similar_memory, score), ...])
        """
        candidates = []
        
        # Get recent memories that might have duplicates
        recent_memories = Memory.objects.filter(
            user_id=user_id,
            is_active=True,
            created_at__gte=timezone.now() - timedelta(days=30)  # Focus on recent memories
        ).order_by('-created_at')[:limit]
        
        processed_ids: Set[str] = set()
        
        for memory in recent_memories:
            if str(memory.id) in processed_ids:
                continue
                
            duplicates = self.find_duplicates(memory, user_id, min_similarity)
            
            if duplicates:
                # Filter out already processed duplicates
                unprocessed_duplicates = [
                    (dup_memory, score) for dup_memory, score, _ in duplicates
                    if str(dup_memory.id) not in processed_ids
                ]
                
                if unprocessed_duplicates:
                    candidates.append((memory, unprocessed_duplicates))
                    
                    # Mark all memories in this group as processed for this analysis
                    processed_ids.add(str(memory.id))
                    for dup_memory, _ in unprocessed_duplicates:
                        processed_ids.add(str(dup_memory.id))
        
        return candidates

    def _calculate_cosine_similarity(self, embedding1, embedding2) -> float:
        """Calculate cosine similarity between two embeddings"""
        try:
            import numpy as np
            
            # Convert to numpy arrays
            a = np.array(embedding1)
            b = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
                
            return float(dot_product / (norm_a * norm_b))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0


# Global instance
memory_consolidation_service = MemoryConsolidationService()
"""
Conflict Resolution Service for Memory Management

This service handles detection and resolution of conflicting memories,
manages temporal decay of confidence, and ensures consistency in the memory store.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.utils import timezone

from .llm_service import llm_service
from .models import Memory
from .vector_service import vector_service

logger = logging.getLogger(__name__)


class ConflictResolutionService:
    """Service for detecting and resolving conflicts between memories"""
    
    def __init__(self):
        self.conflict_threshold = 0.8  # Similarity threshold for potential conflicts
        self.decay_rate = 0.99  # Monthly decay rate for confidence
        self.decay_period_days = 30  # Period for decay calculation
        
    def detect_conflicts(
        self, 
        new_memory_content: str,
        new_memory_metadata: Dict,
        existing_memories: List[Memory]
    ) -> List[Tuple[Memory, float, str]]:
        """
        Detect memories that potentially conflict with a new memory
        
        Args:
            new_memory_content: Content of the new memory
            new_memory_metadata: Metadata of the new memory
            existing_memories: List of existing memories to check against
            
        Returns:
            List of tuples (conflicting_memory, similarity_score, conflict_type)
        """
        if not existing_memories:
            return []
            
        conflicts = []
        new_fact_type = new_memory_metadata.get('fact_type', 'mutable')
        
        # Only check for conflicts with active memories of the same type
        relevant_memories = [
            m for m in existing_memories 
            if m.is_active and (
                m.fact_type in ['mutable', 'temporal'] or 
                new_fact_type in ['mutable', 'temporal']
            )
        ]
        
        if not relevant_memories:
            return []
            
        # Use LLM to analyze potential conflicts
        conflict_prompt = self._create_conflict_detection_prompt(
            new_memory_content, 
            relevant_memories
        )
        
        try:
            result = llm_service.query_llm(
                prompt=conflict_prompt,
                temperature=0.3,  # Lower temperature for more consistent analysis
                response_format={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "memory_index": {"type": "integer"},
                            "is_conflict": {"type": "boolean"},
                            "conflict_type": {
                                "type": "string",
                                "enum": ["direct_contradiction", "update", "refinement", "partial_overlap"]
                            },
                            "confidence": {"type": "number"},
                            "reasoning": {"type": "string"}
                        },
                        "required": ["memory_index", "is_conflict", "conflict_type", "confidence"]
                    }
                }
            )
            
            if result['success']:
                conflict_data = json.loads(result['response'])
                
                for item in conflict_data:
                    if item['is_conflict'] and item['memory_index'] < len(relevant_memories):
                        memory = relevant_memories[item['memory_index']]
                        conflicts.append((
                            memory,
                            item['confidence'],
                            item['conflict_type']
                        ))
                        
                        logger.info(
                            f"Detected {item['conflict_type']} conflict with memory {memory.id}: {item.get('reasoning', '')}"
                        )
                        
        except Exception as e:
            logger.error(f"Error detecting conflicts with LLM: {e}")
            # Fall back to simple semantic similarity check
            conflicts = self._fallback_conflict_detection(
                new_memory_content,
                relevant_memories
            )
            
        return conflicts
    
    def _create_conflict_detection_prompt(
        self, 
        new_content: str, 
        existing_memories: List[Memory]
    ) -> str:
        """Create prompt for LLM conflict detection"""
        memory_list = []
        for i, memory in enumerate(existing_memories[:20]):  # Limit to prevent token overflow
            memory_list.append(
                f"{i}. {memory.content} (Created: {memory.created_at.strftime('%Y-%m-%d')})"
            )
        
        return f"""Analyze if this new memory conflicts with any existing memories.

NEW MEMORY: {new_content}

EXISTING MEMORIES:
{chr(10).join(memory_list)}

For each existing memory, determine:
1. Is there a conflict? (contradictory information)
2. What type of conflict:
   - direct_contradiction: Mutually exclusive facts
   - update: New information replaces old
   - refinement: More specific/accurate version
   - partial_overlap: Some conflicting elements

Only mark clear conflicts, not just related topics.
Focus on factual contradictions, not just different aspects of the same topic."""
    
    def _fallback_conflict_detection(
        self,
        new_content: str,
        existing_memories: List[Memory]
    ) -> List[Tuple[Memory, float, str]]:
        """Fallback conflict detection using embeddings"""
        conflicts = []
        
        try:
            # Get embedding for new content
            embedding_result = llm_service.get_embeddings([new_content])
            if not embedding_result['success']:
                return conflicts
                
            new_embedding = embedding_result['embeddings'][0]
            
            # Check similarity with existing memories
            for memory in existing_memories:
                if memory.vector_id:
                    # Get similarity from vector DB
                    similarity = vector_service.calculate_similarity(
                        new_embedding,
                        memory.vector_id
                    )
                    
                    if similarity >= self.conflict_threshold:
                        conflicts.append((
                            memory,
                            similarity,
                            "potential_conflict"
                        ))
                        
        except Exception as e:
            logger.error(f"Error in fallback conflict detection: {e}")
            
        return conflicts
    
    def resolve_conflict(
        self,
        new_memory: Memory,
        conflicting_memory: Memory,
        conflict_type: str
    ) -> Memory:
        """
        Resolve conflict between two memories
        
        Args:
            new_memory: The newly created memory
            conflicting_memory: The existing conflicting memory
            conflict_type: Type of conflict detected
            
        Returns:
            The resolved memory (could be new_memory with updates)
        """
        logger.info(
            f"Resolving {conflict_type} between new memory and {conflicting_memory.id}"
        )
        
        if conflict_type == "direct_contradiction":
            # New memory supersedes old for mutable/temporal facts
            if conflicting_memory.fact_type in ['mutable', 'temporal']:
                new_memory.supersedes = conflicting_memory
                conflicting_memory.is_active = False
                conflicting_memory.save()
                
                # Boost confidence for the new memory as it's more recent
                new_memory.original_confidence = max(
                    new_memory.original_confidence,
                    conflicting_memory.original_confidence * 1.1
                )
                new_memory.temporal_confidence = new_memory.original_confidence
                
                logger.info(f"New memory supersedes {conflicting_memory.id}")
                
        elif conflict_type == "update":
            # Mark as an update to the previous memory
            new_memory.supersedes = conflicting_memory
            conflicting_memory.is_active = False
            conflicting_memory.save()
            
            # Inherit some confidence from the previous memory
            new_memory.original_confidence = max(
                new_memory.original_confidence,
                conflicting_memory.original_confidence
            )
            new_memory.temporal_confidence = new_memory.original_confidence
            
        elif conflict_type == "refinement":
            # Keep both but link them
            new_memory.supersedes = conflicting_memory
            # Don't deactivate the old memory for refinements
            
            # Slightly boost confidence as it's a refinement
            new_memory.original_confidence = min(
                1.0,
                new_memory.original_confidence * 1.05
            )
            new_memory.temporal_confidence = new_memory.original_confidence
            
        elif conflict_type == "partial_overlap":
            # Keep both memories active but note the relationship
            # Add reference in metadata
            if 'related_memories' not in new_memory.metadata:
                new_memory.metadata['related_memories'] = []
            new_memory.metadata['related_memories'].append(str(conflicting_memory.id))
            
        new_memory.save()
        return new_memory
    
    def apply_temporal_decay(self, memory: Memory) -> float:
        """
        Calculate and apply temporal confidence decay
        
        Args:
            memory: Memory to calculate decay for
            
        Returns:
            Updated temporal confidence value
        """
        now = timezone.now()
        
        # Use created_at if last_validated is None (for existing memories)
        validation_date = memory.last_validated or memory.created_at
        age_days = (now - validation_date).days
        
        if age_days <= 0:
            return memory.original_confidence
            
        # Calculate decay based on age
        decay_periods = age_days / self.decay_period_days
        decay_factor = self.decay_rate ** decay_periods
        
        # Apply decay but maintain minimum confidence
        temporal_confidence = max(
            0.1,  # Minimum confidence threshold
            memory.original_confidence * decay_factor
        )
        
        # Immutable facts decay slower
        if memory.fact_type == 'immutable':
            temporal_confidence = max(
                temporal_confidence,
                memory.original_confidence * 0.8  # Maintain at least 80% for immutable
            )
            
        memory.temporal_confidence = temporal_confidence
        memory.save()
        
        return temporal_confidence
    
    def validate_memory(self, memory: Memory, validation_source: str = "user_interaction"):
        """
        Validate/refresh a memory, resetting its temporal decay
        
        Args:
            memory: Memory to validate
            validation_source: Source of validation (e.g., "user_interaction", "confirmation")
        """
        memory.last_validated = timezone.now()
        memory.temporal_confidence = memory.original_confidence
        
        # Optionally boost confidence if repeatedly validated
        if validation_source == "user_interaction":
            memory.original_confidence = min(1.0, memory.original_confidence * 1.02)
            memory.temporal_confidence = memory.original_confidence
            
        # Add validation event to metadata
        if 'validations' not in memory.metadata:
            memory.metadata['validations'] = []
            
        memory.metadata['validations'].append({
            'timestamp': timezone.now().isoformat(),
            'source': validation_source
        })
        
        memory.save()
        logger.info(f"Validated memory {memory.id} from {validation_source}")
    
    def batch_apply_decay(self, user_id: str):
        """
        Apply temporal decay to all memories for a user
        
        Args:
            user_id: User ID to process memories for
        """
        active_memories = Memory.objects.filter(
            user_id=user_id,
            is_active=True
        )
        
        updated_count = 0
        for memory in active_memories:
            old_confidence = memory.temporal_confidence
            new_confidence = self.apply_temporal_decay(memory)
            
            if abs(old_confidence - new_confidence) > 0.01:
                updated_count += 1
                
        logger.info(f"Applied temporal decay to {updated_count} memories for user {user_id}")
        
    def get_active_memory_chain(self, memory: Memory) -> List[Memory]:
        """
        Get the chain of memories (superseding relationships)
        
        Args:
            memory: Memory to get chain for
            
        Returns:
            List of memories in chronological order
        """
        chain = []
        
        # Walk backwards to find the original
        current = memory
        while current.supersedes:
            current = current.supersedes
            
        # Now walk forward building the chain
        chain.append(current)
        while True:
            next_memory = Memory.objects.filter(supersedes=current).first()
            if next_memory:
                chain.append(next_memory)
                current = next_memory
            else:
                break
                
        return chain
    
    def consolidate_conflicting_memories(
        self,
        memories: List[Memory]
    ) -> Optional[Memory]:
        """
        Consolidate multiple conflicting memories into a single coherent memory
        
        Args:
            memories: List of conflicting memories to consolidate
            
        Returns:
            Consolidated memory or None if consolidation fails
        """
        if len(memories) < 2:
            return memories[0] if memories else None
            
        # Sort by creation date (newest first)
        sorted_memories = sorted(memories, key=lambda m: m.created_at, reverse=True)
        
        # Use LLM to create consolidated memory
        consolidation_prompt = self._create_consolidation_prompt(sorted_memories)
        
        try:
            result = llm_service.query_llm(
                prompt=consolidation_prompt,
                temperature=0.3,
                response_format={
                    "type": "object",
                    "properties": {
                        "consolidated_content": {"type": "string"},
                        "fact_type": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reasoning": {"type": "string"}
                    },
                    "required": ["consolidated_content", "fact_type", "confidence"]
                }
            )
            
            if result['success']:
                consolidated_data = json.loads(result['response'])
                
                # Create new consolidated memory
                newest_memory = sorted_memories[0]
                newest_memory.content = consolidated_data['consolidated_content']
                newest_memory.fact_type = consolidated_data['fact_type']
                newest_memory.original_confidence = consolidated_data['confidence']
                newest_memory.temporal_confidence = consolidated_data['confidence']
                
                # Mark all older memories as superseded
                for old_memory in sorted_memories[1:]:
                    old_memory.is_active = False
                    old_memory.save()
                    
                newest_memory.save()
                
                logger.info(
                    f"Consolidated {len(memories)} memories into {newest_memory.id}"
                )
                return newest_memory
                
        except Exception as e:
            logger.error(f"Error consolidating memories: {e}")
            
        return None
    
    def _create_consolidation_prompt(self, memories: List[Memory]) -> str:
        """Create prompt for memory consolidation"""
        memory_list = []
        for i, memory in enumerate(memories):
            memory_list.append(
                f"{i + 1}. {memory.content} "
                f"(Created: {memory.created_at.strftime('%Y-%m-%d')}, "
                f"Confidence: {memory.original_confidence:.2f})"
            )
            
        return f"""Consolidate these potentially conflicting memories into a single, accurate memory.

MEMORIES TO CONSOLIDATE:
{chr(10).join(memory_list)}

Create a consolidated memory that:
1. Preserves the most recent and accurate information
2. Resolves any contradictions by using the most recent facts
3. Maintains important context from all memories
4. Identifies the appropriate fact_type (mutable, immutable, or temporal)

Return a single consolidated memory that best represents the current state of this information."""


# Global instance
conflict_resolution_service = ConflictResolutionService()
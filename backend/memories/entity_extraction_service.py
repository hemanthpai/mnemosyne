"""
Entity Extraction Service for Knowledge Graph Construction

This service extracts entities and relationships from conversation text using LLM analysis,
then stores them in the proper entity-relationship knowledge graph structure.
"""

import json
import logging
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime

from django.utils import timezone
from django.db import transaction

from .llm_service import llm_service
from .entity_models import Entity, Relationship, EntityConversationChunk

logger = logging.getLogger(__name__)


class EntityExtractionService:
    """Service for extracting entities and relationships from conversation text"""
    
    def __init__(self):
        # Entity extraction schema for LLM
        self.entity_extraction_schema = {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Canonical name of the entity"},
                            "type": {"type": "string", "enum": [
                                "user", "person", "place", "concept", "object", 
                                "activity", "preference", "skill", "event", "organization", "product"
                            ]},
                            "aliases": {"type": "array", "items": {"type": "string"}, "description": "Alternative names"},
                            "description": {"type": "string", "description": "Brief description"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                        },
                        "required": ["name", "type", "confidence"]
                    }
                },
                "relationships": {
                    "type": "array", 
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_entity": {"type": "string", "description": "Name of source entity"},
                            "target_entity": {"type": "string", "description": "Name of target entity"},
                            "relationship_type": {"type": "string", "enum": [
                                "LOVES", "LIKES", "DISLIKES", "HATES", "PREFERS",
                                "KNOWS", "WORKS_WITH", "FRIENDS_WITH", "FAMILY_OF",
                                "WORKS_AT", "STUDIES_AT", "SKILLED_IN", "LEARNING",
                                "LIVES_IN", "VISITED", "WANTS_TO_VISIT",
                                "DOES", "ENJOYS", "PRACTICES",
                                "USED_TO", "CURRENTLY", "PLANS_TO",
                                "HAS", "DIAGNOSED_WITH", "TREATS_WITH",
                                "RELATED_TO", "PART_OF", "SIMILAR_TO"
                            ]},
                            "temporal_qualifier": {"type": "string", "enum": [
                                "past", "present", "future", "ongoing", "temporary"
                            ], "default": "present"},
                            "strength": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "evidence": {"type": "string", "description": "Supporting text from conversation"}
                        },
                        "required": ["source_entity", "target_entity", "relationship_type", "confidence", "evidence"]
                    }
                }
            },
            "required": ["entities", "relationships"]
        }
        
        # Comprehensive entity extraction prompt - optimized for speed while maintaining completeness
        self.extraction_prompt = """
Extract entities and relationships from this AI-User conversation to enable future context retrieval.

**ENTITIES:** people, places, concepts, skills, preferences, activities, events, organizations
**RELATIONSHIPS:** 
- Preferences: LOVES, LIKES, DISLIKES, HATES, PREFERS
- Social: KNOWS, WORKS_WITH, FRIENDS_WITH, FAMILY_OF  
- Professional: WORKS_AT, STUDIES_AT, SKILLED_IN, LEARNING
- Spatial/Temporal: LIVES_IN, VISITED, WANTS_TO_VISIT, USED_TO, CURRENTLY, PLANS_TO
- Activities: DOES, ENJOYS, PRACTICES
- Medical: HAS, DIAGNOSED_WITH, TREATS_WITH
- Conceptual: RELATED_TO, PART_OF, SIMILAR_TO

**FOCUS AREAS:**
- Medical conditions, diagnoses, treatments (ADHD, anxiety, etc.)
- Learning preferences and styles 
- Knowledge levels in subjects
- Work patterns and productivity preferences
- Research interests and expertise levels
- Communication styles and needs

**EXAMPLES:**
"I have ADHD and find large tasks overwhelming. I need things broken into small steps."
→ User-DIAGNOSED_WITH->ADHD, User-DISLIKES->Large tasks, User-PREFERS->Small steps

"I'm a beginner in quantum physics but have strong math background"
→ User-LEARNING->Quantum physics, User-SKILLED_IN->Mathematics

**TEXT:** {conversation_text}

**OUTPUT:** JSON with entities and relationships arrays as specified in schema.
"""

    def extract_entities_and_relationships(
        self, 
        conversation_text: str, 
        user_id: str,
        timestamp: Optional[str] = None,
        max_chunk_size: int = 2000  # Split large conversations to avoid timeouts
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from conversation text
        
        Args:
            conversation_text: The conversation text to process
            user_id: ID of the user
            timestamp: When the conversation occurred
            
        Returns:
            Dict containing extracted entities, relationships, and metadata
        """
        try:
            if timestamp is None:
                timestamp = timezone.now().isoformat()
            
            # Split large conversations to avoid timeouts
            if len(conversation_text) > max_chunk_size:
                logger.info(f"Large conversation ({len(conversation_text)} chars), processing in chunks")
                return self._extract_from_large_conversation(
                    conversation_text, user_id, timestamp, max_chunk_size
                )
                
            # Prepare the extraction prompt
            formatted_prompt = self.extraction_prompt.format(
                conversation_text=conversation_text
            )
            
            # Call LLM for extraction with extended timeout
            logger.info(f"Extracting entities and relationships from {len(conversation_text)} chars of text")
            
            # Use specific entity extraction timeout if available
            original_timeout = llm_service.settings.extraction_timeout if llm_service.settings else 120
            entity_timeout = getattr(llm_service.settings, 'entity_extraction_timeout', None) if llm_service.settings else None
            extended_timeout = entity_timeout or max(300, original_timeout * 2)  # Use entity timeout or fallback
            
            # Temporarily extend timeout for this operation
            if llm_service.settings:
                old_timeout = llm_service.settings.extraction_timeout
                llm_service.settings.extraction_timeout = extended_timeout
            
            try:
                result = llm_service.query_llm(
                    prompt=formatted_prompt,
                    temperature=0.1,  # Even lower temperature for more consistent extraction
                    response_format=self.entity_extraction_schema
                )
            finally:
                # Restore original timeout
                if llm_service.settings:
                    llm_service.settings.extraction_timeout = old_timeout
            
            if not result.get('success'):
                logger.error(f"Entity extraction failed: {result.get('error')}")
                return {
                    'success': False,
                    'error': result.get('error'),
                    'entities': [],
                    'relationships': []
                }
            
            # Parse the extracted data
            extracted_data = json.loads(result['response'])
            entities_data = extracted_data.get('entities', [])
            relationships_data = extracted_data.get('relationships', [])
            
            logger.info(f"Extracted {len(entities_data)} entities and {len(relationships_data)} relationships")
            
            return {
                'success': True,
                'entities': entities_data,
                'relationships': relationships_data,
                'extraction_metadata': {
                    'timestamp': timestamp,
                    'model_used': result.get('model_used', 'unknown'),
                    'conversation_length': len(conversation_text),
                    'entity_count': len(entities_data),
                    'relationship_count': len(relationships_data)
                }
            }
            
        except Exception as e:
            logger.error(f"Error in entity extraction: {e}")
            return {
                'success': False,
                'error': str(e),
                'entities': [],
                'relationships': []
            }
    
    def store_entities_and_relationships(
        self,
        conversation_text: str,
        user_id: str,
        vector_id: str,
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete pipeline: extract entities/relationships and store in database and graph
        
        Args:
            conversation_text: Original conversation text
            user_id: User ID 
            vector_id: Vector database ID for the conversation chunk
            timestamp: When conversation occurred
            
        Returns:
            Dict containing storage results and created entity/relationship IDs
        """
        try:
            if timestamp is None:
                timestamp = timezone.now().isoformat()
                
            # Parse timestamp
            timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            with transaction.atomic():
                # Step 1: Create conversation chunk record
                chunk = EntityConversationChunk.objects.create(
                    user_id=user_id,
                    content=conversation_text,
                    vector_id=vector_id,
                    timestamp=timestamp_dt,
                    extraction_status='processing'
                )
                
                # Step 2: Extract entities and relationships
                extraction_result = self.extract_entities_and_relationships(
                    conversation_text, user_id, timestamp
                )
                
                if not extraction_result['success']:
                    chunk.extraction_status = 'failed'
                    chunk.extraction_metadata = {'error': extraction_result.get('error')}
                    chunk.save()
                    return extraction_result
                
                # Step 3: Store entities
                created_entities = {}  # name -> Entity object
                entity_ids = []
                
                for entity_data in extraction_result['entities']:
                    entity = self._get_or_create_entity(
                        user_id=user_id,
                        entity_data=entity_data,
                        chunk_id=chunk.id
                    )
                    created_entities[entity_data['name']] = entity
                    entity_ids.append(entity.id)
                
                # Step 4: Store relationships
                relationship_ids = []
                
                for rel_data in extraction_result['relationships']:
                    relationship = self._get_or_create_relationship(
                        user_id=user_id,
                        relationship_data=rel_data,
                        entities_map=created_entities,
                        chunk_id=chunk.id
                    )
                    if relationship:
                        relationship_ids.append(relationship.id)
                
                # Step 5: Update chunk with extraction results
                chunk.extracted_entities = entity_ids
                chunk.extracted_relationships = relationship_ids
                chunk.extraction_status = 'completed'
                chunk.extraction_metadata = extraction_result['extraction_metadata']
                chunk.save()
                
                logger.info(f"Successfully stored {len(entity_ids)} entities and {len(relationship_ids)} relationships")
                
                return {
                    'success': True,
                    'chunk_id': chunk.id,
                    'entity_ids': entity_ids,
                    'relationship_ids': relationship_ids,
                    'entities_created': len(entity_ids),
                    'relationships_created': len(relationship_ids)
                }
                
        except Exception as e:
            logger.error(f"Error storing entities and relationships: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_or_create_entity(self, user_id: str, entity_data: Dict, chunk_id: str) -> Entity:
        """Get existing entity or create new one"""
        name = entity_data['name']
        entity_type = entity_data['type']
        
        # Try to find existing entity
        existing_entity = Entity.objects.filter(
            user_id=user_id,
            name=name,
            entity_type=entity_type
        ).first()
        
        if existing_entity:
            # Update existing entity
            if chunk_id not in existing_entity.conversation_chunk_ids:
                existing_entity.conversation_chunk_ids.append(chunk_id)
            existing_entity.mention_count += 1
            existing_entity.last_mentioned = timezone.now()
            
            # Update aliases if new ones provided
            new_aliases = entity_data.get('aliases', [])
            for alias in new_aliases:
                if alias not in existing_entity.aliases:
                    existing_entity.aliases.append(alias)
                    
            existing_entity.save()
            return existing_entity
        
        # Create new entity
        entity = Entity.objects.create(
            user_id=user_id,
            name=name,
            entity_type=entity_type,
            aliases=entity_data.get('aliases', []),
            description=entity_data.get('description', ''),
            confidence=entity_data.get('confidence', 0.5),
            conversation_chunk_ids=[chunk_id],
            graph_node_id=f"entity_{entity_type}_{name}_{user_id}".replace(' ', '_').lower()
        )
        
        return entity
    
    def _get_or_create_relationship(
        self, 
        user_id: str, 
        relationship_data: Dict, 
        entities_map: Dict[str, Entity],
        chunk_id: str
    ) -> Optional[Relationship]:
        """Get existing relationship or create new one"""
        source_name = relationship_data['source_entity']
        target_name = relationship_data['target_entity']
        rel_type = relationship_data['relationship_type']
        
        # Check if entities exist
        source_entity = entities_map.get(source_name)
        target_entity = entities_map.get(target_name)
        
        if not source_entity or not target_entity:
            logger.warning(f"Missing entities for relationship {source_name}-{rel_type}->{target_name}")
            return None
        
        # Try to find existing relationship
        existing_rel = Relationship.objects.filter(
            user_id=user_id,
            source_entity=source_entity,
            target_entity=target_entity,
            relationship_type=rel_type
        ).first()
        
        if existing_rel:
            # Update existing relationship
            if chunk_id not in existing_rel.conversation_chunk_ids:
                existing_rel.conversation_chunk_ids.append(chunk_id)
            existing_rel.last_confirmed = timezone.now()
            existing_rel.save()
            return existing_rel
        
        # Create new relationship
        relationship = Relationship.objects.create(
            user_id=user_id,
            source_entity=source_entity,
            target_entity=target_entity,
            relationship_type=rel_type,
            temporal_qualifier=relationship_data.get('temporal_qualifier', 'present'),
            strength=relationship_data.get('strength', 0.5),
            confidence=relationship_data.get('confidence', 0.5),
            conversation_chunk_ids=[chunk_id],
            evidence=relationship_data.get('evidence', ''),
            graph_relationship_id=f"rel_{source_entity.id}_{rel_type}_{target_entity.id}".lower()
        )
        
        return relationship
    
    def _extract_from_large_conversation(
        self,
        conversation_text: str,
        user_id: str,
        timestamp: str,
        max_chunk_size: int
    ) -> Dict[str, Any]:
        """
        Process large conversations by splitting into smaller chunks and merging results
        """
        # Split conversation into chunks
        chunks = []
        words = conversation_text.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            if current_size + word_size > max_chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        logger.info(f"Split conversation into {len(chunks)} chunks")
        
        # Process each chunk
        all_entities = []
        all_relationships = []
        
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            
            chunk_result = self.extract_entities_and_relationships(
                conversation_text=chunk,
                user_id=user_id,
                timestamp=timestamp,
                max_chunk_size=max_chunk_size * 2  # Prevent infinite recursion
            )
            
            if chunk_result.get('success'):
                all_entities.extend(chunk_result.get('entities', []))
                all_relationships.extend(chunk_result.get('relationships', []))
        
        # Deduplicate entities by name and type
        seen_entities = set()
        unique_entities = []
        for entity in all_entities:
            entity_key = (entity.get('name', '').lower(), entity.get('type', ''))
            if entity_key not in seen_entities:
                seen_entities.add(entity_key)
                unique_entities.append(entity)
        
        # Deduplicate relationships
        seen_relationships = set()
        unique_relationships = []
        for rel in all_relationships:
            rel_key = (
                rel.get('source_entity', '').lower(),
                rel.get('target_entity', '').lower(),
                rel.get('relationship_type', '')
            )
            if rel_key not in seen_relationships:
                seen_relationships.add(rel_key)
                unique_relationships.append(rel)
        
        logger.info(f"After deduplication: {len(unique_entities)} entities, {len(unique_relationships)} relationships")
        
        return {
            'success': True,
            'entities': unique_entities,
            'relationships': unique_relationships,
            'extraction_metadata': {
                'timestamp': timestamp,
                'conversation_length': len(conversation_text),
                'chunks_processed': len(chunks),
                'entity_count': len(unique_entities),
                'relationship_count': len(unique_relationships)
            }
        }


# Global instance
entity_extraction_service = EntityExtractionService()
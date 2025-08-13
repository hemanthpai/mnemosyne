"""
Entity-Relationship Search Service

This service provides search capabilities over the entity-relationship knowledge graph,
combining vector search for conversation context with graph traversal for knowledge queries.
"""

import logging
from typing import Any, Dict, List, Optional

from .llm_service import llm_service
from .vector_service import vector_service
from .entity_graph_service import entity_graph_service
from .entity_models import Entity, Relationship, EntityConversationChunk

logger = logging.getLogger(__name__)


class EntitySearchService:
    """Enhanced search service for entity-relationship knowledge graph"""
    
    def __init__(self):
        self.search_query_types = {
            'preference': ['LOVES', 'LIKES', 'PREFERS', 'ENJOYS', 'DISLIKES', 'HATES'],
            'skill': ['SKILLED_IN', 'LEARNING', 'PRACTICES'],
            'social': ['KNOWS', 'WORKS_WITH', 'FRIENDS_WITH', 'FAMILY_OF'],
            'professional': ['WORKS_AT', 'STUDIES_AT'],
            'location': ['LIVES_IN', 'VISITED', 'WANTS_TO_VISIT'],
            'activity': ['DOES', 'ENJOYS', 'PRACTICES'],
            'temporal': ['USED_TO', 'CURRENTLY', 'PLANS_TO']
        }
    
    def search_knowledge_graph(
        self,
        query: str,
        user_id: str,
        search_type: str = "auto",
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Primary search method that determines query intent and routes to appropriate search strategy
        
        Args:
            query: Natural language search query
            user_id: User ID to search within
            search_type: Type of search ("auto", "preference", "skill", "social", etc.)
            limit: Maximum number of results
            
        Returns:
            Dict containing search results and metadata
        """
        try:
            logger.info(f"Searching knowledge graph for: '{query}' (user: {user_id}, type: {search_type})")
            
            # Step 1: Classify query intent if auto mode
            if search_type == "auto":
                search_type = self._classify_query_intent(query)
                logger.info(f"Classified query as type: {search_type}")
            
            # Step 2: Route to appropriate search strategy
            if search_type == "preference":
                return self._search_preferences(query, user_id, limit)
            elif search_type == "skill":
                return self._search_skills(query, user_id, limit)
            elif search_type == "social":
                return self._search_social_connections(query, user_id, limit)
            elif search_type == "entity_related":
                return self._search_entity_relationships(query, user_id, limit)
            else:
                # Fallback to hybrid search
                return self._hybrid_search(query, user_id, limit)
                
        except Exception as e:
            logger.error(f"Error in knowledge graph search: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "total_found": 0
            }
    
    def _classify_query_intent(self, query: str) -> str:
        """Classify the intent of a search query"""
        query_lower = query.lower()
        
        # Preference-related keywords
        preference_keywords = [
            'like', 'love', 'prefer', 'favorite', 'interest', 'enjoy', 'hate', 'dislike',
            'passion', 'hobby', 'interests', 'preferences', 'loves', 'likes'
        ]
        
        # Skill-related keywords  
        skill_keywords = [
            'skill', 'ability', 'good at', 'knows how', 'expert', 'learning', 'studying',
            'competent', 'proficient', 'experienced'
        ]
        
        # Social-related keywords
        social_keywords = [
            'friend', 'family', 'colleague', 'relationship', 'knows', 'works with',
            'married', 'dating', 'connected to'
        ]
        
        # Entity-specific keywords
        entity_keywords = [
            'about', 'related to', 'connected to', 'associated with', 'regarding'
        ]
        
        # Check for each category
        if any(keyword in query_lower for keyword in preference_keywords):
            return "preference"
        elif any(keyword in query_lower for keyword in skill_keywords):
            return "skill"
        elif any(keyword in query_lower for keyword in social_keywords):
            return "social"
        elif any(keyword in query_lower for keyword in entity_keywords):
            return "entity_related"
        else:
            return "hybrid"
    
    def _search_preferences(self, query: str, user_id: str, limit: int) -> Dict[str, Any]:
        """Search for user preferences and interests"""
        try:
            # Get preference relationships from graph
            preferences = entity_graph_service.query_user_preferences(
                user_id=user_id,
                preference_types=self.search_query_types['preference']
            )
            
            # Filter preferences based on query if specific terms mentioned
            filtered_preferences = []
            query_terms = query.lower().split()
            
            for pref in preferences[:limit]:
                # Check if query terms match the preference item or evidence
                item_text = f"{pref['item']} {pref.get('evidence', '')}".lower()
                
                if any(term in item_text for term in query_terms) or len(query_terms) <= 2:
                    # Include if query terms found or if it's a general preference query
                    filtered_preferences.append({
                        "type": "preference",
                        "item": pref['item'],
                        "item_type": pref['item_type'],
                        "preference_type": pref['preference_type'],
                        "strength": pref['strength'],
                        "confidence": pref['confidence'],
                        "evidence": pref.get('evidence', ''),
                        "temporal_qualifier": pref.get('temporal_qualifier', 'present')
                    })
            
            return {
                "success": True,
                "search_type": "preference",
                "query": query,
                "results": filtered_preferences,
                "total_found": len(filtered_preferences)
            }
            
        except Exception as e:
            logger.error(f"Error in preference search: {e}")
            return {"success": False, "error": str(e), "results": []}
    
    def _search_skills(self, query: str, user_id: str, limit: int) -> Dict[str, Any]:
        """Search for user skills and competencies"""
        try:
            # Query skill-related relationships
            skills = entity_graph_service.query_user_preferences(
                user_id=user_id,
                preference_types=self.search_query_types['skill']
            )
            
            # Filter and format skill results
            skill_results = []
            query_terms = query.lower().split()
            
            for skill in skills[:limit]:
                item_text = f"{skill['item']} {skill.get('evidence', '')}".lower()
                
                if any(term in item_text for term in query_terms) or len(query_terms) <= 2:
                    skill_results.append({
                        "type": "skill",
                        "skill": skill['item'],
                        "skill_type": skill['item_type'],
                        "relationship": skill['preference_type'],  # SKILLED_IN, LEARNING, etc.
                        "proficiency": skill['strength'],
                        "confidence": skill['confidence'],
                        "evidence": skill.get('evidence', ''),
                        "status": skill.get('temporal_qualifier', 'present')
                    })
            
            return {
                "success": True,
                "search_type": "skill",
                "query": query,
                "results": skill_results,
                "total_found": len(skill_results)
            }
            
        except Exception as e:
            logger.error(f"Error in skill search: {e}")
            return {"success": False, "error": str(e), "results": []}
    
    def _search_social_connections(self, query: str, user_id: str, limit: int) -> Dict[str, Any]:
        """Search for social connections and relationships"""
        try:
            # Query social relationships
            connections = entity_graph_service.query_user_preferences(
                user_id=user_id,
                preference_types=self.search_query_types['social']
            )
            
            # Filter and format social results
            social_results = []
            query_terms = query.lower().split()
            
            for conn in connections[:limit]:
                item_text = f"{conn['item']} {conn.get('evidence', '')}".lower()
                
                if any(term in item_text for term in query_terms) or len(query_terms) <= 2:
                    social_results.append({
                        "type": "social",
                        "person": conn['item'],
                        "person_type": conn['item_type'],
                        "relationship": conn['preference_type'],  # KNOWS, WORKS_WITH, etc.
                        "strength": conn['strength'],
                        "confidence": conn['confidence'],
                        "evidence": conn.get('evidence', ''),
                        "status": conn.get('temporal_qualifier', 'present')
                    })
            
            return {
                "success": True,
                "search_type": "social",
                "query": query,
                "results": social_results,
                "total_found": len(social_results)
            }
            
        except Exception as e:
            logger.error(f"Error in social search: {e}")
            return {"success": False, "error": str(e), "results": []}
    
    def _search_entity_relationships(self, query: str, user_id: str, limit: int) -> Dict[str, Any]:
        """Search for entity relationships and connections"""
        try:
            # Extract potential entity names from query
            entities = self._extract_entities_from_query(query, user_id)
            
            all_results = []
            
            for entity_name in entities:
                # Get relationships for this entity
                connections = entity_graph_service.query_entity_relationships(
                    user_id=user_id,
                    entity_name=entity_name,
                    max_depth=2
                )
                
                for conn in connections:
                    all_results.append({
                        "type": "entity_relationship",
                        "source_entity": conn['start_entity'],
                        "source_type": conn['start_type'],
                        "target_entity": conn['connected_entity'],
                        "target_type": conn['connected_type'],
                        "relationship_chain": conn['relationship_chain'],
                        "path_length": conn['path_length']
                    })
            
            # Sort by path length and relevance
            all_results.sort(key=lambda x: x['path_length'])
            
            return {
                "success": True,
                "search_type": "entity_relationship",
                "query": query,
                "entities_searched": entities,
                "results": all_results[:limit],
                "total_found": len(all_results)
            }
            
        except Exception as e:
            logger.error(f"Error in entity relationship search: {e}")
            return {"success": False, "error": str(e), "results": []}
    
    def _extract_entities_from_query(self, query: str, user_id: str) -> List[str]:
        """Extract entity names mentioned in the query"""
        # Get all entities for this user
        entities = Entity.objects.filter(user_id=user_id)
        
        query_lower = query.lower()
        mentioned_entities = []
        
        for entity in entities:
            # Check if entity name or aliases are mentioned in query
            if entity.name.lower() in query_lower:
                mentioned_entities.append(entity.name)
            else:
                # Check aliases
                for alias in entity.aliases:
                    if alias.lower() in query_lower:
                        mentioned_entities.append(entity.name)
                        break
        
        return mentioned_entities
    
    def _hybrid_search(self, query: str, user_id: str, limit: int) -> Dict[str, Any]:
        """Fallback hybrid search using both vector and graph"""
        try:
            # Step 1: Vector search for relevant conversation chunks
            embedding_result = llm_service.get_embeddings([query])
            if not embedding_result["success"]:
                return {"success": False, "error": "Failed to get query embedding"}
            
            query_embedding = embedding_result["embeddings"][0]
            
            # Search conversation chunks
            conversation_results = vector_service.search_conversation_context(
                query_embedding=query_embedding,
                user_id=user_id,
                limit=limit * 2,
                score_threshold=0.5
            )
            
            # Step 2: Get entities and relationships from matching chunks
            chunk_ids = [result["chunk_id"] for result in conversation_results]
            
            if not chunk_ids:
                return {
                    "success": True,
                    "search_type": "hybrid",
                    "query": query,
                    "results": [],
                    "total_found": 0,
                    "message": "No relevant conversation chunks found"
                }
            
            # Find entities and relationships linked to these chunks
            entities = Entity.objects.filter(
                user_id=user_id,
                conversation_chunk_ids__overlap=chunk_ids
            )
            
            relationships = Relationship.objects.filter(
                user_id=user_id,
                conversation_chunk_ids__overlap=chunk_ids,
                is_active=True
            )
            
            # Combine results
            results = []
            
            # Add entity results
            for entity in entities[:limit//2]:
                results.append({
                    "type": "entity",
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "confidence": entity.confidence,
                    "mention_count": entity.mention_count
                })
            
            # Add relationship results  
            for rel in relationships[:limit//2]:
                results.append({
                    "type": "relationship",
                    "source": rel.source_entity.name,
                    "target": rel.target_entity.name,
                    "relationship_type": rel.relationship_type,
                    "strength": rel.strength,
                    "confidence": rel.confidence,
                    "evidence": rel.evidence,
                    "temporal_qualifier": rel.temporal_qualifier
                })
            
            return {
                "success": True,
                "search_type": "hybrid",
                "query": query,
                "results": results,
                "total_found": len(results),
                "conversation_chunks_found": len(chunk_ids)
            }
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return {"success": False, "error": str(e), "results": []}
    
    def get_user_knowledge_summary(self, user_id: str) -> Dict[str, Any]:
        """Get a comprehensive summary of user's knowledge graph"""
        try:
            # Get graph statistics
            stats = entity_graph_service.get_graph_statistics(user_id)
            
            # Get top preferences
            preferences = entity_graph_service.query_user_preferences(user_id)[:10]
            
            # Get entity counts by type
            entity_counts = Entity.objects.filter(user_id=user_id).values('entity_type').distinct()
            
            return {
                "success": True,
                "user_id": user_id,
                "statistics": stats,
                "top_preferences": preferences,
                "entity_distribution": dict(entity_counts),
                "total_conversation_chunks": EntityConversationChunk.objects.filter(user_id=user_id).count()
            }
            
        except Exception as e:
            logger.error(f"Error getting knowledge summary: {e}")
            return {"success": False, "error": str(e)}


# Global instance
entity_search_service = EntitySearchService()
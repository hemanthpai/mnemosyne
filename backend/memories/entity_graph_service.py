"""
Entity-Relationship Graph Service

This service manages the Neo4j knowledge graph using proper entity-relationship modeling
instead of memory-to-memory relationships.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from django.conf import settings
from neo4j import GraphDatabase

from .entity_models import Entity, Relationship

logger = logging.getLogger(__name__)


class EntityGraphService:
    """Service for managing entity-relationship knowledge graph in Neo4j"""
    
    def __init__(self):
        self.driver = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """Initialize Neo4j connection"""
        try:
            # Get Neo4j connection parameters
            neo4j_uri = getattr(
                settings, "NEO4J_URI", os.getenv("NEO4J_URI", "neo4j://localhost:7687")
            )
            neo4j_username = getattr(
                settings, "NEO4J_USERNAME", os.getenv("NEO4J_USERNAME", "neo4j")
            )
            neo4j_password = getattr(
                settings, "NEO4J_PASSWORD", os.getenv("NEO4J_PASSWORD", "password")
            )

            logger.info(f"Connecting to Neo4j at: {neo4j_uri}")

            # Initialize Neo4j driver
            self.driver = GraphDatabase.driver(
                neo4j_uri, auth=(neo4j_username, neo4j_password)
            )

            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")

            logger.info("Entity graph service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Neo4j connection: {e}")
            self.driver = None
    
    def health_check(self) -> Dict[str, Any]:
        """Check the health of the Neo4j connection"""
        try:
            if not self.driver:
                return {"healthy": False, "error": "Neo4j driver not initialized"}

            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()

                if record and record["test"] == 1:
                    return {"healthy": True, "message": "Neo4j connection is healthy"}
                else:
                    return {"healthy": False, "error": "Unexpected response from Neo4j"}

        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return {"healthy": False, "error": str(e)}
    
    def create_entity_node(self, entity: Entity) -> Dict[str, Any]:
        """Create or update an entity node in the graph"""
        try:
            if not self.driver:
                return {"success": False, "error": "Neo4j driver not initialized"}
            
            with self.driver.session() as session:
                # Create entity node with proper label
                entity_label = entity.entity_type.title()
                
                query = f"""
                MERGE (e:{entity_label} {{entity_id: $entity_id, user_id: $user_id}})
                SET e.name = $name,
                    e.canonical_name = $name,
                    e.entity_type = $entity_type,
                    e.description = $description,
                    e.confidence = $confidence,
                    e.aliases = $aliases,
                    e.mention_count = $mention_count,
                    e.first_mentioned = $first_mentioned,
                    e.last_mentioned = $last_mentioned,
                    e.created_at = datetime($created_at),
                    e.updated_at = datetime()
                RETURN e
                """
                
                result = session.run(query, {
                    "entity_id": str(entity.id),
                    "user_id": str(entity.user_id),
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "confidence": entity.confidence,
                    "aliases": entity.aliases,
                    "mention_count": entity.mention_count,
                    "first_mentioned": entity.first_mentioned.isoformat(),
                    "last_mentioned": entity.last_mentioned.isoformat(),
                    "created_at": entity.created_at.isoformat()
                })
                
                node = result.single()
                if node:
                    logger.info(f"Created/updated entity node: {entity.name} ({entity.entity_type})")
                    return {"success": True, "node_id": str(entity.id)}
                else:
                    return {"success": False, "error": "Failed to create entity node"}
                    
        except Exception as e:
            logger.error(f"Error creating entity node for {entity.name}: {e}")
            return {"success": False, "error": str(e)}
    
    def create_relationship_edge(self, relationship: Relationship) -> Dict[str, Any]:
        """Create or update a relationship edge in the graph"""
        try:
            if not self.driver:
                return {"success": False, "error": "Neo4j driver not initialized"}
            
            with self.driver.session() as session:
                # Get entity labels for the query
                source_label = relationship.source_entity.entity_type.title()
                target_label = relationship.target_entity.entity_type.title()
                rel_type = relationship.relationship_type
                
                query = f"""
                MATCH (source:{source_label} {{entity_id: $source_id, user_id: $user_id}})
                MATCH (target:{target_label} {{entity_id: $target_id, user_id: $user_id}})
                MERGE (source)-[r:{rel_type}]->(target)
                SET r.relationship_id = $relationship_id,
                    r.strength = $strength,
                    r.confidence = $confidence,
                    r.temporal_qualifier = $temporal_qualifier,
                    r.evidence = $evidence,
                    r.established_at = datetime($established_at),
                    r.last_confirmed = datetime($last_confirmed),
                    r.is_active = $is_active,
                    r.created_at = datetime($created_at),
                    r.updated_at = datetime()
                RETURN r
                """
                
                result = session.run(query, {
                    "source_id": str(relationship.source_entity.id),
                    "target_id": str(relationship.target_entity.id),
                    "user_id": str(relationship.user_id),
                    "relationship_id": str(relationship.id),
                    "strength": relationship.strength,
                    "confidence": relationship.confidence,
                    "temporal_qualifier": relationship.temporal_qualifier,
                    "evidence": relationship.evidence,
                    "established_at": relationship.established_at.isoformat(),
                    "last_confirmed": relationship.last_confirmed.isoformat(),
                    "is_active": relationship.is_active,
                    "created_at": relationship.created_at.isoformat()
                })
                
                edge = result.single()
                if edge:
                    logger.info(f"Created/updated relationship: {relationship.source_entity.name} -{rel_type}-> {relationship.target_entity.name}")
                    return {"success": True, "relationship_id": str(relationship.id)}
                else:
                    return {"success": False, "error": "Failed to create relationship edge"}
                    
        except Exception as e:
            logger.error(f"Error creating relationship edge: {e}")
            return {"success": False, "error": str(e)}
    
    def build_user_knowledge_graph(self, user_id: str, incremental: bool = True) -> Dict[str, Any]:
        """Build complete knowledge graph for a user"""
        try:
            if not self.driver:
                return {"success": False, "error": "Neo4j driver not initialized"}
            
            logger.info(f"Building knowledge graph for user {user_id} (incremental: {incremental})")
            
            # Get all entities for the user
            entities = Entity.objects.filter(user_id=user_id)
            relationships = Relationship.objects.filter(user_id=user_id, is_active=True)
            
            logger.info(f"Processing {entities.count()} entities and {relationships.count()} relationships")
            
            nodes_created = 0
            edges_created = 0
            
            # Create entity nodes
            for entity in entities:
                result = self.create_entity_node(entity)
                if result.get('success'):
                    nodes_created += 1
                else:
                    logger.warning(f"Failed to create node for entity {entity.name}: {result.get('error')}")
            
            # Create relationship edges
            for relationship in relationships:
                result = self.create_relationship_edge(relationship)
                if result.get('success'):
                    edges_created += 1
                else:
                    logger.warning(f"Failed to create edge for relationship {relationship}: {result.get('error')}")
            
            return {
                "success": True,
                "user_id": user_id,
                "nodes_created": nodes_created,
                "edges_created": edges_created,
                "total_entities": entities.count(),
                "total_relationships": relationships.count()
            }
            
        except Exception as e:
            logger.error(f"Error building knowledge graph for user {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def query_user_preferences(self, user_id: str, preference_types: List[str] = None) -> List[Dict[str, Any]]:
        """Query user preferences and interests"""
        try:
            if not self.driver:
                return []
            
            if preference_types is None:
                preference_types = ["LOVES", "LIKES", "PREFERS", "ENJOYS"]
            
            with self.driver.session() as session:
                query = """
                MATCH (user:User {user_id: $user_id})-[r]->(target)
                WHERE type(r) IN $preference_types
                RETURN target.name as item,
                       target.entity_type as item_type,
                       type(r) as preference_type,
                       r.strength as strength,
                       r.confidence as confidence,
                       r.temporal_qualifier as temporal_qualifier,
                       r.evidence as evidence
                ORDER BY r.strength DESC, r.confidence DESC
                """
                
                result = session.run(query, {
                    "user_id": user_id,
                    "preference_types": preference_types
                })
                
                preferences = []
                for record in result:
                    preferences.append({
                        "item": record["item"],
                        "item_type": record["item_type"], 
                        "preference_type": record["preference_type"],
                        "strength": record["strength"],
                        "confidence": record["confidence"],
                        "temporal_qualifier": record["temporal_qualifier"],
                        "evidence": record["evidence"]
                    })
                
                logger.info(f"Found {len(preferences)} preferences for user {user_id}")
                return preferences
                
        except Exception as e:
            logger.error(f"Error querying user preferences: {e}")
            return []
    
    def query_entity_relationships(self, user_id: str, entity_name: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Query all relationships for a specific entity"""
        try:
            if not self.driver:
                return []
            
            with self.driver.session() as session:
                query = f"""
                MATCH path = (start {{name: $entity_name, user_id: $user_id}})-[r*1..{max_depth}]-(connected {{user_id: $user_id}})
                RETURN path,
                       start.name as start_entity,
                       start.entity_type as start_type,
                       connected.name as connected_entity,
                       connected.entity_type as connected_type,
                       [rel in relationships(path) | {{
                           type: type(rel),
                           strength: rel.strength,
                           confidence: rel.confidence,
                           temporal_qualifier: rel.temporal_qualifier
                       }}] as relationship_chain
                ORDER BY length(path), connected.name
                """
                
                result = session.run(query, {
                    "entity_name": entity_name,
                    "user_id": user_id
                })
                
                connections = []
                for record in result:
                    connections.append({
                        "start_entity": record["start_entity"],
                        "start_type": record["start_type"],
                        "connected_entity": record["connected_entity"],
                        "connected_type": record["connected_type"],
                        "relationship_chain": record["relationship_chain"],
                        "path_length": len(record["relationship_chain"])
                    })
                
                return connections
                
        except Exception as e:
            logger.error(f"Error querying entity relationships for {entity_name}: {e}")
            return []
    
    def get_graph_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about the user's knowledge graph"""
        try:
            if not self.driver:
                return {"error": "Neo4j driver not initialized"}
            
            with self.driver.session() as session:
                # Count entities by type
                entity_query = """
                MATCH (n {user_id: $user_id})
                RETURN labels(n) as labels, count(n) as count
                """
                
                entity_result = session.run(entity_query, {"user_id": user_id})
                entity_counts = {}
                total_entities = 0
                
                for record in entity_result:
                    labels = record["labels"]
                    count = record["count"]
                    if labels:  # Skip nodes without labels
                        label = labels[0]  # Take first label
                        entity_counts[label] = count
                        total_entities += count
                
                # Count relationships by type
                rel_query = """
                MATCH ()-[r]-() 
                WHERE r.user_id = $user_id
                RETURN type(r) as relationship_type, count(r) as count
                """
                
                rel_result = session.run(rel_query, {"user_id": user_id})
                relationship_counts = {}
                total_relationships = 0
                
                for record in rel_result:
                    rel_type = record["relationship_type"]
                    count = record["count"]
                    relationship_counts[rel_type] = count
                    total_relationships += count
                
                return {
                    "user_id": user_id,
                    "total_entities": total_entities,
                    "total_relationships": total_relationships,
                    "entity_types": entity_counts,
                    "relationship_types": relationship_counts
                }
                
        except Exception as e:
            logger.error(f"Error getting graph statistics: {e}")
            return {"error": str(e)}
    
    def clear_user_graph(self, user_id: str) -> Dict[str, Any]:
        """Clear all graph data for a specific user"""
        try:
            if not self.driver:
                return {"success": False, "error": "Neo4j driver not initialized"}
            
            with self.driver.session() as session:
                # Delete all nodes and relationships for the user
                query = """
                MATCH (n {user_id: $user_id})
                DETACH DELETE n
                RETURN count(n) as deleted_count
                """
                
                result = session.run(query, {"user_id": user_id})
                deleted_count = result.single()["deleted_count"]
                
                logger.info(f"Cleared {deleted_count} nodes from graph for user {user_id}")
                
                return {
                    "success": True,
                    "deleted_nodes": deleted_count,
                    "user_id": user_id
                }
                
        except Exception as e:
            logger.error(f"Error clearing user graph: {e}")
            return {"success": False, "error": str(e)}
    
    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")


# Global instance
entity_graph_service = EntityGraphService()
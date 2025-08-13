import logging
import os
import time
from typing import Any, Dict, List

from django.conf import settings
from langchain_core.documents import Document
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_neo4j import Neo4jGraph
from neo4j import GraphDatabase

from .llm_service import llm_service

logger = logging.getLogger(__name__)


class GraphService:
    """
    Service class for Neo4j graph database operations and LLM graph transformation
    """

    def __init__(self):
        self.driver = None
        self.graph = None
        self.transformer = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize Neo4j connection and LLM graph transformer"""
        try:
            # Get Neo4j connection parameters from settings or environment
            neo4j_uri = getattr(
                settings, "NEO4J_URI", os.getenv("NEO4J_URI", "neo4j://localhost:7687")
            )
            neo4j_username = getattr(
                settings, "NEO4J_USERNAME", os.getenv("NEO4J_USERNAME", "neo4j")
            )
            neo4j_password = getattr(
                settings, "NEO4J_PASSWORD", os.getenv("NEO4J_PASSWORD", "password")
            )

            logger.info(f"Neo4J URI: {neo4j_uri}")

            # Initialize Neo4j driver
            self.driver = GraphDatabase.driver(
                neo4j_uri, auth=(neo4j_username, neo4j_password)
            )

            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")

            # Initialize LangChain Neo4j graph
            self.graph = Neo4jGraph(
                url=neo4j_uri, username=neo4j_username, password=neo4j_password
            )

            # Initialize LLM Graph Transformer
            self._initialize_transformer()

            logger.info("Neo4j graph service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Neo4j connection: {e}")
            self.driver = None
            self.graph = None
            self.transformer = None

    def _initialize_transformer(self):
        """Initialize the LLM Graph Transformer with ChatOpenAI"""
        try:
            from langchain_openai import ChatOpenAI

            # Get LLM settings from the existing service
            if not llm_service.settings:
                logger.error("LLM settings not available for graph transformer")
                self.transformer = None
                return

            settings = llm_service.settings

            # Initialize ChatOpenAI with the same settings as the LLM service
            # For Ollama, we need to add /v1 to the base URL for OpenAI compatibility
            base_url = settings.extraction_endpoint_url
            if settings.extraction_provider_type == "ollama":
                base_url = f"{base_url.rstrip('/')}/v1"

            chat_llm = ChatOpenAI(
                base_url=base_url,
                api_key=(
                    None
                    if not getattr(settings, "extraction_endpoint_api_key", "None")
                    else __import__("pydantic").SecretStr(
                        getattr(settings, "extraction_endpoint_api_key")
                    )
                ),
                model=settings.extraction_model,
                temperature=0.1,  # Lower temperature for more consistent graph extraction
                max_completion_tokens=4000,
            )

            # Initialize the transformer with ChatOpenAI (no restrictions for testing)
            self.transformer = LLMGraphTransformer(llm=chat_llm)

            logger.info(
                "LLM Graph Transformer initialized successfully with ChatOpenAI"
            )

        except Exception as e:
            logger.error(f"Failed to initialize LLM Graph Transformer: {e}")
            self.transformer = None

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

    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the Neo4j database"""
        try:
            if not self.driver:
                return {"error": "Neo4j driver not initialized"}

            with self.driver.session() as session:
                # Get node counts
                node_result = session.run("MATCH (n) RETURN COUNT(n) as node_count")
                node_count = node_result.single()["node_count"]

                # Get relationship counts
                rel_result = session.run(
                    "MATCH ()-[r]->() RETURN COUNT(r) as rel_count"
                )
                rel_count = rel_result.single()["rel_count"]

                # Get node types
                label_result = session.run("CALL db.labels()")
                labels = [record["label"] for record in label_result]

                # Get relationship types
                type_result = session.run("CALL db.relationshipTypes()")
                relationship_types = [
                    record["relationshipType"] for record in type_result
                ]

                return {
                    "node_count": node_count,
                    "relationship_count": rel_count,
                    "node_types": labels,
                    "relationship_types": relationship_types,
                }

        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}

    def text_to_graph(self, text: str, user_id: str) -> Dict[str, Any]:
        """
        DEPRECATED: This method is deprecated in favor of memory-focused graph construction.
        Use build_memory_graph() instead which operates on structured memory data.
        
        Convert text to graph documents and store in Neo4j

        Args:
            text: The input text to convert
            user_id: The user ID for context

        Returns:
            Dict containing success status and extraction results
        """
        logger.warning("text_to_graph() is deprecated. Use build_memory_graph() for new conversation-based architecture.")
        return {
            "success": False,
            "error": "text_to_graph() is deprecated. Use memory-based graph construction instead.",
            "deprecated": True
        }

    def query_graph(self, query: str) -> Dict[str, Any]:
        """
        Execute a Cypher query against the graph database

        Args:
            query: Cypher query string

        Returns:
            Dict containing query results
        """
        try:
            if not self.driver:
                return {"success": False, "error": "Neo4j driver not initialized"}

            with self.driver.session() as session:
                result = session.run(query)  # type: ignore
                records = [record.data() for record in result]

                return {"success": True, "results": records, "count": len(records)}

        except Exception as e:
            logger.error(f"Graph query failed: {e}")
            return {"success": False, "error": str(e)}

    def get_user_graph_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get graph statistics for a specific user

        Args:
            user_id: The user ID

        Returns:
            Dict containing user-specific graph statistics
        """
        try:
            if not self.driver:
                return {"error": "Neo4j driver not initialized"}
            
            # Convert UUID to string if needed
            user_id = str(user_id)

            with self.driver.session() as session:
                # Get nodes created by this user
                node_query = """
                MATCH (n)
                WHERE n.user_id = $user_id
                RETURN COUNT(n) as node_count, COLLECT(DISTINCT labels(n)) as node_types
                """
                node_result = session.run(node_query, user_id=user_id)
                node_data = node_result.single()

                # Get relationships involving user's nodes
                rel_query = """
                MATCH (n)-[r]->(m)
                WHERE n.user_id = $user_id OR m.user_id = $user_id
                RETURN COUNT(r) as rel_count, COLLECT(DISTINCT type(r)) as rel_types
                """
                rel_result = session.run(rel_query, user_id=user_id)
                rel_data = rel_result.single()

                return {
                    "user_id": user_id,
                    "node_count": node_data["node_count"] if node_data else 0,
                    "relationship_count": rel_data["rel_count"] if rel_data else 0,
                    "node_types": node_data["node_types"] if node_data else [],
                    "relationship_types": rel_data["rel_types"] if rel_data else [],
                }

        except Exception as e:
            logger.error(f"Failed to get user graph stats: {e}")
            return {"error": str(e)}

    def clear_user_graph(self, user_id: str) -> Dict[str, Any]:
        """
        Clear all graph data for a specific user

        Args:
            user_id: The user ID

        Returns:
            Dict containing deletion results
        """
        try:
            if not self.driver:
                return {"success": False, "error": "Neo4j driver not initialized"}
            
            # Convert UUID to string if needed
            user_id = str(user_id)

            with self.driver.session() as session:
                # Delete all nodes and relationships for the user
                query = """
                MATCH (n)
                WHERE n.user_id = $user_id
                DETACH DELETE n
                RETURN COUNT(n) as deleted_count
                """
                result = session.run(query, user_id=user_id)
                deleted_count = result.single()["deleted_count"]

                return {
                    "success": True,
                    "deleted_nodes": deleted_count,
                    "user_id": user_id,
                }

        except Exception as e:
            logger.error(f"Failed to clear user graph: {e}")
            return {"success": False, "error": str(e)}

    def build_memory_graph(
        self, user_id: str, incremental: bool = True
    ) -> Dict[str, Any]:
        """
        Build relationship graph for user's memories using semantic connections

        Args:
            user_id: User ID to build graph for
            incremental: If True, only process new memories since last build

        Returns:
            Dict containing graph building results
        """
        try:
            if not self.driver:
                return {"success": False, "error": "Neo4j driver not initialized"}
            
            # Convert UUID to string if needed
            user_id = str(user_id)

            from settings_app.models import LLMSettings

            from .models import Memory

            # Get settings to check last build time
            settings = LLMSettings.get_settings()

            # Determine which memories to process
            if incremental and settings.graph_last_build:
                # Only process memories created/modified after last build
                memories = Memory.objects.filter(
                    user_id=user_id,
                    is_active=True,
                    created_at__gt=settings.graph_last_build,
                )
                logger.info(
                    f"Incremental build: processing memories created after {settings.graph_last_build}"
                )
            else:
                # Full rebuild - process all memories
                memories = Memory.objects.filter(user_id=user_id, is_active=True)
                logger.info("Full build: processing all active memories")

            memory_count = memories.count()
            if memory_count == 0:
                return {
                    "success": True,
                    "message": "No memories to process",
                    "nodes_created": 0,
                    "relationships_created": 0,
                    "incremental": incremental,
                }
            
            # Even with 1 memory, we should create the node for future relationships
            logger.info(
                f"Building memory graph for {memory_count} memories of user {user_id}"
            )

            nodes_created = 0
            relationships_created = 0

            with self.driver.session() as session:
                # Create memory nodes with enhanced metadata
                for memory in memories:
                    # Get standardized metadata
                    metadata = memory.get_standardized_metadata()
                    
                    # Create memory node with rich properties for graph traversal
                    node_query = """
                    MERGE (m:Memory {memory_id: $memory_id, user_id: $user_id})
                    SET m.content = $content,
                        m.created_at = $created_at,
                        m.inference_level = $inference_level,
                        m.temporal_confidence = $temporal_confidence,
                        m.tags = $tags,
                        m.fact_type = $fact_type,
                        m.entity_type = $entity_type,
                        m.evidence = $evidence,
                        m.last_validated = $last_validated,
                        m.is_active = $is_active
                    """

                    session.run(
                        node_query,
                        {
                            "memory_id": str(memory.id),
                            "user_id": user_id,
                            "content": memory.content,
                            "created_at": memory.created_at.isoformat(),
                            "inference_level": metadata.get("inference_level", "stated"),
                            "temporal_confidence": memory.temporal_confidence,
                            "tags": metadata.get("tags", []),
                            "fact_type": memory.fact_type or "mutable",
                            "entity_type": metadata.get("entity_type", "general"),
                            "evidence": metadata.get("evidence", ""),
                            "last_validated": memory.last_validated.isoformat() if memory.last_validated else None,
                            "is_active": memory.is_active,
                        },
                    )
                    nodes_created += 1

                # Create enhanced memory-to-memory relationships
                from .llm_service import llm_service
                from .vector_service import vector_service

                # Build relationship map
                relationships_created += self._create_enhanced_relationships(
                    session, memories, user_id
                )

                # Create tag-based relationships
                memories_with_tags = [
                    (m, m.metadata.get("tags", []))
                    for m in memories
                    if m.metadata.get("tags")
                ]

                for i, (memory1, tags1) in enumerate(memories_with_tags):
                    for memory2, tags2 in memories_with_tags[i + 1 :]:
                        if memory1.id != memory2.id:
                            # Find common tags
                            common_tags = set(tags1) & set(tags2)
                            if common_tags:
                                rel_query = """
                                MATCH (m1:Memory {memory_id: $memory1_id, user_id: $user_id})
                                MATCH (m2:Memory {memory_id: $memory2_id, user_id: $user_id})
                                MERGE (m1)-[r:RELATED_BY_TAG]-(m2)
                                SET r.common_tags = $common_tags,
                                    r.connection_type = 'tag_based',
                                    r.strength = $strength,
                                    r.created_at = datetime()
                                """

                                strength = len(common_tags) / max(
                                    len(tags1), len(tags2)
                                )

                                session.run(
                                    rel_query,
                                    {
                                        "memory1_id": str(memory1.id),
                                        "memory2_id": str(memory2.id),
                                        "user_id": user_id,
                                        "common_tags": list(common_tags),
                                        "strength": strength,
                                    },
                                )
                                relationships_created += 1

                # Create temporal relationships (for sequential memories)
                temporal_memories = memories.order_by("created_at")
                for i in range(len(temporal_memories) - 1):
                    current = temporal_memories[i]
                    next_mem = temporal_memories[i + 1]

                    # Only create temporal links if memories are close in time (within 24 hours)
                    time_diff = (
                        next_mem.created_at - current.created_at
                    ).total_seconds()
                    if time_diff < 86400:  # 24 hours
                        rel_query = """
                        MATCH (m1:Memory {memory_id: $memory1_id, user_id: $user_id})
                        MATCH (m2:Memory {memory_id: $memory2_id, user_id: $user_id})
                        MERGE (m1)-[r:TEMPORAL_SEQUENCE]->(m2)
                        SET r.time_difference = $time_diff,
                            r.connection_type = 'temporal',
                            r.created_at = datetime()
                        """

                        session.run(
                            rel_query,
                            {
                                "memory1_id": str(current.id),
                                "memory2_id": str(next_mem.id),
                                "user_id": user_id,
                                "time_diff": time_diff,
                            },
                        )
                        relationships_created += 1

            logger.info(
                f"Built memory graph: {nodes_created} nodes, {relationships_created} relationships"
            )

            # Update settings with successful build timestamp
            from django.utils import timezone

            settings.graph_last_build = timezone.now()
            settings.graph_build_status = "built"
            settings.save()

            return {
                "success": True,
                "nodes_created": nodes_created,
                "relationships_created": relationships_created,
                "incremental": incremental,
                "user_id": user_id,
            }

        except Exception as e:
            logger.error(f"Failed to build memory graph: {e}")

            # Update settings with failed build status
            try:
                from settings_app.models import LLMSettings

                settings = LLMSettings.get_settings()
                settings.graph_build_status = "failed"
                settings.save()
            except Exception as settings_error:
                logger.error(f"Failed to update build status: {settings_error}")

            return {"success": False, "error": str(e)}

    def traverse_related_memories(
        self, memory_id: str, user_id: str, depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get related memories through graph traversal

        Args:
            memory_id: Starting memory ID
            user_id: User ID for filtering
            depth: Maximum traversal depth

        Returns:
            List of related memory data with relationship information
        """
        try:
            if not self.driver:
                return []
            
            # Convert UUIDs to strings if needed
            user_id = str(user_id)
            memory_id = str(memory_id)

            with self.driver.session() as session:
                # Multi-hop traversal query with relationship strength
                query = (
                    """
                MATCH path = (start:Memory {memory_id: $memory_id, user_id: $user_id})
                -[r*1.."""
                    + str(depth)
                    + """]-
                (related:Memory {user_id: $user_id})
                WHERE start <> related
                WITH related, r, 
                     CASE 
                         WHEN any(rel IN r WHERE type(rel) = 'SIMILAR_TO') THEN 1.0
                         WHEN any(rel IN r WHERE type(rel) = 'RELATED_BY_TAG') THEN 0.8  
                         WHEN any(rel IN r WHERE type(rel) = 'TEMPORAL_SEQUENCE') THEN 0.6
                         ELSE 0.5
                     END as base_score,
                     length(path) as path_length,
                     [rel IN r | {type: type(rel), properties: properties(rel)}] as relationships
                RETURN DISTINCT 
                       related.memory_id as memory_id,
                       related.content as content,
                       related.inference_level as inference_level,
                       related.confidence as confidence,
                       related.tags as tags,
                       related.fact_type as fact_type,
                       related.created_at as created_at,
                       base_score / path_length as relevance_score,
                       path_length,
                       relationships
                ORDER BY relevance_score DESC, related.confidence DESC
                LIMIT 50
                """
                )

                result = session.run(
                    query, {"memory_id": memory_id, "user_id": user_id}
                )

                related_memories = []
                for record in result:
                    related_memories.append(
                        {
                            "memory_id": record["memory_id"],
                            "content": record["content"],
                            "inference_level": record["inference_level"],
                            "confidence": record["confidence"],
                            "tags": record["tags"],
                            "fact_type": record["fact_type"],
                            "created_at": record["created_at"],
                            "relevance_score": record["relevance_score"],
                            "path_length": record["path_length"],
                            "relationships": record["relationships"],
                        }
                    )

                logger.info(
                    f"Found {len(related_memories)} related memories for {memory_id}"
                )
                return related_memories

        except Exception as e:
            logger.error(f"Failed to traverse related memories: {e}")
            return []

    def get_memory_clusters(self, user_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identify memory clusters/topics using community detection

        Args:
            user_id: User ID to analyze

        Returns:
            Dict of clusters with their memories
        """
        try:
            if not self.driver:
                return {}
            
            # Convert UUID to string if needed
            user_id = str(user_id)

            with self.driver.session() as session:
                # Use Louvain community detection algorithm
                community_query = """
                CALL gds.graph.project(
                    'memoryGraph_' + $user_id,
                    {Memory: {properties: ['confidence']}},
                    {
                        SIMILAR_TO: {orientation: 'UNDIRECTED', properties: ['similarity_score']},
                        RELATED_BY_TAG: {orientation: 'UNDIRECTED', properties: ['strength']},
                        TEMPORAL_SEQUENCE: {orientation: 'DIRECTED'}
                    },
                    {nodeQuery: 'MATCH (n:Memory) WHERE n.user_id = "' + $user_id + '" RETURN id(n) AS id', 
                     relationshipQuery: 'MATCH (n:Memory)-[r]-(m:Memory) WHERE n.user_id = "' + $user_id + '" AND m.user_id = "' + $user_id + '" RETURN id(n) AS source, id(m) AS target, type(r) AS type'}
                )
                YIELD graphName
                RETURN graphName
                """

                try:
                    # This is a simplified approach since GDS might not be available
                    # Instead, use tag-based clustering as a fallback
                    cluster_query = """
                    MATCH (m:Memory {user_id: $user_id})
                    WITH m, m.tags as tags
                    UNWIND tags as tag
                    WITH tag, collect({
                        memory_id: m.memory_id,
                        content: m.content,
                        confidence: m.confidence,
                        inference_level: m.inference_level,
                        created_at: m.created_at
                    }) as memories
                    WHERE size(memories) >= 2
                    RETURN tag as cluster_name, memories
                    ORDER BY size(memories) DESC
                    LIMIT 10
                    """

                    result = session.run(cluster_query, {"user_id": user_id})

                    clusters = {}
                    for record in result:
                        cluster_name = record["cluster_name"]
                        memories = record["memories"]
                        clusters[f"tag_cluster_{cluster_name}"] = memories

                    # Add temporal clusters (memories from same day/period)
                    temporal_query = """
                    MATCH (m:Memory {user_id: $user_id})
                    WITH date(m.created_at) as creation_date, collect({
                        memory_id: m.memory_id,
                        content: m.content,
                        confidence: m.confidence,
                        inference_level: m.inference_level,
                        created_at: m.created_at
                    }) as memories
                    WHERE size(memories) >= 2
                    RETURN creation_date, memories
                    ORDER BY creation_date DESC
                    LIMIT 5
                    """

                    temporal_result = session.run(temporal_query, {"user_id": user_id})

                    for record in temporal_result:
                        creation_date = record["creation_date"]
                        memories = record["memories"]
                        clusters[f"temporal_cluster_{creation_date}"] = memories

                    logger.info(
                        f"Found {len(clusters)} memory clusters for user {user_id}"
                    )
                    return clusters

                except Exception as e:
                    logger.warning(
                        f"Advanced clustering failed, using simple tag-based clustering: {e}"
                    )
                    return {}

        except Exception as e:
            logger.error(f"Failed to get memory clusters: {e}")
            return {}

    def get_memory_centrality_scores(self, user_id: str) -> Dict[str, float]:
        """
        Calculate centrality scores for memories to identify important/central memories

        Args:
            user_id: User ID to analyze

        Returns:
            Dict mapping memory_id to centrality score
        """
        try:
            if not self.driver:
                return {}
            
            # Convert UUID to string if needed
            user_id = str(user_id)

            with self.driver.session() as session:
                # Calculate degree centrality (number of connections)
                centrality_query = """
                MATCH (m:Memory {user_id: $user_id})-[r]-(connected:Memory {user_id: $user_id})
                WITH m, count(r) as degree, 
                     avg(CASE 
                         WHEN type(r) = 'SIMILAR_TO' THEN r.similarity_score 
                         WHEN type(r) = 'RELATED_BY_TAG' THEN r.strength
                         ELSE 0.5 
                     END) as avg_connection_strength
                RETURN m.memory_id as memory_id, 
                       degree,
                       avg_connection_strength,
                       degree * avg_connection_strength as centrality_score
                ORDER BY centrality_score DESC
                """

                result = session.run(centrality_query, {"user_id": user_id})

                centrality_scores = {}
                for record in result:
                    centrality_scores[record["memory_id"]] = record["centrality_score"]

                logger.info(
                    f"Calculated centrality scores for {len(centrality_scores)} memories"
                )
                return centrality_scores

        except Exception as e:
            logger.error(f"Failed to calculate centrality scores: {e}")
            return {}

    def _create_enhanced_relationships(self, session, memories, user_id: str) -> int:
        """
        Create enhanced memory-to-memory relationships with multiple relationship types.
        
        Enhanced relationship types:
        - CONTRADICTS (temporal conflicts)
        - UPDATES (newer information superseding older)
        - RELATES_TO (semantic similarity)
        - SUPPORTS (evidence relationships)
        - TEMPORAL_SEQUENCE (chronological order)
        """
        relationships_created = 0
        from .llm_service import llm_service
        from .vector_service import vector_service
        
        # Convert to list for indexing
        memory_list = list(memories)
        
        for i, memory1 in enumerate(memory_list):
            # Get embedding for similarity comparisons
            embedding_result = llm_service.get_embeddings([memory1.content])
            if not embedding_result["success"]:
                continue
                
            memory1_embedding = embedding_result["embeddings"][0]
            memory1_metadata = memory1.get_standardized_metadata()
            
            # Compare with other memories
            for memory2 in memory_list[i+1:]:
                if memory1.id == memory2.id:
                    continue
                    
                memory2_metadata = memory2.get_standardized_metadata()
                
                # Priority 1: Check for LLM-provided relationship hints
                relationship_created = self._create_hint_based_relationships(
                    session, memory1, memory2, memory1_metadata, memory2_metadata, user_id
                )
                if relationship_created:
                    relationships_created += relationship_created
                    continue  # Skip heuristic analysis if hint-based relationship was created
                
                # Priority 2: Fallback to heuristic relationship detection
                # 1. Check for contradiction relationships
                if self._detect_contradiction(memory1, memory2):
                    self._create_relationship(
                        session, memory1, memory2, "CONTRADICTS", 
                        {"conflict_detected": True, "requires_resolution": True}, user_id
                    )
                    relationships_created += 1
                
                # 2. Check for update relationships (newer supersedes older)
                elif self._detect_update_relationship(memory1, memory2):
                    newer, older = (memory1, memory2) if memory1.created_at > memory2.created_at else (memory2, memory1)
                    self._create_relationship(
                        session, newer, older, "UPDATES", 
                        {"supersedes": True, "temporal_relationship": True}, user_id
                    )
                    relationships_created += 1
                
                # 3. Check for support relationships
                elif self._detect_support_relationship(memory1, memory2):
                    self._create_relationship(
                        session, memory1, memory2, "SUPPORTS", 
                        {"evidence_type": "supporting", "confidence_boost": True}, user_id
                    )
                    relationships_created += 1
                
                # 4. Check for semantic similarity
                else:
                    # Get embedding for memory2
                    embedding_result2 = llm_service.get_embeddings([memory2.content])
                    if embedding_result2["success"]:
                        # Calculate similarity
                        similarity_score = self._calculate_similarity(
                            memory1_embedding, embedding_result2["embeddings"][0]
                        )
                        
                        if similarity_score > 0.7:  # High similarity threshold
                            self._create_relationship(
                                session, memory1, memory2, "RELATES_TO", 
                                {"similarity_score": similarity_score, "connection_type": "semantic"}, user_id
                            )
                            relationships_created += 1
                
                # 5. Check for temporal sequence (same topic, different times)
                if self._detect_temporal_sequence(memory1, memory2):
                    earlier, later = (memory1, memory2) if memory1.created_at < memory2.created_at else (memory2, memory1)
                    self._create_relationship(
                        session, earlier, later, "TEMPORAL_SEQUENCE", 
                        {"sequence_type": "chronological", "temporal_gap": str(later.created_at - earlier.created_at)}, user_id
                    )
                    relationships_created += 1
        
        return relationships_created
    
    def _detect_contradiction(self, memory1, memory2) -> bool:
        """Detect if two memories contradict each other"""
        # Basic contradiction detection based on content analysis
        # Could be enhanced with LLM-based analysis
        
        # Check if they are about similar topics but have conflicting content
        memory1_tags = set(memory1.get_standardized_metadata().get("tags", []))
        memory2_tags = set(memory2.get_standardized_metadata().get("tags", []))
        
        # If they share tags but have conflicting content, they might contradict
        if memory1_tags & memory2_tags:  # Common tags
            # Check for explicit contradiction indicators
            contradiction_words = ["not", "never", "doesn't", "don't", "can't", "won't", "hate", "dislike"]
            opposite_words = ["love", "like", "prefer", "enjoy"]
            
            content1_lower = memory1.content.lower()
            content2_lower = memory2.content.lower()
            
            # Simple heuristic: if one contains contradiction words and the other doesn't
            has_contradiction_1 = any(word in content1_lower for word in contradiction_words)
            has_contradiction_2 = any(word in content2_lower for word in contradiction_words)
            has_positive_1 = any(word in content1_lower for word in opposite_words)
            has_positive_2 = any(word in content2_lower for word in opposite_words)
            
            return (has_contradiction_1 and has_positive_2) or (has_positive_1 and has_contradiction_2)
        
        return False
    
    def _detect_update_relationship(self, memory1, memory2) -> bool:
        """Detect if one memory updates/supersedes another"""
        # Check if memories are about the same topic but one is newer
        memory1_tags = set(memory1.get_standardized_metadata().get("tags", []))
        memory2_tags = set(memory2.get_standardized_metadata().get("tags", []))
        
        # Must have significant tag overlap and reasonable time difference
        tag_overlap = len(memory1_tags & memory2_tags) / max(len(memory1_tags | memory2_tags), 1)
        time_diff = abs((memory1.created_at - memory2.created_at).days)
        
        return tag_overlap > 0.5 and time_diff > 1  # Same topic, different days
    
    def _detect_support_relationship(self, memory1, memory2) -> bool:
        """Detect if one memory supports/provides evidence for another"""
        # Check if one memory provides evidence or context for another
        memory1_tags = set(memory1.get_standardized_metadata().get("tags", []))
        memory2_tags = set(memory2.get_standardized_metadata().get("tags", []))
        
        # Look for support indicators in content
        support_words = ["because", "since", "due to", "as", "evidence", "proof", "shows", "indicates"]
        
        content1_lower = memory1.content.lower()
        content2_lower = memory2.content.lower()
        
        has_support_1 = any(word in content1_lower for word in support_words)
        has_support_2 = any(word in content2_lower for word in support_words)
        
        # If they share tags and one has support language
        return bool(memory1_tags & memory2_tags) and (has_support_1 or has_support_2)
    
    def _detect_temporal_sequence(self, memory1, memory2) -> bool:
        """Detect if memories form a temporal sequence"""
        # Check if memories are related and form a time-based sequence
        memory1_tags = set(memory1.get_standardized_metadata().get("tags", []))
        memory2_tags = set(memory2.get_standardized_metadata().get("tags", []))
        
        # Must have some tag overlap and be from different times
        tag_overlap = len(memory1_tags & memory2_tags) / max(len(memory1_tags | memory2_tags), 1)
        time_diff_hours = abs((memory1.created_at - memory2.created_at).total_seconds()) / 3600
        
        return tag_overlap > 0.3 and 1 < time_diff_hours < 168  # Same topic, 1 hour to 1 week apart
    
    def _calculate_similarity(self, embedding1, embedding2) -> float:
        """Calculate cosine similarity between two embeddings"""
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
            
        return dot_product / (norm_a * norm_b)
    
    def _create_relationship(self, session, memory1, memory2, relationship_type: str, properties: dict, user_id: str):
        """Create a relationship between two memories"""
        rel_query = f"""
        MATCH (m1:Memory {{memory_id: $memory1_id, user_id: $user_id}})
        MATCH (m2:Memory {{memory_id: $memory2_id, user_id: $user_id}})
        MERGE (m1)-[r:{relationship_type}]->(m2)
        SET r += $properties,
            r.created_at = datetime(),
            r.user_id = $user_id
        """
        
        session.run(
            rel_query,
            {
                "memory1_id": str(memory1.id),
                "memory2_id": str(memory2.id),
                "user_id": user_id,
                "properties": properties,
            },
        )

    def _create_hint_based_relationships(
        self, session, memory1, memory2, memory1_metadata, memory2_metadata, user_id: str
    ) -> int:
        """
        Create relationships based on LLM-provided relationship hints.
        
        Returns the number of relationships created (0-2, since we check both directions).
        """
        relationships_created = 0
        
        # Check hints from memory1 about potential relationships
        memory1_hints = memory1_metadata.get("relationship_hints", [])
        memory2_hints = memory2_metadata.get("relationship_hints", [])
        
        # Map relationship hints to graph relationship types
        hint_to_relationship = {
            "contradicts": "CONTRADICTS",
            "updates": "UPDATES", 
            "relates_to": "RELATES_TO",
            "supports": "SUPPORTS",
            "temporal_sequence": "TEMPORAL_SEQUENCE"
        }
        
        # Process hints from memory1 (memory1 -> memory2)
        for hint in memory1_hints:
            if hint in hint_to_relationship:
                relationship_type = hint_to_relationship[hint]
                properties = {
                    "source": "llm_hint",
                    "confidence": 0.8,  # High confidence since LLM provided the hint
                    "hint_provided_by": str(memory1.id)
                }
                
                # Add specific properties based on relationship type
                if hint == "updates":
                    properties.update({"supersedes": True, "temporal_relationship": True})
                elif hint == "contradicts":
                    properties.update({"conflict_detected": True, "requires_resolution": True})
                elif hint == "supports":
                    properties.update({"evidence_type": "supporting", "confidence_boost": True})
                elif hint == "temporal_sequence":
                    properties.update({"sequence_type": "chronological"})
                elif hint == "relates_to":
                    properties.update({"connection_type": "semantic"})
                
                self._create_relationship(session, memory1, memory2, relationship_type, properties, user_id)
                relationships_created += 1
        
        # Process hints from memory2 (memory2 -> memory1) 
        for hint in memory2_hints:
            if hint in hint_to_relationship:
                relationship_type = hint_to_relationship[hint]
                properties = {
                    "source": "llm_hint",
                    "confidence": 0.8,
                    "hint_provided_by": str(memory2.id)
                }
                
                # Add specific properties based on relationship type
                if hint == "updates":
                    properties.update({"supersedes": True, "temporal_relationship": True})
                elif hint == "contradicts":
                    properties.update({"conflict_detected": True, "requires_resolution": True})
                elif hint == "supports":
                    properties.update({"evidence_type": "supporting", "confidence_boost": True})
                elif hint == "temporal_sequence":
                    properties.update({"sequence_type": "chronological"})
                elif hint == "relates_to":
                    properties.update({"connection_type": "semantic"})
                
                self._create_relationship(session, memory2, memory1, relationship_type, properties, user_id)
                relationships_created += 1
        
        return relationships_created

    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")


# Global instance
graph_service = GraphService()

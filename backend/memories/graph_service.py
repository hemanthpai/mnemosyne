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
        Convert text to graph documents and store in Neo4j

        Args:
            text: The input text to convert
            user_id: The user ID for context

        Returns:
            Dict containing success status and extraction results
        """
        try:
            if not self.transformer or not self.graph:
                return {
                    "success": False,
                    "error": "Graph transformer or Neo4j connection not initialized",
                }
            
            # Convert UUID to string if needed
            user_id = str(user_id)

            # Check for empty text input
            if not text.strip():
                return {
                    "success": False,
                    "error": "Empty text input provided",
                }

            # Create LangChain document from text
            document = Document(
                page_content=text,
                metadata={
                    "user_id": user_id,
                    "source": "memory_extraction",
                    "extraction_timestamp": str(int(time.time())),
                },
            )

            logger.info(f"Converting text to graph for user {user_id}")

            # Transform document to graph documents
            graph_documents = self.transformer.convert_to_graph_documents([document])

            if not graph_documents:
                return {
                    "success": False,
                    "error": "No graph documents generated from text",
                }

            # Store graph documents in Neo4j and add user_id to all nodes
            nodes_created = 0
            relationships_created = 0

            for graph_doc in graph_documents:
                # Add user_id property to all nodes in the graph document
                for node in graph_doc.nodes:
                    if not hasattr(node, "properties"):
                        node.properties = {}
                    node.properties["user_id"] = user_id
                    node.properties["extraction_timestamp"] = str(int(time.time()))

                # Add graph document to Neo4j
                self.graph.add_graph_documents([graph_doc])

                # Count nodes and relationships
                nodes_created += len(graph_doc.nodes)
                relationships_created += len(graph_doc.relationships)

            logger.info(
                f"Successfully stored {nodes_created} nodes and {relationships_created} relationships"
            )

            return {
                "success": True,
                "nodes_created": nodes_created,
                "relationships_created": relationships_created,
                "graph_documents_count": len(graph_documents),
                "user_id": user_id,
            }

        except Exception as e:
            logger.error(f"Failed to convert text to graph: {e}")
            return {"success": False, "error": str(e)}

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
                    # Create memory node
                    node_query = """
                    MERGE (m:Memory {memory_id: $memory_id, user_id: $user_id})
                    SET m.content = $content,
                        m.created_at = $created_at,
                        m.inference_level = $inference_level,
                        m.certainty = $certainty,
                        m.confidence = $confidence,
                        m.tags = $tags,
                        m.fact_type = $fact_type
                    """

                    session.run(
                        node_query,
                        {
                            "memory_id": str(memory.id),
                            "user_id": user_id,
                            "content": memory.content,
                            "created_at": memory.created_at.isoformat(),
                            "inference_level": memory.metadata.get(
                                "inference_level", "stated"
                            ),
                            "certainty": memory.metadata.get("certainty", 0.5),
                            "confidence": memory.temporal_confidence,
                            "tags": memory.metadata.get("tags", []),
                            "fact_type": memory.fact_type or "mutable",
                        },
                    )
                    nodes_created += 1

                # Create semantic similarity relationships using vector similarity
                from .llm_service import llm_service
                from .vector_service import vector_service

                for memory in memories:
                    # Get embedding for this memory
                    embedding_result = llm_service.get_embeddings([memory.content])
                    if not embedding_result["success"]:
                        continue

                    memory_embedding = embedding_result["embeddings"][0]

                    # Find similar memories
                    similar_memories = vector_service.search_similar(
                        query_embedding=memory_embedding,
                        user_id=user_id,
                        limit=10,
                        score_threshold=0.7,  # High similarity for graph connections
                    )

                    # Create relationships to similar memories
                    for result in similar_memories:
                        similar_id = result["memory_id"]
                        similarity_score = result["score"]

                        if similar_id != str(memory.id):  # Don't connect to self
                            rel_query = """
                            MATCH (m1:Memory {memory_id: $memory1_id, user_id: $user_id})
                            MATCH (m2:Memory {memory_id: $memory2_id, user_id: $user_id})
                            MERGE (m1)-[r:SIMILAR_TO]-(m2)
                            SET r.similarity_score = $similarity_score,
                                r.connection_type = 'semantic',
                                r.created_at = datetime()
                            """

                            session.run(
                                rel_query,
                                {
                                    "memory1_id": str(memory.id),
                                    "memory2_id": similar_id,
                                    "user_id": user_id,
                                    "similarity_score": similarity_score,
                                },
                            )
                            relationships_created += 1

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
                       related.certainty as certainty,
                       related.confidence as confidence,
                       related.tags as tags,
                       related.fact_type as fact_type,
                       related.created_at as created_at,
                       base_score / path_length as relevance_score,
                       path_length,
                       relationships
                ORDER BY relevance_score DESC, related.certainty DESC
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
                            "certainty": record["certainty"],
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
                    {Memory: {properties: ['certainty', 'confidence']}},
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
                        certainty: m.certainty,
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
                        certainty: m.certainty,
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

    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")


# Global instance
graph_service = GraphService()

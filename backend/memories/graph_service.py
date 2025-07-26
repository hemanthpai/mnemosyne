import logging
import os
import time
from typing import Any, Dict

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

    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")


# Global instance
graph_service = GraphService()

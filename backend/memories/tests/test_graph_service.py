import logging
import os
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

import pytest
import requests
from django.test import TestCase

from memories.graph_service import GraphService
from memories.llm_service import llm_service as llm_service_instance

# Configure logging to ensure messages are visible
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

# Increase verbosity of specific loggers
logging.getLogger("memories.graph_service").setLevel(logging.DEBUG)
logging.getLogger("memories.llm_service").setLevel(logging.DEBUG)

# Test database connection details
NEO4J_TEST_URI = "bolt://localhost:7688"  # Mapped port from docker-compose.test.yml
NEO4J_TEST_USERNAME = "neo4j"
NEO4J_TEST_PASSWORD = "testpassword"


def is_neo4j_test_available():
    """Check if Neo4j test instance is available"""
    # Store original environment variables
    orig_uri = os.environ.get("NEO4J_URI")
    orig_user = os.environ.get("NEO4J_USERNAME")
    orig_pass = os.environ.get("NEO4J_PASSWORD")
    orig_test_uri = os.environ.get("NEO4J_TEST_URI")
    orig_test_user = os.environ.get("NEO4J_TEST_USERNAME")
    orig_test_pass = os.environ.get("NEO4J_TEST_PASSWORD")

    try:
        # Set both sets of environment variables
        os.environ["NEO4J_URI"] = NEO4J_TEST_URI
        os.environ["NEO4J_USERNAME"] = NEO4J_TEST_USERNAME
        os.environ["NEO4J_PASSWORD"] = NEO4J_TEST_PASSWORD
        os.environ["NEO4J_TEST_URI"] = NEO4J_TEST_URI
        os.environ["NEO4J_TEST_USERNAME"] = NEO4J_TEST_USERNAME
        os.environ["NEO4J_TEST_PASSWORD"] = NEO4J_TEST_PASSWORD

        print("=== Neo4j Test Availability Check ===")
        print(f"Neo4j test connection details: {NEO4J_TEST_URI}")
        print(f"Neo4j test username: {NEO4J_TEST_USERNAME}")

        # Connect directly with Neo4j driver to avoid Django dependency
        print("Attempting direct Neo4j connection...")
        try:
            from neo4j import GraphDatabase

            driver = None
            try:
                driver = GraphDatabase.driver(
                    NEO4J_TEST_URI, auth=(NEO4J_TEST_USERNAME, NEO4J_TEST_PASSWORD)
                )
                with driver.session() as session:
                    result = session.run("RETURN 1 as test")
                    record = result.single()
                    if record and record["test"] == 1:
                        print("Direct Neo4j connection successful!")
                        print("=== Neo4j is AVAILABLE ===\n")
                        return True
                    else:
                        print("Neo4j connection test returned unexpected result")
                        print("=== Neo4j is NOT AVAILABLE ===\n")
                        logger.warning(
                            "Neo4j connection test returned unexpected result"
                        )
                        return False
            finally:
                # Always close the driver, even if an exception occurred
                if driver:
                    driver.close()
        except Exception as e:
            print(f"Failed direct Neo4j connection: {e}")
            print("=== Neo4j is NOT AVAILABLE ===\n")
            logger.warning(f"Direct Neo4j connection failed: {e}")
            return False
    except Exception as e:
        print(f"Error checking Neo4j availability: {e}")
        logger.error(f"Error checking Neo4j availability: {e}")
        return False
    finally:
        # Restore original environment variables
        if orig_uri:
            os.environ["NEO4J_URI"] = orig_uri
        else:
            os.environ.pop("NEO4J_URI", None)
        if orig_user:
            os.environ["NEO4J_USERNAME"] = orig_user
        else:
            os.environ.pop("NEO4J_USERNAME", None)
        if orig_pass:
            os.environ["NEO4J_PASSWORD"] = orig_pass
        else:
            os.environ.pop("NEO4J_PASSWORD", None)

        # Restore original TEST environment variables
        if orig_test_uri:
            os.environ["NEO4J_TEST_URI"] = orig_test_uri
        else:
            os.environ.pop("NEO4J_TEST_URI", None)
        if orig_test_user:
            os.environ["NEO4J_TEST_USERNAME"] = orig_test_user
        else:
            os.environ.pop("NEO4J_TEST_USERNAME", None)
        if orig_test_pass:
            os.environ["NEO4J_TEST_PASSWORD"] = orig_test_pass
        else:
            os.environ.pop("NEO4J_TEST_PASSWORD", None)


@pytest.mark.neo4j
class GraphServiceIntegrationTest(TestCase):
    """Integration tests for the GraphService class - requires Neo4j connection"""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once before all tests"""
        super().setUpClass()
        cls.test_user_id = (
            f"test_user_{uuid.uuid4().hex[:8]}"  # Generate unique test user ID
        )

    def setUp(self):
        """Set up test environment before each test"""
        # Set up Neo4j test configuration
        logger.info("Checking Neo4j availability in setUp...")
        neo4j_available = is_neo4j_test_available()
        logger.info(f"Neo4j availability check result: {neo4j_available}")

        if not neo4j_available:
            self.skipTest("Neo4j is not available for testing")

        logger.info("Neo4j is available, continuing with test")

        # Get API endpoint from environment or use default mock endpoint
        endpoint_url = os.environ.get(
            "OPENAI_API_BASE", os.environ.get("OPENAI_API_ENDPOINT")
        )
        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            # Set dummy API key if not provided in environment
            api_key = "sk-dummy-api-key-for-testing"
            os.environ["OPENAI_API_KEY"] = api_key

        # Create settings with actual endpoint from environment if available
        mock_settings = SimpleNamespace(
            extraction_endpoint_url=endpoint_url or "http://localhost:11434",
            extraction_model=os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
            if endpoint_url
            else "llama3",
            extraction_provider_type="openai" if endpoint_url else "ollama",
            extraction_endpoint_api_key=api_key,
        )

        # Replace the settings in the llm_service
        llm_service_instance._settings = mock_settings
        llm_service_instance._settings_loaded = True

        # Log the endpoint being used
        logger.info(f"Using LLM endpoint: {mock_settings.extraction_endpoint_url}")
        logger.info(f"Using LLM model: {mock_settings.extraction_model}")
        logger.info(f"Using LLM provider: {mock_settings.extraction_provider_type}")

        # Create a fresh instance of GraphService for each test
        logger.info("Creating GraphService instance for test...")
        try:
            # First ensure LLM service has proper settings
            # GraphService will use the global llm_service instance when initializing

            # Create GraphService
            self.graph_service = GraphService()
            logger.info(
                f"GraphService created. Driver: {self.graph_service.driver is not None}, Transformer: {self.graph_service.transformer is not None}"
            )

            # If transformer is None, log the reason if possible
            if not self.graph_service.transformer:
                logger.error(
                    "Transformer initialization failed, check GraphService for details"
                )

        except Exception as e:
            logger.error(f"Exception during GraphService creation: {e}")
            self.skipTest(f"Could not create GraphService: {e}")

        if not self.graph_service.driver:
            self.skipTest("Neo4j connection could not be established")

        # Clear any existing test user data to start with clean state
        self.graph_service.clear_user_graph(self.test_user_id)

    def tearDown(self):
        """Clean up after each test"""
        # Disable Neo4j logging to prevent 'I/O operation on closed file' warnings
        neo4j_logger = logging.getLogger("neo4j")
        neo4j_logger.setLevel(logging.CRITICAL)  # Suppress most Neo4j log messages

        if hasattr(self, "graph_service") and self.graph_service.driver:
            # Remove test data to leave the database clean
            self.graph_service.clear_user_graph(self.test_user_id)

            # Explicitly close the Neo4jGraph object if it exists
            if self.graph_service.graph:
                try:
                    self.graph_service.graph.close()
                except Exception:
                    pass

            # Close the driver
            self.graph_service.close()

        # Restore original environment variables
        if hasattr(self, "orig_uri") and self.orig_uri:
            os.environ["NEO4J_URI"] = self.orig_uri
        else:
            os.environ.pop("NEO4J_URI", None)

        if hasattr(self, "orig_user") and self.orig_user:
            os.environ["NEO4J_USERNAME"] = self.orig_user
        else:
            os.environ.pop("NEO4J_USERNAME", None)

        if hasattr(self, "orig_pass") and self.orig_pass:
            os.environ["NEO4J_PASSWORD"] = self.orig_pass
        else:
            os.environ.pop("NEO4J_PASSWORD", None)

    # 1. Connection and Initialization Tests
    def test_connection_initialization(self):
        """Test successful connection to Neo4j database"""
        # Check if connection is established
        self.assertIsNotNone(self.graph_service.driver)
        self.assertIsNotNone(self.graph_service.graph)

        # Verify health check returns healthy
        health_status = self.graph_service.health_check()
        self.assertTrue(health_status["healthy"])
        self.assertEqual(health_status["message"], "Neo4j connection is healthy")

    # 2. Health Check Tests
    def test_health_check(self):
        """Test health check functionality"""
        # Test with active connection
        health_status = self.graph_service.health_check()
        self.assertTrue(health_status["healthy"])

        # Test with broken connection (simulate by temporarily setting driver to None)
        original_driver = self.graph_service.driver
        try:
            self.graph_service.driver = None
            health_status = self.graph_service.health_check()
            self.assertFalse(health_status["healthy"])
            self.assertEqual(health_status["error"], "Neo4j driver not initialized")
        finally:
            # Restore driver for cleanup
            self.graph_service.driver = original_driver

    # 3. Database Information Tests
    def test_get_database_info(self):
        """Test retrieving database information"""
        # Get initial database info
        db_info = self.graph_service.get_database_info()

        # Verify the response structure
        self.assertIn("node_count", db_info)
        self.assertIn("relationship_count", db_info)
        self.assertIn("node_types", db_info)
        self.assertIn("relationship_types", db_info)

        # Test with broken connection
        original_driver = self.graph_service.driver
        try:
            self.graph_service.driver = None
            db_info = self.graph_service.get_database_info()
            self.assertIn("error", db_info)
            self.assertEqual(db_info["error"], "Neo4j driver not initialized")
        finally:
            # Restore driver for cleanup
            self.graph_service.driver = original_driver

    # 4. Text to Graph Conversion Tests
    def test_text_to_graph_simple(self):
        """Test converting simple text to graph"""
        # Simple text with clear entities and relationships
        simple_text = "John likes pizza. Pizza is a type of food."

        # Skip if transformer is not available
        if not self.graph_service.transformer:
            self.skipTest("LLM Graph Transformer not available for this test")

        # Validate LLM endpoint and get endpoint URL and API key
        endpoint_url, api_key = self._validate_llm_endpoint()

        logger.info(
            f"Using real OpenAI API endpoint: {endpoint_url} for test_text_to_graph_simple"
        )

        # First clear any existing data for this user
        self.graph_service.clear_user_graph(self.test_user_id)

        # Make the actual API call
        result = self.graph_service.text_to_graph(simple_text, self.test_user_id)

        # Verify the operation was successful
        self.assertTrue(
            result["success"],
            f"text_to_graph operation failed: {result.get('error', 'Unknown error')}",
        )
        self.assertGreater(result["nodes_created"], 0, "No nodes were created")
        self.assertGreater(
            result["relationships_created"], 0, "No relationships were created"
        )
        self.assertEqual(result["user_id"], self.test_user_id, "User ID mismatch")

        # Query to verify nodes exist in the graph
        expected_query = f"MATCH (n) WHERE n.user_id = '{self.test_user_id}' RETURN COUNT(n) as count"
        query_result = self.graph_service.query_graph(expected_query)

        self.assertTrue(query_result["success"], "Graph query failed")
        self.assertEqual(
            len(query_result["results"]), 1, "Expected exactly one result row"
        )
        self.assertGreater(
            query_result["results"][0]["count"], 0, "No nodes found in graph"
        )

    def test_text_to_graph_empty_text(self):
        """Test handling of empty text input"""
        result = self.graph_service.text_to_graph("", self.test_user_id)

        logger.info(f"Result: {result}")

        # Empty text should be handled gracefully
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    # 5. Graph Querying Tests
    def test_query_graph(self):
        """Test executing valid Cypher queries"""
        # Always manually insert test data to ensure test reliability
        # This avoids test failures when using mocked LLM endpoints
        query = f"""
        CREATE (a:Person {{name: 'Alice', user_id: '{self.test_user_id}'}}),
               (b:Person {{name: 'Bob', user_id: '{self.test_user_id}'}}),
               (c:Person {{name: 'Charlie', user_id: '{self.test_user_id}'}}),
               (a)-[:WORKS_WITH]->(b),
               (c)-[:MANAGES]->(a)
        """
        self.graph_service.query_graph(query)

        # Query the inserted data
        query_result = self.graph_service.query_graph(
            f"""
            MATCH (a:Person {{user_id: '{self.test_user_id}'}})-[r]->(b:Person {{user_id: '{self.test_user_id}'}})
            RETURN a.name as source, type(r) as relationship, b.name as target
            """
        )

        self.assertTrue(query_result["success"])
        self.assertGreater(len(query_result["results"]), 0)

        # Test invalid query
        invalid_query = "MATCH (n) WHERE x.invalid RETURN n"
        invalid_result = self.graph_service.query_graph(invalid_query)
        self.assertFalse(invalid_result["success"])
        self.assertIn("error", invalid_result)

    # 6. User Graph Statistics Tests
    def test_user_graph_stats(self):
        """Test retrieving user graph statistics"""
        # Always manually insert test data to ensure test reliability
        # This avoids test failures when using mocked LLM endpoints
        query = f"""
        CREATE (earth:Planet {{name: 'Earth', user_id: '{self.test_user_id}'}}),
               (sun:Star {{name: 'Sun', user_id: '{self.test_user_id}'}}),
               (mars:Planet {{name: 'Mars', user_id: '{self.test_user_id}'}}),
               (earth)-[:ORBITS]->(sun)
        """
        self.graph_service.query_graph(query)

        # Get user stats
        stats = self.graph_service.get_user_graph_stats(self.test_user_id)

        # Verify stats structure and data
        self.assertEqual(stats["user_id"], self.test_user_id)
        self.assertGreater(stats["node_count"], 0)
        self.assertGreater(stats["relationship_count"], 0)
        self.assertGreater(len(stats["node_types"]), 0)
        self.assertGreater(len(stats["relationship_types"]), 0)

        # Test with non-existent user
        empty_stats = self.graph_service.get_user_graph_stats("nonexistent_user")
        self.assertEqual(empty_stats["node_count"], 0)
        self.assertEqual(empty_stats["relationship_count"], 0)

    # 7. Data Cleanup Tests
    def test_clear_user_graph(self):
        """Test clearing user graph data"""
        # Always manually insert test data to ensure test reliability
        # This avoids test failures when using mocked LLM endpoints
        query = f"""
        CREATE (dog:Animal {{name: 'Dog', user_id: '{self.test_user_id}'}}),
               (cat:Animal {{name: 'Cat', user_id: '{self.test_user_id}'}}),
               (fish:Animal {{name: 'Fish', user_id: '{self.test_user_id}'}}),
               (dog)-[:CHASES]->(cat),
               (cat)-[:EATS]->(fish)
        """
        self.graph_service.query_graph(query)

        # Verify data exists
        pre_stats = self.graph_service.get_user_graph_stats(self.test_user_id)
        self.assertGreater(pre_stats["node_count"], 0)

        # Clear the data
        result = self.graph_service.clear_user_graph(self.test_user_id)
        self.assertTrue(result["success"])
        self.assertGreater(result["deleted_nodes"], 0)

        # Verify data is gone
        post_stats = self.graph_service.get_user_graph_stats(self.test_user_id)
        self.assertEqual(post_stats["node_count"], 0)
        self.assertEqual(post_stats["relationship_count"], 0)

        # Test clearing non-existent user data
        empty_result = self.graph_service.clear_user_graph("nonexistent_user")
        self.assertTrue(empty_result["success"])
        self.assertEqual(empty_result["deleted_nodes"], 0)

    # Helper methods for tests
    def _validate_llm_endpoint(self):
        """Validate that an LLM endpoint is available and properly configured.
        Returns tuple of (endpoint_url, api_key) if valid, otherwise skips the test.
        """
        # Use the same environment variables as the actual LLM service
        endpoint_url = os.environ.get("OLLAMA_BASE_URL")
        api_key = os.environ.get("OLLAMA_API_KEY")  # Optional for Ollama

        # Debug output for environment variables
        logger.info(f"OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
        logger.info(f"Resolved endpoint_url: {endpoint_url}")
        logger.info(f"API key available: {bool(api_key)}")

        # Skip test if no endpoint URL
        if not endpoint_url:
            self.skipTest("No LLM endpoint URL specified (set OLLAMA_BASE_URL)")

        # Test connectivity to the LLM endpoint before running the test
        try:
            # Configure headers for API request (only add auth if API key is provided)
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # For Ollama, test with a simple health check
            health_url = f"{endpoint_url.rstrip('/')}/health"
            logger.info(f"Testing health endpoint: {health_url}")

            try:
                response = requests.get(health_url, headers=headers or None, timeout=5)
                if response.status_code < 400:
                    logger.info(f"Health check successful: {response.status_code}")
                    return endpoint_url, api_key
            except requests.exceptions.RequestException:
                logger.info(
                    "Health endpoint not available, trying basic endpoint validation"
                )

            # Final fallback: just check if we can connect to the base endpoint
            logger.info(f"Testing base endpoint connectivity: {endpoint_url}")
            response = requests.get(endpoint_url, headers=headers or None, timeout=5)
            if (
                response.status_code < 500
            ):  # Even 401/403 is OK - it means the endpoint exists
                logger.info(
                    f"Base endpoint connectivity check successful: {response.status_code}"
                )
                return endpoint_url, api_key
            else:
                logger.error(
                    f"Failed to connect to LLM API base endpoint: {response.status_code}"
                )
                self.skipTest(
                    f"Could not connect to LLM API base endpoint: {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Connection error to LLM API: {e}")
            self.skipTest(f"Cannot connect to LLM API endpoint: {e}")
        except Exception as e:
            logger.error(f"Unexpected error testing LLM API: {e}")
            self.skipTest(f"Error testing LLM API connectivity: {e}")

        return endpoint_url, api_key

    # 8. Error Handling and Edge Cases
    def test_error_handling(self):
        """Test error handling in various scenarios"""
        # Test with invalid query
        invalid_query = "INVALID CYPHER QUERY"
        result = self.graph_service.query_graph(invalid_query)
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    @unittest.skip("This test may disrupt other tests - run manually if needed")
    def test_connection_failure(self):
        """Test handling connection failures (skipped by default)"""
        # Create service with invalid credentials
        with mock.patch("os.getenv", return_value="invalid_password"):
            bad_service = GraphService()
            health = bad_service.health_check()
            self.assertFalse(health["healthy"])
            # Ensure the driver is properly closed even with invalid credentials
            bad_service.close()

    # 9. Integration with LLM Service
    def test_transformer_initialization(self):
        """Test LLM Graph Transformer initialization"""
        # This test may be skipped if transformer is not available
        if not self.graph_service.transformer:
            self.skipTest("LLM Graph Transformer not available")

        # Verify transformer was initialized
        self.assertIsNotNone(self.graph_service.transformer)

    # 10. Performance Test (simple version)
    def test_text_to_graph_large(self):
        """Simple performance test with moderate text input"""
        # Skip if transformer is not available
        if not self.graph_service.transformer:
            self.skipTest("LLM Graph Transformer not available for this test")

        print("===== PERFORMANCE TEST DEBUG =====")

        # Set log level to DEBUG for this test
        logging.getLogger().setLevel(logging.DEBUG)

        # Validate LLM endpoint and get endpoint URL and API key
        endpoint_url, api_key = self._validate_llm_endpoint()

        # Print some additional debug info specific to performance test
        print(
            f"API key value: {api_key[:5]}... (truncated)" if api_key else "No API key"
        )
        print(
            "Environment vars related to OpenAI:",
            [k for k in os.environ.keys() if "OPENAI" in k],
        )

        # Create a longer text with multiple entities and relationships
        longer_text = """
        The solar system consists of the Sun and eight planets. 
        Mercury is the closest planet to the Sun.
        Venus is the second planet from the Sun.
        Earth is the third planet and has one natural satellite called the Moon.
        Mars is the fourth planet and has two moons: Phobos and Deimos.
        Jupiter is the largest planet with many moons including Europa and Ganymede.
        Saturn has prominent rings and moons like Titan and Enceladus.
        Uranus and Neptune are ice giants in the outer solar system.
        """

        # Time the operation
        import time

        start_time = time.time()

        result = self.graph_service.text_to_graph(longer_text, self.test_user_id)

        elapsed_time = time.time() - start_time

        # Verify the operation was successful
        if not result["success"]:
            self.fail(f"text_to_graph failed: {result.get('error', 'Unknown error')}")

        self.assertGreater(result["nodes_created"], 5)  # Should create many nodes

        # Log performance metrics
        print(
            f"Performance test: processed {len(longer_text)} characters in {elapsed_time:.2f} seconds"
        )
        print(
            f"Created {result['nodes_created']} nodes and {result['relationships_created']} relationships"
        )

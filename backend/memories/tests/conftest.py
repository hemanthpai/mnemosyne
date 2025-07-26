"""
Pytest configuration file for memory service tests.
Contains fixtures for setting up test dependencies like Neo4j.
"""
import os
import pytest
import logging
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default Neo4j Test connection details
# These will be used if the environment variables are not set
DEFAULT_NEO4J_TEST_URI = "neo4j://localhost:7688"
DEFAULT_NEO4J_TEST_USERNAME = "neo4j"
DEFAULT_NEO4J_TEST_PASSWORD = "testpassword"

def is_neo4j_available():
    """Check if Neo4j is available at the configured location"""
    uri = os.environ.get("NEO4J_TEST_URI", DEFAULT_NEO4J_TEST_URI)
    username = os.environ.get("NEO4J_TEST_USERNAME", DEFAULT_NEO4J_TEST_USERNAME)
    password = os.environ.get("NEO4J_TEST_PASSWORD", DEFAULT_NEO4J_TEST_PASSWORD)
    
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            driver.close()
            return record and record["test"] == 1
    except Exception as e:
        logger.warning(f"Neo4j not available: {e}")
        return False

@pytest.fixture(scope="session")
def neo4j_test_settings():
    """
    Fixture to provide Neo4j test settings.
    Gets settings from environment variables or uses defaults.
    
    Returns:
        dict: Neo4j connection settings
    """
    if not is_neo4j_available():
        pytest.skip("Neo4j test database is not available")
    
    return {
        "uri": os.environ.get("NEO4J_TEST_URI", DEFAULT_NEO4J_TEST_URI),
        "username": os.environ.get("NEO4J_TEST_USERNAME", DEFAULT_NEO4J_TEST_USERNAME),
        "password": os.environ.get("NEO4J_TEST_PASSWORD", DEFAULT_NEO4J_TEST_PASSWORD)
    }

@pytest.fixture(scope="function", autouse=True)
def setup_neo4j_env(neo4j_test_settings):
    """
    Fixture to set up Neo4j environment variables for testing.
    This is auto-used for all tests.
    
    Args:
        neo4j_test_settings: Fixture providing Neo4j settings
    """
    # Store original environment variables
    orig_uri = os.environ.get("NEO4J_URI")
    orig_user = os.environ.get("NEO4J_USERNAME") 
    orig_pass = os.environ.get("NEO4J_PASSWORD")
    
    # Set environment variables for testing
    os.environ["NEO4J_URI"] = neo4j_test_settings["uri"]
    os.environ["NEO4J_USERNAME"] = neo4j_test_settings["username"]
    os.environ["NEO4J_PASSWORD"] = neo4j_test_settings["password"]
    
    yield
    
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

#!/usr/bin/env python
"""
Script to manage the test database for integration tests.
This script handles starting and stopping the Neo4j test container.

Usage:
  python manage_testdb.py start   # Start the Neo4j test container
  python manage_testdb.py stop    # Stop the Neo4j test container
  python manage_testdb.py status  # Check if the Neo4j test container is running
"""

import os
import sys
import time
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DOCKER_COMPOSE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "docker-compose.test.yml"
)
SERVICE_NAME = "neo4j-test"
NEO4J_TEST_PORT = 7688
MAX_WAIT_TIME = 60  # Maximum time to wait for Neo4j to start (seconds)

def run_command(command, check=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command, 
            check=check, 
            capture_output=True, 
            text=True,
            shell=True
        )
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"Error output: {e.stderr}")
        if check:
            sys.exit(1)
        return e

def is_docker_available():
    """Check if Docker is available"""
    result = run_command("docker --version", check=False)
    return result.returncode == 0

def is_container_running():
    """Check if the Neo4j test container is running"""
    result = run_command(
        f"docker-compose -f {DOCKER_COMPOSE_FILE} ps -q {SERVICE_NAME}", 
        check=False
    )
    return bool(result.stdout.strip())

def wait_for_neo4j(timeout=MAX_WAIT_TIME):
    """Wait for Neo4j to become responsive"""
    from neo4j import GraphDatabase

    start_time = time.time()
    uri = f"neo4j://localhost:{NEO4J_TEST_PORT}"
    
    while time.time() - start_time < timeout:
        try:
            driver = GraphDatabase.driver(uri, auth=("neo4j", "testpassword"))
            with driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if record and record["test"] == 1:
                    driver.close()
                    return True
        except Exception as e:
            logger.info(f"Waiting for Neo4j to start... ({e})")
            time.sleep(2)
    
    logger.error(f"Neo4j did not become responsive within {timeout} seconds")
    return False

def start_testdb():
    """Start the Neo4j test container"""
    if not is_docker_available():
        logger.error("Docker is not available. Please install Docker.")
        sys.exit(1)
    
    if is_container_running():
        logger.info("Neo4j test container is already running")
        return True
    
    logger.info("Starting Neo4j test container...")
    result = run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} up -d {SERVICE_NAME}")
    
    if result.returncode != 0:
        logger.error("Failed to start Neo4j test container")
        return False
    
    logger.info("Waiting for Neo4j to become responsive...")
    if wait_for_neo4j():
        logger.info(f"Neo4j test container is running at localhost:{NEO4J_TEST_PORT}")
        logger.info("Username: neo4j, Password: testpassword")
        
        # Print environment variables to set
        logger.info("\nSet these environment variables for your tests:")
        logger.info("export NEO4J_URI=neo4j://localhost:7688")
        logger.info("export NEO4J_USERNAME=neo4j")
        logger.info("export NEO4J_PASSWORD=testpassword\n")
        
        return True
    else:
        logger.error("Neo4j test container did not become responsive")
        return False

def stop_testdb():
    """Stop the Neo4j test container"""
    if not is_docker_available():
        logger.error("Docker is not available. Please install Docker.")
        sys.exit(1)
    
    if not is_container_running():
        logger.info("Neo4j test container is not running")
        return True
    
    logger.info("Stopping Neo4j test container...")
    result = run_command(f"docker-compose -f {DOCKER_COMPOSE_FILE} down")
    
    if result.returncode != 0:
        logger.error("Failed to stop Neo4j test container")
        return False
    
    logger.info("Neo4j test container stopped")
    return True

def check_status():
    """Check if the Neo4j test container is running"""
    if not is_docker_available():
        logger.error("Docker is not available. Please install Docker.")
        sys.exit(1)
    
    if is_container_running():
        logger.info(f"Neo4j test container is running at localhost:{NEO4J_TEST_PORT}")
        logger.info("Username: neo4j, Password: testpassword")
        
        # Print environment variables to set
        logger.info("\nSet these environment variables for your tests:")
        logger.info("export NEO4J_URI=neo4j://localhost:7688")
        logger.info("export NEO4J_USERNAME=neo4j")
        logger.info("export NEO4J_PASSWORD=testpassword\n")
    else:
        logger.info("Neo4j test container is not running")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
        
    action = sys.argv[1].lower()
    
    if action == "start":
        if start_testdb():
            sys.exit(0)
        else:
            sys.exit(1)
    elif action == "stop":
        if stop_testdb():
            sys.exit(0)
        else:
            sys.exit(1)
    elif action == "status":
        check_status()
    else:
        print(__doc__)
        sys.exit(1)

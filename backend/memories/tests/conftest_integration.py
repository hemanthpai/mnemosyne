"""
Configuration fixtures for integration tests requiring Django settings
"""
import os
import logging
import pytest
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def is_openai_api_available():
    """Check if an OpenAI-compatible API endpoint is available"""
    # Check for endpoint URL in environment (using OLLAMA_BASE_URL like the main tests)
    endpoint_url = os.environ.get('OLLAMA_BASE_URL')
    api_key = os.environ.get('OLLAMA_API_KEY')  # Optional for Ollama
    
    if not endpoint_url:
        logger.info('No LLM endpoint URL specified (set OLLAMA_BASE_URL)')
        return False
    
    # Validate the URL format
    try:
        parsed = urlparse(endpoint_url)
        if not parsed.scheme or not parsed.netloc:
            logger.warning(f'Invalid LLM endpoint URL format: {endpoint_url}')
            return False
    except Exception as e:
        logger.warning(f'Error parsing LLM endpoint URL: {e}')
        return False
    
    # Try a simple request to check if the endpoint is accessible
    # Only do this for http/https URLs to avoid hanging on local connections
    if parsed.scheme in ['http', 'https']:
        try:
            logger.info(f'Testing LLM endpoint: {endpoint_url}')
            # Set a short timeout to avoid hanging tests
            headers = {}
            if api_key:
                headers['Authorization'] = f'Bearer {api_key}'
            response = requests.get(endpoint_url, timeout=3, headers=headers or None)
            # We don't actually care about the response content, just that the endpoint exists
            logger.info(f'LLM endpoint test status code: {response.status_code}')
            # Even 401/403 is OK here - it means the endpoint exists but we need proper auth
            return response.status_code < 500
        except requests.RequestException as e:
            logger.warning(f'Error connecting to LLM endpoint: {e}')
            return False
    
    # For non-HTTP endpoints, just return True if the URL is valid
    return True

@pytest.fixture(scope="session", autouse=True)
def django_settings():
    """Setup Django settings for tests that require it"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "memories.tests.test_settings")
    # Now force Django to load the settings
    from django.conf import settings
    
    # This import will trigger settings initialization
    import django
    if not settings.configured:
        django.setup()
    
    return settings

@pytest.fixture(scope="session")
def openai_api_available():
    """Check if an OpenAI API endpoint is available for tests"""
    return is_openai_api_available()

"""
Tests for LLM Service with separate generation configuration
"""

from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from memories.llm_service import LLMService
from memories.settings_model import Settings


class LLMServiceConfigTest(TestCase):
    """Test LLM Service configuration handling"""

    def setUp(self):
        """Clear cache and reset settings before each test"""
        cache.clear()
        Settings.objects.all().delete()
        self.llm_service = LLMService()

    def test_get_generation_config_from_database(self):
        """Test that generation config is loaded from database"""
        # Create settings with custom generation config
        settings = Settings.get_settings()
        settings.generation_provider = 'openai'
        settings.generation_endpoint_url = 'https://api.openai.com/v1'
        settings.generation_model = 'gpt-4'
        settings.generation_api_key = 'sk-test123'
        settings.generation_temperature = 0.5
        settings.generation_max_tokens = 2000
        settings.generation_timeout = 90
        settings.save()

        config = self.llm_service._get_generation_config()

        self.assertEqual(config['provider'], 'openai')
        self.assertEqual(config['endpoint_url'], 'https://api.openai.com/v1')
        self.assertEqual(config['model'], 'gpt-4')
        self.assertEqual(config['api_key'], 'sk-test123')
        self.assertEqual(config['temperature'], 0.5)
        self.assertEqual(config['max_tokens'], 2000)
        self.assertEqual(config['timeout'], 90)

    def test_get_generation_config_fallback_to_embeddings(self):
        """Test that empty generation config falls back to embeddings config"""
        # Create settings with only embeddings config
        settings = Settings.get_settings()
        settings.embeddings_provider = 'ollama'
        settings.embeddings_endpoint_url = 'http://localhost:11434'
        settings.embeddings_model = 'mxbai-embed-large'
        settings.save()

        config = self.llm_service._get_generation_config()

        # Should use embeddings config
        self.assertEqual(config['provider'], 'ollama')
        self.assertEqual(config['endpoint_url'], 'http://localhost:11434')
        self.assertEqual(config['model'], 'mxbai-embed-large')

    def test_get_generation_config_partial_override(self):
        """Test that partial generation config works (some fields use embeddings fallback)"""
        settings = Settings.get_settings()
        settings.embeddings_provider = 'ollama'
        settings.embeddings_endpoint_url = 'http://localhost:11434'
        settings.embeddings_model = 'llama3'
        settings.generation_model = 'mixtral'  # Only override model
        settings.save()

        config = self.llm_service._get_generation_config()

        # Provider and endpoint should use embeddings config
        self.assertEqual(config['provider'], 'ollama')
        self.assertEqual(config['endpoint_url'], 'http://localhost:11434')
        # Model should use generation config
        self.assertEqual(config['model'], 'mixtral')

    @patch('memories.llm_service.requests.Session.post')
    def test_generate_text_uses_config_defaults(self, mock_post):
        """Test that generate_text uses config defaults when params not provided"""
        # Setup settings
        settings = Settings.get_settings()
        settings.generation_temperature = 0.7
        settings.generation_max_tokens = 1500
        settings.save()

        # Mock Ollama response
        mock_response = Mock()
        mock_response.json.return_value = {"response": "test output"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Call without specifying temperature or max_tokens
        result = self.llm_service.generate_text(prompt="test prompt")

        # Should use config defaults
        self.assertTrue(result['success'])
        call_args = mock_post.call_args
        json_data = call_args[1]['json']

        self.assertEqual(json_data['options']['temperature'], 0.7)
        self.assertEqual(json_data['options']['num_predict'], 1500)

    @patch('memories.llm_service.requests.Session.post')
    def test_generate_text_override_defaults(self, mock_post):
        """Test that generate_text can override config defaults"""
        # Setup settings
        settings = Settings.get_settings()
        settings.generation_temperature = 0.3
        settings.save()

        # Mock Ollama response
        mock_response = Mock()
        mock_response.json.return_value = {"response": "test output"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        # Call with explicit temperature
        result = self.llm_service.generate_text(
            prompt="test prompt",
            temperature=0.9  # Override default
        )

        # Should use provided value
        call_args = mock_post.call_args
        json_data = call_args[1]['json']

        self.assertEqual(json_data['options']['temperature'], 0.9)

    @patch('memories.llm_service.requests.Session.post')
    def test_generate_text_ollama_uses_correct_endpoint(self, mock_post):
        """Test that Ollama generation uses generation_endpoint_url"""
        # Setup with different endpoints
        settings = Settings.get_settings()
        settings.embeddings_endpoint_url = 'http://embeddings-server:11434'
        settings.generation_endpoint_url = 'http://generation-server:11434'
        settings.save()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"response": "test"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        self.llm_service.generate_text(prompt="test")

        # Should call generation endpoint
        call_args = mock_post.call_args
        endpoint_url = call_args[0][0]

        self.assertIn('generation-server', endpoint_url)

    @patch('memories.llm_service.requests.Session.post')
    def test_generate_text_openai_uses_api_key(self, mock_post):
        """Test that OpenAI generation uses generation_api_key"""
        # Setup with OpenAI config
        settings = Settings.get_settings()
        settings.generation_provider = 'openai'
        settings.generation_endpoint_url = 'https://api.openai.com/v1'
        settings.generation_api_key = 'sk-generation-key'
        settings.save()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test response"}}],
            "model": "gpt-4"
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        self.llm_service.generate_text(prompt="test")

        # Should include API key in headers
        call_args = mock_post.call_args
        headers = call_args[1]['headers']

        self.assertEqual(headers['Authorization'], 'Bearer sk-generation-key')

    @patch('memories.llm_service.requests.Session.post')
    def test_generate_text_uses_generation_timeout(self, mock_post):
        """Test that generation uses generation_timeout"""
        # Setup with custom timeout
        settings = Settings.get_settings()
        settings.generation_timeout = 120
        settings.save()

        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {"response": "test"}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        self.llm_service.generate_text(prompt="test")

        # Should use generation timeout
        call_args = mock_post.call_args
        timeout = call_args[1]['timeout']

        self.assertEqual(timeout, 120)


class LLMServiceErrorHandlingTest(TestCase):
    """Test LLM Service error handling"""

    def setUp(self):
        """Set up test service"""
        cache.clear()
        Settings.objects.all().delete()
        self.llm_service = LLMService()

    @patch('memories.llm_service.requests.Session.post')
    def test_generate_text_network_error(self, mock_post):
        """Test that network errors are handled gracefully"""
        mock_post.side_effect = Exception("Network error")

        result = self.llm_service.generate_text(prompt="test")

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch('memories.llm_service.requests.Session.post')
    def test_generate_text_invalid_response(self, mock_post):
        """Test that invalid JSON responses are handled"""
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.llm_service.generate_text(prompt="test")

        self.assertFalse(result['success'])

import json
from unittest.mock import Mock, patch
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
import requests

from .models import LLMSettings


class LLMSettingsModelTest(TestCase):
    """Test cases for LLMSettings model"""

    def test_get_settings_creates_default_if_none_exist(self):
        """Test that get_settings creates default settings if none exist"""
        # Ensure no settings exist
        LLMSettings.objects.all().delete()
        
        settings = LLMSettings.get_settings()
        
        self.assertIsNotNone(settings)
        self.assertEqual(LLMSettings.objects.count(), 1)

    def test_get_settings_returns_existing_settings(self):
        """Test that get_settings returns existing settings"""
        # Create a settings object
        existing_settings = LLMSettings.objects.create(
            extraction_model="test-model",
            extraction_endpoint_url="http://test.com"
        )
        
        settings = LLMSettings.get_settings()
        
        self.assertEqual(settings.id, existing_settings.id)
        self.assertEqual(settings.extraction_model, "test-model")


class LLMSettingsAPITest(APITestCase):
    """Test cases for LLM Settings API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.settings_url = reverse('llm-settings')
        self.token_counts_url = reverse('prompt_token_counts')
        self.validate_endpoint_url = reverse('validate_endpoint')
        self.fetch_models_url = reverse('fetch_models')

    def test_get_settings(self):
        """Test GET /api/settings/"""
        response = self.client.get(self.settings_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('extraction_model', response.data)
        self.assertIn('extraction_endpoint_url', response.data)

    def test_update_settings(self):
        """Test PUT /api/settings/"""
        data = {
            'extraction_model': 'updated-model',
            'extraction_endpoint_url': 'http://updated.com'
        }
        
        response = self.client.put(
            self.settings_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['extraction_model'], 'updated-model')

    @patch('settings_app.views.get_token_counts_for_prompts')
    def test_get_prompt_token_counts_success(self, mock_token_counts):
        """Test successful token counts retrieval"""
        mock_token_counts.return_value = {
            'memory_extraction_prompt': 100,
            'memory_search_prompt': 50,
            'semantic_connection_prompt': 25,
            'memory_summarization_prompt': 75
        }
        
        response = self.client.get(self.token_counts_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('token_counts', response.data)

    @patch('settings_app.views.get_token_counts_for_prompts')
    def test_get_prompt_token_counts_error(self, mock_token_counts):
        """Test token counts retrieval with error"""
        mock_token_counts.side_effect = Exception("Test error")
        
        response = self.client.get(self.token_counts_url)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(response.data['success'])
        self.assertIn('error', response.data)


class ValidateEndpointAPITest(APITestCase):
    """Test cases for endpoint validation API"""

    def setUp(self):
        self.validate_url = reverse('validate_endpoint')

    def test_validate_endpoint_missing_url(self):
        """Test validation with missing URL"""
        data = {'provider_type': 'ollama'}
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('URL is required', response.data['error'])

    def test_validate_endpoint_missing_provider_type(self):
        """Test validation with missing provider type"""
        data = {'url': 'http://localhost:11434'}
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Provider type is required', response.data['error'])

    @patch('settings_app.views.requests.get')
    def test_validate_endpoint_ollama_success(self, mock_get):
        """Test successful Ollama endpoint validation"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        mock_get.assert_called_once_with(
            'http://localhost:11434/api/tags',
            headers={'Content-Type': 'application/json'},
            timeout=10
        )

    @patch('settings_app.views.requests.get')
    def test_validate_endpoint_openai_success(self, mock_get):
        """Test successful OpenAI compatible endpoint validation"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:8000',
            'provider_type': 'openai_compatible',
            'api_key': 'test-key'
        }
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        mock_get.assert_called_once_with(
            'http://localhost:8000/v1/models',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-key'
            },
            timeout=10
        )

    @patch('settings_app.views.requests.get')
    def test_validate_endpoint_timeout(self, mock_get):
        """Test endpoint validation timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_408_REQUEST_TIMEOUT)
        self.assertFalse(response.data['success'])
        self.assertIn('timed out', response.data['error'])

    @patch('settings_app.views.requests.get')
    def test_validate_endpoint_connection_error(self, mock_get):
        """Test endpoint validation connection error"""
        mock_get.side_effect = requests.exceptions.ConnectionError()
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(response.data['success'])
        self.assertIn('Could not connect', response.data['error'])

    @patch('settings_app.views.requests.get')
    def test_validate_endpoint_401_error(self, mock_get):
        """Test endpoint validation 401 authentication error"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.reason = "Unauthorized"
        mock_get.side_effect = requests.exceptions.HTTPError(response=mock_response)
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Authentication failed', response.data['error'])

    @patch('settings_app.views.requests.get')
    def test_validate_endpoint_404_error(self, mock_get):
        """Test endpoint validation 404 not found error"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_get.side_effect = requests.exceptions.HTTPError(response=mock_response)
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.validate_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Endpoint not found', response.data['error'])


class FetchModelsAPITest(APITestCase):
    """Test cases for model fetching API"""

    def setUp(self):
        self.fetch_models_url = reverse('fetch_models')

    def test_fetch_models_missing_url(self):
        """Test model fetching with missing URL"""
        data = {'provider_type': 'ollama'}
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('URL is required', response.data['error'])

    def test_fetch_models_missing_provider_type(self):
        """Test model fetching with missing provider type"""
        data = {'url': 'http://localhost:11434'}
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('Provider type is required', response.data['error'])

    @patch('settings_app.views.requests.get')
    def test_fetch_models_ollama_success(self, mock_get):
        """Test successful Ollama model fetching"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'models': [
                {'name': 'llama3:8b'},
                {'name': 'codellama:7b'},
                {'name': 'mistral:7b'}
            ]
        }
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['models']), 3)
        self.assertIn('llama3:8b', response.data['models'])
        self.assertIn('codellama:7b', response.data['models'])
        self.assertIn('mistral:7b', response.data['models'])

    @patch('settings_app.views.requests.get')
    def test_fetch_models_openai_success(self, mock_get):
        """Test successful OpenAI compatible model fetching"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'data': [
                {'id': 'gpt-4'},
                {'id': 'gpt-3.5-turbo'},
                {'id': 'text-embedding-ada-002'}
            ]
        }
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:8000',
            'provider_type': 'openai_compatible',
            'api_key': 'test-key'
        }
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['models']), 3)
        self.assertIn('gpt-4', response.data['models'])
        self.assertIn('gpt-3.5-turbo', response.data['models'])

    @patch('settings_app.views.requests.get')
    def test_fetch_models_empty_response(self, mock_get):
        """Test model fetching with empty response"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'models': []}
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(len(response.data['models']), 0)

    @patch('settings_app.views.requests.get')
    def test_fetch_models_invalid_json(self, mock_get):
        """Test model fetching with invalid JSON response"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid JSON response', response.data['error'])

    @patch('settings_app.views.requests.get')
    def test_fetch_models_timeout(self, mock_get):
        """Test model fetching timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_408_REQUEST_TIMEOUT)
        self.assertFalse(response.data['success'])
        self.assertIn('timed out', response.data['error'])

    @patch('settings_app.views.requests.get')
    def test_fetch_models_malformed_ollama_response(self, mock_get):
        """Test model fetching with malformed Ollama response"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'models': [
                {'invalid_field': 'llama3:8b'},  # Missing 'name' field
                {'name': 'codellama:7b'},
                {'name': None}  # None name
            ]
        }
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        # Should only return the valid model
        self.assertEqual(len(response.data['models']), 1)
        self.assertIn('codellama:7b', response.data['models'])

    @patch('settings_app.views.requests.get')
    def test_fetch_models_url_normalization(self, mock_get):
        """Test that URLs are properly normalized (trailing slashes removed)"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'models': []}
        mock_get.return_value = mock_response
        
        data = {
            'url': 'http://localhost:11434/',  # Note trailing slash
            'provider_type': 'ollama'
        }
        
        response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that the trailing slash was removed
        mock_get.assert_called_once_with(
            'http://localhost:11434/api/tags',  # No double slash
            headers={'Content-Type': 'application/json'},
            timeout=15
        )


class EndpointIntegrationTest(APITestCase):
    """Integration tests for endpoint validation and model fetching"""

    def setUp(self):
        self.validate_url = reverse('validate_endpoint')
        self.fetch_models_url = reverse('fetch_models')

    @patch('settings_app.views.requests.get')
    def test_validate_then_fetch_workflow(self, mock_get):
        """Test the typical workflow of validating an endpoint then fetching models"""
        # First call - validation
        mock_response_validate = Mock()
        mock_response_validate.raise_for_status.return_value = None
        
        # Second call - fetch models
        mock_response_fetch = Mock()
        mock_response_fetch.raise_for_status.return_value = None
        mock_response_fetch.json.return_value = {
            'models': [{'name': 'llama3:8b'}]
        }
        
        mock_get.side_effect = [mock_response_validate, mock_response_fetch]
        
        endpoint_data = {
            'url': 'http://localhost:11434',
            'provider_type': 'ollama'
        }
        
        # Step 1: Validate endpoint
        validate_response = self.client.post(
            self.validate_url,
            data=json.dumps(endpoint_data),
            content_type='application/json'
        )
        
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        self.assertTrue(validate_response.data['success'])
        
        # Step 2: Fetch models
        fetch_response = self.client.post(
            self.fetch_models_url,
            data=json.dumps(endpoint_data),
            content_type='application/json'
        )
        
        self.assertEqual(fetch_response.status_code, status.HTTP_200_OK)
        self.assertTrue(fetch_response.data['success'])
        self.assertEqual(len(fetch_response.data['models']), 1)
        self.assertIn('llama3:8b', fetch_response.data['models'])
        
        # Verify that both endpoints were called
        self.assertEqual(mock_get.call_count, 2)
"""
Tests for Settings model and API
"""

import uuid
from django.test import TestCase, Client
from django.core.cache import cache
from rest_framework import status

from memories.settings_model import Settings


class SettingsModelTest(TestCase):
    """Test Settings model behavior"""

    def setUp(self):
        """Clear cache and reset settings before each test"""
        cache.clear()
        Settings.objects.all().delete()

    def test_singleton_pattern(self):
        """Test that only one Settings instance can exist"""
        settings1 = Settings.get_settings()
        settings2 = Settings.get_settings()

        self.assertEqual(settings1.id, settings2.id)
        self.assertEqual(settings1.singleton_key, 1)
        self.assertEqual(Settings.objects.count(), 1)

    def test_default_values(self):
        """Test default values are correct"""
        settings = Settings.get_settings()

        # Embeddings defaults
        self.assertEqual(settings.embeddings_provider, 'ollama')
        self.assertEqual(settings.embeddings_endpoint_url, 'http://host.docker.internal:11434')
        self.assertEqual(settings.embeddings_model, 'mxbai-embed-large')
        self.assertEqual(settings.embeddings_api_key, '')
        self.assertEqual(settings.embeddings_timeout, 30)

        # Generation defaults
        self.assertEqual(settings.generation_provider, '')
        self.assertEqual(settings.generation_endpoint_url, '')
        self.assertEqual(settings.generation_model, '')
        self.assertEqual(settings.generation_api_key, '')
        self.assertEqual(settings.generation_temperature, 0.3)
        self.assertEqual(settings.generation_max_tokens, 1000)
        self.assertEqual(settings.generation_timeout, 60)

    def test_cache_clearing_on_save(self):
        """Test that cache is cleared when settings are saved"""
        settings = Settings.get_settings()

        # Verify it's cached
        cached = cache.get('mnemosyne_settings')
        self.assertIsNotNone(cached)

        # Update settings
        settings.embeddings_timeout = 45
        settings.save()

        # Cache should be cleared
        cached = cache.get('mnemosyne_settings')
        self.assertIsNone(cached)

    def test_to_dict_masks_api_keys(self):
        """Test that to_dict masks API keys"""
        settings = Settings.get_settings()
        settings.embeddings_api_key = 'sk-1234567890abcdef'
        settings.generation_api_key = 'sk-abcdef1234567890'
        settings.save()

        settings_dict = settings.to_dict(mask_api_key=True)

        # API keys should be masked
        self.assertEqual(settings_dict['embeddings_api_key'], 'sk-1...cdef')
        self.assertEqual(settings_dict['generation_api_key'], 'sk-a...7890')

    def test_to_dict_no_masking(self):
        """Test that to_dict can return unmasked keys"""
        settings = Settings.get_settings()
        settings.embeddings_api_key = 'sk-1234567890abcdef'
        settings.save()

        settings_dict = settings.to_dict(mask_api_key=False)

        # API key should NOT be masked
        self.assertEqual(settings_dict['embeddings_api_key'], 'sk-1234567890abcdef')

    def test_generation_config_fallbacks(self):
        """Test that generation config falls back to embeddings config"""
        settings = Settings.get_settings()

        settings_dict = settings.to_dict()

        # When generation fields are empty, should return embeddings values
        self.assertEqual(settings_dict['generation_provider'], settings.embeddings_provider)
        self.assertEqual(settings_dict['generation_endpoint_url'], settings.embeddings_endpoint_url)
        self.assertEqual(settings_dict['generation_model'], settings.embeddings_model)


class SettingsAPITest(TestCase):
    """Test Settings API endpoints"""

    def setUp(self):
        """Set up test client and clear settings"""
        self.client = Client()
        cache.clear()
        Settings.objects.all().delete()

    def test_get_settings(self):
        """Test GET /api/settings/"""
        response = self.client.get('/api/settings/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertIn('settings', data)
        self.assertIn('embeddings_provider', data['settings'])
        self.assertIn('generation_temperature', data['settings'])

    def test_update_embeddings_timeout(self):
        """Test updating embeddings timeout"""
        response = self.client.put(
            '/api/settings/update/',
            data={'embeddings_timeout': 45},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertIn('embeddings_timeout', data['updated_fields'])
        self.assertEqual(data['settings']['embeddings_timeout'], 45)

    def test_update_generation_temperature(self):
        """Test updating generation temperature"""
        response = self.client.put(
            '/api/settings/update/',
            data={'generation_temperature': 0.7},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(data['settings']['generation_temperature'], 0.7)

    def test_validation_temperature_too_high(self):
        """Test that temperature > 1.0 is rejected"""
        response = self.client.put(
            '/api/settings/update/',
            data={'generation_temperature': 1.5},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()

        self.assertFalse(data['success'])
        self.assertIn('Temperature must be between 0.0 and 1.0', data['error'])

    def test_validation_temperature_too_low(self):
        """Test that temperature < 0.0 is rejected"""
        response = self.client.put(
            '/api/settings/update/',
            data={'generation_temperature': -0.1},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_invalid_provider(self):
        """Test that invalid provider is rejected"""
        response = self.client.put(
            '/api/settings/update/',
            data={'embeddings_provider': 'invalid'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()

        self.assertIn('Invalid provider', data['error'])

    def test_validation_timeout_too_high(self):
        """Test that timeout > 600 is rejected"""
        response = self.client.put(
            '/api/settings/update/',
            data={'embeddings_timeout': 700},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_max_tokens_too_high(self):
        """Test that max_tokens > 100000 is rejected"""
        response = self.client.put(
            '/api/settings/update/',
            data={'generation_max_tokens': 150000},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_multiple_field_update(self):
        """Test updating multiple fields at once"""
        response = self.client.put(
            '/api/settings/update/',
            data={
                'generation_temperature': 0.5,
                'generation_max_tokens': 2000,
                'generation_timeout': 90
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data['success'])
        self.assertEqual(len(data['updated_fields']), 3)
        self.assertEqual(data['settings']['generation_temperature'], 0.5)
        self.assertEqual(data['settings']['generation_max_tokens'], 2000)
        self.assertEqual(data['settings']['generation_timeout'], 90)

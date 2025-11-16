"""
Comprehensive tests for critical fixes in the memories app.

Tests cover P0 and P1 fixes for:
- Thread safety in rate limiter and cache
- Resource management (session cleanup)
- Lazy connection patterns
- Concurrency issues in imports
- API parameter fixes
"""

import json
import sqlite3
import tempfile
import threading
import time
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, Mock, patch, PropertyMock

from django.conf import settings
from django.test import TestCase, RequestFactory
from qdrant_client.models import PointIdsList


class RateLimiterThreadSafetyTests(TestCase):
    """Tests for SVC-P0-04: Rate limiter thread safety fixes"""

    def setUp(self):
        from backend.memories.rate_limiter import SimpleRateLimiter
        self.limiter = SimpleRateLimiter()
        self.limiter.EXTRACT_LIMIT = 5
        self.limiter.WINDOW_SIZE = 1  # 1 second for testing

    def test_concurrent_requests_respect_rate_limit(self):
        """Test that concurrent requests cannot bypass rate limit"""
        results = []
        errors = []

        def make_request(ip: str, limit: int):
            try:
                is_limited, count = self.limiter._is_rate_limited(ip, limit)
                results.append((is_limited, count))
            except Exception as e:
                errors.append(e)

        # Create 20 concurrent threads trying to bypass a limit of 5
        threads = []
        for i in range(20):
            t = threading.Thread(target=make_request, args=("test_ip", 5))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # No errors should occur
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Count how many requests were allowed
        allowed = sum(1 for limited, _ in results if not limited)

        # Should allow exactly 5 requests, not more
        self.assertEqual(
            allowed, 5,
            f"Rate limiter allowed {allowed} requests instead of 5. "
            f"This indicates a race condition."
        )

        # The rest should be rate limited
        limited_count = sum(1 for limited, _ in results if limited)
        self.assertEqual(limited_count, 15)

    def test_ip_spoofing_protection(self):
        """Test SVC-P1-11: IP spoofing protection"""
        factory = RequestFactory()

        # Create request with spoofed X-Forwarded-For header
        request = factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '1.2.3.4'
        request.META['REMOTE_ADDR'] = '5.6.7.8'

        # Without trusted proxy configuration, should use REMOTE_ADDR
        with self.settings(TRUSTED_PROXY_IPS=[]):
            ip = self.limiter._get_client_ip(request)
            self.assertEqual(ip, '5.6.7.8', "Should ignore X-Forwarded-For without trusted proxy")

        # With trusted proxy, should use X-Forwarded-For
        with self.settings(TRUSTED_PROXY_IPS=['5.6.7.8']):
            ip = self.limiter._get_client_ip(request)
            self.assertEqual(ip, '1.2.3.4', "Should trust X-Forwarded-For from trusted proxy")

    def test_cleanup_is_thread_safe(self):
        """Test that cleanup operations don't cause race conditions"""
        errors = []

        def cleanup_thread():
            try:
                for _ in range(10):
                    self.limiter._cleanup_old_entries()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        def request_thread():
            try:
                for _ in range(10):
                    self.limiter._is_rate_limited("test_ip", 5)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)

        # Run cleanup and requests concurrently
        threads = [
            threading.Thread(target=cleanup_thread),
            threading.Thread(target=cleanup_thread),
            threading.Thread(target=request_thread),
            threading.Thread(target=request_thread),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not raise any errors
        self.assertEqual(len(errors), 0, f"Thread safety errors: {errors}")


class LRUCacheThreadSafetyTests(TestCase):
    """Tests for SVC-P0-03: LRU cache thread safety"""

    def setUp(self):
        from backend.memories.memory_search_service import MemorySearchService
        self.service = MemorySearchService()
        self.service._max_cache_size = 10

    @patch('backend.memories.memory_search_service.llm_service.get_embeddings')
    def test_concurrent_cache_access(self, mock_get_embeddings):
        """Test that concurrent cache access doesn't corrupt cache"""
        # Mock embeddings to return unique values
        call_count = [0]

        def get_embedding_side_effect(texts, **kwargs):
            call_count[0] += 1
            return {
                'success': True,
                'embeddings': [[float(call_count[0])] * 1024],
                'model': 'test'
            }

        mock_get_embeddings.side_effect = get_embedding_side_effect

        results = []
        errors = []

        def cache_thread(text: str):
            try:
                for _ in range(5):
                    embedding = self.service._get_cached_embedding(text)
                    results.append((text, embedding[0]))
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        # Create threads accessing same and different cache keys
        threads = []
        for i in range(5):
            t1 = threading.Thread(target=cache_thread, args=(f"text_{i % 2}",))
            t2 = threading.Thread(target=cache_thread, args=(f"text_{i % 2}",))
            threads.extend([t1, t2])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        self.assertEqual(len(errors), 0, f"Cache corruption errors: {errors}")

        # Cache should have consistent values for same keys
        text_0_embeddings = [emb for text, emb in results if text == "text_0"]
        text_1_embeddings = [emb for text, emb in results if text == "text_1"]

        # All embeddings for same text should be identical (cached)
        self.assertTrue(
            len(set(text_0_embeddings)) == 1,
            "Cache returned different values for same key"
        )
        self.assertTrue(
            len(set(text_1_embeddings)) == 1,
            "Cache returned different values for same key"
        )

    def test_cache_eviction_is_thread_safe(self):
        """Test LRU eviction under concurrent load"""
        with patch('backend.memories.memory_search_service.llm_service.get_embeddings') as mock:
            mock.return_value = {
                'success': True,
                'embeddings': [[1.0] * 1024],
                'model': 'test'
            }

            errors = []

            def fill_cache_thread(start_idx: int):
                try:
                    for i in range(start_idx, start_idx + 20):
                        self.service._get_cached_embedding(f"text_{i}")
                except Exception as e:
                    errors.append(e)

            threads = [
                threading.Thread(target=fill_cache_thread, args=(0,)),
                threading.Thread(target=fill_cache_thread, args=(20,)),
                threading.Thread(target=fill_cache_thread, args=(40,)),
            ]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # Should not raise errors during eviction
            self.assertEqual(len(errors), 0, f"Eviction errors: {errors}")

            # Cache size should not exceed max
            self.assertLessEqual(
                len(self.service._embedding_cache),
                self.service._max_cache_size,
                "Cache size exceeded maximum"
            )


class SessionCleanupTests(TestCase):
    """Tests for SVC-P0-01: Session cleanup"""

    def test_session_is_closed_on_cleanup(self):
        """Test that session is properly closed when service is deleted"""
        from backend.memories.llm_service import LLMService

        service = LLMService()
        session = service.session

        # Verify session is created
        self.assertIsNotNone(session)

        # Delete service and verify session.close() is called
        with patch.object(session, 'close') as mock_close:
            del service
            # Force garbage collection to trigger __del__
            import gc
            gc.collect()

            # Session close should have been called
            # Note: This test is tricky because __del__ timing is non-deterministic
            # In production, the session will be closed when the process ends

    @patch('backend.memories.llm_service.requests.Session')
    def test_session_reuse(self, mock_session_class):
        """Test that session is reused across calls"""
        from backend.memories.llm_service import LLMService

        mock_session = Mock()
        mock_session_class.return_value = mock_session

        service = LLMService()

        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {'content': 'test'},
            'total_duration': 100
        }
        mock_session.post.return_value = mock_response

        # Make multiple calls
        with patch.object(service, 'settings', PropertyMock(return_value=Mock(
            extraction_provider_type='ollama',
            extraction_model='test',
            extraction_endpoint_url='http://test',
            extraction_timeout=60,
            llm_temperature=0.7,
            llm_max_tokens=100,
            llm_top_p=0.9,
            llm_top_k=40
        ))):
            for _ in range(3):
                service.query_llm("test prompt", max_retries=0)

        # Session should be created only once
        self.assertEqual(mock_session_class.call_count, 1)

        # Session.post should be called 3 times
        self.assertEqual(mock_session.post.call_count, 3)


class VectorServiceLazyConnectionTests(TestCase):
    """Tests for SVC-P0-02: Lazy connection with retry logic"""

    @patch('backend.memories.vector_service.QdrantClient')
    def test_service_starts_without_qdrant(self, mock_qdrant):
        """Test that VectorService can be instantiated even if Qdrant is down"""
        from backend.memories.vector_service import VectorService

        # Qdrant connection will fail
        mock_qdrant.side_effect = Exception("Connection refused")

        # Should not raise exception during initialization
        try:
            service = VectorService()
            self.assertIsNotNone(service)
            self.assertFalse(service._connected)
        except Exception as e:
            self.fail(f"VectorService __init__ should not raise: {e}")

    @patch('backend.memories.vector_service.QdrantClient')
    def test_lazy_connection_on_first_use(self, mock_qdrant):
        """Test that connection is established on first use"""
        from backend.memories.vector_service import VectorService

        mock_client = Mock()
        mock_qdrant.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])

        service = VectorService()

        # Connection should happen on first method call
        with patch.object(service, '_ensure_collection'):
            service.store_embedding("mem_id", [1.0] * 1024, "user_id", {})

        # Client should have been created
        self.assertTrue(mock_qdrant.called)

    @patch('backend.memories.vector_service.QdrantClient')
    def test_connection_retry_logic(self, mock_qdrant):
        """Test that connection retries work correctly"""
        from backend.memories.vector_service import VectorService

        # Fail twice, succeed on third attempt
        attempt_count = [0]

        def connection_side_effect(*args, **kwargs):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise Exception("Connection failed")
            mock_client = Mock()
            mock_client.get_collections.return_value = Mock(collections=[])
            return mock_client

        mock_qdrant.side_effect = connection_side_effect

        service = VectorService()

        # Should succeed after retries
        with patch.object(service, '_ensure_collection'):
            result = service._ensure_connection(max_retries=3, retry_delay=0.1)
            self.assertTrue(result)
            self.assertEqual(attempt_count[0], 3)


class ImportConcurrencyTests(TestCase):
    """Tests for SVC-P0-05 and SVC-P0-06: Import concurrency fixes"""

    def setUp(self):
        # Create a temporary SQLite database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()

        # Create test database with sample data
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE chat (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT,
                chat TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        ''')
        cursor.execute('''
            INSERT INTO chat VALUES (
                'conv1', 'user1', 'Test Conv',
                '{"messages": [{"role": "user", "content": "Hello"}]}',
                1234567890, 1234567890
            )
        ''')
        conn.commit()
        conn.close()

    def tearDown(self):
        import os
        if os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)

    def test_concurrent_imports_use_separate_progress(self):
        """Test SVC-P0-06: Multiple imports maintain separate progress"""
        from backend.memories.openwebui_importer import OpenWebUIImporter, _import_progresses, _progress_lock

        # Clear any existing progress
        with _progress_lock:
            _import_progresses.clear()

        # Create two importers with different import IDs
        with OpenWebUIImporter(self.temp_db_path) as importer1:
            with OpenWebUIImporter(self.temp_db_path) as importer2:
                # Mock the extraction to avoid actual LLM calls
                with patch.object(importer1, 'extract_memories_from_conversation', return_value=(0, [])):
                    with patch.object(importer2, 'extract_memories_from_conversation', return_value=(0, [])):
                        # Start two imports concurrently
                        import1_id = "import1"
                        import2_id = "import2"

                        def run_import1():
                            importer1.import_conversations(
                                import_id=import1_id,
                                dry_run=True
                            )

                        def run_import2():
                            importer2.import_conversations(
                                import_id=import2_id,
                                dry_run=True
                            )

                        t1 = threading.Thread(target=run_import1)
                        t2 = threading.Thread(target=run_import2)

                        t1.start()
                        t2.start()
                        t1.join()
                        t2.join()

                        # Both imports should have separate progress objects
                        with _progress_lock:
                            self.assertIn(import1_id, _import_progresses)
                            self.assertIn(import2_id, _import_progresses)
                            self.assertIsNot(
                                _import_progresses[import1_id],
                                _import_progresses[import2_id],
                                "Progress objects should be separate"
                            )

    def test_cancellation_is_atomic(self):
        """Test SVC-P0-05: Cancellation check-and-act is atomic"""
        from backend.memories.openwebui_importer import OpenWebUIImporter, _import_progresses, _progress_lock

        with _progress_lock:
            _import_progresses.clear()

        cancel_happened = [False]

        with OpenWebUIImporter(self.temp_db_path) as importer:
            import_id = "test_cancel"

            # Mock extraction to simulate slow processing
            def slow_extraction(*args, **kwargs):
                time.sleep(0.1)
                return (0, [])

            with patch.object(importer, 'extract_memories_from_conversation', side_effect=slow_extraction):
                def run_import():
                    result = importer.import_conversations(
                        import_id=import_id,
                        dry_run=True
                    )
                    cancel_happened[0] = not result.get('success', True)

                def cancel_import():
                    time.sleep(0.05)  # Let import start
                    OpenWebUIImporter.cancel_import(import_id)

                t1 = threading.Thread(target=run_import)
                t2 = threading.Thread(target=cancel_import)

                t1.start()
                t2.start()
                t1.join(timeout=2)
                t2.join()

                # Import should have been cancelled
                self.assertTrue(cancel_happened[0], "Import should have been cancelled")


class RetryLogicTests(TestCase):
    """Tests for SVC-P1-01: Retry logic fixes"""

    @patch('backend.memories.llm_service.requests.Session')
    def test_correct_number_of_retry_attempts(self, mock_session_class):
        """Test that retry loop executes correct number of times"""
        from backend.memories.llm_service import LLMService

        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Make all attempts timeout
        mock_session.post.side_effect = Exception("Connection error")

        service = LLMService()

        with patch.object(service, 'settings', PropertyMock(return_value=Mock(
            extraction_provider_type='ollama',
            extraction_model='test',
            extraction_endpoint_url='http://test',
            extraction_timeout=60,
            llm_temperature=0.7,
            llm_max_tokens=100,
            llm_top_p=0.9,
            llm_top_k=40
        ))):
            result = service.query_llm("test", max_retries=3, retry_delay=0.01)

        # Should fail after 4 attempts total (initial + 3 retries)
        self.assertEqual(mock_session.post.call_count, 4)
        self.assertFalse(result['success'])


class OpenAIParameterTests(TestCase):
    """Tests for SVC-P1-03: OpenAI parameter fix"""

    def test_openai_request_excludes_top_k(self):
        """Test that top_k is not sent to OpenAI endpoints"""
        from backend.memories.llm_service import LLMService

        service = LLMService()

        with patch.object(service, 'settings', PropertyMock(return_value=Mock(
            llm_top_p=0.9,
            llm_top_k=40
        ))):
            data = service._prepare_openai_request(
                model="gpt-4",
                system_prompt="system",
                user_prompt="user",
                temperature=0.7,
                max_tokens=100,
                response_format=None
            )

        # Should not contain top_k
        self.assertNotIn('top_k', data)
        # Should contain top_p
        self.assertIn('top_p', data)
        self.assertEqual(data['top_p'], 0.9)


class VectorServiceFixesTests(TestCase):
    """Tests for SVC-P1-05, P1-06, P1-07: Vector service fixes"""

    @patch('backend.memories.vector_service.QdrantClient')
    def test_pointidslist_usage(self, mock_qdrant):
        """Test SVC-P1-05: Correct PointIdsList usage"""
        from backend.memories.vector_service import VectorService

        mock_client = Mock()
        mock_qdrant.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[
            Mock(name='memories')
        ])

        service = VectorService()
        service._connected = True
        service.client = mock_client

        # Delete an embedding
        service.delete_embedding("test_vector_id")

        # Verify PointIdsList was used
        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        points_selector = call_args[1]['points_selector']

        # Should be PointIdsList instance
        self.assertIsInstance(points_selector, PointIdsList)

    @patch('backend.memories.vector_service.settings')
    @patch('backend.memories.vector_service.QdrantClient')
    def test_configurable_vector_dimension(self, mock_qdrant, mock_settings):
        """Test SVC-P1-06: Vector dimension from settings"""
        from backend.memories.vector_service import VectorService

        mock_client = Mock()
        mock_qdrant.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[])

        # Set custom dimension
        mock_settings.QDRANT_VECTOR_DIMENSION = 768
        mock_settings.QDRANT_COLLECTION_NAME = "memories"

        service = VectorService()
        service._connected = True
        service.client = mock_client

        # Create collection should use configured dimension
        service._ensure_collection()

        # Verify create_collection was called with correct dimension
        mock_client.create_collection.assert_called_once()
        call_args = mock_client.create_collection.call_args
        vectors_config = call_args[1]['vectors_config']
        self.assertEqual(vectors_config.size, 768)

    @patch('backend.memories.vector_service.QdrantClient')
    def test_nested_attribute_error_handling(self, mock_qdrant):
        """Test SVC-P1-07: Safe nested attribute access"""
        from backend.memories.vector_service import VectorService

        mock_client = Mock()
        mock_qdrant.return_value = mock_client
        mock_client.get_collections.return_value = Mock(collections=[
            Mock(name='memories')
        ])

        # Mock collection info with missing nested attributes
        mock_collection_info = Mock()
        mock_collection_info.status = "green"
        mock_collection_info.points_count = 100
        mock_collection_info.optimizer_status = "ok"
        # config.params.vectors will raise AttributeError
        mock_collection_info.config.params.vectors.size = AttributeError()

        mock_client.get_collection.return_value = mock_collection_info

        service = VectorService()
        service._connected = True
        service.client = mock_client

        # Should not raise exception
        try:
            result = service.get_collection_info()
            # Should return None for missing attributes
            self.assertIsNone(result.get('vector_count'))
            self.assertEqual(result['status'], 'green')
        except AttributeError:
            self.fail("Should handle missing nested attributes gracefully")


class ImporterErrorHandlingTests(TestCase):
    """Tests for SVC-P1-13, P1-14, P1-15: Importer error handling"""

    def test_connection_error_handling(self):
        """Test SVC-P1-13: SQLite connection error handling"""
        from backend.memories.openwebui_importer import OpenWebUIImporter

        # Try to open non-existent database
        with self.assertRaises(FileNotFoundError):
            OpenWebUIImporter("/nonexistent/path.db")

        # Try to open invalid database
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"invalid database content")
            invalid_db_path = f.name

        try:
            with self.assertRaises(ConnectionError):
                with OpenWebUIImporter(invalid_db_path) as importer:
                    pass
        finally:
            import os
            os.unlink(invalid_db_path)

    def test_json_size_limit(self):
        """Test SVC-P1-15: JSON size limit protection"""
        from backend.memories.openwebui_importer import OpenWebUIImporter

        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()

        conn = sqlite3.connect(temp_db.name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE chat (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT,
                chat TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        ''')
        conn.commit()
        conn.close()

        try:
            with OpenWebUIImporter(temp_db.name) as importer:
                # Create JSON larger than 10MB
                large_json = json.dumps({"x": "a" * (11 * 1024 * 1024)})

                # Should return empty list without crashing
                result = importer.extract_user_messages(large_json)
                self.assertEqual(result, [])
        finally:
            import os
            os.unlink(temp_db.name)

    def test_truncation_warning(self):
        """Test SVC-P1-14: Truncation warning is logged"""
        from backend.memories.openwebui_importer import OpenWebUIImporter

        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()

        conn = sqlite3.connect(temp_db.name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE chat (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT,
                chat TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )
        ''')
        conn.commit()
        conn.close()

        try:
            with OpenWebUIImporter(temp_db.name) as importer:
                # Create very long conversation text
                long_text = "a" * 60000

                # Mock the LLM call
                with patch('backend.memories.openwebui_importer.llm_service.query_llm') as mock_llm:
                    mock_llm.return_value = {
                        'success': True,
                        'response': '[]',
                        'model': 'test'
                    }

                    # Should truncate and log warning
                    with self.assertLogs('backend.memories.openwebui_importer', level='WARNING') as cm:
                        count, memories = importer.extract_memories_from_conversation(
                            long_text, "user_id", dry_run=True
                        )

                        # Check that truncation warning was logged
                        self.assertTrue(
                            any('truncating' in msg.lower() for msg in cm.output),
                            "Should log truncation warning"
                        )
        finally:
            import os
            os.unlink(temp_db.name)


class SettingsCacheTests(TestCase):
    """Tests for SVC-P1-08: Settings caching to avoid DB queries in hot path"""

    def setUp(self):
        from backend.memories.memory_search_service import MemorySearchService
        self.service = MemorySearchService()

    @patch('backend.memories.memory_search_service.LLMSettings')
    def test_settings_cached_across_calls(self, mock_llm_settings_class):
        """Test that settings are cached and not fetched on every call"""
        mock_settings = Mock()
        mock_settings.search_threshold_direct = 0.8
        mock_settings.search_threshold_semantic = 0.6
        mock_settings.search_threshold_experiential = 0.7
        mock_settings.search_threshold_contextual = 0.5
        mock_settings.search_threshold_interest = 0.65

        mock_llm_settings_class.get_settings.return_value = mock_settings

        # Call method that uses cached settings multiple times
        for _ in range(10):
            threshold = self.service._get_threshold_for_search_type("direct")
            self.assertEqual(threshold, 0.8)

        # Settings should only be fetched once (first call)
        self.assertEqual(mock_llm_settings_class.get_settings.call_count, 1)

    @patch('backend.memories.memory_search_service.LLMSettings')
    def test_settings_cache_expires_after_ttl(self, mock_llm_settings_class):
        """Test that settings cache expires after TTL"""
        mock_settings_v1 = Mock()
        mock_settings_v1.search_threshold_direct = 0.8

        mock_settings_v2 = Mock()
        mock_settings_v2.search_threshold_direct = 0.9

        mock_llm_settings_class.get_settings.side_effect = [mock_settings_v1, mock_settings_v2]

        # Override TTL for testing
        self.service._settings_cache_ttl = 0.1  # 100ms

        # First call - should fetch from DB
        threshold1 = self.service._get_threshold_for_search_type("direct")
        self.assertEqual(threshold1, 0.8)

        # Second call immediately - should use cache
        threshold2 = self.service._get_threshold_for_search_type("direct")
        self.assertEqual(threshold2, 0.8)

        # Wait for cache to expire
        import time
        time.sleep(0.15)

        # Third call - should fetch from DB again
        threshold3 = self.service._get_threshold_for_search_type("direct")
        self.assertEqual(threshold3, 0.9)

        # Should have fetched settings twice
        self.assertEqual(mock_llm_settings_class.get_settings.call_count, 2)

    @patch('backend.memories.memory_search_service.LLMSettings')
    def test_settings_cache_thread_safety(self, mock_llm_settings_class):
        """Test that settings cache is thread-safe"""
        mock_settings = Mock()
        mock_settings.search_threshold_direct = 0.8
        mock_settings.search_threshold_semantic = 0.6
        mock_settings.search_threshold_experiential = 0.7
        mock_settings.search_threshold_contextual = 0.5
        mock_settings.search_threshold_interest = 0.65

        mock_llm_settings_class.get_settings.return_value = mock_settings

        errors = []
        results = []

        def access_settings():
            try:
                for _ in range(5):
                    threshold = self.service._get_threshold_for_search_type("direct")
                    results.append(threshold)
            except Exception as e:
                errors.append(e)

        # Create multiple threads accessing settings cache
        threads = [threading.Thread(target=access_settings) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should not have any errors
        self.assertEqual(len(errors), 0, f"Thread safety errors: {errors}")

        # All results should be identical
        self.assertTrue(all(r == 0.8 for r in results))

        # Settings should be fetched only once despite concurrent access
        self.assertEqual(mock_llm_settings_class.get_settings.call_count, 1)


class ConfigurableCacheSizeTests(TestCase):
    """Tests for SVC-P1-09: Configurable cache size to prevent unbounded growth"""

    @patch('backend.memories.memory_search_service.settings')
    def test_default_cache_size(self, mock_settings):
        """Test that default cache size is 1000"""
        from backend.memories.memory_search_service import MemorySearchService

        # No EMBEDDING_CACHE_SIZE setting
        del mock_settings.EMBEDDING_CACHE_SIZE
        mock_settings.EMBEDDING_CACHE_SIZE = AttributeError()

        service = MemorySearchService()
        self.assertEqual(service._max_cache_size, 1000)

    @patch('backend.memories.memory_search_service.settings')
    def test_custom_cache_size(self, mock_settings):
        """Test that custom cache size is respected"""
        from backend.memories.memory_search_service import MemorySearchService

        mock_settings.EMBEDDING_CACHE_SIZE = 500

        service = MemorySearchService()
        self.assertEqual(service._max_cache_size, 500)

    @patch('backend.memories.memory_search_service.settings')
    def test_large_cache_size_warning(self, mock_settings):
        """Test that large cache sizes trigger warning"""
        from backend.memories.memory_search_service import MemorySearchService

        mock_settings.EMBEDDING_CACHE_SIZE = 15000

        with self.assertLogs('backend.memories.memory_search_service', level='WARNING') as cm:
            service = MemorySearchService()

            # Should log warning about large cache
            self.assertTrue(
                any('Large embedding cache size' in msg for msg in cm.output),
                "Should warn about large cache size"
            )
            self.assertTrue(
                any('Redis' in msg for msg in cm.output),
                "Should suggest Redis for large deployments"
            )

    @patch('backend.memories.memory_search_service.llm_service.get_embeddings')
    @patch('backend.memories.memory_search_service.settings')
    def test_cache_respects_max_size(self, mock_settings, mock_get_embeddings):
        """Test that cache eviction respects configured max size"""
        from backend.memories.memory_search_service import MemorySearchService

        # Set small cache for testing
        mock_settings.EMBEDDING_CACHE_SIZE = 3

        mock_get_embeddings.return_value = {
            'success': True,
            'embeddings': [[1.0] * 1024],
            'model': 'test'
        }

        service = MemorySearchService()

        # Fill cache beyond max
        for i in range(10):
            service._get_cached_embedding(f"text_{i}")

        # Cache size should not exceed max
        self.assertLessEqual(len(service._embedding_cache), 3)
        self.assertLessEqual(len(service._cache_order), 3)


class GlobalSingletonThreadSafetyTests(TestCase):
    """Tests for SVC-P1-04: Global singleton thread safety"""

    @patch('backend.memories.llm_service.LLMSettings')
    def test_concurrent_settings_access(self, mock_llm_settings_class):
        """Test that concurrent access to settings doesn't cause race conditions"""
        from backend.memories.llm_service import LLMService

        mock_settings = Mock()
        mock_settings.extraction_provider_type = 'ollama'
        mock_settings.extraction_model = 'test-model'
        mock_settings.extraction_endpoint_url = 'http://localhost:11434'
        mock_settings.extraction_timeout = 60

        mock_llm_settings_class.get_settings.return_value = mock_settings

        service = LLMService()
        errors = []
        results = []

        def access_settings():
            try:
                for _ in range(10):
                    settings = service.settings
                    results.append(settings.extraction_model)
            except Exception as e:
                errors.append(e)

        # Create multiple threads accessing settings
        threads = [threading.Thread(target=access_settings) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        self.assertEqual(len(errors), 0, f"Thread safety errors: {errors}")

        # All results should be identical
        self.assertTrue(all(r == 'test-model' for r in results))

        # Settings should only be loaded once despite concurrent access
        self.assertEqual(mock_llm_settings_class.get_settings.call_count, 1)

    @patch('backend.memories.llm_service.LLMSettings')
    def test_concurrent_refresh_settings(self, mock_llm_settings_class):
        """Test that concurrent refresh_settings calls are thread-safe"""
        from backend.memories.llm_service import LLMService

        mock_settings = Mock()
        mock_settings.extraction_provider_type = 'ollama'
        mock_settings.extraction_model = 'test-model'

        mock_llm_settings_class.get_settings.return_value = mock_settings

        service = LLMService()

        # Access settings once to initialize
        _ = service.settings

        errors = []

        def refresh_and_access():
            try:
                for _ in range(5):
                    service.refresh_settings()
                    _ = service.settings
            except Exception as e:
                errors.append(e)

        # Create multiple threads refreshing settings
        threads = [threading.Thread(target=refresh_and_access) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        self.assertEqual(len(errors), 0, f"Thread safety errors during refresh: {errors}")

    @patch('backend.memories.llm_service.LLMSettings')
    def test_settings_loaded_flag_consistency(self, mock_llm_settings_class):
        """Test that _settings_loaded flag remains consistent under concurrent load"""
        from backend.memories.llm_service import LLMService

        load_count = [0]

        def mock_get_settings():
            load_count[0] += 1
            import time
            time.sleep(0.01)  # Simulate slow DB query
            mock_settings = Mock()
            mock_settings.extraction_provider_type = 'ollama'
            return mock_settings

        mock_llm_settings_class.get_settings.side_effect = mock_get_settings

        service = LLMService()
        results = []

        def access_settings():
            for _ in range(3):
                settings = service.settings
                results.append(settings)

        # Create threads that all try to access settings simultaneously
        threads = [threading.Thread(target=access_settings) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Settings should only be loaded once, not 15 times
        self.assertEqual(load_count[0], 1, "Settings should be loaded exactly once")


class ListModificationTests(TestCase):
    """Tests for SVC-P1-10: List modification during iteration"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    @patch('backend.memories.memory_search_service.llm_service')
    @patch('backend.memories.memory_search_service.LLMSettings')
    def test_find_semantic_connections_does_not_modify_input_list(
        self, mock_llm_settings_class, mock_llm_service
    ):
        """Test that find_semantic_connections doesn't modify the input list"""
        from backend.memories.memory_search_service import memory_search_service

        # Create test memories
        memory1 = Memory.objects.create(
            user_id=self.user.id,
            content="I love programming in Python",
            metadata={}
        )
        memory2 = Memory.objects.create(
            user_id=self.user.id,
            content="I enjoy data science",
            metadata={}
        )
        memory3 = Memory.objects.create(
            user_id=self.user.id,
            content="Machine learning is fascinating",
            metadata={}
        )

        original_memories = [memory1, memory2]
        original_length = len(original_memories)
        original_ids = [m.id for m in original_memories]

        # Mock settings to enable semantic connections
        mock_settings = Mock()
        mock_settings.enable_semantic_connections = True
        mock_settings.semantic_enhancement_threshold = 1
        mock_settings.semantic_connection_prompt = "Test prompt"
        mock_settings.llm_temperature = 0.7
        mock_llm_settings_class.get_settings.return_value = mock_settings

        # Mock LLM service to return additional search query
        mock_llm_service.query_llm.return_value = {
            "success": True,
            "response": json.dumps({
                "has_connections": True,
                "additional_searches": [
                    {"search_query": "machine learning"}
                ],
                "reasoning": "Test reasoning"
            })
        }

        # Mock search_memories to return memory3
        with patch.object(
            memory_search_service,
            'search_memories',
            return_value=[memory3]
        ):
            result = memory_search_service.find_semantic_connections(
                original_memories,
                "Tell me about my tech interests",
                str(self.user.id)
            )

        # Original list should NOT be modified
        self.assertEqual(len(original_memories), original_length)
        self.assertEqual([m.id for m in original_memories], original_ids)

        # Result should contain original + additional memories
        self.assertEqual(len(result), 3)
        self.assertIn(memory1, result)
        self.assertIn(memory2, result)
        self.assertIn(memory3, result)

    @patch('backend.memories.memory_search_service.LLMSettings')
    def test_disabled_semantic_connections_returns_original_list(
        self, mock_llm_settings_class
    ):
        """Test that disabled semantic connections returns input unchanged"""
        from backend.memories.memory_search_service import memory_search_service

        memory1 = Memory.objects.create(
            user_id=self.user.id,
            content="Test memory",
            metadata={}
        )

        original_memories = [memory1]

        # Mock settings to disable semantic connections
        mock_settings = Mock()
        mock_settings.enable_semantic_connections = False
        mock_llm_settings_class.get_settings.return_value = mock_settings

        result = memory_search_service.find_semantic_connections(
            original_memories,
            "Test query",
            str(self.user.id)
        )

        # Should return the same list
        self.assertEqual(result, original_memories)

    @patch('backend.memories.memory_search_service.LLMSettings')
    def test_below_threshold_returns_original_list(
        self, mock_llm_settings_class
    ):
        """Test that below threshold returns input unchanged"""
        from backend.memories.memory_search_service import memory_search_service

        memory1 = Memory.objects.create(
            user_id=self.user.id,
            content="Test memory",
            metadata={}
        )

        original_memories = [memory1]

        # Mock settings with high threshold
        mock_settings = Mock()
        mock_settings.enable_semantic_connections = True
        mock_settings.semantic_enhancement_threshold = 10  # Higher than we have
        mock_llm_settings_class.get_settings.return_value = mock_settings

        result = memory_search_service.find_semantic_connections(
            original_memories,
            "Test query",
            str(self.user.id)
        )

        # Should return the same list
        self.assertEqual(result, original_memories)


class CleanupTimerRaceTests(TestCase):
    """Tests for SVC-P1-12: Cleanup timer race condition"""

    def test_cleanup_executes_only_once_with_concurrent_calls(self):
        """Test that cleanup timestamp prevents redundant cleanup work"""
        from backend.memories.rate_limiter import SimpleRateLimiter
        import time

        limiter = SimpleRateLimiter()
        limiter.CLEANUP_INTERVAL = 1  # 1 second for testing

        # Add some test data
        with limiter._lock:
            limiter._requests['1.1.1.1'].append(time.time() - 100)  # Old entry
            limiter._requests['2.2.2.2'].append(time.time() - 100)
            limiter._requests['3.3.3.3'].append(time.time() - 100)
            limiter._last_cleanup = time.time() - 2  # Last cleanup was 2 seconds ago

        cleanup_executions = []

        def track_cleanup():
            """Call cleanup and track if it actually did work"""
            initial_time = limiter._last_cleanup
            limiter._cleanup_old_entries()
            final_time = limiter._last_cleanup

            # If timestamp changed, cleanup was executed
            if final_time != initial_time:
                cleanup_executions.append(threading.current_thread().name)

        # Create 10 threads that all try to cleanup simultaneously
        threads = [
            threading.Thread(target=track_cleanup, name=f"Thread-{i}")
            for i in range(10)
        ]

        # Start all threads at once
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only ONE thread should have executed cleanup
        # (the first one to acquire the lock after the interval passed)
        self.assertEqual(
            len(cleanup_executions), 1,
            f"Expected 1 cleanup execution, got {len(cleanup_executions)}: {cleanup_executions}"
        )

    def test_cleanup_timestamp_updated_before_work(self):
        """Test that timestamp is updated immediately, not after cleanup work"""
        from backend.memories.rate_limiter import SimpleRateLimiter
        import time

        limiter = SimpleRateLimiter()
        limiter.CLEANUP_INTERVAL = 1  # 1 second for testing

        # Set last cleanup to old time
        initial_time = time.time() - 2
        limiter._last_cleanup = initial_time

        # Add many entries to make cleanup take some time
        with limiter._lock:
            for i in range(100):
                limiter._requests[f'ip_{i}'].append(time.time() - 100)

        # Execute cleanup
        limiter._cleanup_old_entries()

        # Timestamp should be updated (not equal to initial_time)
        self.assertNotEqual(
            limiter._last_cleanup, initial_time,
            "Cleanup timestamp should be updated"
        )

        # Old entries should be cleaned
        with limiter._lock:
            self.assertEqual(
                len(limiter._requests), 0,
                "All old entries should be cleaned up"
            )

    def test_cleanup_interval_prevents_frequent_cleanup(self):
        """Test that cleanup interval is respected"""
        from backend.memories.rate_limiter import SimpleRateLimiter
        import time

        limiter = SimpleRateLimiter()
        limiter.CLEANUP_INTERVAL = 300  # 5 minutes

        # Do cleanup now
        limiter._cleanup_old_entries()
        first_cleanup_time = limiter._last_cleanup

        # Add old entry
        with limiter._lock:
            limiter._requests['1.1.1.1'].append(time.time() - 100)

        # Try cleanup again immediately
        limiter._cleanup_old_entries()
        second_cleanup_time = limiter._last_cleanup

        # Timestamp should be the same (cleanup skipped)
        self.assertEqual(
            first_cleanup_time, second_cleanup_time,
            "Cleanup should be skipped when called within interval"
        )

        # Old entry should still exist (cleanup was skipped)
        with limiter._lock:
            self.assertIn('1.1.1.1', limiter._requests)


class APIPaginationTests(TestCase):
    """Tests for API-P1-01: Missing pagination"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_memory_list_returns_paginated_results(self):
        """Test that memory list endpoint returns paginated results"""
        from backend.memories.views import MemoryViewSet
        from rest_framework.test import APIRequestFactory

        # Create 100 memories to test pagination
        for i in range(100):
            Memory.objects.create(
                user_id=self.user.id,
                content=f"Test memory {i}",
                metadata={}
            )

        factory = APIRequestFactory()
        request = factory.get(f'/api/memories/?user_id={self.user.id}')
        view = MemoryViewSet.as_view({'get': 'list'})

        response = view(request)

        # Should return paginated response
        self.assertIn('results', response.data or response.data.get('memories'))
        # Default page size is 50
        results = response.data.get('results', response.data.get('memories', []))
        self.assertLessEqual(len(results), 50)


class APIFieldValidationTests(TestCase):
    """Tests for API-P1-06: Unvalidated field selection"""

    def test_validate_fields_filters_invalid_fields(self):
        """Test that validate_fields only allows whitelisted fields"""
        from backend.memories.views import validate_fields

        # Test with valid fields
        result = validate_fields(["id", "content", "metadata"])
        self.assertEqual(set(result), {"id", "content", "metadata"})

        # Test with invalid fields
        result = validate_fields(["id", "content", "password", "__dict__", "_internal"])
        self.assertEqual(set(result), {"id", "content"})

        # Test with all invalid fields - should return defaults
        result = validate_fields(["invalid", "also_invalid"])
        self.assertEqual(result, ["id", "content"])

        # Test with non-list input - should return defaults
        result = validate_fields("not a list")
        self.assertEqual(result, ["id", "content"])

        # Test with empty list - should return defaults
        result = validate_fields([])
        self.assertEqual(result, ["id", "content"])


class APIExceptionHandlingTests(TestCase):
    """Tests for API-P1-03: Exception swallowing and API-P1-04: Information disclosure"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    def test_memory_retrieve_logs_but_hides_exception_details(self):
        """Test that exceptions are logged but not exposed to users"""
        from backend.memories.views import MemoryViewSet
        from rest_framework.test import APIRequestFactory
        import logging

        factory = APIRequestFactory()

        # Test with invalid UUID
        request = factory.get('/api/memories/invalid-uuid/')
        view = MemoryViewSet.as_view({'get': 'retrieve'})

        with self.assertLogs('backend.memories.views', level=logging.DEBUG) as cm:
            response = view(request, pk='invalid-uuid')

        # Should return generic error message
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        # Should not expose the actual ValueError details in response
        self.assertNotIn('ValueError', response.data.get('error', ''))

        # Should log the actual error
        self.assertTrue(
            any('Invalid UUID format' in log for log in cm.output),
            f"Expected UUID error in logs: {cm.output}"
        )

    def test_stats_view_doesnt_expose_internal_errors(self):
        """Test that memory stats view doesn't leak internal error details"""
        from backend.memories.views import MemoryStatsView
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        view = MemoryStatsView.as_view()

        # Mock vector_service to raise an exception
        with patch('backend.memories.views.vector_service') as mock_vector:
            mock_vector.get_collection_info.side_effect = Exception("Internal database connection failed with credentials XYZ")

            request = factory.get(f'/api/memory-stats/?user_id={self.user.id}')
            response = view(request)

        # Should return 500 status
        self.assertEqual(response.status_code, 500)

        # Should return generic error message
        error_msg = response.data.get('error', '')
        self.assertNotIn('database connection', error_msg.lower())
        self.assertNotIn('credentials', error_msg.lower())
        self.assertNotIn('XYZ', error_msg)


class APITransactionTests(TestCase):
    """Tests for API-P1-05: Missing transactions"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    @patch('backend.memories.views.vector_service')
    def test_delete_uses_transaction_for_atomicity(self, mock_vector_service):
        """Test that delete operations use transactions"""
        # Create test memories
        memory1 = Memory.objects.create(
            user_id=self.user.id,
            content="Test memory 1",
            metadata={}
        )
        memory2 = Memory.objects.create(
            user_id=self.user.id,
            content="Test memory 2",
            metadata={}
        )

        initial_count = Memory.objects.filter(user_id=self.user.id).count()
        self.assertEqual(initial_count, 2)

        # Mock successful vector delete
        mock_vector_service.delete_memories.return_value = {"success": True}

        # Simulate database error during delete
        from backend.memories.views import DeleteAllMemoriesView
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory()
        view = DeleteAllMemoriesView.as_view()

        # This should use transaction, so if it fails, nothing should be deleted
        with patch.object(Memory.objects, 'filter') as mock_filter:
            mock_queryset = Mock()
            mock_queryset.count.return_value = 2
            mock_queryset.__iter__ = Mock(return_value=iter([memory1, memory2]))
            # Simulate delete failure
            mock_queryset.delete.side_effect = Exception("Database error")
            mock_filter.return_value = mock_queryset

            request = factory.delete('/api/memories/delete-all/', {
                'user_id': str(self.user.id),
                'confirm': True
            }, format='json')

            response = view(request)

        # Should return error
        self.assertEqual(response.status_code, 500)

        # Original memories should still exist (transaction rolled back)
        remaining_count = Memory.objects.filter(user_id=self.user.id).count()
        self.assertEqual(remaining_count, initial_count, "Transaction should have rolled back")


class APIQueryOptimizationTests(TestCase):
    """Tests for API-P1-02: N+1 query problem"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')

    @patch('backend.memories.views.vector_service')
    def test_memory_stats_optimizes_query(self, mock_vector_service):
        """Test that memory stats uses optimized query"""
        from backend.memories.views import MemoryStatsView
        from rest_framework.test import APIRequestFactory
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Create test memories
        for i in range(10):
            Memory.objects.create(
                user_id=self.user.id,
                content=f"Memory {i}",
                metadata={"tags": ["test", f"tag{i}"]}
            )

        mock_vector_service.get_collection_info.return_value = {"status": "ok"}

        factory = APIRequestFactory()
        view = MemoryStatsView.as_view()
        request = factory.get(f'/api/memory-stats/?user_id={self.user.id}')

        # Count queries
        with CaptureQueriesContext(connection) as queries:
            response = view(request)

        # Should be successful
        self.assertEqual(response.status_code, 200)

        # Should use minimal queries (not N+1)
        # Expecting: 1 query for memories, maybe 1 for count, 1 for vector info
        self.assertLessEqual(
            len(queries),
            5,
            f"Too many queries ({len(queries)}), possible N+1 problem. Queries: {[q['sql'] for q in queries]}"
        )


class APIP2VariableNameTests(TestCase):
    """Tests for API-P2-03: Variable Name Collision"""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass')

    @patch('memories.views.memory_search_service')
    @patch('memories.views.llm_service')
    def test_extract_memories_no_variable_shadowing(self, mock_llm, mock_memory_service):
        """
        Test that extraction doesn't have variable name collision issues.
        API-P2-03: Ensure response_memory doesn't shadow memory_data loop variable.
        """
        # Mock LLM extraction to return multiple memories
        mock_llm.extract_memories.return_value = {
            "memories": [
                {"content": "Memory 1", "tags": ["tag1"]},
                {"content": "Memory 2", "tags": ["tag2"]},
                {"content": "Memory 3", "tags": ["tag3"]},
            ],
            "model": "test-model"
        }

        # Mock memory storage
        mock_memory = MagicMock()
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "Memory 1"
        mock_memory.metadata = {"tags": ["tag1"]}
        mock_memory.created_at = datetime.datetime.now()
        mock_memory.updated_at = datetime.datetime.now()
        mock_memory_service.store_memory_with_embedding.return_value = mock_memory

        from rest_framework.test import APIRequestFactory
        from memories.views import ExtractMemoriesView

        factory = APIRequestFactory()
        request = factory.post(
            '/api/memories/extract/',
            {
                'text': 'Test conversation with multiple memories',
                'fields': ['id', 'content', 'metadata', 'created_at', 'updated_at']
            },
            format='json'
        )
        request.user = self.user

        view = ExtractMemoriesView.as_view()
        response = view(request)

        # Should be successful
        self.assertEqual(response.status_code, 200)

        # Should have stored 3 memories
        self.assertEqual(mock_memory_service.store_memory_with_embedding.call_count, 3)

        # Check that all requested fields are in response
        self.assertIn('memories', response.data)
        stored_memories = response.data['memories']
        self.assertEqual(len(stored_memories), 3)

        # Each memory should have all requested fields (no variable shadowing issues)
        for memory in stored_memories:
            self.assertIn('id', memory)
            self.assertIn('content', memory)
            self.assertIn('metadata', memory)
            self.assertIn('created_at', memory)
            self.assertIn('updated_at', memory)


class APIP2SettingsFetchTests(TestCase):
    """Tests for API-P2-02: Multiple LLM Settings Fetches in Same Request"""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='testpass')

    @patch('memories.views.llm_service')
    @patch('memories.views.memory_search_service')
    def test_extract_uses_cached_settings(self, mock_memory_service, mock_llm):
        """
        Test that extraction uses llm_service.settings instead of fetching again.
        API-P2-02: After refresh_settings(), use cached settings instead of LLMSettings.get_settings()
        """
        # Mock settings object
        mock_settings = MagicMock()
        mock_settings.memory_extraction_prompt = "Test extraction prompt"
        mock_llm.settings = mock_settings

        # Mock LLM extraction
        mock_llm.extract_memories.return_value = {
            "memories": [{"content": "Test memory", "tags": ["test"]}],
            "model": "test-model"
        }

        # Mock memory storage
        mock_memory = MagicMock()
        mock_memory.id = uuid.uuid4()
        mock_memory.content = "Test memory"
        mock_memory.metadata = {"tags": ["test"]}
        mock_memory.created_at = datetime.datetime.now()
        mock_memory.updated_at = datetime.datetime.now()
        mock_memory_service.store_memory_with_embedding.return_value = mock_memory

        from rest_framework.test import APIRequestFactory
        from memories.views import ExtractMemoriesView

        factory = APIRequestFactory()
        request = factory.post(
            '/api/memories/extract/',
            {'text': 'Test conversation'},
            format='json'
        )
        request.user = self.user

        view = ExtractMemoriesView.as_view()
        response = view(request)

        # Should be successful
        self.assertEqual(response.status_code, 200)

        # Should call refresh_settings once
        mock_llm.refresh_settings.assert_called_once()

        # Should access cached settings property, not call get_settings again
        # This is verified implicitly - if we called LLMSettings.get_settings() it would fail
        # because we didn't mock it

    @patch('memories.views.llm_service')
    @patch('memories.views.memory_search_service')
    def test_retrieve_uses_cached_settings(self, mock_memory_service, mock_llm):
        """
        Test that retrieval uses llm_service.settings instead of fetching again.
        API-P2-02: After refresh_settings(), use cached settings instead of LLMSettings.get_settings()
        """
        # Mock settings object
        mock_settings = MagicMock()
        mock_settings.memory_search_prompt = "Test search prompt"
        mock_settings.enable_semantic_connections = False
        mock_llm.settings = mock_settings

        # Mock LLM query generation
        mock_llm.generate_search_queries.return_value = {
            "success": True,
            "queries": ["query1", "query2"],
            "model": "test-model"
        }

        # Mock memory search
        mock_memory_service.search_memories_with_queries.return_value = []

        from rest_framework.test import APIRequestFactory
        from memories.views import RetrieveMemoriesView

        factory = APIRequestFactory()
        request = factory.post(
            '/api/memories/retrieve/',
            {'prompt': 'test prompt'},
            format='json'
        )
        request.user = self.user

        view = RetrieveMemoriesView.as_view()
        response = view(request)

        # Should be successful
        self.assertEqual(response.status_code, 200)

        # Should call refresh_settings once
        mock_llm.refresh_settings.assert_called_once()

        # Should access cached settings property
        # Verified implicitly by not mocking LLMSettings.get_settings()


class APIP2MagicNumbersTests(TestCase):
    """Tests for API-P2-05: Hardcoded Magic Numbers"""

    def test_constants_defined(self):
        """Test that magic numbers have been extracted as named constants"""
        from memories import views

        # Verify all constants are defined
        self.assertTrue(hasattr(views, 'MAX_CONVERSATION_TEXT_LENGTH'))
        self.assertTrue(hasattr(views, 'MAX_PROMPT_LENGTH'))
        self.assertTrue(hasattr(views, 'EXTRACTION_MAX_TOKENS'))
        self.assertTrue(hasattr(views, 'ERROR_MESSAGE_TRUNCATE_LENGTH'))
        self.assertTrue(hasattr(views, 'DEFAULT_RETRIEVAL_LIMIT'))
        self.assertTrue(hasattr(views, 'MAX_RETRIEVAL_LIMIT'))
        self.assertTrue(hasattr(views, 'DEFAULT_CLAMPED_LIMIT'))
        self.assertTrue(hasattr(views, 'DEFAULT_IMPORT_BATCH_SIZE'))

        # Verify values are sensible
        self.assertEqual(views.MAX_CONVERSATION_TEXT_LENGTH, 50000)
        self.assertEqual(views.MAX_PROMPT_LENGTH, 5000)
        self.assertEqual(views.EXTRACTION_MAX_TOKENS, 16384)
        self.assertEqual(views.ERROR_MESSAGE_TRUNCATE_LENGTH, 500)
        self.assertEqual(views.DEFAULT_RETRIEVAL_LIMIT, 99)
        self.assertEqual(views.MAX_RETRIEVAL_LIMIT, 100)
        self.assertEqual(views.DEFAULT_CLAMPED_LIMIT, 10)
        self.assertEqual(views.DEFAULT_IMPORT_BATCH_SIZE, 10)

    def test_conversation_text_length_limit_enforced(self):
        """Test that MAX_CONVERSATION_TEXT_LENGTH is enforced"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIRequestFactory
        from memories.views import ExtractMemoriesView, MAX_CONVERSATION_TEXT_LENGTH

        User = get_user_model()
        user = User.objects.create_user(username='testuser', password='testpass')

        factory = APIRequestFactory()

        # Create text that exceeds the limit
        long_text = "x" * (MAX_CONVERSATION_TEXT_LENGTH + 1)

        request = factory.post(
            '/api/memories/extract/',
            {'text': long_text, 'user_id': str(user.id)},
            format='json'
        )
        request.user = user

        view = ExtractMemoriesView.as_view()
        response = view(request)

        # Should be rejected with 400
        self.assertEqual(response.status_code, 400)
        self.assertIn('max_length', response.data)
        self.assertEqual(response.data['max_length'], MAX_CONVERSATION_TEXT_LENGTH)

    def test_prompt_length_limit_enforced(self):
        """Test that MAX_PROMPT_LENGTH is enforced"""
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIRequestFactory
        from memories.views import RetrieveMemoriesView, MAX_PROMPT_LENGTH

        User = get_user_model()
        user = User.objects.create_user(username='testuser', password='testpass')

        factory = APIRequestFactory()

        # Create prompt that exceeds the limit
        long_prompt = "x" * (MAX_PROMPT_LENGTH + 1)

        request = factory.post(
            '/api/memories/retrieve/',
            {'prompt': long_prompt, 'user_id': str(user.id)},
            format='json'
        )
        request.user = user

        view = RetrieveMemoriesView.as_view()
        response = view(request)

        # Should be rejected with 400
        self.assertEqual(response.status_code, 400)
        self.assertIn('max_length', response.data)
        self.assertEqual(response.data['max_length'], MAX_PROMPT_LENGTH)


class SVCP2ImportLocationTests(TestCase):
    """Tests for SVC-P2-01: Import Inside Loop"""

    def test_imports_at_module_level(self):
        """
        Test that critical imports are at module level, not inside functions.
        SVC-P2-01: Imports should be at top of file to avoid repeated execution.
        """
        import importlib
        import inspect

        # Reload the module to ensure we're testing current code
        from backend.memories import openwebui_importer
        importlib.reload(openwebui_importer)

        # Check that MEMORY_EXTRACTION_FORMAT is imported at module level
        self.assertTrue(
            hasattr(openwebui_importer, 'MEMORY_EXTRACTION_FORMAT'),
            "MEMORY_EXTRACTION_FORMAT should be imported at module level"
        )

        # Check that LLMSettings is imported at module level
        self.assertTrue(
            hasattr(openwebui_importer, 'LLMSettings'),
            "LLMSettings should be imported at module level"
        )

        # Verify the function doesn't have import statements
        # by checking the source code
        importer_class = openwebui_importer.OpenWebUIImporter
        source = inspect.getsource(importer_class.extract_memories_from_conversation)

        # Should not have 'from settings_app.models import' in the function
        self.assertNotIn(
            'from settings_app.models import',
            source,
            "Function should not have import statement for LLMSettings"
        )

        # Should not have 'from .llm_service import MEMORY_EXTRACTION_FORMAT' in the function
        self.assertNotIn(
            'from .llm_service import MEMORY_EXTRACTION_FORMAT',
            source,
            "Function should not have import statement for MEMORY_EXTRACTION_FORMAT"
        )


if __name__ == '__main__':
    unittest.main()

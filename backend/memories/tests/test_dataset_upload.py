"""
Dataset Upload Tests

Tests the dataset upload and management feature:
- Upload valid JSON datasets
- Validation of JSON format and structure
- Duplicate filename handling
- Listing available datasets
"""

import json
import tempfile
import uuid
from pathlib import Path
from io import BytesIO
from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient, force_authenticate
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from memories.views import UploadDatasetView, ListDatasetsView


class DatasetUploadTest(TestCase):
    """Test dataset upload and validation"""

    def setUp(self):
        """Set up test environment"""
        self.client = APIClient()
        self.factory = RequestFactory()
        self.upload_view = UploadDatasetView.as_view()
        self.list_view = ListDatasetsView.as_view()

        # Determine test_data directory
        from django.conf import settings as django_settings
        self.test_data_dir = Path(django_settings.BASE_DIR) / 'memories' / 'test_data'
        self.test_data_dir.mkdir(parents=True, exist_ok=True)

        # Clean up any test datasets
        self.cleanup_test_datasets()

    def tearDown(self):
        """Clean up test datasets"""
        self.cleanup_test_datasets()

    def cleanup_test_datasets(self):
        """Remove test datasets created during tests"""
        test_filenames = [
            'test_upload_valid.json',
            'test_upload_duplicate.json',
            'test_dataset_1.json',
            'test_dataset_2.json',
            'test_dataset_3.json',
            'invalid.json',
            'missing_fields.json',
            'test_file.txt'
        ]
        for filename in test_filenames:
            filepath = self.test_data_dir / filename
            if filepath.exists():
                filepath.unlink()

    def upload_file(self, filename, content):
        """Helper to upload a file"""
        # Use BytesIO to create a file-like object
        file_obj = BytesIO(content)
        uploaded_file = InMemoryUploadedFile(
            file_obj,
            field_name='file',
            name=filename,
            content_type='application/json',
            size=len(content),
            charset='utf-8'
        )
        # Reset file pointer to beginning
        uploaded_file.seek(0)

        request = self.factory.post(
            '/api/benchmarks/datasets/upload/',
            {'file': uploaded_file}
        )
        request.FILES['file'] = uploaded_file
        return self.upload_view(request)

    def test_valid_dataset_upload(self):
        """Test uploading a valid dataset JSON file"""
        # Create a valid dataset
        dataset = {
            "dataset_version": "1.0",
            "description": "Test dataset for upload",
            "test_conversations": [
                {
                    "user_id": str(uuid.uuid4()),
                    "turns": [
                        {"user": "Hello", "assistant": "Hi"}
                    ]
                }
            ],
            "test_queries": [
                {"query": "test query", "expected_count": 1}
            ]
        }

        # Upload dataset
        response = self.upload_file(
            'test_upload_valid.json',
            json.dumps(dataset).encode('utf-8')
        )

        # Verify success
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['filename'], 'test_upload_valid.json')
        self.assertEqual(response.data['num_conversations'], 1)
        self.assertEqual(response.data['num_queries'], 1)

        # Verify file was saved
        saved_file = self.test_data_dir / 'test_upload_valid.json'
        self.assertTrue(saved_file.exists())

        # Verify file content is correct
        with open(saved_file, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data['description'], 'Test dataset for upload')
        self.assertEqual(len(saved_data['test_conversations']), 1)

    def test_invalid_json_rejected(self):
        """Test that invalid JSON is rejected"""
        # Upload invalid JSON
        response = self.upload_file(
            'invalid.json',
            b'This is not valid JSON at all!'
        )

        # Verify rejection
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('Invalid JSON format', response.data['error'])

        # Verify file was NOT saved
        saved_file = self.test_data_dir / 'invalid.json'
        self.assertFalse(saved_file.exists())

    def test_missing_required_fields_rejected(self):
        """Test that datasets missing required fields are rejected"""
        # Create dataset without test_conversations or test_queries
        dataset = {
            "dataset_version": "1.0",
            "description": "Invalid dataset - missing required fields"
        }

        # Upload dataset
        response = self.upload_file(
            'missing_fields.json',
            json.dumps(dataset).encode('utf-8')
        )

        # Verify rejection
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('test_conversations', response.data['error'])
        self.assertIn('test_queries', response.data['error'])

        # Verify file was NOT saved
        saved_file = self.test_data_dir / 'missing_fields.json'
        self.assertFalse(saved_file.exists())

    def test_duplicate_filename_rejected(self):
        """Test that uploading a duplicate filename is rejected"""
        # Create initial dataset
        dataset = {
            "description": "First upload",
            "test_conversations": []
        }

        # Upload first time
        response = self.upload_file(
            'test_upload_duplicate.json',
            json.dumps(dataset).encode('utf-8')
        )
        self.assertEqual(response.status_code, 201)

        # Try to upload again with same filename
        dataset['description'] = "Second upload (should fail)"
        response = self.upload_file(
            'test_upload_duplicate.json',
            json.dumps(dataset).encode('utf-8')
        )

        # Verify rejection
        self.assertEqual(response.status_code, 409)  # Conflict
        self.assertFalse(response.data['success'])
        self.assertIn('already exists', response.data['error'])
        self.assertIn('delete it first', response.data['error'].lower())

        # Verify original file is still intact
        saved_file = self.test_data_dir / 'test_upload_duplicate.json'
        with open(saved_file, 'r') as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data['description'], 'First upload')

    def test_list_datasets_returns_all_files(self):
        """Test that listing datasets returns all uploaded files with correct metadata"""
        # Create multiple datasets
        datasets = [
            {
                'filename': 'test_dataset_1.json',
                'data': {
                    "dataset_version": "1.0",
                    "description": "First test dataset",
                    "test_conversations": [{"turns": []}],
                    "test_queries": [{"query": "q1"}, {"query": "q2"}]
                }
            },
            {
                'filename': 'test_dataset_2.json',
                'data': {
                    "dataset_version": "2.0",
                    "description": "Second test dataset",
                    "test_conversations": [{"turns": []}, {"turns": []}],
                    "test_queries": []
                }
            },
            {
                'filename': 'test_dataset_3.json',
                'data': {
                    "description": "Third test dataset (no version)",
                    "test_conversations": [{"turns": []}, {"turns": []}, {"turns": []}],
                    "test_queries": [{"query": "q1"}]
                }
            }
        ]

        # Upload all datasets
        for dataset_info in datasets:
            response = self.upload_file(
                dataset_info['filename'],
                json.dumps(dataset_info['data']).encode('utf-8')
            )
            self.assertEqual(response.status_code, 201)

        # List datasets
        request = self.factory.get('/api/benchmarks/datasets/')
        response = self.list_view(request)

        # Verify success
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

        # Verify all datasets are listed
        dataset_list = response.data['datasets']
        self.assertEqual(len(dataset_list), 3)

        # Create lookup by filename
        datasets_by_name = {d['filename']: d for d in dataset_list}

        # Verify first dataset metadata
        ds1 = datasets_by_name['test_dataset_1.json']
        self.assertEqual(ds1['description'], 'First test dataset')
        self.assertEqual(ds1['version'], '1.0')
        self.assertEqual(ds1['num_conversations'], 1)
        self.assertEqual(ds1['num_queries'], 2)

        # Verify second dataset metadata
        ds2 = datasets_by_name['test_dataset_2.json']
        self.assertEqual(ds2['description'], 'Second test dataset')
        self.assertEqual(ds2['version'], '2.0')
        self.assertEqual(ds2['num_conversations'], 2)
        self.assertEqual(ds2['num_queries'], 0)

        # Verify third dataset metadata
        ds3 = datasets_by_name['test_dataset_3.json']
        self.assertEqual(ds3['description'], 'Third test dataset (no version)')
        self.assertEqual(ds3['version'], 'Unknown')  # Default when no version
        self.assertEqual(ds3['num_conversations'], 3)
        self.assertEqual(ds3['num_queries'], 1)

    def test_non_json_file_rejected(self):
        """Test that non-JSON files are rejected"""
        # Try to upload a text file
        content = b'This is a text file'
        file_obj = BytesIO(content)
        uploaded_file = InMemoryUploadedFile(
            file_obj,
            field_name='file',
            name='test_file.txt',
            content_type='text/plain',
            size=len(content),
            charset='utf-8'
        )
        # Reset file pointer to beginning
        uploaded_file.seek(0)

        request = self.factory.post(
            '/api/benchmarks/datasets/upload/',
            {'file': uploaded_file}
        )
        request.FILES['file'] = uploaded_file
        response = self.upload_view(request)

        # Verify rejection
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('.json', response.data['error'])

    def test_no_file_upload_rejected(self):
        """Test that requests without a file are rejected"""
        # Try to upload without file
        request = self.factory.post(
            '/api/benchmarks/datasets/upload/',
            {}
        )
        response = self.upload_view(request)

        # Verify rejection
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('No file uploaded', response.data['error'])

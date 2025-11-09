import logging
import time
import uuid

from django.conf import settings as django_settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .conversation_service import conversation_service
from .models import ConversationTurn, AtomicNote, NoteRelationship

logger = logging.getLogger(__name__)


class StoreConversationTurnView(APIView):
    """Store a conversation turn"""

    def post(self, request):
        start_time = time.time()

        # Validate input
        user_id = request.data.get('user_id')
        session_id = request.data.get('session_id')
        user_message = request.data.get('user_message')
        assistant_message = request.data.get('assistant_message')

        if not all([user_id, session_id, user_message, assistant_message]):
            return Response(
                {'success': False, 'error': 'Missing required fields: user_id, session_id, user_message, assistant_message'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate UUID
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {'success': False, 'error': 'Invalid user_id format (must be UUID)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            turn = conversation_service.store_turn(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                assistant_message=assistant_message
            )

            latency = (time.time() - start_time) * 1000  # ms
            logger.info(f"Stored turn in {latency:.0f}ms")

            return Response({
                'success': True,
                'turn_id': str(turn.id),
                'turn_number': turn.turn_number,
                'latency_ms': round(latency, 2)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"Failed to store turn after {latency:.0f}ms: {e}")
            return Response(
                {'success': False, 'error': str(e), 'latency_ms': round(latency, 2)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SearchConversationsView(APIView):
    """Search conversations - supports fast and deep modes"""

    def post(self, request):
        start_time = time.time()

        # Validate input
        query = request.data.get('query')
        user_id = request.data.get('user_id')
        limit = request.data.get('limit', 10)
        threshold = request.data.get('threshold', 0.5)
        mode = request.data.get('mode', 'fast')

        if not all([query, user_id]):
            return Response(
                {'success': False, 'error': 'Missing required fields: query, user_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate UUID
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {'success': False, 'error': 'Invalid user_id format (must be UUID)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate numeric parameters
        try:
            limit = int(limit)
            threshold = float(threshold)
        except (ValueError, TypeError):
            return Response(
                {'success': False, 'error': 'Invalid limit or threshold format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate mode
        if mode not in ['fast', 'deep']:
            return Response(
                {'success': False, 'error': 'Invalid mode. Must be "fast" or "deep"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Call appropriate search method based on mode
            if mode == 'deep':
                results = conversation_service.search_deep(
                    query=query,
                    user_id=user_id,
                    limit=limit,
                    threshold=threshold
                )
            else:
                results = conversation_service.search_fast(
                    query=query,
                    user_id=user_id,
                    limit=limit,
                    threshold=threshold
                )

            latency = (time.time() - start_time) * 1000  # ms
            logger.info(f"Search ({mode} mode) completed in {latency:.0f}ms, found {len(results)} results")

            return Response({
                'success': True,
                'count': len(results),
                'results': results,
                'mode': mode,
                'latency_ms': round(latency, 2)
            })

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"Search ({mode} mode) failed after {latency:.0f}ms: {e}")
            return Response(
                {'success': False, 'error': str(e), 'latency_ms': round(latency, 2)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ListConversationsView(APIView):
    """List recent conversations for a user"""

    def get(self, request):
        start_time = time.time()

        # Validate input
        user_id = request.query_params.get('user_id')
        limit = request.query_params.get('limit', 50)

        if not user_id:
            return Response(
                {'success': False, 'error': 'Missing required parameter: user_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate UUID
        try:
            uuid.UUID(user_id)
        except ValueError:
            return Response(
                {'success': False, 'error': 'Invalid user_id format (must be UUID)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate limit
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            return Response(
                {'success': False, 'error': 'Invalid limit format'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            turns = conversation_service.list_recent(
                user_id=user_id,
                limit=limit
            )

            # Serialize turns
            conversations = [{
                'id': str(turn.id),
                'user_id': str(turn.user_id),
                'session_id': turn.session_id,
                'turn_number': turn.turn_number,
                'user_message': turn.user_message,
                'assistant_message': turn.assistant_message,
                'timestamp': turn.timestamp.isoformat(),
                'extracted': turn.extracted
            } for turn in turns]

            latency = (time.time() - start_time) * 1000  # ms
            logger.info(f"Listed {len(conversations)} conversations in {latency:.0f}ms")

            return Response({
                'success': True,
                'count': len(conversations),
                'conversations': conversations,
                'latency_ms': round(latency, 2)
            })

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"List failed after {latency:.0f}ms: {e}")
            return Response(
                {'success': False, 'error': str(e), 'latency_ms': round(latency, 2)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GetSettingsView(APIView):
    """Get current settings (from database or environment fallback)"""

    def get(self, request):
        """Return current settings (API key masked for security)"""
        try:
            from .settings_model import Settings

            # Get settings from database (with environment fallback)
            settings = Settings.get_settings()
            settings_dict = settings.to_dict(mask_api_key=True)

            return Response({
                'success': True,
                'settings': settings_dict,
                'source': 'database',
                'note': 'Settings are editable via the UI. Changes take effect immediately.'
            })

        except Exception as e:
            logger.error(f"Failed to get settings: {e}")

            # Fallback to environment variables
            api_key = django_settings.EMBEDDINGS_API_KEY
            api_key_masked = None
            if api_key:
                if len(api_key) > 8:
                    api_key_masked = f"{api_key[:4]}...{api_key[-4:]}"
                else:
                    api_key_masked = "***"

            return Response({
                'success': True,
                'settings': {
                    'embeddings_provider': django_settings.EMBEDDINGS_PROVIDER,
                    'embeddings_endpoint_url': django_settings.EMBEDDINGS_ENDPOINT_URL,
                    'embeddings_model': django_settings.EMBEDDINGS_MODEL,
                    'embeddings_api_key': api_key_masked,
                    'embeddings_timeout': django_settings.EMBEDDINGS_TIMEOUT,
                    'generation_model': getattr(django_settings, 'GENERATION_MODEL', django_settings.EMBEDDINGS_MODEL),
                },
                'source': 'environment',
                'note': 'Using environment variables. Database settings not available.'
            })


class UpdateSettingsView(APIView):
    """Update settings in database"""

    def put(self, request):
        """Update settings with provided values"""
        try:
            from .settings_model import Settings

            # Get current settings
            settings = Settings.get_settings()

            # Update fields from request
            updated_fields = []
            for field in ['embeddings_provider', 'embeddings_endpoint_url', 'embeddings_model',
                          'embeddings_api_key', 'embeddings_timeout',
                          'generation_provider', 'generation_endpoint_url', 'generation_model',
                          'generation_api_key', 'generation_temperature', 'generation_max_tokens',
                          'generation_timeout', 'extraction_prompt', 'relationship_prompt']:
                if field in request.data:
                    value = request.data[field]

                    # Validation
                    if field in ['embeddings_provider', 'generation_provider']:
                        if value and value not in ['ollama', 'openai', 'openai_compatible', '']:
                            return Response(
                                {'success': False, 'error': f'Invalid provider: {value}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field in ['embeddings_timeout', 'generation_timeout']:
                        try:
                            value = int(value)
                            if value < 1 or value > 600:
                                return Response(
                                    {'success': False, 'error': 'Timeout must be between 1 and 600 seconds'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid timeout value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'generation_temperature':
                        try:
                            value = float(value)
                            if value < 0.0 or value > 1.0:
                                return Response(
                                    {'success': False, 'error': 'Temperature must be between 0.0 and 1.0'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid temperature value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'generation_max_tokens':
                        try:
                            value = int(value)
                            if value < 1 or value > 100000:
                                return Response(
                                    {'success': False, 'error': 'Max tokens must be between 1 and 100000'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid max_tokens value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field in ['embeddings_endpoint_url', 'embeddings_model']:
                        if not value or not value.strip():
                            return Response(
                                {'success': False, 'error': f'{field} cannot be empty'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    setattr(settings, field, value)
                    updated_fields.append(field)

            # Save settings
            settings.save()

            logger.info(f"Settings updated: {', '.join(updated_fields)}")

            return Response({
                'success': True,
                'message': f'Updated {len(updated_fields)} setting(s)',
                'updated_fields': updated_fields,
                'settings': settings.to_dict(mask_api_key=True)
            })

        except Exception as e:
            logger.error(f"Failed to update settings: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ValidateEndpointView(APIView):
    """Validate an LLM endpoint URL"""

    def post(self, request):
        """Test connection to an LLM endpoint"""
        import requests

        endpoint_url = request.data.get('endpoint_url')
        provider = request.data.get('provider', 'ollama')
        api_key = request.data.get('api_key', '')

        if not endpoint_url:
            return Response(
                {'success': False, 'error': 'endpoint_url is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Different validation based on provider
            if provider == 'ollama':
                # For Ollama, try to fetch the version or tags endpoint
                test_url = f"{endpoint_url.rstrip('/')}/api/tags"
                response = requests.get(test_url, timeout=5)
                response.raise_for_status()

                return Response({
                    'success': True,
                    'message': 'Successfully connected to Ollama endpoint',
                    'provider': 'ollama'
                })

            elif provider in ['openai', 'openai_compatible']:
                # For OpenAI-compatible endpoints, try to list models
                test_url = f"{endpoint_url.rstrip('/')}/v1/models"
                headers = {}
                if api_key:
                    headers['Authorization'] = f'Bearer {api_key}'

                response = requests.get(test_url, headers=headers, timeout=5)
                response.raise_for_status()

                return Response({
                    'success': True,
                    'message': 'Successfully connected to OpenAI-compatible endpoint',
                    'provider': provider
                })

            else:
                return Response(
                    {'success': False, 'error': f'Unknown provider: {provider}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except requests.exceptions.Timeout:
            return Response(
                {'success': False, 'error': 'Connection timeout - endpoint did not respond within 5 seconds'},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        except requests.exceptions.ConnectionError:
            return Response(
                {'success': False, 'error': 'Connection failed - could not reach endpoint'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except requests.exceptions.HTTPError as e:
            return Response(
                {'success': False, 'error': f'HTTP error: {e.response.status_code} - {e.response.reason}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            logger.error(f"Failed to validate endpoint: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class FetchModelsView(APIView):
    """Fetch available models from an LLM endpoint"""

    def post(self, request):
        """Get list of available models from endpoint"""
        import requests

        endpoint_url = request.data.get('endpoint_url')
        provider = request.data.get('provider', 'ollama')
        api_key = request.data.get('api_key', '')

        if not endpoint_url:
            return Response(
                {'success': False, 'error': 'endpoint_url is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            models = []

            if provider == 'ollama':
                # Ollama API endpoint
                url = f"{endpoint_url.rstrip('/')}/api/tags"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Extract model names
                if 'models' in data:
                    models = [model['name'] for model in data['models']]

            elif provider in ['openai', 'openai_compatible']:
                # OpenAI-compatible API endpoint
                url = f"{endpoint_url.rstrip('/')}/v1/models"
                headers = {}
                if api_key:
                    headers['Authorization'] = f'Bearer {api_key}'

                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Extract model IDs
                if 'data' in data:
                    models = [model['id'] for model in data['data']]

            else:
                return Response(
                    {'success': False, 'error': f'Unknown provider: {provider}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                'success': True,
                'models': sorted(models),
                'count': len(models)
            })

        except requests.exceptions.Timeout:
            return Response(
                {'success': False, 'error': 'Connection timeout - endpoint did not respond within 10 seconds'},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        except requests.exceptions.ConnectionError:
            return Response(
                {'success': False, 'error': 'Connection failed - could not reach endpoint'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except requests.exceptions.HTTPError as e:
            return Response(
                {'success': False, 'error': f'HTTP error: {e.response.status_code} - {e.response.reason}'},
                status=status.HTTP_502_BAD_GATEWAY
            )
        except Exception as e:
            logger.error(f"Failed to fetch models: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

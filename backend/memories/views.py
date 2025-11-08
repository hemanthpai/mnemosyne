import logging
import time
import uuid

from django.conf import settings as django_settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .conversation_service import conversation_service
from .models import ConversationTurn

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
    """Search conversations - supports fast and deep modes (Phase 3)"""

    def post(self, request):
        start_time = time.time()

        # Validate input
        query = request.data.get('query')
        user_id = request.data.get('user_id')
        limit = request.data.get('limit', 10)
        threshold = request.data.get('threshold', 0.5)
        mode = request.data.get('mode', 'fast')  # Phase 3: Search mode

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
            # Phase 3: Call appropriate search method based on mode
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
                'mode': mode,  # Phase 3: Include mode in response
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
                          'embeddings_api_key', 'embeddings_timeout', 'generation_model']:
                if field in request.data:
                    value = request.data[field]

                    # Validation
                    if field == 'embeddings_provider':
                        if value not in ['ollama', 'openai', 'openai_compatible']:
                            return Response(
                                {'success': False, 'error': f'Invalid provider: {value}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'embeddings_timeout':
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

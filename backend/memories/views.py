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
    """Fast path search - direct embedding"""

    def post(self, request):
        start_time = time.time()

        # Validate input
        query = request.data.get('query')
        user_id = request.data.get('user_id')
        limit = request.data.get('limit', 10)
        threshold = request.data.get('threshold', 0.5)

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

        try:
            results = conversation_service.search_fast(
                query=query,
                user_id=user_id,
                limit=limit,
                threshold=threshold
            )

            latency = (time.time() - start_time) * 1000  # ms
            logger.info(f"Search completed in {latency:.0f}ms, found {len(results)} results")

            return Response({
                'success': True,
                'count': len(results),
                'results': results,
                'latency_ms': round(latency, 2)
            })

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"Search failed after {latency:.0f}ms: {e}")
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
    """Get current Phase 1 embeddings configuration (read-only from environment)"""

    def get(self, request):
        """Return current embeddings settings (API key masked for security)"""

        api_key = django_settings.EMBEDDINGS_API_KEY
        api_key_masked = None
        if api_key:
            # Show first 4 and last 4 characters, mask the rest
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
            },
            'note': 'Settings are read-only in Phase 1. Configure via environment variables and restart the service.'
        })

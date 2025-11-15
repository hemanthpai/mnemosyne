import logging
import time
import uuid
import json
from pathlib import Path
from io import StringIO
import sys

from django.conf import settings as django_settings
from django.core.management import call_command
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django_q.tasks import async_task, result, fetch
from django_q.models import Task

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
                          'embeddings_api_key', 'embeddings_timeout', 'embeddings_dimension',
                          'generation_provider', 'generation_endpoint_url', 'generation_model',
                          'generation_api_key', 'generation_temperature', 'generation_max_tokens',
                          'generation_timeout', 'generation_top_p', 'generation_top_k', 'generation_min_p',
                          'extraction_prompt',
                          'amem_enrichment_temperature', 'amem_enrichment_max_tokens',
                          'amem_link_generation_temperature', 'amem_link_generation_max_tokens',
                          'amem_link_generation_k', 'amem_evolution_temperature', 'amem_evolution_max_tokens',
                          'enable_multipass_extraction', 'enable_query_expansion', 'enable_query_rewriting', 'enable_hybrid_search',
                          'enable_reranking', 'reranking_provider', 'reranking_endpoint_url', 'reranking_model_name',
                          'reranking_batch_size', 'reranking_device', 'ollama_reranking_base_url',
                          'ollama_reranking_model', 'ollama_reranking_temperature', 'reranking_candidate_multiplier']:
                if field in request.data:
                    value = request.data[field]

                    # Validation
                    if field in ['embeddings_provider', 'generation_provider']:
                        if value and value not in ['ollama', 'openai', 'openai_compatible', '']:
                            return Response(
                                {'success': False, 'error': f'Invalid provider: {value}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'reranking_provider':
                        if value not in ['remote', 'ollama', 'sentence_transformers']:
                            return Response(
                                {'success': False, 'error': f'Invalid reranking provider: {value}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'reranking_batch_size':
                        try:
                            value = int(value)
                            if value < 1 or value > 256:
                                return Response(
                                    {'success': False, 'error': 'Batch size must be between 1 and 256'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid batch size value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'reranking_candidate_multiplier':
                        try:
                            value = int(value)
                            if value < 1 or value > 10:
                                return Response(
                                    {'success': False, 'error': 'Candidate multiplier must be between 1 and 10'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid candidate multiplier value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'ollama_reranking_temperature':
                        try:
                            value = float(value)
                            if value < 0.0 or value > 1.0:
                                return Response(
                                    {'success': False, 'error': 'Ollama reranking temperature must be between 0.0 and 1.0'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid ollama_reranking_temperature value'},
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

                    elif field == 'embeddings_dimension':
                        try:
                            value = int(value)
                            if value not in [384, 768, 1024, 1536, 2048, 3072, 4096, 8192]:
                                return Response(
                                    {'success': False, 'error': 'Dimension must be one of: 384, 768, 1024, 1536, 2048, 3072, 4096, 8192'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid dimension value'},
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

                    elif field in ['generation_top_p', 'generation_min_p']:
                        try:
                            value = float(value)
                            if value < 0.0 or value > 1.0:
                                return Response(
                                    {'success': False, 'error': f'{field} must be between 0.0 and 1.0'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': f'Invalid {field} value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field == 'generation_top_k':
                        try:
                            value = int(value)
                            if value < 0 or value > 1000:
                                return Response(
                                    {'success': False, 'error': 'generation_top_k must be between 0 and 1000 (0 = disabled)'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid generation_top_k value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    elif field in ['embeddings_endpoint_url', 'embeddings_model']:
                        if not value or not value.strip():
                            return Response(
                                {'success': False, 'error': f'{field} cannot be empty'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    # Validate A-MEM temperature fields
                    elif field in ['amem_enrichment_temperature', 'amem_link_generation_temperature',
                                   'amem_evolution_temperature']:
                        try:
                            value = float(value)
                            if value < 0.0 or value > 1.0:
                                return Response(
                                    {'success': False, 'error': f'{field} must be between 0.0 and 1.0'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': f'Invalid {field} value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    # Validate A-MEM max_tokens fields
                    elif field in ['amem_enrichment_max_tokens', 'amem_link_generation_max_tokens',
                                   'amem_evolution_max_tokens']:
                        try:
                            value = int(value)
                            if value < 50 or value > 8192:
                                return Response(
                                    {'success': False, 'error': f'{field} must be between 50 and 8192'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': f'Invalid {field} value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    # Validate A-MEM k parameter
                    elif field == 'amem_link_generation_k':
                        try:
                            value = int(value)
                            if value < 1 or value > 50:
                                return Response(
                                    {'success': False, 'error': 'amem_link_generation_k must be between 1 and 50'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except (ValueError, TypeError):
                            return Response(
                                {'success': False, 'error': 'Invalid amem_link_generation_k value'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    # Validate boolean fields
                    elif field in ['enable_multipass_extraction', 'enable_query_expansion',
                                   'enable_query_rewriting', 'enable_hybrid_search', 'enable_reranking']:
                        if not isinstance(value, bool):
                            return Response(
                                {'success': False, 'error': f'{field} must be a boolean'},
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


class QueueStatusView(APIView):
    """Get Django-Q queue status and worker metrics"""

    def get(self, request):
        """Return current queue statistics with detailed insights"""
        try:
            from django_q.models import OrmQ, Task
            from django.utils import timezone
            from datetime import timedelta
            import pickle

            # Queue depth (pending tasks)
            queue_size = OrmQ.objects.count()

            # Pending task details
            pending_tasks_detail = []
            oldest_waiting = None
            pending_breakdown = {}

            for q in OrmQ.objects.all()[:10]:  # Limit to first 10
                try:
                    # Handle both bytes and string payloads
                    payload = q.payload
                    if isinstance(payload, str):
                        payload = payload.encode('latin-1')  # Django stores pickles as latin-1 strings

                    task_data = pickle.loads(payload)
                    func = task_data.get('func', 'unknown')
                    task_name = task_data.get('name', 'unnamed')

                    pending_tasks_detail.append({
                        'name': task_name,
                        'func': func,
                        'lock': q.lock
                    })

                    # Count by function
                    pending_breakdown[func] = pending_breakdown.get(func, 0) + 1

                    # Track oldest (OrmQ doesn't have timestamps, use lock as proxy)
                    if oldest_waiting is None or q.lock < oldest_waiting:
                        oldest_waiting = q.lock
                except Exception as e:
                    logger.debug(f"Failed to parse pending task: {e}")

            # Currently processing tasks (started but not stopped)
            processing_tasks = Task.objects.filter(
                started__isnull=False,
                stopped__isnull=True
            )
            processing_count = processing_tasks.count()

            processing_detail = [{
                'name': task.name,
                'func': task.func,
                'started': task.started.isoformat() if task.started else None,
                'duration_seconds': (timezone.now() - task.started).total_seconds() if task.started else 0
            } for task in processing_tasks[:10]]

            # Recent task statistics (last hour)
            one_hour_ago = timezone.now() - timedelta(hours=1)
            recent_tasks = Task.objects.filter(started__gte=one_hour_ago)

            recent_total = recent_tasks.count()
            recent_success = recent_tasks.filter(success=True).count()
            recent_failed = recent_tasks.filter(success=False).count()

            # Calculate success rate
            success_rate = (recent_success / recent_total * 100) if recent_total > 0 else 0

            # Last 5 minutes for throughput
            five_min_ago = timezone.now() - timedelta(minutes=5)
            last_5min = Task.objects.filter(started__gte=five_min_ago).count()
            tasks_per_minute = last_5min / 5.0

            # Recent failed tasks (for debugging)
            failed_tasks = Task.objects.filter(
                success=False,
                started__gte=one_hour_ago
            ).order_by('-started')[:5]

            failed_task_info = [{
                'name': task.name,
                'func': task.func,
                'started': task.started.isoformat() if task.started else None,
                'stopped': task.stopped.isoformat() if task.stopped else None,
                'attempt_count': task.attempt_count
            } for task in failed_tasks]

            # Get task breakdown by function (completed tasks)
            from django.db.models import Count
            task_breakdown = recent_tasks.values('func').annotate(
                count=Count('id')
            ).order_by('-count')[:10]

            # Smarter health check:
            # - Healthy if: recent successful tasks OR queue is empty
            # - Unhealthy if: high failure rate (>10%) OR (queue stuck with no recent activity)
            has_recent_activity = last_5min > 0
            low_failure_rate = success_rate >= 90.0 or recent_failed == 0
            worker_healthy = (queue_size == 0) or (has_recent_activity and low_failure_rate)

            return Response({
                'success': True,
                'timestamp': timezone.now().isoformat(),
                'queue': {
                    'waiting_in_queue': queue_size,
                    'currently_running': processing_count,
                    # Legacy fields for backward compatibility
                    'pending': queue_size,
                    'processing': processing_count,
                },
                'queue_details': {
                    'waiting_tasks': pending_tasks_detail,
                    'waiting_breakdown': [
                        {'func': func, 'count': count}
                        for func, count in pending_breakdown.items()
                    ],
                    'running_tasks': processing_detail,
                    'oldest_waiting_lock': oldest_waiting
                },
                'stats': {
                    'last_hour': {
                        'total': recent_total,
                        'successful': recent_success,
                        'failed': recent_failed,
                        'success_rate': round(success_rate, 2)
                    },
                    'throughput': {
                        'tasks_per_minute': round(tasks_per_minute, 2),
                        'last_5_minutes': last_5min
                    }
                },
                'task_breakdown': list(task_breakdown),
                'recent_failures': failed_task_info,
                'worker_healthy': worker_healthy
            })

        except Exception as e:
            logger.error(f"Failed to get queue status: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ClearStuckTasksView(APIView):
    """Clear stuck tasks from the queue"""

    def post(self, request):
        """
        Clear stuck tasks that haven't been processed
        Returns count of cleared tasks
        """
        try:
            from django_q.models import OrmQ
            from django.utils import timezone
            from datetime import timedelta

            # Define "stuck" as tasks older than 30 minutes with past lock time
            thirty_min_ago = timezone.now() - timedelta(minutes=30)
            
            # Find tasks with lock in the past (should be processing but aren't)
            stuck_tasks = OrmQ.objects.filter(lock__lt=thirty_min_ago)
            
            count = stuck_tasks.count()
            stuck_tasks.delete()
            
            logger.info(f"Cleared {count} stuck tasks from queue")
            
            return Response({
                'success': True,
                'cleared_count': count,
                'message': f'Cleared {count} stuck task(s) from queue'
            })

        except Exception as e:
            logger.error(f"Failed to clear stuck tasks: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class QueueHealthDiagnosticsView(APIView):
    """Get detailed diagnostics about queue health"""

    def get(self, request):
        """Return detailed health diagnostics with specific issues and actions"""
        try:
            from django_q.models import OrmQ, Task
            from django.utils import timezone
            from datetime import timedelta

            now = timezone.now()
            five_min_ago = now - timedelta(minutes=5)
            thirty_min_ago = now - timedelta(minutes=30)
            one_hour_ago = now - timedelta(hours=1)

            # Analyze queue state
            queue_size = OrmQ.objects.count()
            stuck_count = OrmQ.objects.filter(lock__lt=thirty_min_ago).count()
            
            # Recent activity
            recent_completions = Task.objects.filter(started__gte=five_min_ago).count()
            recent_failures = Task.objects.filter(
                started__gte=one_hour_ago, 
                success=False
            ).count()
            
            # Determine health status and specific issues
            issues = []
            health_status = 'healthy'
            action_required = False
            
            # Check for stuck tasks
            if stuck_count > 0:
                health_status = 'degraded'
                action_required = True
                issues.append({
                    'type': 'stuck_tasks',
                    'severity': 'warning',
                    'message': f'{stuck_count} task(s) stuck in queue for >30 minutes',
                    'action': 'clear_stuck_tasks',
                    'action_label': f'Clear {stuck_count} Stuck Task(s)'
                })
            
            # Check for low activity when queue has tasks
            if queue_size > 0 and recent_completions == 0 and stuck_count == 0:
                health_status = 'degraded'
                issues.append({
                    'type': 'low_activity',
                    'severity': 'info',
                    'message': f'{queue_size} task(s) in queue but no completions in 5 minutes',
                    'action': None,
                    'action_label': 'Worker may be slow or idle'
                })
            
            # Check for high failure rate
            if recent_failures > 5:
                health_status = 'unhealthy'
                action_required = True
                issues.append({
                    'type': 'high_failures',
                    'severity': 'error',
                    'message': f'{recent_failures} task failures in last hour',
                    'action': 'view_failures',
                    'action_label': 'View Failed Tasks'
                })
            
            # All good?
            if len(issues) == 0:
                health_status = 'healthy'
                issues.append({
                    'type': 'healthy',
                    'severity': 'success',
                    'message': 'Queue is operating normally',
                    'action': None,
                    'action_label': None
                })

            return Response({
                'success': True,
                'health_status': health_status,  # 'healthy', 'degraded', 'unhealthy'
                'action_required': action_required,
                'issues': issues,
                'metrics': {
                    'queue_size': queue_size,
                    'stuck_tasks': stuck_count,
                    'recent_completions': recent_completions,
                    'recent_failures': recent_failures
                }
            })

        except Exception as e:
            logger.error(f"Failed to get health diagnostics: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ============================================================================
# Benchmark API Views
# ============================================================================

class RunBenchmarkView(APIView):
    """Start a benchmark run"""

    def post(self, request):
        try:
            test_type = request.data.get('test_type', 'all')
            dataset = request.data.get('dataset', 'benchmark_dataset.json')

            # Validate test type
            if test_type not in ['extraction', 'search', 'evolution', 'all']:
                return Response(
                    {'success': False, 'error': 'Invalid test_type. Must be one of: extraction, search, evolution, all'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate a tracking ID for progress updates
            # We use our own UUID instead of Django-Q's task ID because:
            # 1. We need the ID before the task starts (for progress tracking)
            # 2. Django-Q task ID isn't available inside the task function
            import uuid
            tracking_id = str(uuid.uuid4())

            # Store metadata in group field for later retrieval
            # Store metadata in cache (group field in django_q has 100 char limit)
            metadata = {
                'test_type': test_type,
                'dataset': dataset,
                'tracking_id': tracking_id
            }
            cache.set(f'benchmark_metadata_{tracking_id}', metadata, timeout=7200)  # 2 hours

            logger.info(f"About to queue benchmark task (type={test_type}, dataset={dataset}, tracking_id={tracking_id})")

            try:
                # Pass tracking_id as first parameter so the task can use it for progress
                logger.info(f"Calling async_task with tracking_id={tracking_id}, test_type={test_type}, dataset={dataset}")

                # Check Django-Q is available
                from django_q.models import OrmQ
                before_count = OrmQ.objects.count()
                logger.info(f"OrmQ count before async_task: {before_count}")

                django_q_task_id = async_task(
                    'memories.tasks.run_benchmark_task',
                    tracking_id,  # Pass our tracking ID as first parameter
                    test_type,
                    dataset,
                    task_name=f'benchmark_{test_type}',
                    timeout=7200,  # 2 hours timeout (benchmarks can take a long time)
                    group=tracking_id,  # Store tracking_id for reference (shorter than full metadata JSON)
                    sync=False  # Ensure async execution
                )

                logger.info(f"async_task returned django_q_task_id: {django_q_task_id}, tracking_id: {tracking_id}")

                # Check if task was added to queue
                import time
                time.sleep(0.1)  # Give it a moment
                after_count = OrmQ.objects.count()
                logger.info(f"OrmQ count after async_task: {after_count}")

                # Store mapping from tracking_id to django_q_task_id for status lookups
                cache.set(f'benchmark_django_q_id_{tracking_id}', django_q_task_id, timeout=7200)  # 2 hours

            except Exception as queue_error:
                logger.error(f"Error during async_task call: {queue_error}", exc_info=True)
                raise

            return Response({
                'success': True,
                'task_id': tracking_id,  # Return tracking_id to frontend
                'test_type': test_type,
                'dataset': dataset,
                'message': 'Benchmark queued successfully'
            })

        except Exception as e:
            logger.error(f"Failed to queue benchmark: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BenchmarkStatusView(APIView):
    """Check benchmark status"""

    def get(self, request, task_id):
        try:
            # task_id here is actually the tracking_id from our system
            tracking_id = task_id

            # Check for progress data in cache (using tracking_id)
            progress_data = cache.get(f'benchmark_progress_{tracking_id}')

            # Get Django-Q task ID from cache
            django_q_task_id = cache.get(f'benchmark_django_q_id_{tracking_id}')

            # Check if task exists in completed tasks (Task table)
            task = None
            if django_q_task_id:
                try:
                    task = Task.objects.get(id=django_q_task_id)
                except Task.DoesNotExist:
                    pass

            if task:
                # Get metadata from cache (we store it there now instead of task.group)
                metadata = cache.get(f'benchmark_metadata_{tracking_id}', {})

                # Determine status
                if task.success is True:
                    task_status = 'completed'
                elif task.success is False:
                    task_status = 'failed'
                else:
                    task_status = 'running'

                response_data = {
                    'success': True,
                    'task_id': tracking_id,  # Return tracking_id to frontend
                    'status': task_status,
                    'test_type': metadata.get('test_type'),
                    'dataset': metadata.get('dataset'),
                    'timestamp': task.stopped.isoformat() if task.stopped else task.started.isoformat() if task.started else None
                }

                # Add progress data if available
                if progress_data:
                    response_data['progress'] = progress_data

                return Response(response_data)
            else:
                # Task not in completed table - check if it's truly pending or if it timed out
                # If task has been running for too long (>2 hours), it likely timed out
                from datetime import timedelta

                # Check if we have stale progress data (task started more than 2 hours ago)
                is_stale = False
                if progress_data:
                    # Try to determine how long ago this task started
                    # If we can't find it in OrmQ either, assume it timed out
                    try:
                        pending_task = OrmQ.objects.filter(task__contains=tracking_id).first()
                        if not pending_task:
                            # Not in queue and not in completed tasks = likely timed out
                            is_stale = True
                    except:
                        pass

                if is_stale:
                    # Clear stale progress data
                    cache.delete(f'benchmark_progress_{tracking_id}')
                    return Response({
                        'success': True,
                        'task_id': tracking_id,
                        'status': 'failed',
                        'test_type': None,
                        'dataset': None,
                        'timestamp': None,
                        'error': 'Task timed out or failed'
                    })

                # Return pending status instead of 404 to avoid frontend polling errors
                # The frontend will continue polling until it gets a completed/failed status
                response_data = {
                    'success': True,
                    'task_id': tracking_id,
                    'status': 'pending',
                    'test_type': None,
                    'dataset': None,
                    'timestamp': None
                }

                # Add progress data if available (task may be running but not yet in DB)
                if progress_data:
                    response_data['progress'] = progress_data
                    response_data['status'] = 'running'  # Override to running if we have progress

                return Response(response_data)

        except Exception as e:
            logger.error(f"Failed to get benchmark status: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class BenchmarkResultsView(APIView):
    """Get benchmark results"""

    def get(self, request, task_id):
        try:
            # task_id here is actually the tracking_id from our system
            tracking_id = task_id

            # Get Django-Q task ID from cache
            django_q_task_id = cache.get(f'benchmark_django_q_id_{tracking_id}')

            if not django_q_task_id:
                return Response(
                    {'success': False, 'error': 'Benchmark task ID not found. Task may have expired.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get task from django-q
            try:
                task = Task.objects.get(id=django_q_task_id)
            except Task.DoesNotExist:
                return Response(
                    {'success': False, 'error': 'Benchmark task not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            if task.success is not True:
                task_status = 'failed' if task.success is False else 'pending'
                return Response(
                    {'success': False, 'error': f'Benchmark not yet completed (status: {task_status})'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get the task result using django-q's result function
            task_result = result(django_q_task_id)

            if task_result is None:
                return Response(
                    {'success': False, 'error': 'Benchmark results not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response({
                'success': task_result.get('success', True),
                'task_id': tracking_id,  # Return tracking_id to frontend
                'output': task_result.get('output', ''),
                'error': task_result.get('error'),
                'timestamp': task_result.get('timestamp')
            })

        except Exception as e:
            logger.error(f"Failed to get benchmark results: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ListDatasetsView(APIView):
    """List available benchmark datasets"""
    
    def get(self, request):
        try:
            # Get test_data directory
            test_data_dir = Path(__file__).parent / 'test_data'
            
            if not test_data_dir.exists():
                return Response({
                    'success': True,
                    'datasets': []
                })
            
            # List all .json files
            datasets = []
            for json_file in test_data_dir.glob('*.json'):
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    datasets.append({
                        'filename': json_file.name,
                        'description': data.get('description', 'No description'),
                        'version': data.get('dataset_version', 'Unknown'),
                        'num_conversations': len(data.get('test_conversations', [])),
                        'num_queries': len(data.get('test_queries', []))
                    })
                except Exception as e:
                    logger.warning(f"Failed to read dataset {json_file.name}: {e}")
                    datasets.append({
                        'filename': json_file.name,
                        'description': 'Error reading file',
                        'version': 'Unknown',
                        'num_conversations': 0,
                        'num_queries': 0
                    })
            
            return Response({
                'success': True,
                'datasets': datasets
            })

        except Exception as e:
            logger.error(f"Failed to list datasets: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UploadDatasetView(APIView):
    """Upload a new benchmark dataset"""

    parser_classes = [MultiPartParser]

    def post(self, request):
        """
        Upload a new benchmark dataset JSON file

        Expected parameters:
        - file: JSON dataset file
        """
        try:
            # Validate file upload
            if 'file' not in request.FILES:
                return Response(
                    {'success': False, 'error': 'No file uploaded'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            uploaded_file = request.FILES['file']

            # Validate file extension
            if not uploaded_file.name.endswith('.json'):
                return Response(
                    {'success': False, 'error': 'File must be a JSON file (.json)'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate filename (alphanumeric, underscores, hyphens only)
            import re
            safe_filename = re.sub(r'[^\w\-.]', '_', uploaded_file.name)

            # Read and validate JSON content
            try:
                content = uploaded_file.read().decode('utf-8')
                dataset = json.loads(content)
            except json.JSONDecodeError as e:
                return Response(
                    {'success': False, 'error': f'Invalid JSON format: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except UnicodeDecodeError:
                return Response(
                    {'success': False, 'error': 'File must be UTF-8 encoded'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate dataset structure
            if 'test_conversations' not in dataset and 'test_queries' not in dataset:
                return Response(
                    {'success': False, 'error': 'Invalid dataset format: must contain "test_conversations" or "test_queries"'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Determine dataset directory
            dataset_dir = Path(django_settings.BASE_DIR) / 'memories' / 'test_data'
            dataset_dir.mkdir(parents=True, exist_ok=True)

            # Check if file already exists
            target_file = dataset_dir / safe_filename
            if target_file.exists():
                return Response(
                    {'success': False, 'error': f'Dataset "{safe_filename}" already exists. Please delete it first or use a different filename.'},
                    status=status.HTTP_409_CONFLICT
                )

            # Write file
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(dataset, f, indent=2)

            logger.info(f"Uploaded new dataset: {safe_filename}")

            # Get dataset info
            num_conversations = len(dataset.get('test_conversations', []))
            num_queries = len(dataset.get('test_queries', []))

            return Response({
                'success': True,
                'message': f'Dataset "{safe_filename}" uploaded successfully',
                'filename': safe_filename,
                'num_conversations': num_conversations,
                'num_queries': num_queries
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Failed to upload dataset: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# =============================================================================
# Activity Monitor API
# =============================================================================

class ActiveTasksView(APIView):
    """Get currently running and pending tasks"""

    def get(self, request):
        try:
            from django_q.models import Task as DjangoQTask, OrmQ
            from django.core.cache import cache

            running_tasks = []
            pending_tasks = []

            current_time = timezone.now()

            # Get actually running tasks from the Task table (started but not stopped)
            # These are tasks that workers have picked up and are actively processing
            executing_tasks = DjangoQTask.objects.filter(
                started__isnull=False,
                stopped__isnull=True
            ).order_by('-started')[:10]

            for task in executing_tasks:
                try:
                    func_name = task.func
                    task_name = task.name

                    # Calculate elapsed time
                    elapsed_seconds = (current_time - task.started).total_seconds() if task.started else 0

                    # Try to get progress for extraction/benchmark tasks
                    progress = None
                    task_type = 'unknown'
                    turn_id = None

                    if 'extract_atomic_notes' in func_name:
                        task_type = 'extraction'
                        # Extract turn_id from task name (extract_{turn_id} or retry_extract_{turn_id}_{attempt})
                        if task_name.startswith('extract_') or task_name.startswith('retry_extract_'):
                            # Parse turn_id from name
                            parts = task_name.replace('retry_', '').replace('extract_', '').split('_')
                            if parts:
                                # First part after 'extract_' is the UUID, rest is attempt number
                                # UUIDs have format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (5 parts separated by -)
                                # So we need to join first 5 parts with '-'
                                if len(parts) >= 5:
                                    turn_id = '-'.join(parts[:5])
                                    progress_data = cache.get(f'extraction_progress_{turn_id}')
                                    if progress_data:
                                        progress = progress_data
                    elif 'run_benchmark_task' in func_name:
                        task_type = 'benchmark'
                        # Extract tracking_id from group metadata
                        if task.group:
                            try:
                                import json
                                metadata = json.loads(task.group)
                                tracking_id = metadata.get('tracking_id')
                                if tracking_id:
                                    progress_data = cache.get(f'benchmark_progress_{tracking_id}')
                                    if progress_data:
                                        progress = progress_data
                            except:
                                pass

                    running_tasks.append({
                        'task_id': str(task.id),
                        'type': task_type,
                        'name': task_name,
                        'started': task.started.isoformat() if task.started else None,
                        'elapsed_seconds': int(elapsed_seconds),
                        'progress': progress,
                        'turn_id': turn_id
                    })
                except Exception as e:
                    logger.warning(f"Error processing running task {task.id}: {e}")

            # Get ALL pending tasks from OrmQ (queued and waiting to be picked up by workers)
            # All tasks in OrmQ are by definition "pending" - once picked up, they move to Task table
            queued_tasks = OrmQ.objects.all().order_by('lock')[:20]

            for orm_task in queued_tasks:
                try:
                    # orm_task.task is already a dict (Django-Q deserializes it automatically)
                    task_data = orm_task.task
                    func_name = task_data.get('func', 'unknown')
                    args = task_data.get('args', [])
                    task_name = task_data.get('name', func_name)

                    task_type = 'unknown'
                    turn_id = None

                    if 'extract_atomic_notes' in func_name:
                        task_type = 'extraction'
                        # Extract turn_id from task name or args
                        if task_name.startswith('extract_') or task_name.startswith('retry_extract_'):
                            # Parse turn_id from name
                            parts = task_name.replace('retry_', '').replace('extract_', '').split('_')
                            if len(parts) >= 5:
                                turn_id = '-'.join(parts[:5])
                        elif args:
                            turn_id = str(args[0])
                    elif 'run_benchmark_task' in func_name:
                        task_type = 'benchmark'

                    # Calculate wait time until task becomes available (lock time)
                    # If lock is in the past, the task is ready to be picked up (wait = 0)
                    wait_seconds = max(0, (orm_task.lock - current_time).total_seconds())

                    pending_tasks.append({
                        'task_id': str(orm_task.id),
                        'type': task_type,
                        'name': task_name,
                        'queued_at': orm_task.lock.isoformat(),
                        'wait_seconds': int(wait_seconds),
                        'turn_id': turn_id
                    })
                except Exception as e:
                    logger.warning(f"Error processing pending task {orm_task.id}: {e}")

            return Response({
                'success': True,
                'timestamp': current_time.isoformat(),
                'running': running_tasks,
                'pending': pending_tasks,
                'running_count': len(running_tasks),
                'pending_count': len(pending_tasks)
            })

        except Exception as e:
            logger.error(f"Error fetching active tasks: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RecentTasksView(APIView):
    """Get recently completed tasks"""

    def get(self, request):
        try:
            from django_q.models import Task as DjangoQTask

            # Get last 20 completed tasks
            recent_tasks = DjangoQTask.objects.all().order_by('-stopped')[:20]

            tasks_list = []
            for task in recent_tasks:
                task_type = 'unknown'
                # Task names are like "extract_{turn_id}" or "retry_extract_{turn_id}_{attempt}" for extraction tasks
                if task.name.startswith('extract_') or task.name.startswith('retry_extract_'):
                    task_type = 'extraction'
                elif 'run_benchmark_task' in task.name or 'benchmark_' in task.name:
                    task_type = 'benchmark'

                # Calculate duration
                duration_seconds = 0
                if task.started and task.stopped:
                    duration_seconds = (task.stopped - task.started).total_seconds()

                task_status = 'completed' if task.success else 'failed'

                tasks_list.append({
                    'task_id': str(task.id),
                    'type': task_type,
                    'name': task.name,
                    'status': task_status,
                    'started': task.started.isoformat() if task.started else None,
                    'stopped': task.stopped.isoformat() if task.stopped else None,
                    'duration_seconds': int(duration_seconds)
                })

            return Response({
                'success': True,
                'tasks': tasks_list
            })

        except Exception as e:
            logger.error(f"Error fetching recent tasks: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ============================================================================
# Data Management API Views  
# ============================================================================

class ClearAllDataView(APIView):
    """Clear all data except settings"""

    def post(self, request):
        """
        Clear all data from conversations, notes, relationships
        Preserves settings and other configuration data
        """
        try:
            logger.info("Starting clear all data operation")
            
            # Clear conversation turns
            conversations_deleted = ConversationTurn.objects.all().delete()[0]
            logger.info(f"Deleted {conversations_deleted} conversation turns")
            
            # Clear atomic notes
            notes_deleted = AtomicNote.objects.all().delete()[0]
            logger.info(f"Deleted {notes_deleted} atomic notes")
            
            # Clear relationships (should cascade, but explicit is safer)
            relationships_deleted = NoteRelationship.objects.all().delete()[0]
            logger.info(f"Deleted {relationships_deleted} note relationships")
            
            # Clear vector storage in Qdrant if available
            try:
                # The vector service exposes a global instance `vector_service`
                # with a `clear_all_memories()` admin method that deletes/recreates
                # the Qdrant collection. Use that instead of non-existent helpers.
                from .vector_service import vector_service as q_vector_service

                if hasattr(q_vector_service, 'clear_all_memories'):
                    resp = q_vector_service.clear_all_memories()
                    logger.info("Cleared all vector embeddings: %s", resp)
                else:
                    logger.warning("Vector service does not implement clear_all_memories(), skipping Qdrant clear")
            except Exception as e:
                logger.warning(f"Failed to clear vector storage: {e}")
            
            # Clear Django-Q cache
            try:
                from django.core.cache import cache
                cache.clear()
                logger.info("Cleared Django cache")
            except Exception as e:
                logger.warning(f"Failed to clear cache: {e}")
            
            total_deleted = conversations_deleted + notes_deleted + relationships_deleted
            logger.info(f"Clear all data completed: {total_deleted} items deleted total")
            
            return Response({
                'success': True,
                'message': f'Successfully cleared all data ({total_deleted} items)',
                'deleted_items': {
                    'conversations': conversations_deleted,
                    'notes': notes_deleted,
                    'relationships': relationships_deleted
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to clear all data: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelBenchmarkView(APIView):
    """Cancel a running benchmark task"""

    def post(self, request):
        """
        Cancel a running benchmark task by stopping it in Django-Q
        """
        try:
            # Accept either the django-q numeric task id or our tracking_id (returned to frontend)
            django_q_task_id = request.data.get('django_q_task_id')
            tracking_id = request.data.get('tracking_id') or request.data.get('task_id')
            
            # Debug logging to understand what's being received
            logger.info(f"Cancel benchmark request data: {request.data}")
            logger.info(f"django_q_task_id: {django_q_task_id}, tracking_id: {tracking_id}")
            logger.info(f"Request method: {request.method}")
            logger.info(f"Content type: {request.content_type}")

            from django.core.cache import cache

            # If caller provided tracking_id, look up the django-q id from cache
            if not django_q_task_id and tracking_id:
                cached = cache.get(f'benchmark_django_q_id_{tracking_id}')
                if cached:
                    django_q_task_id = cached
                else:
                    # Cache miss - try to find the task by group (which contains tracking_id)
                    try:
                        task = Task.objects.filter(group=tracking_id).order_by('-started').first()
                        if task:
                            django_q_task_id = task.id
                            logger.info(f"Found task {django_q_task_id} for tracking_id {tracking_id}")
                    except Exception as e:
                        logger.debug(f"Could not find task by tracking_id: {e}")

            # Try to cancel queued OrmQ entries first (even if Task record not found)
            # This handles cases where task is queued but not yet in Task table
            queued_count = 0
            extraction_count = 0
            try:
                from django_q.models import OrmQ

                # OrmQ.task is a pickled field, we need to iterate to filter
                # Cannot use Django ORM queries on pickled data
                to_delete = []
                extraction_tasks = []

                for q in OrmQ.objects.all():
                    task_data = q.task  # Unpickles the data
                    task_name = task_data.get('name', '')

                    # Check if this task matches our tracking_id or task_id
                    if (tracking_id and task_data.get('group') == tracking_id) or \
                       (django_q_task_id and task_data.get('id') == str(django_q_task_id)):
                        to_delete.append(q.id)
                        logger.debug(f"Marking for deletion: {task_name} (group={task_data.get('group')})")

                    # Also remove any extraction tasks spawned by the benchmark
                    # These have names like "extract_<uuid>" or "retry_extract_<uuid>_N" but no group
                    elif task_name.startswith('extract_') or task_name.startswith('retry_extract_'):
                        extraction_tasks.append(q.id)
                        logger.debug(f"Marking extraction task for deletion: {task_name}")

                if to_delete:
                    queued_count = len(to_delete)
                    OrmQ.objects.filter(id__in=to_delete).delete()
                    logger.info(f"Removed {queued_count} queued benchmark task(s) for tracking_id={tracking_id}")

                # Also remove extraction tasks when cancelling benchmark
                if extraction_tasks:
                    extraction_count = len(extraction_tasks)
                    OrmQ.objects.filter(id__in=extraction_tasks).delete()
                    logger.info(f"Removed {extraction_count} queued extraction task(s)")

            except Exception as e:
                logger.error(f"Error checking/removing OrmQ entries: {e}", exc_info=True)

            # If no Task record found, return success (we already cleaned up OrmQ above)
            if not django_q_task_id:
                total_cleared = queued_count + extraction_count
                logger.warning(f"No Task record found for tracking_id {tracking_id}, cleared {total_cleared} queued entries (benchmark: {queued_count}, extraction: {extraction_count})")
                return Response({
                    'success': True,
                    'message': f'Cleared {total_cleared} queued task(s) for {tracking_id} (benchmark: {queued_count}, extraction: {extraction_count}). Task may have already completed or failed.',
                    'already_stopped': True,
                    'queued_cleared': queued_count,
                    'extraction_cleared': extraction_count
                })

            # Mark the Task object as cancelled/failed so status endpoints reflect cancellation
            try:
                task = Task.objects.get(id=django_q_task_id)

                # Only update if not already stopped
                if not task.stopped:
                    task.success = False
                    task.result = json.dumps({
                        'success': False,
                        'output': f'Benchmark task {django_q_task_id} was cancelled by user',
                        'error': 'cancelled_by_user',
                        'timestamp': timezone.now().isoformat()
                    })
                    task.stopped = timezone.now()
                    task.save()
                    logger.info(f"Marked django-q Task {django_q_task_id} as cancelled")

                return Response({
                    'success': True,
                    'message': f'Benchmark task {django_q_task_id} cancelled successfully'
                })

            except Task.DoesNotExist:
                # Task record doesn't exist - likely already completed/failed
                # We've already cleared any queued entries, so return success
                total_cleared = queued_count + extraction_count
                logger.info(f"Task {django_q_task_id} not found in database (may have completed/failed), cleared {total_cleared} queued entries (benchmark: {queued_count}, extraction: {extraction_count})")
                return Response({
                    'success': True,
                    'message': f'Task not found in database (already completed/failed). Cleared {total_cleared} queued task(s) (benchmark: {queued_count}, extraction: {extraction_count}).',
                    'already_stopped': True,
                    'queued_cleared': queued_count,
                    'extraction_cleared': extraction_count
                })

        except Exception as e:
            logger.error(f"Failed to cancel benchmark task: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

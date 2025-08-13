"""
Entity-Relationship API Views

New API endpoints for the entity-relationship knowledge graph system.
"""

import json
import logging
from typing import Dict, Any

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone

from .entity_extraction_service import entity_extraction_service
from .entity_graph_service import entity_graph_service
from .entity_search_service import entity_search_service
from .vector_service import vector_service
from .llm_service import llm_service

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class EntityExtractionView(View):
    """Extract entities and relationships from conversation text"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            conversation_text = data.get('conversation_text', '').strip()
            user_id = data.get('user_id', '').strip()
            
            if not conversation_text or not user_id:
                return JsonResponse({
                    'success': False,
                    'error': 'conversation_text and user_id are required'
                }, status=400)
            
            logger.info(f"Processing entity extraction for user {user_id}")
            
            # Step 1: Store conversation chunk in vector database
            timestamp = timezone.now().isoformat()
            
            # Create embedding for conversation
            embedding_result = llm_service.get_embeddings([conversation_text])
            if not embedding_result['success']:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to create embedding for conversation'
                }, status=500)
            
            # Store in vector database  
            vector_id = vector_service.store_conversation_chunks(
                chunks=[conversation_text],
                user_id=user_id,
                timestamp=timestamp,
                base_metadata={'source': 'entity_extraction_api'}
            )[0]
            
            # Step 2: Extract entities and relationships
            extraction_result = entity_extraction_service.store_entities_and_relationships(
                conversation_text=conversation_text,
                user_id=user_id,
                vector_id=vector_id,
                timestamp=timestamp
            )
            
            if not extraction_result['success']:
                return JsonResponse({
                    'success': False,
                    'error': extraction_result.get('error', 'Entity extraction failed')
                }, status=500)
            
            # Step 3: Build graph relationships
            graph_result = entity_graph_service.build_user_knowledge_graph(
                user_id=user_id,
                incremental=True
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Entities and relationships extracted successfully',
                'results': {
                    'chunk_id': extraction_result['chunk_id'],
                    'entities_created': extraction_result['entities_created'],
                    'relationships_created': extraction_result['relationships_created'],
                    'graph_nodes_created': graph_result.get('nodes_created', 0),
                    'graph_edges_created': graph_result.get('edges_created', 0)
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in entity extraction: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class EntitySearchView(View):
    """Search the entity-relationship knowledge graph"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            query = data.get('query', '').strip()
            user_id = data.get('user_id', '').strip()
            search_type = data.get('search_type', 'auto')
            limit = data.get('limit', 20)
            
            if not query or not user_id:
                return JsonResponse({
                    'success': False,
                    'error': 'query and user_id are required'
                }, status=400)
            
            logger.info(f"Entity search query: '{query}' for user {user_id}")
            
            # Perform knowledge graph search
            search_result = entity_search_service.search_knowledge_graph(
                query=query,
                user_id=user_id,
                search_type=search_type,
                limit=limit
            )
            
            return JsonResponse(search_result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in entity search: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@require_http_methods(["GET"])
def user_knowledge_summary(request, user_id):
    """Get comprehensive summary of user's knowledge graph"""
    try:
        logger.info(f"Getting knowledge summary for user {user_id}")
        
        summary = entity_search_service.get_user_knowledge_summary(user_id)
        return JsonResponse(summary)
        
    except Exception as e:
        logger.error(f"Error getting knowledge summary: {e}")
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def graph_statistics(request, user_id):
    """Get graph statistics for a user"""
    try:
        stats = entity_graph_service.get_graph_statistics(user_id)
        return JsonResponse({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting graph statistics: {e}")
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class UserPreferencesView(View):
    """Get user preferences from knowledge graph"""
    
    def get(self, request, user_id):
        try:
            preference_types = request.GET.getlist('types')  # Optional filter
            if not preference_types:
                preference_types = None
                
            preferences = entity_graph_service.query_user_preferences(
                user_id=user_id,
                preference_types=preference_types
            )
            
            return JsonResponse({
                'success': True,
                'user_id': user_id,
                'preferences': preferences,
                'total_found': len(preferences)
            })
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return JsonResponse({
                'success': False,
                'error': f'Internal server error: {str(e)}'
            }, status=500)


@require_http_methods(["DELETE"])
@csrf_exempt
def clear_user_graph(request, user_id):
    """Clear all graph data for a user"""
    try:
        logger.warning(f"Clearing graph data for user {user_id}")
        
        # Clear from graph database
        graph_result = entity_graph_service.clear_user_graph(user_id)
        
        # Clear from relational database
        from .entity_models import Entity, Relationship, EntityConversationChunk
        
        Entity.objects.filter(user_id=user_id).delete()
        Relationship.objects.filter(user_id=user_id).delete()
        EntityConversationChunk.objects.filter(user_id=user_id).delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Cleared all graph data for user {user_id}',
            'graph_nodes_deleted': graph_result.get('deleted_nodes', 0)
        })
        
    except Exception as e:
        logger.error(f"Error clearing user graph: {e}")
        return JsonResponse({
            'success': False,
            'error': f'Internal server error: {str(e)}'
        }, status=500)
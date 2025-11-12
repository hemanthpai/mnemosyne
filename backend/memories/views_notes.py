"""
API views for atomic notes management
"""

import logging
import uuid
from typing import Dict, Any

from django_q.tasks import async_task
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Count

from .models import AtomicNote, NoteRelationship, ConversationTurn

logger = logging.getLogger(__name__)


class ListAtomicNotesView(APIView):
    """List atomic notes with filtering and pagination"""

    def get(self, request):
        """
        GET /api/notes/list/

        Query params:
            - user_id (required): Filter by user UUID
            - note_type (optional): Filter by note type (e.g., "preference:ui")
            - search (optional): Search in content
            - limit (optional): Number of results (default: 50, max: 200)
            - offset (optional): Pagination offset (default: 0)
            - order_by (optional): Sort field (default: "importance_score")
                Options: importance_score, created_at, confidence, content
            - order (optional): Sort direction (default: "desc")
                Options: asc, desc
        """
        # Validate required parameters
        user_id = request.GET.get('user_id')
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

        # Parse optional parameters
        note_type = request.GET.get('note_type')
        search = request.GET.get('search')
        limit = min(int(request.GET.get('limit', 50)), 200)
        offset = int(request.GET.get('offset', 0))
        order_by = request.GET.get('order_by', 'importance_score')
        order = request.GET.get('order', 'desc')

        # Validate order_by
        valid_order_by = ['importance_score', 'created_at', 'confidence', 'content']
        if order_by not in valid_order_by:
            return Response(
                {'success': False, 'error': f'Invalid order_by. Must be one of: {", ".join(valid_order_by)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build query
        query = AtomicNote.objects.filter(user_id=user_id)

        # Apply filters
        if note_type:
            query = query.filter(note_type__icontains=note_type)

        if search:
            query = query.filter(
                Q(content__icontains=search) |
                Q(context__icontains=search) |
                Q(tags__contains=[search])
            )

        # Get total count before pagination
        total_count = query.count()

        # Apply ordering
        order_prefix = '-' if order == 'desc' else ''
        query = query.order_by(f'{order_prefix}{order_by}')

        # Apply pagination
        notes = query[offset:offset + limit]

        # Format response
        notes_data = []
        for note in notes:
            # Count relationships
            outgoing_count = NoteRelationship.objects.filter(from_note=note).count()
            incoming_count = NoteRelationship.objects.filter(to_note=note).count()

            notes_data.append({
                'id': str(note.id),
                'content': note.content,
                'note_type': note.note_type,
                'context': note.context,
                'confidence': note.confidence,
                'importance_score': note.importance_score,
                'tags': note.tags or [],
                'relationships': {
                    'outgoing': outgoing_count,
                    'incoming': incoming_count
                },
                'source_turn_id': str(note.source_turn.id) if note.source_turn else None,
                'created_at': note.created_at.isoformat(),
                'updated_at': note.updated_at.isoformat()
            })

        return Response({
            'success': True,
            'count': len(notes_data),
            'total': total_count,
            'offset': offset,
            'limit': limit,
            'notes': notes_data
        })


class GetAtomicNoteView(APIView):
    """Get a single atomic note with its relationships"""

    def get(self, request):
        """
        GET /api/notes/get/

        Query params:
            - note_id (required): UUID of the note
        """
        note_id = request.GET.get('note_id')
        if not note_id:
            return Response(
                {'success': False, 'error': 'Missing required parameter: note_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate UUID
        try:
            uuid.UUID(note_id)
        except ValueError:
            return Response(
                {'success': False, 'error': 'Invalid note_id format (must be UUID)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            note = AtomicNote.objects.get(id=note_id)

            # Get outgoing relationships
            outgoing_rels = NoteRelationship.objects.filter(from_note=note).select_related('to_note')
            outgoing_data = [{
                'id': str(rel.id),
                'to_note': {
                    'id': str(rel.to_note.id),
                    'content': rel.to_note.content,
                    'note_type': rel.to_note.note_type
                },
                'relationship_type': rel.relationship_type,
                'strength': rel.strength,
                'reasoning': rel.reasoning
            } for rel in outgoing_rels]

            # Get incoming relationships
            incoming_rels = NoteRelationship.objects.filter(to_note=note).select_related('from_note')
            incoming_data = [{
                'id': str(rel.id),
                'from_note': {
                    'id': str(rel.from_note.id),
                    'content': rel.from_note.content,
                    'note_type': rel.from_note.note_type
                },
                'relationship_type': rel.relationship_type,
                'strength': rel.strength,
                'reasoning': rel.reasoning
            } for rel in incoming_rels]

            return Response({
                'success': True,
                'note': {
                    'id': str(note.id),
                    'user_id': str(note.user_id),
                    'content': note.content,
                    'note_type': note.note_type,
                    'context': note.context,
                    'confidence': note.confidence,
                    'importance_score': note.importance_score,
                    'tags': note.tags or [],
                    'vector_id': note.vector_id,
                    'source_turn_id': str(note.source_turn.id) if note.source_turn else None,
                    'created_at': note.created_at.isoformat(),
                    'updated_at': note.updated_at.isoformat()
                },
                'relationships': {
                    'outgoing': outgoing_data,
                    'incoming': incoming_data
                }
            })

        except AtomicNote.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Note not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DeleteAtomicNoteView(APIView):
    """Delete an atomic note"""

    def delete(self, request):
        """
        DELETE /api/notes/delete/

        Body:
            - note_id (required): UUID of the note to delete
        """
        note_id = request.data.get('note_id')
        if not note_id:
            return Response(
                {'success': False, 'error': 'Missing required field: note_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate UUID
        try:
            uuid.UUID(note_id)
        except ValueError:
            return Response(
                {'success': False, 'error': 'Invalid note_id format (must be UUID)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            note = AtomicNote.objects.get(id=note_id)

            # Log for audit
            logger.info(f"Deleting atomic note {note_id}: {note.content[:50]}...")

            # Capture user_id before deleting
            user_id = str(note.user_id)

            # Delete note (relationships will be cascade deleted)
            note.delete()

            # Invalidate BM25 cache
            from .bm25_service import get_bm25_service
            bm25_service = get_bm25_service()
            bm25_service.invalidate_cache(user_id)
            logger.debug(f"Invalidated BM25 cache for user {user_id}")

            return Response({
                'success': True,
                'message': 'Note deleted successfully'
            })

        except AtomicNote.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Note not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class GetNoteTypesView(APIView):
    """Get list of all note types used by a user"""

    def get(self, request):
        """
        GET /api/notes/types/

        Query params:
            - user_id (required): Filter by user UUID
        """
        user_id = request.GET.get('user_id')
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

        # Get unique note types with counts
        note_types = AtomicNote.objects.filter(user_id=user_id).values('note_type').annotate(
            count=Count('id')
        ).order_by('-count')

        return Response({
            'success': True,
            'note_types': list(note_types)
        })


class GetAvailableUsersView(APIView):
    """Get list of user_ids that have atomic notes"""

    def get(self, request):
        """
        GET /api/notes/users/

        Returns list of user_ids that have at least one atomic note,
        along with their note counts.
        """
        # Get distinct user_ids with note counts
        users = AtomicNote.objects.values('user_id').annotate(
            note_count=Count('id')
        ).order_by('-note_count')

        return Response({
            'success': True,
            'users': [
                {
                    'user_id': str(user['user_id']),
                    'note_count': user['note_count']
                }
                for user in users
            ]
        })


class TriggerExtractionView(APIView):
    """Manually trigger atomic note extraction for a conversation turn"""

    def post(self, request):
        """
        POST /api/notes/extract/

        Body:
            - turn_id (required): UUID of the conversation turn to extract
            - force (optional): Force re-extraction even if already extracted
        """
        turn_id = request.data.get('turn_id')
        force = request.data.get('force', False)

        if not turn_id:
            return Response(
                {'success': False, 'error': 'Missing required field: turn_id'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate UUID
        try:
            uuid.UUID(turn_id)
        except ValueError:
            return Response(
                {'success': False, 'error': 'Invalid turn_id format (must be UUID)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            turn = ConversationTurn.objects.get(id=turn_id)

            # Check if already extracted
            if turn.extracted and not force:
                return Response(
                    {
                        'success': False,
                        'error': 'Turn already extracted. Use force=true to re-extract.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Reset extraction flag if forcing
            if force and turn.extracted:
                turn.extracted = False
                turn.save()
                logger.info(f"Forcing re-extraction for turn {turn_id}")

            # Schedule extraction task
            task_id = async_task(
                'memories.tasks.extract_atomic_notes',
                str(turn.id),
                q_options={'timeout': 300}
            )

            logger.info(f"Scheduled manual extraction for turn {turn_id}, task_id: {task_id}")

            return Response({
                'success': True,
                'message': 'Extraction task scheduled',
                'task_id': task_id,
                'turn_id': str(turn.id)
            })

        except ConversationTurn.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Turn not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class KnowledgeGraphView(APIView):
    """Get knowledge graph data for visualization"""

    def get(self, request):
        """
        GET /api/notes/graph/

        Query params:
            - user_id (required): Filter by user UUID
            - note_type (optional): Filter by note type (e.g., "skill:programming")
            - limit (optional): Limit number of nodes (default: 100)
            - min_strength (optional): Minimum relationship strength (default: 0.5)

        Returns nodes and edges for graph visualization:
        {
            "success": true,
            "nodes": [
                {
                    "id": "note-uuid",
                    "content": "note content",
                    "note_type": "preference:tool",
                    "confidence": 0.95,
                    "importance_score": 1.0,
                    "tags": ["tag1", "tag2"],
                    "relationship_count": 5
                },
                ...
            ],
            "edges": [
                {
                    "id": "relationship-uuid",
                    "source": "from-note-uuid",
                    "target": "to-note-uuid",
                    "relationship_type": "related_to",
                    "strength": 0.85
                },
                ...
            ],
            "stats": {
                "total_nodes": 100,
                "total_edges": 250,
                "note_types": {"skill:programming": 20, ...}
            }
        }
        """
        user_id = request.GET.get('user_id')
        note_type = request.GET.get('note_type')
        limit = int(request.GET.get('limit', 100))
        min_strength = float(request.GET.get('min_strength', 0.5))

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

        try:
            # Build query for notes
            notes_query = AtomicNote.objects.filter(user_id=user_id)

            if note_type:
                notes_query = notes_query.filter(note_type=note_type)

            # Get notes with relationship counts
            notes = notes_query.annotate(
                relationship_count=Count('outgoing_relationships') + Count('incoming_relationships')
            ).order_by('-importance_score', '-confidence')[:limit]

            # Get note IDs for relationship filtering
            note_ids = [str(note.id) for note in notes]
            note_ids_set = set(note_ids)

            # Build nodes
            nodes = []
            note_type_counts = {}

            for note in notes:
                nodes.append({
                    'id': str(note.id),
                    'content': note.content,
                    'note_type': note.note_type,
                    'confidence': note.confidence,
                    'importance_score': note.importance_score,
                    'tags': note.tags or [],
                    'relationship_count': note.relationship_count,
                    'created_at': note.created_at.isoformat()
                })

                # Track note type counts for stats
                note_type_counts[note.note_type] = note_type_counts.get(note.note_type, 0) + 1

            # Get relationships between these notes
            # Only include edges where both source and target are in our node set
            relationships = NoteRelationship.objects.filter(
                from_note_id__in=note_ids,
                to_note_id__in=note_ids,
                strength__gte=min_strength
            ).select_related('from_note', 'to_note')

            # Build edges
            edges = []
            for rel in relationships:
                # Double-check both nodes are in our set
                if str(rel.from_note_id) in note_ids_set and str(rel.to_note_id) in note_ids_set:
                    edges.append({
                        'id': str(rel.id),
                        'source': str(rel.from_note_id),
                        'target': str(rel.to_note_id),
                        'relationship_type': rel.relationship_type,
                        'strength': rel.strength
                    })

            logger.info(f"Knowledge graph for user {user_id}: {len(nodes)} nodes, {len(edges)} edges")

            return Response({
                'success': True,
                'nodes': nodes,
                'edges': edges,
                'stats': {
                    'total_nodes': len(nodes),
                    'total_edges': len(edges),
                    'note_types': note_type_counts
                }
            })

        except Exception as e:
            logger.error(f"Failed to generate knowledge graph: {e}", exc_info=True)
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

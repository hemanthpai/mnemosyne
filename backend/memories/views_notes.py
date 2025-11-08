"""
API views for atomic notes management (Phase 3)
"""

import logging
import uuid
from typing import Dict, Any

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Count

from .models import AtomicNote, NoteRelationship

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

            # Delete note (relationships will be cascade deleted)
            note.delete()

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

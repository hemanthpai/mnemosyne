"""
Import API Views

Handles OpenWebUI conversation import with progress tracking and cancellation.
"""

import logging
import threading
import uuid
from datetime import datetime
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser

from .openwebui_importer import OpenWebUIImporter

logger = logging.getLogger(__name__)


class StartImportView(APIView):
    """Start OpenWebUI history import"""

    parser_classes = [MultiPartParser]

    def post(self, request):
        """
        Start import from uploaded Open WebUI database file

        Expected parameters:
        - file: webui.db SQLite database file
        - user_id: (Optional) Force all conversations to this Mnemosyne user ID
        - preserve_users: (Optional) Preserve original Open WebUI user IDs (default: true)
        - dry_run: Boolean (optional, default: false)

        If preserve_users=true (default), each Open WebUI user's conversations
        will be imported to a corresponding Mnemosyne user ID.

        If user_id is provided, it overrides preserve_users and forces all
        conversations to that single user (for single-user imports).
        """
        # Validate file upload
        if 'file' not in request.FILES:
            return Response(
                {'success': False, 'error': 'No file uploaded'},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES['file']
        user_id = request.data.get('user_id')  # Optional now
        preserve_users = request.data.get('preserve_users', 'true').lower() == 'true'
        dry_run = request.data.get('dry_run', 'false').lower() == 'true'

        # Validate user_id if provided
        if user_id:
            try:
                uuid.UUID(user_id)
            except ValueError:
                return Response(
                    {'success': False, 'error': 'Invalid user_id format (must be UUID)'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Save uploaded file temporarily
        import tempfile
        temp_dir = Path(tempfile.gettempdir())
        temp_file = temp_dir / f"openwebui_import_{uuid.uuid4()}.db"

        try:
            with open(temp_file, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            # Determine import mode
            if user_id:
                import_mode = f"single-user mode (user_id={user_id})"
                target_user_id = user_id
            elif preserve_users:
                import_mode = "multi-user mode (preserving original user IDs)"
                target_user_id = None
            else:
                # Neither user_id nor preserve_users - invalid
                return Response(
                    {'success': False, 'error': 'Must provide user_id or set preserve_users=true'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.info(f"Starting import from {temp_file} in {import_mode} (dry_run={dry_run})")

            # Start import in background thread
            task_id = str(uuid.uuid4())

            def run_import():
                """Background import task"""
                try:
                    with OpenWebUIImporter(str(temp_file)) as importer:
                        # Initialize progress (before starting import)
                        from .openwebui_importer import _import_progress, _progress_lock
                        with _progress_lock:
                            _import_progress.__init__()  # Reset
                            _import_progress.status = "running"
                            _import_progress.start_time = datetime.now()
                            _import_progress.dry_run = dry_run

                        # Run import
                        result = importer.import_conversations(
                            target_user_id=target_user_id,  # None to preserve users
                            dry_run=dry_run,
                            batch_size=10,
                            limit=None
                        )

                        logger.info(f"Import completed: {result}")

                except Exception as e:
                    logger.error(f"Import failed: {e}", exc_info=True)
                    from .openwebui_importer import _import_progress, _progress_lock
                    with _progress_lock:
                        _import_progress.status = "failed"
                        _import_progress.error_message = str(e)
                        _import_progress.end_time = datetime.now()

                finally:
                    # Clean up temp file
                    try:
                        temp_file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file: {e}")

            # Start background thread
            import_thread = threading.Thread(target=run_import, daemon=True)
            import_thread.start()

            return Response({
                'success': True,
                'task_id': task_id,
                'message': f'Import started (dry_run={dry_run})'
            })

        except Exception as e:
            # Clean up on error
            try:
                temp_file.unlink()
            except:
                pass

            logger.error(f"Failed to start import: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ImportProgressView(APIView):
    """Get import progress"""

    def get(self, request):
        """
        Get current import progress

        Optional parameter:
        - task_id: Task ID (currently unused, using global progress)
        """
        try:
            progress = OpenWebUIImporter.get_progress()

            return Response({
                'success': True,
                **progress
            })

        except Exception as e:
            logger.error(f"Failed to get import progress: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CancelImportView(APIView):
    """Cancel ongoing import"""

    def post(self, request):
        """
        Cancel ongoing import

        Optional parameter:
        - task_id: Task ID (currently unused, using global progress)
        """
        try:
            OpenWebUIImporter.cancel_import()

            return Response({
                'success': True,
                'message': 'Import cancellation requested'
            })

        except Exception as e:
            logger.error(f"Failed to cancel import: {e}")
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

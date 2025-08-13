import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone as django_timezone

from memories.models import Memory, ConversationChunk
from memories.vector_service import VectorService
from memories.graph_service import GraphService
from memories.memory_search_service import MemorySearchService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing memory data to hybrid architecture (Vector DB + Graph DB)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=str,
            help='Migrate data for specific user only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without committing to database'
        )
        parser.add_argument(
            '--chunk-size',
            type=int,
            default=1000,
            help='Conversation chunk size in characters (default: 1000)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of memories to process in each batch (default: 50)'
        )
        parser.add_argument(
            '--skip-vector-migration',
            action='store_true',
            help='Skip vector database migration (only update memory models)'
        )
        parser.add_argument(
            '--skip-graph-rebuild',
            action='store_true',
            help='Skip graph database rebuild after migration'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.user_id = options['user_id']
        self.chunk_size = options['chunk_size']
        self.batch_size = options['batch_size']
        self.skip_vector = options['skip_vector_migration']
        self.skip_graph = options['skip_graph_rebuild']

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be committed')
            )

        try:
            self.migrate_to_hybrid_architecture()
        except Exception as e:
            logger.exception("Migration failed")
            raise CommandError(f'Migration failed: {str(e)}')

    def migrate_to_hybrid_architecture(self):
        """Main migration orchestrator"""
        self.stdout.write("Starting hybrid architecture migration...")
        
        # Initialize services
        self.vector_service = VectorService()
        self.graph_service = GraphService()
        self.search_service = MemorySearchService()
        
        # Get memories to migrate
        memory_queryset = Memory.objects.all()
        if self.user_id:
            memory_queryset = memory_queryset.filter(user_id=self.user_id)
            
        total_memories = memory_queryset.count()
        self.stdout.write(f"Found {total_memories} memories to migrate")
        
        if total_memories == 0:
            self.stdout.write("No memories found to migrate")
            return
            
        # Step 1: Extract conversation context from existing memories
        self.stdout.write("\n=== Step 1: Extracting conversation contexts ===")
        conversation_data = self._extract_conversation_contexts(memory_queryset)
        
        # Step 2: Create conversation chunks and migrate vector data
        if not self.skip_vector:
            self.stdout.write("\n=== Step 2: Migrating to conversation-based vector storage ===")
            self._migrate_vector_storage(conversation_data)
        else:
            self.stdout.write("\n=== Step 2: Skipped (vector migration disabled) ===")
            
        # Step 3: Update memory models and link to conversation chunks
        self.stdout.write("\n=== Step 3: Updating memory models ===")
        self._update_memory_models(conversation_data)
        
        # Step 4: Rebuild graph with enhanced relationships
        if not self.skip_graph:
            self.stdout.write("\n=== Step 4: Rebuilding graph database ===")
            self._rebuild_graph_database()
        else:
            self.stdout.write("\n=== Step 4: Skipped (graph rebuild disabled) ===")
            
        self.stdout.write(
            self.style.SUCCESS(f'\nMigration completed successfully!')
        )

    def _extract_conversation_contexts(self, memory_queryset) -> Dict:
        """Extract conversation contexts from existing memories"""
        conversation_data = {}
        
        # Group memories by user and approximate time windows
        user_memories = {}
        for memory in memory_queryset:
            if memory.user_id not in user_memories:
                user_memories[memory.user_id] = []
            user_memories[memory.user_id].append(memory)
        
        for user_id, memories in user_memories.items():
            # Sort by creation time
            memories.sort(key=lambda m: m.created_at)
            
            # Group into conversation sessions (1 hour gaps)
            conversation_sessions = self._group_into_sessions(memories)
            
            # Create conversation chunks from sessions
            user_chunks = []
            for session_memories in conversation_sessions:
                chunks = self._create_chunks_from_session(session_memories)
                user_chunks.extend(chunks)
            
            conversation_data[user_id] = user_chunks
            self.stdout.write(
                f"User {user_id}: {len(memories)} memories → {len(user_chunks)} conversation chunks"
            )
        
        return conversation_data

    def _group_into_sessions(self, memories: List[Memory]) -> List[List[Memory]]:
        """Group memories into conversation sessions based on time gaps"""
        if not memories:
            return []
            
        sessions = []
        current_session = [memories[0]]
        
        for memory in memories[1:]:
            # If more than 1 hour gap, start new session
            time_gap = memory.created_at - current_session[-1].created_at
            if time_gap.total_seconds() > 3600:  # 1 hour
                sessions.append(current_session)
                current_session = [memory]
            else:
                current_session.append(memory)
                
        sessions.append(current_session)
        return sessions

    def _create_chunks_from_session(self, session_memories: List[Memory]) -> List[Dict]:
        """Create conversation chunks from a session of memories"""
        chunks = []
        
        # Reconstruct conversation text from memories
        conversation_parts = []
        for memory in session_memories:
            # Try to extract original context from memory
            context = self._extract_original_context(memory)
            if context:
                conversation_parts.append({
                    'text': context,
                    'timestamp': memory.created_at,
                    'memory_ids': [str(memory.id)]
                })
        
        if not conversation_parts:
            # Fallback: use memory content as conversation
            for memory in session_memories:
                conversation_parts.append({
                    'text': f"Memory: {memory.content}",
                    'timestamp': memory.created_at,
                    'memory_ids': [str(memory.id)]
                })
        
        # Combine into larger chunks
        combined_text = "\n".join([part['text'] for part in conversation_parts])
        combined_memory_ids = []
        for part in conversation_parts:
            combined_memory_ids.extend(part['memory_ids'])
        
        # Split into appropriately sized chunks
        if len(combined_text) <= self.chunk_size:
            chunks.append({
                'content': combined_text,
                'timestamp': session_memories[0].created_at,
                'memory_ids': combined_memory_ids,
                'metadata': {
                    'source': 'migration',
                    'session_memory_count': len(session_memories)
                }
            })
        else:
            # Split large conversations
            chunk_parts = self.vector_service.chunk_conversation(combined_text, self.chunk_size)
            for i, chunk_text in enumerate(chunk_parts):
                chunks.append({
                    'content': chunk_text,
                    'timestamp': session_memories[0].created_at,
                    'memory_ids': combined_memory_ids,  # All chunks link to all memories in session
                    'metadata': {
                        'source': 'migration',
                        'chunk_index': i,
                        'total_chunks': len(chunk_parts),
                        'session_memory_count': len(session_memories)
                    }
                })
        
        return chunks

    def _extract_original_context(self, memory: Memory) -> Optional[str]:
        """Try to extract original conversation context from memory"""
        # Check if memory metadata contains original context
        if hasattr(memory, 'metadata') and memory.metadata:
            if 'original_context' in memory.metadata:
                return memory.metadata['original_context']
            if 'context' in memory.metadata:
                return memory.metadata['context']
        
        # Fallback: use memory content
        return None

    def _migrate_vector_storage(self, conversation_data: Dict):
        """Migrate vector storage to conversation-based approach"""
        total_chunks = sum(len(chunks) for chunks in conversation_data.values())
        processed = 0
        
        for user_id, chunks in conversation_data.items():
            if self.dry_run:
                self.stdout.write(f"Would create {len(chunks)} conversation chunks for user {user_id}")
                continue
                
            try:
                with transaction.atomic():
                    for chunk_data in chunks:
                        # Create ConversationChunk record
                        chunk = ConversationChunk.objects.create(
                            user_id=user_id,
                            content=chunk_data['content'],
                            vector_id=f"migration_{user_id}_{processed}_{datetime.now().timestamp()}",
                            timestamp=chunk_data['timestamp'],
                            metadata=chunk_data['metadata'],
                            extracted_memory_ids=chunk_data['memory_ids']
                        )
                        
                        # Store embedding in vector database
                        try:
                            self.vector_service.store_conversation_chunk_embedding(
                                chunk_id=str(chunk.id),
                                user_id=user_id,
                                content=chunk_data['content'],
                                timestamp=chunk_data['timestamp'],
                                metadata=chunk_data['metadata']
                            )
                        except Exception as e:
                            logger.warning(f"Failed to store embedding for chunk {chunk.id}: {e}")
                        
                        processed += 1
                        if processed % 10 == 0:
                            self.stdout.write(f"Processed {processed}/{total_chunks} chunks...")
                            
            except Exception as e:
                logger.error(f"Failed to migrate vector storage for user {user_id}: {e}")
                if not self.dry_run:
                    raise

    def _update_memory_models(self, conversation_data: Dict):
        """Update memory models to link with conversation chunks"""
        for user_id, chunks in conversation_data.items():
            # Build mapping from memory IDs to chunk IDs
            memory_to_chunks = {}
            
            if not self.dry_run:
                # Get actual chunk records
                user_chunks = ConversationChunk.objects.filter(user_id=user_id)
                for chunk in user_chunks:
                    for memory_id in chunk.extracted_memory_ids:
                        if memory_id not in memory_to_chunks:
                            memory_to_chunks[memory_id] = []
                        memory_to_chunks[memory_id].append(str(chunk.id))
            else:
                # Simulate for dry run
                for i, chunk_data in enumerate(chunks):
                    for memory_id in chunk_data['memory_ids']:
                        if memory_id not in memory_to_chunks:
                            memory_to_chunks[memory_id] = []
                        memory_to_chunks[memory_id].append(f"simulated_chunk_{i}")
            
            # Update memories
            user_memories = Memory.objects.filter(user_id=user_id)
            for memory in user_memories:
                memory_id = str(memory.id)
                if memory_id in memory_to_chunks:
                    if self.dry_run:
                        self.stdout.write(
                            f"Would link memory {memory_id} to chunks: {memory_to_chunks[memory_id]}"
                        )
                    else:
                        memory.conversation_chunk_ids = memory_to_chunks[memory_id]
                        # Ensure metadata has standardized structure
                        memory.metadata = memory.get_standardized_metadata()
                        memory.save()

    def _rebuild_graph_database(self):
        """Rebuild graph database with enhanced relationships"""
        if self.user_id:
            users_to_rebuild = [self.user_id]
        else:
            # Get all unique user IDs
            users_to_rebuild = list(
                Memory.objects.values_list('user_id', flat=True).distinct()
            )
        
        self.stdout.write(f"Rebuilding graph for {len(users_to_rebuild)} users...")
        
        for user_id in users_to_rebuild:
            if self.dry_run:
                self.stdout.write(f"Would rebuild graph for user {user_id}")
                continue
                
            try:
                result = self.graph_service.build_memory_graph(
                    user_id=user_id,
                    incremental=False  # Full rebuild for migration
                )
                
                if result.get('success'):
                    nodes_created = result.get('nodes_created', 0)
                    relationships_created = result.get('relationships_created', 0)
                    self.stdout.write(
                        f"User {user_id}: {nodes_created} nodes, {relationships_created} relationships"
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"Graph build failed for user {user_id}: {result.get('error')}")
                    )
                    
            except Exception as e:
                logger.warning(f"Failed to rebuild graph for user {user_id}: {e}")
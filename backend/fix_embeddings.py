#!/usr/bin/env python3
"""
Script to fix missing embeddings for existing memories.
This will add vector embeddings for memories that don't have vector_id set.
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/home/hemanth/Developer/mnemosyne/backend')

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'memory_service.settings')
django.setup()

from memories.models import Memory
from memories.vector_service import vector_service
from memories.llm_service import llm_service

def fix_missing_embeddings():
    """Add embeddings for memories that don't have vector_id"""
    
    # Find memories without vector_id
    memories_without_vectors = Memory.objects.filter(vector_id__isnull=True)
    count = memories_without_vectors.count()
    
    print(f"Found {count} memories without vector embeddings")
    
    if count == 0:
        print("All memories already have embeddings!")
        return
    
    # Process in batches to avoid overwhelming the system
    batch_size = 5
    successful = 0
    failed = 0
    
    for i in range(0, count, batch_size):
        batch = memories_without_vectors[i:i+batch_size]
        print(f"\nProcessing batch {i//batch_size + 1} ({len(batch)} memories)...")
        
        for memory in batch:
            try:
                print(f"  Processing memory {memory.id}: '{memory.content[:50]}...'")
                
                # Get embedding for the memory content
                embedding_result = llm_service.get_embeddings([memory.content])
                
                if not embedding_result["success"]:
                    print(f"    ❌ Failed to get embedding: {embedding_result['error']}")
                    failed += 1
                    continue
                
                embedding = embedding_result["embeddings"][0]
                
                # Store in vector database
                vector_id = vector_service.store_embedding(
                    memory_id=str(memory.id),
                    embedding=embedding,
                    user_id=str(memory.user_id),
                    metadata={
                        **memory.metadata,
                        "created_at": memory.created_at.isoformat()
                    }
                )
                
                # Update memory with vector_id
                memory.vector_id = vector_id
                memory.save()
                
                print(f"    ✅ Successfully added embedding (vector_id: {vector_id[:8]}...)")
                successful += 1
                
            except Exception as e:
                print(f"    ❌ Error processing memory {memory.id}: {e}")
                failed += 1
    
    print(f"\n📊 Summary:")
    print(f"  ✅ Successfully processed: {successful}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📊 Total memories now have embeddings: {Memory.objects.filter(vector_id__isnull=False).count()}")
    
    # Check Qdrant collection status
    try:
        collection_info = vector_service.get_collection_info()
        print(f"  🗄️ Qdrant collection points: {collection_info.get('points_count', 'unknown')}")
    except Exception as e:
        print(f"  ⚠️ Could not get Qdrant info: {e}")

if __name__ == "__main__":
    print("🔧 Fixing missing embeddings for existing memories...")
    fix_missing_embeddings()
    print("✨ Done!")
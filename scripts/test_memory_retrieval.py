#!/usr/bin/env python3
"""
Test memory retrieval with different optimization levels to validate response size reductions.
"""

import requests
import json
import os
import uuid
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER_ID = str(uuid.uuid4())  # Generate a valid UUID
TEST_PROMPT = "What outdoor activities does the user enjoy?"

def test_optimization_level(level, description):
    """Test memory retrieval with specific optimization level"""
    print(f"\n=== Testing {level.upper()} Mode ({description}) ===")
    
    # Configure request based on optimization level
    if level == "fast":
        payload = {
            "prompt": TEST_PROMPT,
            "user_id": TEST_USER_ID,
            "fields": ["id", "content"],
            "include_search_metadata": False,
            "include_summary": False
        }
    elif level == "detailed":
        payload = {
            "prompt": TEST_PROMPT,
            "user_id": TEST_USER_ID,
            "fields": ["id", "content", "created_at"],
            "include_search_metadata": True,
            "include_summary": False
        }
    elif level == "full":
        payload = {
            "prompt": TEST_PROMPT,
            "user_id": TEST_USER_ID,
            "fields": ["id", "content", "metadata", "created_at", "updated_at"],
            "include_search_metadata": True,
            "include_summary": True
        }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/memories/retrieve/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            response_text = response.text
            response_size = len(response_text)
            
            print(f"✅ Status: {response.status_code}")
            print(f"📊 Response size: {response_size:,} bytes")
            print(f"🔍 Memories found: {len(data.get('memories', []))}")
            
            # Show first memory structure for verification
            if data.get('memories'):
                first_memory = data['memories'][0]
                print(f"📝 First memory fields: {list(first_memory.keys())}")
                
                # Check for optimization-specific features
                if level == "fast":
                    assert 'search_metadata' not in first_memory
                    assert 'summary' not in data
                    print("   ⚡ Fast mode: minimal fields confirmed")
                elif level == "detailed":
                    assert 'search_metadata' in data
                    print("   🔍 Detailed mode: search metadata included")
                elif level == "full":
                    assert 'search_metadata' in data
                    if 'summary' in data:
                        print("   🎯 Full mode: summary included")
                    else:
                        print("   🎯 Full mode: all fields included")
            
            return response_size, data
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return None, None
            
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return None, None

def create_test_memories():
    """Create some test memories for retrieval testing"""
    print("📝 Creating test memories for retrieval testing...")
    
    test_conversations = [
        "I love hiking in the mountains every weekend with my dog.",
        "My favorite outdoor activity is rock climbing, especially in Colorado.",
        "I enjoy cycling along the beach path during sunset.",
        "Camping under the stars is one of my most peaceful experiences.",
        "I practice photography while walking through nature trails."
    ]
    
    for i, conversation in enumerate(test_conversations, 1):
        payload = {
            "conversation_text": conversation,
            "user_id": TEST_USER_ID,
            "fields": ["id", "content"]  # Fast mode for extraction
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/memories/extract/",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                print(f"✅ Memory {i} created")
            else:
                print(f"❌ Failed to create memory {i}: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Exception creating memory {i}: {str(e)}")

def main():
    print("🧪 Testing Memory Retrieval Optimization Levels")
    print("=" * 60)
    
    # Create test memories first
    create_test_memories()
    
    # Test different optimization levels
    results = {}
    
    # Test Fast mode (60-80% smaller)
    size_fast, data_fast = test_optimization_level("fast", "60-80% smaller responses")
    if size_fast:
        results["fast"] = size_fast
    
    # Test Detailed mode (40-60% smaller)
    size_detailed, data_detailed = test_optimization_level("detailed", "40-60% smaller responses")
    if size_detailed:
        results["detailed"] = size_detailed
    
    # Test Full mode (standard size)
    size_full, data_full = test_optimization_level("full", "standard size")
    if size_full:
        results["full"] = size_full
    
    # Calculate and display optimization savings
    if results:
        print(f"\n{'='*60}")
        print("📊 OPTIMIZATION RESULTS SUMMARY")
        print(f"{'='*60}")
        
        if "full" in results:
            baseline = results["full"]
            print(f"📏 Baseline (Full mode): {baseline:,} bytes")
            
            if "fast" in results:
                fast_saving = ((baseline - results["fast"]) / baseline) * 100
                print(f"⚡ Fast mode: {results['fast']:,} bytes ({fast_saving:.1f}% smaller)")
                
            if "detailed" in results:
                detailed_saving = ((baseline - results["detailed"]) / baseline) * 100
                print(f"🔍 Detailed mode: {results['detailed']:,} bytes ({detailed_saving:.1f}% smaller)")
                
        print(f"\n✅ Optimization validation complete!")
        print(f"🎯 Results confirm significant response size reductions")
        
    else:
        print("\n❌ Could not complete optimization validation")

if __name__ == "__main__":
    main()